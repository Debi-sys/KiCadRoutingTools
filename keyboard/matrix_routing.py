"""
Matrix-aware net ordering for keyboard PCB routing.

Orders row and column nets by physical position for optimal routing results.
Center-out ordering minimizes routing conflicts.
"""

from typing import List, Tuple, Dict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kicad_parser import PCBData
from keyboard.matrix_detection import KeyboardMatrix


def _get_net_center_position(pcb_data: PCBData, net_id: int) -> Tuple[float, float]:
    """Get the centroid of all pads on a net."""
    pads = pcb_data.pads_by_net.get(net_id, [])
    if not pads:
        return (0.0, 0.0)
    avg_x = sum(p.global_x for p in pads) / len(pads)
    avg_y = sum(p.global_y for p in pads) / len(pads)
    return (avg_x, avg_y)


def _center_out_order(items: List[Tuple[int, float]]) -> List[int]:
    """Order items center-out by position value. Returns net_ids."""
    if not items:
        return []
    sorted_items = sorted(items, key=lambda x: x[1])
    mid = len(sorted_items) // 2

    # Start from center, alternate left and right
    result = [sorted_items[mid][0]]
    left = mid - 1
    right = mid + 1
    while left >= 0 or right < len(sorted_items):
        if right < len(sorted_items):
            result.append(sorted_items[right][0])
            right += 1
        if left >= 0:
            result.append(sorted_items[left][0])
            left -= 1
    return result


def order_column_nets(pcb_data: PCBData, matrix: KeyboardMatrix) -> List[int]:
    """
    Order column nets by X position, center-out.

    Routes center columns first, working outward. This gives center columns
    (which have the most routing options) priority.
    """
    col_positions = []
    for net_id in matrix.col_nets:
        cx, cy = _get_net_center_position(pcb_data, net_id)
        col_positions.append((net_id, cx))
    return _center_out_order(col_positions)


def order_row_nets(pcb_data: PCBData, matrix: KeyboardMatrix) -> List[int]:
    """
    Order row nets by Y position, center-out.

    Routes center rows first, working outward.
    """
    row_positions = []
    for net_id in matrix.row_nets:
        cx, cy = _get_net_center_position(pcb_data, net_id)
        row_positions.append((net_id, cy))
    return _center_out_order(row_positions)


def get_net_names_for_ids(pcb_data: PCBData, net_ids: List[int]) -> List[str]:
    """Convert net IDs to net names for use with batch_route()."""
    names = []
    for net_id in net_ids:
        if pcb_data.nets and net_id in pcb_data.nets:
            net = pcb_data.nets[net_id]
            if net and net.name:
                names.append(net.name)
    return names
