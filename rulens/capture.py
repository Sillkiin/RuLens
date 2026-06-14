"""Screen capture helpers. An mss instance must stay on the thread that created it."""
import mss
from PIL import Image


class ScreenCapture:
    def __init__(self) -> None:
        self._mss = mss.MSS()

    def primary_region(self) -> tuple[int, int, int, int]:
        mon = self._mss.monitors[1]
        return (mon["left"], mon["top"], mon["width"], mon["height"])

    def grab(self, region: tuple[int, int, int, int]) -> Image.Image:
        x, y, w, h = region
        shot = self._mss.grab({"left": x, "top": y, "width": w, "height": h})
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    def close(self) -> None:
        self._mss.close()


def thumbprint(img: Image.Image) -> bytes:
    """Tiny grayscale signature used to cheaply detect scene changes."""
    return img.convert("L").resize((48, 27)).tobytes()


def changed_enough(sig_a: bytes, sig_b: bytes, threshold: float = 0.02) -> bool:
    """True when more than `threshold` share of pixels differ noticeably."""
    if sig_a is None or sig_b is None or len(sig_a) != len(sig_b):
        return True
    diff = sum(1 for a, b in zip(sig_a, sig_b) if abs(a - b) > 12)
    return diff / len(sig_a) > threshold
