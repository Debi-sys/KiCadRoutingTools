#!/usr/bin/env python3
"""
One-click keyboard PCB auto-routing.

Detects the switch matrix, classifies nets, and routes the entire keyboard PCB
in a single command.

Usage:
    python route_keyboard.py input.kicad_pcb output.kicad_pcb [--layers 2|4]
    python route_keyboard.py input.kicad_pcb output.kicad_pcb --dry-run
    python route_keyboard.py input.kicad_pcb output.kicad_pcb --verbose
"""

import argparse
import sys
import os

from kicad_parser import parse_kicad_pcb
from keyboard import detect_keyboard_matrix, classify_keyboard_nets
from keyboard.net_classifier import print_classification
from keyboard.presets import keyboard_2layer_preset, keyboard_4layer_preset
from keyboard.routing_strategy import build_routing_plan, print_routing_plan


def main():
    parser = argparse.ArgumentParser(
        description="One-click keyboard PCB auto-routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb
  python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb --layers 4
  python route_keyboard.py board.kicad_pcb board_routed.kicad_pcb --dry-run --verbose
        """
    )

    parser.add_argument("input_file", help="Input unrouted PCB file (.kicad_pcb)")
    parser.add_argument("output_file", nargs='?', help="Output routed PCB file (default: input_routed.kicad_pcb)")
    parser.add_argument("--layers", type=int, choices=[2, 4],
                       help="Number of copper layers (auto-detect if not specified)")
    parser.add_argument("--track-width", type=float, help="Override track width (mm)")
    parser.add_argument("--clearance", type=float, help="Override clearance (mm)")
    parser.add_argument("--via-size", type=float, help="Override via size (mm)")
    parser.add_argument("--via-drill", type=float, help="Override via drill (mm)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    parser.add_argument("--skip-drc", action="store_true", help="Skip DRC checks after routing")
    parser.add_argument("--dry-run", action="store_true",
                       help="Detect matrix and classify nets, but don't route")
    parser.add_argument("--keep-intermediate", action="store_true",
                       help="Keep intermediate phase files (default: clean up)")

    args = parser.parse_args()

    # Set default output filename
    if not args.output_file:
        base, ext = os.path.splitext(args.input_file)
        args.output_file = f"{base}_routed{ext}"

    # Verify input file exists
    if not os.path.exists(args.input_file):
        print(f"ERROR: Input file not found: {args.input_file}")
        sys.exit(1)

    print(f"Loading PCB: {args.input_file}")
    pcb_data = parse_kicad_pcb(args.input_file)
    print(f"  Nets: {len(pcb_data.nets)}, Footprints: {len(pcb_data.footprints)}, "
          f"Segments: {len(pcb_data.segments)}, Vias: {len(pcb_data.vias)}")

    # Auto-detect layer count if not specified
    if args.layers is None:
        layer_count = len([l for l in pcb_data.board_info.copper_layers if l])
        args.layers = 4 if layer_count >= 4 else 2
        if args.verbose:
            print(f"  Auto-detected {args.layers}-layer board")
    else:
        if args.verbose:
            print(f"  Using {args.layers}-layer configuration")

    # Detect keyboard matrix
    print("\nDetecting keyboard matrix...")
    matrix = detect_keyboard_matrix(pcb_data)
    if not matrix:
        print("ERROR: Could not detect a valid keyboard matrix")
        print("  Expected: switches with diodes in a row/column configuration")
        sys.exit(1)

    # Classify nets
    print("\nClassifying nets...")
    classification = classify_keyboard_nets(pcb_data, matrix)

    if args.verbose:
        print_classification(pcb_data, classification)

    # Select routing preset
    if args.layers == 2:
        config = keyboard_2layer_preset()
        config_name = "2-layer"
    else:
        config = keyboard_4layer_preset()
        config_name = "4-layer"

    # Apply overrides
    if args.track_width:
        config.track_width = args.track_width
    if args.clearance:
        config.clearance = args.clearance
    if args.via_size:
        config.via_size = args.via_size
    if args.via_drill:
        config.via_drill = args.via_drill

    print(f"\nUsing {config_name} routing preset")
    print(f"  Track width: {config.track_width}mm, Clearance: {config.clearance}mm")
    print(f"  Via: {config.via_size}mm size / {config.via_drill}mm drill")

    # Build routing plan
    print("\nBuilding routing plan...")
    plan = build_routing_plan(pcb_data, matrix, classification, config, args.layers)
    print_routing_plan(plan, pcb_data)

    if args.dry_run:
        print("Dry-run mode: stopping after plan generation")
        return 0

    # Execute routing plan
    print("=" * 70)
    print("ROUTING IMPLEMENTATION")
    print("=" * 70)
    print("\nWARNING: Routing implementation (execute_plan) is not yet implemented.")
    print("This is a planning stub. To complete this feature, you will need to:")
    print("  1. Implement execute_plan() to call batch_route() for each phase")
    print("  2. Add intermediate file management")
    print("  3. Add error handling and recovery")
    print("  4. Add progress reporting")
    print("\nFor now, the routing plan has been generated and printed above.")
    print(f"\nTo manually route with the generated plan, use:")
    print(f"  python route.py {args.input_file} <output> --nets <net_patterns>")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
