"""Drag-to-select screen region UI."""
import tkinter as tk
from collections.abc import Callable

MIN_SIZE_PX = 24


class RegionSelector:
    """Dimmed fullscreen window; user drags a rectangle, Esc cancels."""

    def __init__(self, root: tk.Tk, screen: tuple[int, int, int, int],
                 on_done: Callable[[tuple[int, int, int, int] | None], None]) -> None:
        self.on_done = on_done
        self.screen = screen
        self.start: tuple[int, int] | None = None
        self.rect_id: int | None = None

        self.win = tk.Toplevel(root)
        x, y, w, h = screen
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.35)
        self.win.configure(bg="black", cursor="crosshair")

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            w // 2, 40, fill="#cdb8ff", font=("Segoe UI", 14, "bold"),
            text="Выделите область с текстом мышью  •  Esc — отмена",
        )

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda _e: self._finish(None))
        self.win.focus_force()
        self.win.grab_set()

    def _press(self, event: tk.Event) -> None:
        self.start = (event.x, event.y)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#7c5cff", width=2,
        )

    def _drag(self, event: tk.Event) -> None:
        if self.start and self.rect_id is not None:
            self.canvas.coords(self.rect_id, self.start[0], self.start[1], event.x, event.y)

    def _release(self, event: tk.Event) -> None:
        if not self.start:
            self._finish(None)
            return
        x0 = min(self.start[0], event.x) + self.screen[0]
        y0 = min(self.start[1], event.y) + self.screen[1]
        w = abs(event.x - self.start[0])
        h = abs(event.y - self.start[1])
        if w < MIN_SIZE_PX or h < MIN_SIZE_PX:
            self._finish(None)
            return
        self._finish((x0, y0, w, h))

    def _finish(self, region: tuple[int, int, int, int] | None) -> None:
        self.win.grab_release()
        self.win.destroy()
        self.on_done(region)
