"""
Keyboard net classification - categorizes all PCB nets for routing.

Classifies nets into: matrix rows, matrix columns, USB differential pairs,
power/ground, MCU signals, and unclassified.
"""

import fnmatch
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kicad_parser import PCBData, Footprint
from routing_config import DiffPairNet
from net_queries import find_differential_pairs
from keyboard.matrix_detection import KeyboardMatrix


# USB net patterns for differential pair detection
USB_NET_PATTERNS = ['*D+*', '*D-*', '*DP*', '*DN*', '*USB*', '*usb*']

# Power net patterns and default track widths
POWER_NET_PATTERNS = ['*GND*', '*VCC*', '*VBUS*', '*3V3*', '*3.3V*',
                      '*5V*', '*1V1*', '+*V', '*VSYS*', '*VREF*']
POWER_NET_WIDTHS = [0.5, 0.5, 0.4, 0.4, 0.4,
                    0.4, 0.4, 0.4, 0.4, 0.3]


@dataclass
class KeyboardNetClassification:
    """Classification of all nets in a keyboard PCB."""
    row_nets: List[int] = field(default_factory=list)
    col_nets: List[int] = field(default_factory=list)
    usb_diff_pairs: Dict[str, DiffPairNet] = field(default_factory=dict)
    power_nets: Dict[int, float] = field(default_factory=dict)  # net_id -> track width
    mcu_signal_nets: List[int] = field(default_factory=list)
    unclassified_nets: List[int] = field(default_factory=list)

    def get_power_net_patterns_and_widths(self):
        """Return patterns and widths for use with identify_power_nets()."""
        return POWER_NET_PATTERNS, POWER_NET_WIDTHS


def classify_keyboard_nets(pcb_data: PCBData, matrix: KeyboardMatrix) -> KeyboardNetClassification:
    """
    Classify all nets in the keyboard PCB.

    Args:
        pcb_data: Parsed PCB data
        matrix: Detected keyboard matrix

    Returns:
        KeyboardNetClassification with all nets categorized
    """
    classification = KeyboardNetClassification()

    # Collect all classified net IDs to avoid double-classification
    classified: Set[int] = set()

    # 1. Matrix row and column nets (from matrix detection)
    classification.row_nets = sorted(matrix.row_nets.keys())
    classification.col_nets = sorted(matrix.col_nets.keys())
    classified.update(classification.row_nets)
    classified.update(classification.col_nets)

    # 2. USB differential pairs
    classification.usb_diff_pairs = find_differential_pairs(pcb_data, USB_NET_PATTERNS)
    for pair in classification.usb_diff_pairs.values():
        if pair.p_net_id:
            classified.add(pair.p_net_id)
        if pair.n_net_id:
            classified.add(pair.n_net_id)

    # 3. Power nets
    for net_id, net in pcb_data.nets.items():
        if not net.name or net_id == 0 or net_id in classified:
            continue
        for pattern, width in zip(POWER_NET_PATTERNS, POWER_NET_WIDTHS):
            if fnmatch.fnmatch(net.name, pattern):
                classification.power_nets[net_id] = width
                classified.add(net_id)
                break

    # 4. MCU signal nets (connected to MCU but not in above categories)
    if matrix.mcu_footprint:
        mcu_net_ids = set()
        for pad in matrix.mcu_footprint.pads:
            if pad.net_id and pad.net_id > 0 and pad.net_id not in classified:
                mcu_net_ids.add(pad.net_id)
        classification.mcu_signal_nets = sorted(mcu_net_ids)
        classified.update(mcu_net_ids)

    # 5. Everything else with at least 2 pads
    for net_id, net in pcb_data.nets.items():
        if net_id == 0 or net_id in classified:
            continue
        if not net.name:
            continue
        # Only include nets with multiple pads (single-pad nets are unroutable)
        pads = pcb_data.pads_by_net.get(net_id, [])
        if len(pads) >= 2:
            classification.unclassified_nets.append(net_id)

    return classification


def print_classification(pcb_data: PCBData, classification: KeyboardNetClassification):
    """Print a human-readable summary of the net classification."""
    print("\n=== Keyboard Net Classification ===")

    print(f"\nMatrix rows ({len(classification.row_nets)} nets):")
    for net_id in classification.row_nets:
        name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"  {name}")

    print(f"\nMatrix columns ({len(classification.col_nets)} nets):")
    for net_id in classification.col_nets:
        name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"  {name}")

    if classification.usb_diff_pairs:
        print(f"\nUSB differential pairs ({len(classification.usb_diff_pairs)}):")
        for base, pair in classification.usb_diff_pairs.items():
            print(f"  {base}: {pair.p_net_name} / {pair.n_net_name}")

    print(f"\nPower nets ({len(classification.power_nets)}):")
    for net_id, width in classification.power_nets.items():
        name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"  {name} (width: {width}mm)")

    print(f"\nMCU signal nets ({len(classification.mcu_signal_nets)}):")
    for net_id in classification.mcu_signal_nets:
        name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"  {name}")

    if classification.unclassified_nets:
        print(f"\nUnclassified nets ({len(classification.unclassified_nets)}):")
        for net_id in classification.unclassified_nets:
            name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
            print(f"  {name}")

    total = (len(classification.row_nets) + len(classification.col_nets) +
             sum(2 for p in classification.usb_diff_pairs.values() if p.is_complete) +
             len(classification.power_nets) + len(classification.mcu_signal_nets) +
             len(classification.unclassified_nets))
    print(f"\nTotal classified: {total} nets")
