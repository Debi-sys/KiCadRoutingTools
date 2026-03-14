---
name: route-keyboard
description: Routes a mechanical keyboard PCB end-to-end. Auto-detects switch matrix, classifies nets, and runs the full routing pipeline (fanout, USB, matrix, power, MCU signals). Provides one-click keyboard routing specialization.
---

# Route Keyboard PCB

When this skill is invoked with a keyboard PCB file, perform end-to-end keyboard routing with matrix auto-detection.

## Step 1: Load and Analyze the Keyboard PCB

```python
from kicad_parser import parse_kicad_pcb
from keyboard import detect_keyboard_matrix, classify_keyboard_nets

pcb = parse_kicad_pcb('path/to/keyboard.kicad_pcb')
print(f'Loaded: {len(pcb.footprints)} footprints, {len(pcb.nets)} nets, '
      f'{len(pcb.segments)} segments, {len(pcb.vias)} vias')

# Detect the keyboard matrix
matrix = detect_keyboard_matrix(pcb)
if not matrix:
    print("ERROR: Could not detect a keyboard matrix")
    print("Expected: Key switches with diodes in a row/column configuration")
    sys.exit(1)

print(f"Detected {matrix.matrix_size[0]}x{matrix.matrix_size[1]} matrix with "
      f"{len(matrix.switches)} switches")
```

Report to user:
- Board stats: layers, nets, footprints, existing routing
- Matrix dimensions and switch/diode counts
- MCU footprint type (RP2040, STM32, ATMEGA, etc.)

## Step 2: Classify Keyboard Nets

```python
from keyboard import classify_keyboard_nets

classification = classify_keyboard_nets(pcb, matrix)

print(f"Classified {len(classification.row_nets)} row nets, "
      f"{len(classification.col_nets)} column nets, "
      f"{len(classification.usb_diff_pairs)} USB pairs, "
      f"{len(classification.power_nets)} power nets, "
      f"{len(classification.mcu_signal_nets)} MCU signals")
```

Report to user:
- Count of nets in each category
- MCU net types (crystal, reset, boot, I2C, SPI)
- USB differential pairs (if present)
- Power nets with track width recommendations

## Step 3: Select Routing Preset

```python
from keyboard.presets import keyboard_2layer_preset, keyboard_4layer_preset

# Auto-detect layer count from PCB
layer_count = len([l for l in pcb.board_info.copper_layers if l])
if layer_count >= 4:
    config = keyboard_4layer_preset()
else:
    config = keyboard_2layer_preset()

print(f"Using {layer_count}-layer preset")
print(f"  Track width: {config.track_width}mm")
print(f"  Clearance: {config.clearance}mm")
print(f"  Via: {config.via_size}mm size / {config.via_drill}mm drill")
```

The presets are optimized for:
- **2-layer**: high via cost (discourage layer changes), high turn cost (straight traces), columns on F.Cu, rows on B.Cu
- **4-layer**: low via cost, inner layers discouraged for signals, power planes on In1.Cu/In2.Cu

Allow user to override:
```bash
--track-width 0.2
--clearance 0.15
--via-size 0.4 --via-drill 0.25
```

## Step 4: Build Routing Plan

```python
from keyboard.routing_strategy import build_routing_plan, print_routing_plan

plan = build_routing_plan(pcb, matrix, classification, config, layer_count)
print_routing_plan(plan, pcb)
```

This generates a multi-phase routing plan:

| Phase | Action | Description |
|-------|--------|-------------|
| 1 | QFN Fanout | Escape routing for MCU (if QFN package) |
| 2 | USB Diff Pair | Route D+/D- with 90Ω impedance (if present) |
| 3 | Matrix Columns | Route column nets, prefer F.Cu |
| 4 | Matrix Rows | Route row nets, prefer B.Cu |
| 5 | Power Nets | Route power nets with wide tracks |
| 6 | MCU Signals | Route remaining MCU nets |
| 7 | DRC Check | Verify DRC and connectivity |

Report to user:
- Number of phases and nets per phase
- Configuration parameters being used
- Ask for approval before proceeding with full routing

## Step 5: Invoke CLI Entry Point

Instead of implementing the full routing here, invoke the CLI entry point:

```bash
python route_keyboard.py input.kicad_pcb output.kicad_pcb --layers 2 --verbose
```

### CLI Arguments

```
positional:
  input_file              Input unrouted PCB file (.kicad_pcb)
  output_file             Output routed PCB file (default: input_routed.kicad_pcb)

optional:
  --layers {2,4}          Number of copper layers (auto-detect if not specified)
  --track-width FLOAT     Override track width (mm)
  --clearance FLOAT       Override clearance (mm)
  --via-size FLOAT        Override via size (mm)
  --via-drill FLOAT       Override via drill (mm)
  --verbose               Print detailed progress
  --skip-drc              Skip DRC checks after routing
  --dry-run               Detect matrix and plan, but don't route
  --keep-intermediate     Keep intermediate phase files
```

## Step 6: Execute Routing Plan

When the user approves, run the full keyboard routing:

```bash
python route_keyboard.py input.kicad_pcb output.kicad_pcb --layers 2 --verbose
```

This executes each phase sequentially:
1. QFN fanout (if needed) → `input_phase1.kicad_pcb`
2. USB diff pair (if present) → `input_phase2.kicad_pcb`
3. Matrix columns → `input_phase3.kicad_pcb`
4. Matrix rows → `input_phase4.kicad_pcb`
5. Power nets → `input_phase5.kicad_pcb`
6. MCU signals → `input_phase6.kicad_pcb`
7. DRC check (output: `output.kicad_pcb`)

## Step 7: Verify Results

After routing completes:

```bash
# Check DRC violations
python check_drc.py output.kicad_pcb --clearance 0.15

# Check connectivity
python check_connected.py output.kicad_pcb

# Check for orphan stubs
python check_orphan_stubs.py output.kicad_pcb
```

Report to user:
- DRC violations (if any)
- Connectivity status (all nets connected?)
- Orphan stub count
- Routing success rate

## Step 8: Troubleshooting Routing Failures

If routing fails:

1. **Matrix detection failed** → Board doesn't have typical keyboard layout
   - Check footprint names match patterns: `*MX*`, `*Choc*`, `*D_DO-35*`, etc.
   - Check diode pads connect to switch pads

2. **Route failed** → Congestion or connectivity issue
   - Increase `--max-iterations 1000000` (default 500000)
   - Try `--max-rip-up 10` (default 5)
   - Check for crossing column/row nets (requires separate routing)

3. **DRC violations** → Spacing or hole clearance issue
   - Tighten via placement: `--hole-to-hole-clearance 0.25`
   - Increase routing area: `--board-edge-clearance 0.5`

4. **Orphan stubs** → Incomplete routing on some nets
   - Rerun with `--verbose` to identify failing nets
   - Try manual routing for problematic nets via `route.py`

## Step 9: Post-Routing Optimization

After successful routing, optionally:

```bash
# Add teardrops for manufacturability
python route_keyboard.py input.kicad_pcb output_final.kicad_pcb --add-teardrops
```

## Key Design Differences from General Routing

**Keyboard-specific vs. general PCB routing:**

| Aspect | Keyboard | General |
|--------|----------|---------|
| **Net selection** | Auto-detect matrix + classify | User specifies via `--nets` |
| **Layer strategy** | Rows on B.Cu, columns on F.Cu | User specifies via `--layer-costs` |
| **Ordering** | Center-out by position | MPS (minimum planar subset) |
| **Bus detection** | Enabled by default | Disabled by default |
| **Via cost** | High on 2-layer (300) | Default (50) |
| **Turn cost** | High (2000) | Default (1000) |
| **Target users** | Keyboard designers | PCB designers (general) |

## Integration with Other Skills

- **plan-pcb-routing**: If keyboard matrix detected, recommend using this skill instead
- **find-high-speed-nets**: Optional for MCU signal integrity analysis
- **analyze-power-nets**: Optional for power distribution planning

## Example Workflow

```bash
# Dry-run to see the plan without routing
python route_keyboard.py board.kicad_pcb /tmp/plan.kicad_pcb --dry-run --verbose

# Full routing (4-layer board)
python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb --layers 4

# With overrides
python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb \
    --track-width 0.2 \
    --clearance 0.15 \
    --via-size 0.4 \
    --verbose

# Keep intermediate files for debugging
python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb \
    --keep-intermediate \
    --verbose
```

## Testing

Run the integration test suite:

```bash
python tests/test_keyboard_routing.py
```

This verifies:
- ✓ Matrix detection on test keyboard
- ✓ Net classification (rows, cols, USB, power)
- ✓ Routing plan generation
- ✓ DRC checks on output

## Notes

1. **Keyboard matrix requirement**: Expects switches with diodes in row/column topology
2. **Through-hole handling**: Automatically detects cherry MX switch pad geometry
3. **Layer count auto-detection**: Reads copper layer count from PCB stackup
4. **No schematic sync**: Routing doesn't update the schematic (no swaps expected in keyboards)
5. **Intermediate file cleanup**: Automatically deletes phase files unless `--keep-intermediate` is used
