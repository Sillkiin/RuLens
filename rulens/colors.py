"""Sample background/text color and font weight of an OCR block from a frame.

Works on a numpy RGB array (H, W, 3, uint8) — the worker converts each captured
frame once and reuses it across all blocks, so sampling stays cheap even for
near-fullscreen regions (vectorized, ~hundreds of microseconds vs ~0.8 s in pure
Python).
"""
from typing import Literal

import numpy as np

RING_MARGIN = 4
MIN_CONTRAST = 90
# Calibrated on Arial/Segoe/Times 18-40px: regular <= 0.21, bold >= 0.25.
BOLD_INK_THRESHOLD = 0.235
DEFAULT_BG = "#101018"
DEFAULT_FG = "#f2f2f7"


def block_colors(arr: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[str, str]:
    """Return (background_hex, text_hex) for the block at `bbox`.

    Background = median of a thin ring just outside the text box.
    Text = the interior pixel most distant from the background, falling back to
    black/white when contrast is too low to trust (OCR noise on a flat surface).
    """
    height, width = arr.shape[:2]
    x0, y0, x1, y1 = _clamp(bbox, width, height)
    if x1 <= x0 or y1 <= y0:
        return DEFAULT_BG, DEFAULT_FG

    bg = _ring_median(arr, x0, y0, x1, y1, width, height)
    if bg is None:
        return DEFAULT_BG, DEFAULT_FG

    region = arr[y0:y1, x0:x1].reshape(-1, 3).astype(np.int16)
    distance = np.abs(region - bg).sum(axis=1)
    idx = int(distance.argmax())
    fg: tuple[int, int, int]
    if int(distance[idx]) < MIN_CONTRAST:
        luma = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
        fg = (16, 16, 16) if luma > 128 else (242, 242, 247)
    else:
        px = region[idx]
        fg = (int(px[0]), int(px[1]), int(px[2]))

    return _hex((int(bg[0]), int(bg[1]), int(bg[2]))), _hex(fg)


def block_weight(arr: np.ndarray, line_bboxes: list[tuple[int, int, int, int]],
                 bg_hex: str, fg_hex: str) -> Literal["normal", "bold"]:
    """Estimate font weight ("normal"/"bold") from ink density inside text lines."""
    bg = np.array(_parse_hex(bg_hex), dtype=np.int16)
    fg = np.array(_parse_hex(fg_hex), dtype=np.int16)
    height, width = arr.shape[:2]
    total = ink = 0
    for bbox in line_bboxes:
        x0, y0, x1, y1 = _clamp(bbox, width, height)
        if x1 <= x0 or y1 <= y0:
            continue
        region = arr[y0:y1, x0:x1].reshape(-1, 3).astype(np.int16)
        d_fg = np.abs(region - fg).sum(axis=1)
        d_bg = np.abs(region - bg).sum(axis=1)
        ink += int((d_fg < d_bg).sum())
        total += region.shape[0]
    if not total:
        return "normal"
    return "bold" if ink / total > BOLD_INK_THRESHOLD else "normal"


def _ring_median(arr, x0, y0, x1, y1, width, height) -> np.ndarray | None:
    rx0, ry0 = max(0, x0 - RING_MARGIN), max(0, y0 - RING_MARGIN)
    rx1, ry1 = min(width, x1 + RING_MARGIN), min(height, y1 + RING_MARGIN)
    strips = [
        arr[ry0:y0, rx0:rx1],   # top margin band
        arr[y1:ry1, rx0:rx1],   # bottom
        arr[y0:y1, rx0:x0],     # left
        arr[y0:y1, x1:rx1],     # right
    ]
    pixels = [s.reshape(-1, 3) for s in strips if s.size]
    if not pixels:
        # Box reaches the frame edge — sample its own 1px border instead.
        border = [arr[y0, x0:x1], arr[y1 - 1, x0:x1],
                  arr[y0:y1, x0], arr[y0:y1, x1 - 1]]
        pixels = [b.reshape(-1, 3) for b in border if b.size]
        if not pixels:
            return None
    stacked = np.concatenate(pixels, axis=0)
    return np.median(stacked, axis=0).astype(np.int16)


def _clamp(bbox, width, height) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (max(0, int(x0)), max(0, int(y0)),
            min(width, int(x1)), min(height, int(y1)))


def _parse_hex(value: str) -> tuple[int, int, int]:
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
