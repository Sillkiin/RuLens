"""Tests for the drag-to-select region UI (the area-selection mechanism)."""
from rulens.selector import RegionSelector


def test_drag_produces_region(tk_root):
    got = []
    sel = RegionSelector(tk_root, (0, 0, 1000, 800), got.append)
    tk_root.update()
    sel.canvas.event_generate("<ButtonPress-1>", x=100, y=120)
    sel.canvas.event_generate("<B1-Motion>", x=400, y=420)
    sel.canvas.event_generate("<ButtonRelease-1>", x=400, y=420)
    tk_root.update()
    assert got, "selector did not call back"
    assert got[0] == (100, 120, 300, 300)  # x, y, w, h (screen offset 0)


def test_tiny_drag_is_cancelled(tk_root):
    got = []
    sel = RegionSelector(tk_root, (0, 0, 1000, 800), got.append)
    tk_root.update()
    sel.canvas.event_generate("<ButtonPress-1>", x=100, y=100)
    sel.canvas.event_generate("<ButtonRelease-1>", x=105, y=105)  # below MIN_SIZE_PX
    tk_root.update()
    assert got == [None]


def test_region_offset_by_screen_origin(tk_root):
    got = []
    sel = RegionSelector(tk_root, (200, 100, 1000, 800), got.append)
    tk_root.update()
    sel.canvas.event_generate("<ButtonPress-1>", x=50, y=60)
    sel.canvas.event_generate("<B1-Motion>", x=250, y=260)
    sel.canvas.event_generate("<ButtonRelease-1>", x=250, y=260)
    tk_root.update()
    assert got[0] == (250, 160, 200, 200)  # offset by screen origin (200, 100)
