"""Pipeline smoke test: PIL-rendered text -> Windows OCR -> Google translate."""
import sys

import requests
import winocr
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

img = Image.new("RGB", (900, 200), "black")
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("arial.ttf", 36)
draw.text((20, 30), "Find a way out of the hospital.", font=font, fill="white")
draw.text((20, 110), "Restore power to the elevator.", font=font, fill="white")

result = winocr.recognize_pil_sync(img, "en")
print("OCR lines:")
for line in result["lines"]:
    words = line["words"]
    x0 = min(w["bounding_rect"]["x"] for w in words)
    y0 = min(w["bounding_rect"]["y"] for w in words)
    x1 = max(w["bounding_rect"]["x"] + w["bounding_rect"]["width"] for w in words)
    y1 = max(w["bounding_rect"]["y"] + w["bounding_rect"]["height"] for w in words)
    print(f"  '{line['text']}' bbox=({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")

text = " ".join(line["text"] for line in result["lines"])
resp = requests.get(
    "https://translate.googleapis.com/translate_a/single",
    params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text},
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10,
)
resp.raise_for_status()
translated = "".join(seg[0] for seg in resp.json()[0] if seg[0])
print("Translated:", translated)
