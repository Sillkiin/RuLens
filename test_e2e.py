"""End-to-end test: real window -> capture -> OCR(en) -> batched translate ->
seamless overlay -> re-capture -> OCR(ru) + background color match.

A short-lived window with English text appears on screen during the test.
"""
import ctypes
import sys
import time
import tkinter as tk

import numpy as np

ctypes.windll.shcore.SetProcessDpiAwareness(2)
sys.stdout.reconfigure(encoding="utf-8")

from rulens.capture import ScreenCapture
from rulens.colors import block_colors, block_weight
from rulens.ocr import group_blocks, recognize
from rulens.overlay import Overlay, RenderBlock
from rulens.translate import Translator

REGION = (120, 120, 700, 260)
PANEL_BG = "#1a2a4a"  # dark blue: sampled patches must reproduce it

root = tk.Tk()
overlay = Overlay(root, REGION, {"opacity": 1.0, "font_family": "Segoe UI", "padding": 4})
# Keep the overlay capturable so the test can verify what it draws.

text_win = tk.Toplevel(root)
text_win.geometry(f"{REGION[2]}x{REGION[3]}+{REGION[0]}+{REGION[1]}")
text_win.overrideredirect(True)
text_win.attributes("-topmost", True)
text_win.configure(bg=PANEL_BG)
tk.Label(text_win, text="OBJECTIVES: Find a way out\nof the hospital.",
         bg=PANEL_BG, fg="white", font=("Arial", 22, "bold"), justify="left").place(x=20, y=20)
tk.Label(text_win, text="Stranger: Hello? Is anyone here?",
         bg=PANEL_BG, fg="white", font=("Arial", 20)).place(x=20, y=170)
root.update()
time.sleep(0.4)

cap = ScreenCapture()
img = cap.grab(REGION)
arr = np.asarray(img)
lines = recognize(img, "en")
print(f"OCR(en): {len(lines)} lines")
assert lines, "FAIL: no English text recognized on screen"

blocks = group_blocks(lines)
translator = Translator("en", "ru")
translations = translator.translate_many([b.text for b in blocks])
print("Batched translation:")
rendered = []
for block, translated in zip(blocks, translations):
    print(f"  '{block.text}' -> '{translated}'")
    assert translated, f"FAIL: translation unavailable for '{block.text}'"
    bg, fg = block_colors(arr, block.bbox)
    weight = block_weight(arr, [ln.bbox for ln in block.lines], bg, fg)
    print(f"    colors: bg={bg} fg={fg} weight={weight}")
    rendered.append(RenderBlock(bbox=block.bbox, text=translated,
                                line_height=block.line_height, bg=bg, fg=fg, weight=weight))

weights = {rb.text.split(":")[0]: rb.weight for rb in rendered}
bold_blocks = [rb for rb in rendered if rb.weight == "bold"]
normal_blocks = [rb for rb in rendered if rb.weight == "normal"]
assert bold_blocks and normal_blocks, f"FAIL: weight detection did not separate bold/normal: {weights}"
assert rendered[0].weight == "bold", "FAIL: OBJECTIVES block (bold source) detected as normal"
assert rendered[-1].weight == "normal", "FAIL: dialog block (regular source) detected as bold"
print("Weight detection: bold objectives + regular dialog recognized correctly")

expected_bg = (0x1A, 0x2A, 0x4A)
for rb in rendered:
    sampled = tuple(int(rb.bg[i:i + 2], 16) for i in (1, 3, 5))
    drift = sum(abs(a - b) for a, b in zip(sampled, expected_bg))
    assert drift < 60, f"FAIL: sampled bg {rb.bg} too far from panel color {PANEL_BG}"
print("Background sampling matches the panel color")

overlay.root.attributes("-topmost", True)
overlay.show_blocks(rendered)
text_win.lower()           # overlay must cover the original text
root.update()
time.sleep(0.5)

check = cap.grab(REGION)
result_ru = recognize(check, "ru")
ru_text = " ".join(ln.text for ln in result_ru)
print(f"OCR(ru) of overlaid screen: '{ru_text}'")

cap.close()
root.destroy()

cyrillic = sum("а" <= ch.lower() <= "я" for ch in ru_text)
assert cyrillic >= 10, f"FAIL: overlay does not show Russian text (cyrillic chars: {cyrillic})"
keywords = [w for w in ("больниц", "выход", "кто", "привет", "здесь", "незнаком") if w in ru_text.lower()]
assert keywords, f"FAIL: expected Russian keywords not found in '{ru_text}'"
print(f"PASS: seamless overlay renders contextual Russian translation (matched: {keywords})")
