"""
Keyboard routing strategy orchestrator - builds and executes the multi-phase routing pipeline.

Orchestrates the complete routing workflow: QFN fanout, USB differential pairs,
matrix columns/rows, power nets, MCU signals, and verification.
"""

import os
import sys
import tempfile
import shutil
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kicad_parser import PCBData, detect_package_type
from routing_config import GridRouteConfig
from keyboard.matrix_detection import KeyboardMatrix
from keyboard.net_classifier import KeyboardNetClassification
from keyboard.presets import get_column_layer_costs, get_row_layer_costs
from keyboard.matrix_routing import (
    order_column_nets, order_row_nets, get_net_names_for_ids
)


@dataclass
class RoutingPhase:
    """A single phase in the keyboard routing pipeline."""
    name: str
    phase_type: str  # "fanout", "diff_pair", "power_plane", "single_ended", "drc"
    net_ids: List[int]
    config_overrides: dict
    description: str = ""


@dataclass
class KeyboardRoutingPlan:
    """Complete keyboard routing plan with all phases."""
    phases: List[RoutingPhase]
    base_config: GridRouteConfig
    matrix: KeyboardMatrix
    classification: KeyboardNetClassification
    layer_count: int


def build_routing_plan(
    pcb_data: PCBData,
    matrix: KeyboardMatrix,
    classification: KeyboardNetClassification,
    base_config: GridRouteConfig,
    layer_count: int,
) -> KeyboardRoutingPlan:
    """
    Build a multi-phase routing plan for keyboard PCB.

    Phases (2-layer):
    1. QFN Fanout (if MCU is QFN-56)
    2. USB Differential Pair (if D+/D- exist)
    3. Matrix Columns (center-out ordering, F.Cu preferred)
    4. Matrix Rows (center-out ordering, B.Cu preferred)
    5. Power nets (wide traces)
    6. MCU signal nets
    7. DRC + connectivity check

    Phases (4-layer):
    Same as above, plus inner power plane routing for GND/VCC.

    Args:
        pcb_data: Parsed PCB data
        matrix: Detected keyboard matrix
        classification: Net classification result
        base_config: Base routing configuration (from preset)
        layer_count: Number of copper layers

    Returns:
        KeyboardRoutingPlan with all phases configured
    """
    phases: List[RoutingPhase] = []

    # Phase 1: QFN Fanout (if applicable)
    if matrix.mcu_footprint:
        pkg_type = detect_package_type(matrix.mcu_footprint)
        if pkg_type == 'QFN':
            phases.append(RoutingPhase(
                name="QFN Fanout",
                phase_type="fanout",
                net_ids=[],  # fanout handles its own net selection
                config_overrides={},
                description=f"Escape routing for {matrix.mcu_footprint.reference} "
                           f"({matrix.mcu_footprint.footprint_name}, {len(matrix.mcu_footprint.pads)} pads)"
            ))

    # Phase 2: USB Differential Pair (if present)
    if classification.usb_diff_pairs:
        usb_net_ids = []
        for pair in classification.usb_diff_pairs.values():
            if pair.p_net_id:
                usb_net_ids.append(pair.p_net_id)
            if pair.n_net_id:
                usb_net_ids.append(pair.n_net_id)
        if usb_net_ids:
            phases.append(RoutingPhase(
                name="USB Differential Pair",
                phase_type="diff_pair",
                net_ids=usb_net_ids,
                config_overrides={'impedance_target': 90.0},
                description=f"Route USB D+/D- differential pair (90Ω impedance)"
            ))

    # Phase 3: Matrix Columns (prefer F.Cu)
    col_order = order_column_nets(pcb_data, matrix)
    if col_order:
        phases.append(RoutingPhase(
            name="Matrix Columns",
            phase_type="single_ended",
            net_ids=col_order,
            config_overrides={
                'layer_costs': get_column_layer_costs(layer_count),
                'direction_preference_cost': 0,  # Use layer_costs instead
            },
            description=f"Route {len(col_order)} column nets (prefer F.Cu, center-out)"
        ))

    # Phase 4: Matrix Rows (prefer B.Cu)
    row_order = order_row_nets(pcb_data, matrix)
    if row_order:
        phases.append(RoutingPhase(
            name="Matrix Rows",
            phase_type="single_ended",
            net_ids=row_order,
            config_overrides={
                'layer_costs': get_row_layer_costs(layer_count),
                'direction_preference_cost': 0,  # Use layer_costs instead
            },
            description=f"Route {len(row_order)} row nets (prefer B.Cu, center-out)"
        ))

    # Phase 5: Power nets (wide traces)
    if classification.power_nets:
        phases.append(RoutingPhase(
            name="Power Nets",
            phase_type="single_ended",
            net_ids=list(classification.power_nets.keys()),
            config_overrides={
                'power_net_widths': classification.power_nets,
                'turn_cost': 500,  # Less strict on power nets
                'max_rip_up_count': 2,
            },
            description=f"Route {len(classification.power_nets)} power nets with wide traces"
        ))

    # Phase 6: MCU Signal nets
    if classification.mcu_signal_nets:
        phases.append(RoutingPhase(
            name="MCU Signals",
            phase_type="single_ended",
            net_ids=classification.mcu_signal_nets,
            config_overrides={},
            description=f"Route {len(classification.mcu_signal_nets)} MCU signal nets "
                       f"(crystal, reset, boot, I2C, SPI, etc.)"
        ))

    # Phase 7: Unclassified nets (if any)
    if classification.unclassified_nets:
        phases.append(RoutingPhase(
            name="Remaining Nets",
            phase_type="single_ended",
            net_ids=classification.unclassified_nets,
            config_overrides={},
            description=f"Route {len(classification.unclassified_nets)} remaining nets"
        ))

    # Phase 8: DRC + Connectivity Check
    phases.append(RoutingPhase(
        name="DRC Check",
        phase_type="drc",
        net_ids=[],
        config_overrides={},
        description="Verify DRC clearances and net connectivity"
    ))

    return KeyboardRoutingPlan(
        phases=phases,
        base_config=base_config,
        matrix=matrix,
        classification=classification,
        layer_count=layer_count,
    )


def print_routing_plan(plan: KeyboardRoutingPlan, pcb_data: PCBData):
    """Print a human-readable summary of the routing plan."""
    print("\n" + "=" * 70)
    print(f"KEYBOARD ROUTING PLAN")
    print("=" * 70)

    print(f"\nBoard: {plan.layer_count}-layer")
    print(f"Matrix: {plan.matrix.matrix_size[0]}R x {plan.matrix.matrix_size[1]}C "
          f"({len(plan.matrix.switches)} switches)")
    print(f"Total phases: {len(plan.phases)}")

    print("\nPhases:")
    for i, phase in enumerate(plan.phases, 1):
        net_desc = ""
        if phase.net_ids:
            net_names = get_net_names_for_ids(pcb_data, phase.net_ids)
            if len(net_names) <= 3:
                net_desc = f" ({', '.join(net_names)})"
            else:
                net_desc = f" ({len(net_names)} nets)"

        print(f"\n  {i}. {phase.name}{net_desc}")
        if phase.description:
            print(f"     {phase.description}")

    print("\n" + "=" * 70 + "\n")
