"""Render the RuLens interface (control bar + text panel) to docs/interface.png.

The live UI is excluded from screen capture (so it never OCRs itself); here we
temporarily disable that exclusion and grab just the window rectangle.
"""
import ctypes
import ctypes.wintypes as wt
import time
import tkinter as tk
from pathlib import Path

ctypes.windll.shcore.SetProcessDpiAwareness(2)
from PIL import ImageGrab

import rulens.controlbar as controlbar
from rulens.controlbar import ControlBar
from rulens.paths import resource_path
from rulens.textwindow import TextPanel

controlbar.ControlBar._exclude_from_capture = lambda self: None  # make it visible in a capture

DEMO_IN = "Find a way out of the hospital. Restore power to the elevator."
DEMO_OUT = "Найдите выход из больницы. Восстановите питание лифта."


class _DemoTranslator:
    def set_languages(self, *_):
        pass

    def translate(self, text):
        return text


root = tk.Tk()
root.withdraw()
try:
    root.iconbitmap(default=resource_path("rulens.ico"))
except tk.TclError:
    pass

bar = ControlBar(root, (120, 120), on_select=lambda: None, on_toggle_auto=lambda: None,
                 on_toggle_visibility=lambda: None, on_quit=lambda: None, on_text=lambda: None)
panel = TextPanel(bar.text_container, _DemoTranslator(), "en", "ru")
bar.toggle_text()
panel._clear_placeholder()
panel.inp.delete("1.0", "end")
panel.inp.insert("1.0", DEMO_IN)
panel._set_output(DEMO_OUT)
bar.set_auto(True)  # show the active "⏸ Пауза" state
bar.win.deiconify()
bar.win.lift()
root.update_idletasks()
root.update()
ctypes.windll.user32.SetForegroundWindow(bar.hwnd)
time.sleep(0.5)
root.update()

rect = wt.RECT()
ctypes.windll.user32.GetWindowRect(bar.hwnd, ctypes.byref(rect))
img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
Path("docs").mkdir(exist_ok=True)
img.save("docs/interface.png")
print("saved docs/interface.png", img.size)
root.destroy()
