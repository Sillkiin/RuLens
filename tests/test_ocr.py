"""Unit tests for block grouping (pure geometry) and a live OCR smoke check."""
from PIL import Image, ImageDraw, ImageFont

from rulens.ocr import Block, Line, group_blocks, recognize


def line(text, x0, y0, x1, y1):
    return Line(text=text, bbox=(x0, y0, x1, y1))


def test_empty_input_returns_no_blocks():
    assert group_blocks([]) == []


def test_single_line_is_one_block():
    blocks = group_blocks([line("Hello world", 10, 10, 200, 40)])
    assert len(blocks) == 1
    assert blocks[0].text == "Hello world"
    assert blocks[0].bbox == (10, 10, 200, 40)


def test_close_lines_merge_into_one_block():
    lines = [line("Line one", 10, 10, 200, 40),
             line("Line two", 10, 44, 200, 74)]  # gap ~4px << line height
    blocks = group_blocks(lines)
    assert len(blocks) == 1
    assert blocks[0].text == "Line one Line two"


def test_far_apart_lines_split_into_blocks():
    lines = [line("Header", 10, 10, 200, 40),
             line("Footer", 10, 400, 200, 430)]  # huge vertical gap
    blocks = group_blocks(lines)
    assert len(blocks) == 2


def test_block_bbox_is_union_of_lines():
    block = Block(lines=[line("a", 10, 10, 50, 30), line("bb", 5, 32, 80, 55)])
    assert block.bbox == (5, 10, 80, 55)


def test_block_line_height_is_median():
    block = Block(lines=[line("a", 0, 0, 10, 20), line("b", 0, 30, 10, 50)])
    assert block.line_height == 20


def test_recognize_reads_rendered_text_with_bbox():
    img = Image.new("RGB", (400, 80), "black")
    font = ImageFont.truetype("arial.ttf", 32)
    ImageDraw.Draw(img).text((10, 20), "Hello world", font=font, fill="white")
    lines = recognize(img, "en")
    assert lines, "Windows OCR returned no lines for clear rendered text"
    assert "hello" in " ".join(ln.text for ln in lines).lower()
    x0, y0, x1, y1 = lines[0].bbox
    assert x1 > x0 and y1 > y0
