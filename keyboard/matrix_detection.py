"""
Keyboard matrix detection - identifies switch matrix from PCB netlist topology.

Analyzes footprint names and pad-to-net connectivity to find:
- Key switch footprints (Cherry MX, Kailh, Alps, Gateron, Choc)
- Diode footprints (1N4148, SOD-123, DO-35, etc.)
- Row and column nets by tracing switch-diode connections
"""

import fnmatch
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kicad_parser import PCBData, Footprint, Pad


# Footprint name patterns for mechanical key switches
SWITCH_FOOTPRINT_PATTERNS = [
    '*Cherry_MX*', '*Kailh*', '*Alps*', '*Gateron*',
    '*MX*', '*PG1350*', '*Choc*', '*SW_Push*',
    '*KEY_*', '*Key_Switch*', '*Hotswap*',
]

# Footprint name patterns for diodes
DIODE_FOOTPRINT_PATTERNS = [
    '*D_DO-35*', '*D_A-405*', '*1N4148*', '*D_DO-204*',
    '*SOD-123*', '*SOD-323*', '*SOD-523*', '*D_SOD*',
    '*D_MiniMELF*', '*D_0402*', '*D_0603*', '*D_0805*',
]

# Value patterns for diodes (fallback detection)
DIODE_VALUE_PATTERNS = ['1N4148*', 'BAV70*', 'D', 'D_*']

# Expected pad spacing for Cherry MX switches (~6.35mm between pins)
MX_PAD_SPACING = 6.35
MX_PAD_SPACING_TOLERANCE = 1.5


@dataclass
class KeyboardMatrix:
    """Detected keyboard switch matrix structure."""
    switches: List[Footprint]
    diodes: List[Footprint]
    row_nets: Dict[int, List[str]]   # net_id -> list of switch references in this row
    col_nets: Dict[int, List[str]]   # net_id -> list of switch references in this column
    matrix_size: Tuple[int, int]     # (num_rows, num_cols)
    switch_to_row: Dict[str, int]    # switch_ref -> row net_id
    switch_to_col: Dict[str, int]    # switch_ref -> col net_id
    switch_to_diode: Dict[str, str]  # switch_ref -> diode_ref
    mcu_footprint: Optional[Footprint] = None


def _matches_any_pattern(name: str, patterns: List[str]) -> bool:
    """Check if name matches any of the given fnmatch patterns (case-insensitive)."""
    name_upper = name.upper()
    for pattern in patterns:
        if fnmatch.fnmatch(name_upper, pattern.upper()):
            return True
    return False


def _is_switch_by_geometry(fp: Footprint) -> bool:
    """Detect switch by pad geometry: 2 through-hole pads with ~6.35mm spacing."""
    th_pads = [p for p in fp.pads if p.drill > 0]
    if len(th_pads) != 2:
        return False
    p1, p2 = th_pads
    dist = math.sqrt((p1.global_x - p2.global_x)**2 + (p1.global_y - p2.global_y)**2)
    return abs(dist - MX_PAD_SPACING) < MX_PAD_SPACING_TOLERANCE


def find_switches(pcb_data: PCBData) -> List[Footprint]:
    """Find all key switch footprints in the PCB."""
    switches = []
    for ref, fp in pcb_data.footprints.items():
        if _matches_any_pattern(fp.footprint_name, SWITCH_FOOTPRINT_PATTERNS):
            switches.append(fp)
        elif _is_switch_by_geometry(fp):
            switches.append(fp)
    return switches


def find_diodes(pcb_data: PCBData) -> List[Footprint]:
    """Find all diode footprints in the PCB."""
    diodes = []
    for ref, fp in pcb_data.footprints.items():
        if _matches_any_pattern(fp.footprint_name, DIODE_FOOTPRINT_PATTERNS):
            diodes.append(fp)
        elif _matches_any_pattern(fp.value, DIODE_VALUE_PATTERNS):
            diodes.append(fp)
        elif ref.startswith('D') and ref[1:].isdigit() and len(fp.pads) == 2:
            # Component with reference D1, D2, etc. and exactly 2 pads
            diodes.append(fp)
    return diodes


def find_mcu(pcb_data: PCBData) -> Optional[Footprint]:
    """Find the MCU footprint (QFN/QFP with most pads, typically RP2040/STM32/ATmega)."""
    mcu_patterns = ['*RP2040*', '*STM32*', '*ATmega*', '*ATMEGA*', '*nRF52*',
                    '*QFN*', '*QFP*', '*LQFP*', '*TQFP*']
    candidates = []
    for ref, fp in pcb_data.footprints.items():
        if _matches_any_pattern(fp.footprint_name, mcu_patterns):
            candidates.append(fp)
        elif _matches_any_pattern(fp.value, ['*RP2040*', '*STM32*', '*ATmega*', '*nRF52*']):
            candidates.append(fp)
    if not candidates:
        return None
    # Return the candidate with the most pads (most likely the MCU)
    return max(candidates, key=lambda fp: len(fp.pads))


def _build_net_to_footprints(pcb_data: PCBData, footprints: List[Footprint]) -> Dict[int, List[Tuple[Footprint, Pad]]]:
    """Build mapping from net_id to list of (footprint, pad) tuples for given footprints."""
    refs = {fp.reference for fp in footprints}
    result: Dict[int, List[Tuple[Footprint, Pad]]] = {}
    for fp in footprints:
        for pad in fp.pads:
            if pad.net_id and pad.net_id > 0:
                if pad.net_id not in result:
                    result[pad.net_id] = []
                result[pad.net_id].append((fp, pad))
    return result


def detect_keyboard_matrix(pcb_data: PCBData) -> Optional[KeyboardMatrix]:
    """
    Detect the keyboard switch matrix from PCB netlist topology.

    Algorithm:
    1. Find switch and diode footprints
    2. For each switch, find which pad's net connects to a diode
    3. The diode's other net is a row net; the switch's other pad net is a column net
    4. Validate that row nets connect multiple diodes and column nets connect multiple switches

    Returns:
        KeyboardMatrix if a valid matrix is detected, None otherwise
    """
    switches = find_switches(pcb_data)
    diodes = find_diodes(pcb_data)

    if len(switches) < 4:
        print(f"  Only {len(switches)} switches found, not enough for a keyboard matrix")
        return None
    if len(diodes) < 4:
        print(f"  Only {len(diodes)} diodes found, not enough for a keyboard matrix")
        return None

    print(f"  Found {len(switches)} switches and {len(diodes)} diodes")

    # Build net -> footprint mappings
    diode_refs = {fp.reference for fp in diodes}
    switch_refs = {fp.reference for fp in switches}
    diode_by_ref = {fp.reference: fp for fp in diodes}
    switch_by_ref = {fp.reference: fp for fp in switches}

    # Build net_id -> list of (footprint_ref, pad) for diodes
    net_to_diode_pads: Dict[int, List[Tuple[str, Pad]]] = {}
    for fp in diodes:
        for pad in fp.pads:
            if pad.net_id and pad.net_id > 0:
                if pad.net_id not in net_to_diode_pads:
                    net_to_diode_pads[pad.net_id] = []
                net_to_diode_pads[pad.net_id].append((fp.reference, pad))

    # For each switch, trace connectivity to find row/col nets
    switch_to_row: Dict[str, int] = {}
    switch_to_col: Dict[str, int] = {}
    switch_to_diode: Dict[str, str] = {}
    row_net_switches: Dict[int, List[str]] = {}
    col_net_switches: Dict[int, List[str]] = {}

    for sw in switches:
        # Get the two pad nets
        pad_nets = [(pad, pad.net_id) for pad in sw.pads if pad.net_id and pad.net_id > 0]
        if len(pad_nets) < 2:
            continue

        # Find which pad connects to a diode
        diode_pad = None
        other_pad = None
        connected_diode_ref = None

        for pad, net_id in pad_nets:
            if net_id in net_to_diode_pads:
                # Check if any diode on this net is NOT this switch
                for dref, dpad in net_to_diode_pads[net_id]:
                    if dref in diode_refs:
                        diode_pad = (pad, net_id)
                        connected_diode_ref = dref
                        break
            if diode_pad:
                break

        if not diode_pad:
            continue

        # The other pad's net is the column net
        for pad, net_id in pad_nets:
            if net_id != diode_pad[1]:
                other_pad = (pad, net_id)
                break

        if not other_pad:
            continue

        # The diode's OTHER net (not the one shared with the switch) is the row net
        diode_fp = diode_by_ref.get(connected_diode_ref)
        if not diode_fp:
            continue

        row_net_id = None
        for dpad in diode_fp.pads:
            if dpad.net_id and dpad.net_id > 0 and dpad.net_id != diode_pad[1]:
                row_net_id = dpad.net_id
                break

        if row_net_id is None:
            continue

        col_net_id = other_pad[1]

        switch_to_row[sw.reference] = row_net_id
        switch_to_col[sw.reference] = col_net_id
        switch_to_diode[sw.reference] = connected_diode_ref

        if row_net_id not in row_net_switches:
            row_net_switches[row_net_id] = []
        row_net_switches[row_net_id].append(sw.reference)

        if col_net_id not in col_net_switches:
            col_net_switches[col_net_id] = []
        col_net_switches[col_net_id].append(sw.reference)

    # Validate: rows and columns should each have multiple switches
    valid_rows = {k: v for k, v in row_net_switches.items() if len(v) >= 2}
    valid_cols = {k: v for k, v in col_net_switches.items() if len(v) >= 2}

    if len(valid_rows) < 2 or len(valid_cols) < 2:
        print(f"  Insufficient matrix structure: {len(valid_rows)} rows, {len(valid_cols)} cols")
        return None

    # Filter switch mappings to only include validated row/col nets
    switch_to_row = {k: v for k, v in switch_to_row.items() if v in valid_rows}
    switch_to_col = {k: v for k, v in switch_to_col.items() if v in valid_cols}

    # Find MCU
    mcu = find_mcu(pcb_data)

    num_rows = len(valid_rows)
    num_cols = len(valid_cols)
    matched_switches = len(switch_to_row)

    print(f"  Detected {num_rows}x{num_cols} keyboard matrix ({matched_switches} switches matched)")
    if mcu:
        print(f"  MCU: {mcu.reference} ({mcu.footprint_name}, {len(mcu.pads)} pads)")

    # Name the row/col nets for display
    for net_id in valid_rows:
        net_name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"    Row: {net_name} ({len(valid_rows[net_id])} switches)")
    for net_id in valid_cols:
        net_name = pcb_data.nets[net_id].name if net_id in pcb_data.nets else f"net_{net_id}"
        print(f"    Col: {net_name} ({len(valid_cols[net_id])} switches)")

    return KeyboardMatrix(
        switches=switches,
        diodes=diodes,
        row_nets=valid_rows,
        col_nets=valid_cols,
        matrix_size=(num_rows, num_cols),
        switch_to_row=switch_to_row,
        switch_to_col=switch_to_col,
        switch_to_diode=switch_to_diode,
        mcu_footprint=mcu,
    )
