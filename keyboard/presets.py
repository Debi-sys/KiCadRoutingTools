"""
Keyboard routing presets - pre-configured GridRouteConfig for keyboard PCBs.

Provides optimized routing parameters for 2-layer and 4-layer keyboard designs.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing_config import GridRouteConfig


def keyboard_2layer_preset(**overrides) -> GridRouteConfig:
    """
    Optimized routing config for 2-layer keyboard PCBs.

    Strategy: columns on F.Cu, rows on B.Cu, high via cost to discourage
    layer changes, strong turn cost for straight matrix traces.
    """
    config = GridRouteConfig(
        layers=['F.Cu', 'B.Cu'],
        track_width=0.25,
        clearance=0.15,
        via_size=0.5,
        via_drill=0.3,
        grid_step=0.1,
        via_cost=300,           # High - discourage layer changes on 2-layer
        turn_cost=2000,         # Encourage straight traces for matrix routing
        heuristic_weight=1.9,
        max_iterations=500000,
        max_probe_iterations=10000,
        max_rip_up_count=5,
        stub_proximity_radius=3.0,
        stub_proximity_cost=0.3,
        via_proximity_cost=10.0,
        track_proximity_distance=2.0,
        track_proximity_cost=0.1,
        direction_preference_cost=100,  # Strong layer direction preference
        hole_to_hole_clearance=0.25,
        board_edge_clearance=0.5,
        bus_enabled=True,
        bus_detection_radius=10.0,      # Large radius for keyboard matrix buses
        bus_min_nets=3,
        bus_attraction_radius=8.0,
        bus_attraction_bonus=3000,
    )

    # Apply user overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def keyboard_4layer_preset(**overrides) -> GridRouteConfig:
    """
    Optimized routing config for 4-layer keyboard PCBs.

    Strategy: signals on F.Cu/B.Cu, inner layers for power planes.
    Lower via cost since vias are cheaper on 4-layer.
    """
    config = GridRouteConfig(
        layers=['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu'],
        track_width=0.2,
        clearance=0.15,
        via_size=0.45,
        via_drill=0.25,
        grid_step=0.1,
        via_cost=50,            # Vias are cheap on 4-layer
        turn_cost=1500,
        heuristic_weight=1.9,
        max_iterations=500000,
        max_probe_iterations=10000,
        max_rip_up_count=5,
        layer_costs=[1.0, 5.0, 5.0, 1.0],  # Discourage inner signal routing
        stub_proximity_radius=2.5,
        stub_proximity_cost=0.2,
        via_proximity_cost=10.0,
        track_proximity_distance=2.0,
        track_proximity_cost=0.1,
        direction_preference_cost=50,
        hole_to_hole_clearance=0.25,
        board_edge_clearance=0.5,
        bus_enabled=True,
        bus_detection_radius=10.0,
        bus_min_nets=3,
        bus_attraction_radius=8.0,
        bus_attraction_bonus=3000,
    )

    # Apply user overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def get_column_layer_costs(layer_count: int) -> list:
    """Layer costs biased toward F.Cu for column routing."""
    if layer_count == 2:
        return [1.0, 3.0]
    return [1.0, 5.0, 5.0, 3.0]


def get_row_layer_costs(layer_count: int) -> list:
    """Layer costs biased toward B.Cu for row routing."""
    if layer_count == 2:
        return [3.0, 1.0]
    return [3.0, 5.0, 5.0, 1.0]
