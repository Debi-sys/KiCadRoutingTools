# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Building the Rust Router

Use `build_router.py` to build the Rust router:

```bash
python build_router.py
```

This builds the Rust module, copies the library to the correct location, and verifies the version. Do not run `cargo build` directly. To clean build artifacts: `python build_router.py --clean`.

**Important:** When making changes to the Rust router, bump the version in `rust_router/Cargo.toml` and update the version history in `rust_router/README.md`.

## Main Entry Point Scripts

| Script | Purpose |
|--------|---------|
| `route_keyboard.py` | **One-click keyboard PCB auto-routing** |
| `route.py` | Route single-ended nets via Rust A* |
| `route_diff.py` | Route differential pairs (P/N) |
| `route_disconnected_planes.py` | Connect split power plane regions |
| `bga_fanout.py` | BGA escape routing |
| `qfn_fanout.py` | QFN/QFP fanout |
| `route_planes.py` | Route power plane connections |

Typical usage:
```bash
# Keyboard PCB: one-click routing for mechanical keyboards
python route_keyboard.py input.kicad_pcb output.kicad_pcb --layers 2

# General routing
python route.py input.kicad_pcb output.kicad_pcb --nets "Net-(U2A-*)"
python route_diff.py input.kicad_pcb output.kicad_pcb --nets "*lvds*"
python route_disconnected_planes.py input.kicad_pcb output.kicad_pcb
```

## Running Tests

Tests live in `tests/`. Run a specific test script directly:

```bash
python tests/test_kit_route.py
python tests/test_interf_u.py
python tests/test_fanout_and_route.py
```

All test scripts use `tests/run_utils.py` which executes commands from the project root.

## Installing the KiCad Plugin

```bash
python install_plugin.py           # Install to KiCad 9 plugins directory
python install_plugin.py --symlink # Symlink for development (no copy needed after changes)
python install_plugin.py --uninstall
```

The plugin (`kicad_routing_plugin/`) integrates with KiCad's PCB Editor as an ActionPlugin. It reads the live board via `pcbnew` and launches the GUI.

## High-Level Architecture

### Layer Overview

```
KiCad PCB file (.kicad_pcb)
        │
        ▼
kicad_parser.py          # Parses PCB → PCBData (footprints, nets, segments, vias)
        │
        ▼
obstacle_map.py          # Builds GridObstacleMap from PCBData (pads, tracks, vias)
obstacle_costs.py        # Adds proximity costs (stub zones, BGA zones, track proximity)
obstacle_cache.py        # Caches per-net obstacle maps for incremental updates
        │
        ▼
rust_router/             # Rust A* engine (grid_router.so) — ~10x faster than Python
  ├── GridObstacleMap    # O(1) blocked cell lookup (FxHashMap with ref-counting)
  ├── GridRouter         # A* for single-ended nets (octilinear, multi-layer)
  └── PoseRouter         # Orientation-aware A* for diff pairs (Dubins heuristic)
        │
        ▼
single_ended_routing.py  # Routes one net at a time, calls GridRouter
diff_pair_routing.py     # Routes P/N pairs, calls PoseRouter for centerline
        │
        ├── blocking_analysis.py  # Why did a route fail? Which nets block it?
        ├── rip_up_reroute.py     # Rip up blocking nets and retry (progressive N+1)
        └── layer_swap_optimization.py  # Post-route layer swap improvements
        │
        ▼
kicad_writer.py          # Generates KiCad s-expression for segments/vias
output_writer.py         # Writes final .kicad_pcb file
```

### Keyboard-Specific Layer (route_keyboard.py)

```
keyboard/
  ├── matrix_detection.py    # Auto-detect switches, diodes, row/col nets
  ├── net_classifier.py      # Classify nets (rows, cols, USB, power, MCU signals)
  ├── presets.py             # GridRouteConfig presets for 2-layer and 4-layer
  ├── routing_strategy.py    # Multi-phase routing orchestrator
  └── matrix_routing.py      # Net ordering (center-out for matrix routing)
```

Keyboard routing is a **specialized orchestration** that reuses the core A* router.
It detects the switch matrix topology from PCB netlist, classifies nets, and routes
in phases (columns → rows → power → MCU signals) with layer biases for clean traces.

### Routing Pipeline (route.py / route_diff.py / route_keyboard.py)

1. **Parse** PCB with `kicad_parser.py`
2. **Identify nets** to route (glob patterns, unrouted filter, or keyboard matrix detection)
3. **Order nets** (MPS or inside-out ordering for better results)
4. **Build obstacle map** (base + per-net incremental cache)
5. **Route each net** via Rust A*; on failure, analyze blockers and rip-up/reroute
6. **Post-processing**: layer swap optimization, polarity swap, target swap
7. **Write output** PCB file

### Key Supporting Modules

- `routing_config.py` — `GridRouteConfig` dataclass (all routing parameters)
- `routing_state.py` — `RoutingState` tracks routed paths, ripped nets, failures
- `routing_context.py` — Helper to build obstacle maps for a specific net
- `connectivity.py` — Find stub endpoints, connected groups, edge stubs
- `net_queries.py` — Net pattern expansion, power net detection, MPS ordering
- `geometry_utils.py` / `bresenham_utils.py` — Grid-space geometry helpers
- `bus_detection.py` — Identifies bus groups for parallel routing with attraction
- `routing_constants.py` — Shared numeric constants

### Differential Pair Routing

Diff pair routing (`diff_pair_routing.py`) uses a 3-step approach:
1. Route centerline with `PoseRouter` (Dubins heuristic, pose-aware A*)
2. Offset P/N tracks from centerline by `diff_pair_gap / 2`
3. Place coupled vias where centerline crosses layers

### KiCad Plugin

`kicad_routing_plugin/` is a SWIG ActionPlugin that:
- Reads live board data from `pcbnew` API (avoids file I/O)
- Launches a wxPython GUI (`swig_gui.py`) with tabs: Basic, Advanced, Differential, Fanout, Planes, Log, About
- Routes in-process and writes back to the live board

## KiCad Parser Usage

```python
from kicad_parser import parse_kicad_pcb, Pad, Footprint, PCBData

pcb = parse_kicad_pcb('path/to/file.kicad_pcb')
```

### PCBData Structure

- `pcb.footprints` — `Dict[str, Footprint]` keyed by reference (e.g., `'U9'`, `'R1'`)
- `pcb.nets` — `Dict[int, Net]` keyed by net_id
- `pcb.segments` — `List[Segment]` of track segments
- `pcb.vias` — `List[Via]`

### Key Attribute Reference

**Footprint:** `.reference`, `.footprint_name`, `.pads`, `.x`, `.y`, `.rotation`, `.layer`

**Pad:** `.pad_number`, `.net_id`, `.net_name`, `.global_x`, `.global_y`, `.local_x`, `.local_y`, `.size_x`, `.size_y`, `.shape`, `.layers`, `.drill`, `.component_ref`, `.pinfunction`, `.pintype`
- Through-hole pads (`pad.drill > 0`) block tracks on ALL layers; SMD pads only block their layer

**Net:** `.net_id`, `.name`, `.pads`

**Segment:** `.start_x`, `.start_y`, `.end_x`, `.end_y`, `.width`, `.layer`, `.net_id`

**Via:** `.x`, `.y`, `.size`, `.drill`, `.layers`, `.net_id`

## Rust Router API Summary

```python
import grid_router
from grid_router import GridObstacleMap, GridRouter, PoseRouter

obstacles = GridObstacleMap(num_layers)
obstacles.add_blocked_cell(gx, gy, layer)
obstacles.add_blocked_via(gx, gy)

router = GridRouter(via_cost=500000, h_weight=1.5)
path, iterations, stats = router.route_multi(obstacles, sources, targets, max_iterations=200000)
# path: List[(gx, gy, layer)] or None
```

Key `GridRouter` parameters: `via_cost`, `h_weight`, `turn_cost`, `via_proximity_cost`, `vertical_attraction_radius`, `vertical_attraction_bonus`, `layer_costs`, `proximity_heuristic_cost`.

Key `PoseRouter` parameters: same as above plus `min_radius_grid`. Uses `route_pose(...)` returning `(path, iterations)` with pose states `(gx, gy, theta_idx, layer)`.
