"""Unit tests for color sampling and weight detection (numpy arrays)."""
import numpy as np

from rulens.colors import (
    _clamp,
    _hex,
    _parse_hex,
    block_colors,
    block_weight,
)


def test_hex_round_trip():
    assert _hex((26, 42, 74)) == "#1a2a4a"
    assert _parse_hex("#1a2a4a") == (26, 42, 74)


def test_clamp_keeps_box_inside_frame():
    assert _clamp((-5, -5, 200, 200), 100, 100) == (0, 0, 100, 100)


def test_solid_region_yields_its_color_and_fallback_fg():
    arr = np.full((100, 100, 3), (26, 42, 74), dtype=np.uint8)
    bg, fg = block_colors(arr, (0, 0, 100, 100))
    assert bg == "#1a2a4a"
    assert fg == "#f2f2f7"  # low contrast -> light fallback over a dark bg


def test_bright_text_pixel_is_detected_as_fg():
    arr = np.full((100, 100, 3), (10, 10, 10), dtype=np.uint8)
    arr[40:60, 40:60] = (250, 250, 250)
    bg, fg = block_colors(arr, (0, 0, 100, 100))
    assert bg == "#0a0a0a"
    assert fg == "#fafafa"


def test_dense_ink_reads_as_bold():
    arr = np.full((20, 100, 3), (255, 255, 255), dtype=np.uint8)  # all foreground
    assert block_weight(arr, [(0, 0, 100, 20)], "#000000", "#ffffff") == "bold"


def test_sparse_ink_reads_as_normal():
    arr = np.zeros((20, 100, 3), dtype=np.uint8)  # all background
    assert block_weight(arr, [(0, 0, 100, 20)], "#000000", "#ffffff") == "normal"


def test_weight_with_no_lines_is_normal():
    arr = np.zeros((20, 100, 3), dtype=np.uint8)
    assert block_weight(arr, [], "#000000", "#ffffff") == "normal"
