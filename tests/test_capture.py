"""Unit tests for change-detection helpers and screen grab."""
from PIL import Image

from rulens.capture import ScreenCapture, changed_enough, thumbprint


def test_screencapture_grab_returns_region_image():
    cap = ScreenCapture()
    try:
        img = cap.grab((0, 0, 8, 8))
        assert img.size == (8, 8)
        assert img.mode == "RGB"
    finally:
        cap.close()


def test_thumbprint_is_fixed_size():
    img = Image.new("RGB", (640, 480), "white")
    assert len(thumbprint(img)) == 48 * 27


def test_changed_enough_handles_missing_signatures():
    assert changed_enough(None, b"abc") is True
    assert changed_enough(b"abc", None) is True


def test_changed_enough_length_mismatch_is_change():
    assert changed_enough(b"\x00\x00", b"\x00") is True


def test_identical_signatures_are_not_a_change():
    sig = bytes(range(0, 200))
    assert changed_enough(sig, sig) is False


def test_large_difference_is_a_change():
    a = bytes([0] * 100)
    b = bytes([255] * 100)
    assert changed_enough(a, b) is True


def test_tiny_difference_below_threshold_is_not_a_change():
    a = bytes([100] * 100)
    b = bytearray(a)
    b[0] = 200  # one pixel differs -> 1% < default 2% threshold
    assert changed_enough(a, bytes(b)) is False
