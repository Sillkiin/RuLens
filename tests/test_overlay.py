"""Unit tests for overlay font sizing (pure logic — no window needed)."""
from rulens.overlay import MAX_FONT_SIZE, MIN_FONT_SIZE, Overlay


def test_size_matches_original_line_height():
    # Same size as the source text — glyphs are not shrunk to fit.
    assert Overlay._size_for(30) == 30
    assert Overlay._size_for(18) == 18


def test_size_is_clamped():
    assert Overlay._size_for(2) == MIN_FONT_SIZE       # tiny -> floor
    assert Overlay._size_for(9999) == MAX_FONT_SIZE    # huge -> ceil
