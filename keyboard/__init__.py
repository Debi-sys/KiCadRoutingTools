"""
Keyboard PCB routing specialization.

Provides auto-detection of keyboard switch matrices, net classification,
routing presets, and one-click routing orchestration for mechanical keyboard PCBs.
"""

from keyboard.matrix_detection import detect_keyboard_matrix, KeyboardMatrix
from keyboard.net_classifier import classify_keyboard_nets, KeyboardNetClassification
from keyboard.presets import keyboard_2layer_preset, keyboard_4layer_preset
