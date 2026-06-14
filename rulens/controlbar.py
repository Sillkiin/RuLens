"""Compact RuLens control window.

A normal (decorated) top-level window so Windows handles it conventionally:
  • the title-bar Minimize button → minimizes to the taskbar (stays as a button),
  • the title-bar Close [X] → hides to the system tray (on_close),
  • a "Выход" button → full quit.
Always-on-top and excluded from screen capture so it never gets OCR'd itself.
"""
import ctypes
import tkinter as tk
from collections.abc import Callable

WDA_EXCLUDEFROMCAPTURE = 0x11

_BG = "#15151f"
_HOVER = "#2a2a3d"
_FG = "#e8e8f0"
_MUTED = "#9a9aa8"
_ACTIVE = "#34d399"


class ControlBar:
    def __init__(self, root: tk.Tk, position, on_select: Callable, on_toggle_auto: Callable,
                 on_toggle_visibility: Callable, on_quit: Callable, on_close: Callable | None = None,
                 on_swap: Callable | None = None, on_text: Callable | None = None,
                 direction_label: str = "EN→RU", title: str = "RuLens") -> None:
        self._on_toggle_auto = on_toggle_auto
        self._on_toggle_visibility = on_toggle_visibility
        self._on_swap = on_swap
        self._on_close = on_close
        self._on_text = on_text

        self.win = tk.Toplevel(root)
        self.win.title(title)
        self.win.configure(bg=_BG)
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        x, y = position or (40, 40)
        self.win.geometry(f"+{int(x)}+{int(y)}")
        if on_close:
            self.win.protocol("WM_DELETE_WINDOW", on_close)  # [X] -> tray

        row = tk.Frame(self.win, bg=_BG)
        row.pack(side="top", fill="x")
        self._row = row
        self._btn_select = self._button("⊡  Область", on_select)
        self._btn_text = self._button("✎  Текст", lambda: self._on_text() if self._on_text else None)
        self._btn_dir = self._button(direction_label,
                                     lambda: self._on_swap() if self._on_swap else None, fg=_ACTIVE)
        self._btn_auto = self._button("▶  Авто", lambda: self._on_toggle_auto())
        self._btn_eye = self._button("◐  Скрыть перевод", lambda: self._on_toggle_visibility())
        self._button("Выход", on_quit, fg=_MUTED)

        # Collapsible container for the docked text-translator panel (hidden by default).
        self.text_container = tk.Frame(self.win, bg=_BG)
        self._text_visible = False

        self.win.update_idletasks()
        self._exclude_from_capture()

    def toggle_text(self) -> bool:
        x, y = self.win.winfo_x(), self.win.winfo_y()
        self._text_visible = not self._text_visible
        if self._text_visible:
            self.text_container.pack(side="top", fill="both", expand=True)
        else:
            self.text_container.pack_forget()
        self.win.update_idletasks()
        # Re-fit to content while keeping the current position.
        self.win.geometry(f"{self.win.winfo_reqwidth()}x{self.win.winfo_reqheight()}+{x}+{y}")
        return self._text_visible

    @property
    def hwnd(self) -> int:
        user32 = ctypes.windll.user32
        return user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()

    def _button(self, text: str, command: Callable, fg: str = _FG) -> tk.Label:
        lbl = tk.Label(self._row, text=text, bg=_BG, fg=fg,
                       font=("Segoe UI", 10, "bold"), padx=10, pady=6, cursor="hand2")
        lbl.pack(side="left", padx=2, pady=5)
        lbl.bind("<Enter>", lambda _e: lbl.config(bg=_HOVER))
        lbl.bind("<Leave>", lambda _e: lbl.config(bg=_BG))
        lbl.bind("<Button-1>", lambda _e: command())
        return lbl

    def _exclude_from_capture(self) -> None:
        ctypes.windll.user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE)

    def set_auto(self, active: bool) -> None:
        self._btn_auto.config(text="⏸  Пауза" if active else "▶  Авто",
                              fg=_ACTIVE if active else _FG)

    def set_visible(self, visible: bool) -> None:
        self._btn_eye.config(text="◐  Скрыть перевод" if visible else "◐  Показать перевод")

    def set_direction(self, label: str) -> None:
        self._btn_dir.config(text=label)
