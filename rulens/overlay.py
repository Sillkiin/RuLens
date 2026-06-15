"""Click-through topmost overlay window that repaints text blocks seamlessly."""
import ctypes
import logging
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

TRANSPARENT_KEY = "#010203"

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

MIN_FONT_SIZE = 9
MAX_FONT_SIZE = 42


@dataclass
class RenderBlock:
    bbox: tuple[int, int, int, int]
    text: str
    line_height: float
    bg: str
    fg: str
    weight: Literal["normal", "bold"] = "normal"  # detected from source pixels


class Overlay:
    """Fullscreen-region window; everything except drawn blocks is transparent."""

    def __init__(self, root: tk.Tk, region: tuple[int, int, int, int], style: dict) -> None:
        self.root = root
        self.style = style
        self.region = region
        self._visible = True
        self._fonts: dict[tuple[int, str], tkfont.Font] = {}

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", style.get("opacity", 1.0))
        root.attributes("-transparentcolor", TRANSPARENT_KEY)
        root.configure(bg=TRANSPARENT_KEY)

        self.canvas = tk.Canvas(root, bg=TRANSPARENT_KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._hwnd = 0
        self.set_region(region)
        root.update_idletasks()
        self._hwnd = self._resolve_hwnd()
        self._apply_clickthrough()

    def _resolve_hwnd(self) -> int:
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        return hwnd or self.root.winfo_id()

    def _apply_clickthrough(self) -> None:
        user32 = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex_style)

    def set_capture_exclusion(self, excluded: bool) -> bool:
        """Apply or clear capture exclusion; returns whether the overlay is now excluded.

        When NOT excluded the overlay is visible to screen capture / remote desktop
        (AnyDesk, OBS, screen-share); the worker then briefly hides it during each
        grab so it doesn't OCR itself.
        """
        affinity = WDA_EXCLUDEFROMCAPTURE if excluded else WDA_NONE
        ok = bool(ctypes.windll.user32.SetWindowDisplayAffinity(self._hwnd, affinity))
        if excluded and not ok:
            logger.warning("SetWindowDisplayAffinity не сработал — оверлей будет скрываться на время захвата")
            return False
        return excluded

    def set_region(self, region: tuple[int, int, int, int]) -> None:
        self.region = region
        x, y, w, h = region
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        if self._hwnd:
            # geometry() resizes an overrideredirect window but can fail to MOVE it
            # (the window keeps the old position) — force the exact rect via Win32.
            self.root.update_idletasks()
            SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
            ctypes.windll.user32.SetWindowPos(
                self._hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE)

    def show_blocks(self, blocks: list[RenderBlock]) -> None:
        """Repaint each block: erase the original with its own background color,
        then draw the translation in the original text color — browser-translate style."""
        self.canvas.delete("all")
        pad = self.style.get("padding", 4)
        for block in blocks:
            x0, y0, x1, y1 = block.bbox
            width = max(x1 - x0, 60)
            font = self._font(self._size_for(block.line_height), block.weight)
            text_id = self.canvas.create_text(
                x0, y0, text=block.text, anchor="nw", width=width,
                font=font, fill=block.fg,
            )
            tx0, ty0, tx1, ty1 = self.canvas.bbox(text_id)
            rect_id = self.canvas.create_rectangle(
                min(tx0, x0) - pad, min(ty0, y0) - pad,
                max(tx1, x1) + pad, max(ty1, y1) + pad,
                fill=block.bg, outline=block.bg,
            )
            self.canvas.tag_lower(rect_id, text_id)

    @staticmethod
    def _size_for(line_height: float) -> int:
        """Pixel font size matching the original text height — never shrink the glyphs.

        Longer Russian text wraps within the original width and the background grows
        to cover it, so the font stays the same size and place as the source.
        """
        return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, round(line_height)))

    def _font(self, size: int, weight: Literal["normal", "bold"]) -> tkfont.Font:
        key = (size, weight)
        if key not in self._fonts:
            family = self.style.get("font_family", "Segoe UI")
            self._fonts[key] = tkfont.Font(family=family, size=-size, weight=weight)
        return self._fonts[key]

    def clear(self) -> None:
        self.canvas.delete("all")

    def toggle_visibility(self) -> bool:
        self._visible = not self._visible
        if self._visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        else:
            self.root.withdraw()
        return self._visible

    def hide_temporarily(self) -> None:
        if self._visible:
            self.root.withdraw()
            self.root.update_idletasks()

    def restore_after_capture(self) -> None:
        if self._visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
