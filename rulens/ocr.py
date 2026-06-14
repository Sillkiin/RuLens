"""Windows OCR wrapper: recognize text lines and group them into blocks."""
import statistics
from dataclasses import dataclass, field

import winocr
from PIL import Image


@dataclass
class Line:
    text: str
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1


@dataclass
class Block:
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        x0 = min(line.bbox[0] for line in self.lines)
        y0 = min(line.bbox[1] for line in self.lines)
        x1 = max(line.bbox[2] for line in self.lines)
        y1 = max(line.bbox[3] for line in self.lines)
        return (x0, y0, x1, y1)

    @property
    def line_height(self) -> float:
        return statistics.median(line.bbox[3] - line.bbox[1] for line in self.lines)


MIN_LINE_CHARS = 2


def recognize(img: Image.Image, lang: str) -> list[Line]:
    result = winocr.recognize_pil_sync(img, lang)
    lines = []
    for raw in result.get("lines", []):
        words = raw.get("words", [])
        if not words or len(raw["text"].strip()) < MIN_LINE_CHARS:
            continue
        rects = [w["bounding_rect"] for w in words]
        bbox = (
            int(min(r["x"] for r in rects)),
            int(min(r["y"] for r in rects)),
            int(max(r["x"] + r["width"] for r in rects)),
            int(max(r["y"] + r["height"] for r in rects)),
        )
        lines.append(Line(text=raw["text"].strip(), bbox=bbox))
    return lines


def group_blocks(lines: list[Line]) -> list[Block]:
    """Merge lines that visually belong to one paragraph/dialog box."""
    if not lines:
        return []

    ordered = sorted(lines, key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    blocks: list[Block] = []

    for line in ordered:
        target = None
        for block in blocks:
            if _belongs(block, line):
                target = block
                break
        if target is None:
            target = Block()
            blocks.append(target)
        target.lines.append(line)

    return blocks


def _belongs(block: Block, line: Line) -> bool:
    bx0, _, bx1, by1 = block.bbox
    lx0, ly0, lx1, _ = line.bbox
    height = max(block.line_height, line.bbox[3] - line.bbox[1])

    vertical_gap = ly0 - by1
    if vertical_gap > height * 0.9:
        return False

    overlap = min(bx1, lx1) - max(bx0, lx0)
    return overlap > -height * 2
