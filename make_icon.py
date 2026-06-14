"""Generate rulens.ico — a purple lens badge with 'Я' and a magnifier loupe."""
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
PURPLE_TOP = (140, 92, 255)
PURPLE_BOT = (96, 60, 230)
WHITE = (245, 245, 252)


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def vertical_gradient(size, top, bot):
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return grad.resize((size, size))


def build(size=SIZE):
    base = vertical_gradient(size, PURPLE_TOP, PURPLE_BOT)
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(base, (0, 0), rounded_mask(size, int(size * 0.22)))

    draw = ImageDraw.Draw(icon)
    font = ImageFont.truetype("arialbd.ttf", int(size * 0.62))
    text = "Я"
    box = draw.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    tx = (size - tw) / 2 - box[0] - size * 0.06
    ty = (size - th) / 2 - box[1] - size * 0.06
    draw.text((tx, ty), text, font=font, fill=WHITE)

    # magnifier loupe, bottom-right
    cx, cy, r = int(size * 0.70), int(size * 0.70), int(size * 0.17)
    ring = max(4, int(size * 0.045))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=ring)
    hx, hy = cx + int(r * 0.72), cy + int(r * 0.72)
    draw.line([hx, hy, hx + int(size * 0.13), hy + int(size * 0.13)], fill=WHITE, width=ring + 2)
    return icon


icon = build()
icon.save("rulens.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icon.save("rulens.png")
print("wrote rulens.ico and rulens.png")
