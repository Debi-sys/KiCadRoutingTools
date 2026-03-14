#!/usr/bin/env python3
"""Quick test of keyboard matrix detection on existing test files."""

import sys
from kicad_parser import parse_kicad_pcb
from keyboard import detect_keyboard_matrix

test_files = [
    "kicad_files/sonde_u.kicad_pcb",
    "kicad_files/flat_hierarchy.kicad_pcb",
    "kicad_files/interf_u_unrouted.kicad_pcb",
]

for file in test_files:
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {file}")
        print('='*60)
        pcb = parse_kicad_pcb(file)
        print(f"Loaded: {len(pcb.footprints)} footprints, {len(pcb.nets)} nets")

        matrix = detect_keyboard_matrix(pcb)
        if matrix:
            print(f"✓ Matrix detected: {matrix.matrix_size[0]}R x {matrix.matrix_size[1]}C")
        else:
            print(f"✗ No keyboard matrix (expected for non-keyboard designs)")
    except Exception as e:
        print(f"✗ Error: {e}")
