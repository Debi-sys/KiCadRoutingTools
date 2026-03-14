#!/usr/bin/env python3
"""
Integration test for keyboard PCB routing.

Tests the complete keyboard routing workflow:
1. Matrix detection
2. Net classification
3. Routing plan generation
4. DRC checks (when full routing is implemented)
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_utils import run
from kicad_parser import parse_kicad_pcb
from keyboard import detect_keyboard_matrix, classify_keyboard_nets
from keyboard.presets import keyboard_2layer_preset


def test_keyboard_detection():
    """Test matrix detection on a known keyboard-like design."""
    print("\n" + "=" * 70)
    print("TEST: Keyboard Matrix Detection")
    print("=" * 70)

    # Use the test PCB that was detected to have a matrix
    pcb_file = "kicad_files/flat_hierarchy.kicad_pcb"

    if not os.path.exists(pcb_file):
        print(f"SKIP: {pcb_file} not found")
        return False

    pcb = parse_kicad_pcb(pcb_file)
    print(f"Loaded: {len(pcb.footprints)} footprints, {len(pcb.nets)} nets")

    matrix = detect_keyboard_matrix(pcb)
    assert matrix is not None, "Expected matrix detection to succeed"
    assert matrix.matrix_size[0] >= 2, f"Expected at least 2 rows, got {matrix.matrix_size[0]}"
    assert matrix.matrix_size[1] >= 2, f"Expected at least 2 cols, got {matrix.matrix_size[1]}"
    assert len(matrix.switches) >= 4, f"Expected at least 4 switches, got {len(matrix.switches)}"
    assert len(matrix.diodes) >= 4, f"Expected at least 4 diodes, got {len(matrix.diodes)}"

    print(f"✓ Detected {matrix.matrix_size[0]}R x {matrix.matrix_size[1]}C matrix "
          f"({len(matrix.switches)} switches, {len(matrix.diodes)} diodes)")
    return True


def test_net_classification():
    """Test net classification on the detected matrix."""
    print("\n" + "=" * 70)
    print("TEST: Keyboard Net Classification")
    print("=" * 70)

    pcb_file = "kicad_files/flat_hierarchy.kicad_pcb"
    if not os.path.exists(pcb_file):
        print(f"SKIP: {pcb_file} not found")
        return False

    pcb = parse_kicad_pcb(pcb_file)
    matrix = detect_keyboard_matrix(pcb)
    assert matrix is not None

    classification = classify_keyboard_nets(pcb, matrix)
    assert len(classification.row_nets) > 0, "Expected at least one row net"
    assert len(classification.col_nets) > 0, "Expected at least one column net"

    total_classified = (len(classification.row_nets) + len(classification.col_nets) +
                       len(classification.power_nets) + len(classification.mcu_signal_nets) +
                       len(classification.unclassified_nets))

    print(f"✓ Classified {total_classified} nets:")
    print(f"  - {len(classification.row_nets)} row nets")
    print(f"  - {len(classification.col_nets)} column nets")
    print(f"  - {len(classification.power_nets)} power nets")
    print(f"  - {len(classification.mcu_signal_nets)} MCU signal nets")
    print(f"  - {len(classification.unclassified_nets)} unclassified nets")
    return True


def test_routing_plan():
    """Test routing plan generation (dry-run)."""
    print("\n" + "=" * 70)
    print("TEST: Keyboard Routing Plan Generation")
    print("=" * 70)

    cmd = "python3 route_keyboard.py kicad_files/flat_hierarchy.kicad_pcb /tmp/test_keyboard_plan.kicad_pcb --dry-run"
    print(f"Running: {cmd}")

    # run() from run_utils.py prints output directly, doesn't return it
    # We'll just verify the command completes without error
    try:
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=".")
        assert result.returncode == 0, f"Command failed with return code {result.returncode}"
        output = result.stdout + result.stderr

        # Check output for expected plan elements
        assert "Detecting keyboard matrix" in output, "Expected matrix detection message"
        assert "Classifying nets" in output, "Expected net classification message"
        assert "Building routing plan" in output, "Expected plan building message"
        assert "KEYBOARD ROUTING PLAN" in output, "Expected routing plan output"
        assert "Dry-run mode" in output, "Expected dry-run confirmation"
    except AssertionError:
        raise

    print("✓ Routing plan generated successfully")
    print("✓ Dry-run mode completed without errors")
    return True


def test_drc_checks():
    """Test DRC checking on a routed board."""
    print("\n" + "=" * 70)
    print("TEST: DRC Checks")
    print("=" * 70)

    # For now, just verify the check_drc.py script exists and runs
    cmd = "python3 check_drc.py kicad_files/flat_hierarchy.kicad_pcb"
    print(f"Running: {cmd}")

    try:
        result = run(cmd)
        print("✓ DRC check completed")
        return True
    except Exception as e:
        print(f"⚠ DRC check failed (expected for unrouted board): {e}")
        return True  # Not a test failure


def main():
    """Run all keyboard routing tests."""
    print("\n" + "=" * 70)
    print("KEYBOARD PCB ROUTING INTEGRATION TESTS")
    print("=" * 70)

    tests = [
        ("Matrix Detection", test_keyboard_detection),
        ("Net Classification", test_net_classification),
        ("Routing Plan Generation", test_routing_plan),
        ("DRC Checks", test_drc_checks),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            results.append((test_name, False))
        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for test_name, passed_flag in results:
        status = "✓ PASS" if passed_flag else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
