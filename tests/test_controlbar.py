"""Tests for the click control bar (constructs, maps, reflects state, fires callbacks).

A single module-scoped Tk root is reused: creating/destroying multiple Tk() roots in
one process corrupts the Tcl interpreter on Windows.
"""
import tkinter as tk

import pytest

from rulens.controlbar import ControlBar


@pytest.fixture
def root(tk_root):
    return tk_root  # session-wide root from conftest (one Tk per process)


@pytest.fixture
def make_bar(root):
    bars = []

    def _make(**cbs):
        defaults = dict(on_select=lambda: None, on_toggle_auto=lambda: None,
                        on_toggle_visibility=lambda: None, on_quit=lambda: None)
        defaults.update(cbs)
        bar = ControlBar(root, (60, 60), **defaults)
        bars.append(bar)
        root.update()
        return bar

    yield _make
    for bar in bars:
        try:
            bar.win.destroy()
        except tk.TclError:
            pass


def test_control_bar_maps_and_has_size(make_bar):
    bar = make_bar()
    assert bar.win.winfo_ismapped()
    assert bar.win.winfo_width() > 80


def test_state_methods_update_button_labels(make_bar):
    bar = make_bar()
    bar.set_auto(True)
    bar.set_visible(False)
    bar.win.update()
    assert "Пауза" in bar._btn_auto.cget("text")
    assert "Показать" in bar._btn_eye.cget("text")
    bar.set_auto(False)
    assert "Авто" in bar._btn_auto.cget("text")


def test_clicking_buttons_fires_callbacks(make_bar):
    calls = []
    bar = make_bar(on_select=lambda: calls.append("select"),
                   on_toggle_auto=lambda: calls.append("auto"))
    bar._btn_select.event_generate("<Button-1>")
    bar._btn_auto.event_generate("<Button-1>")
    bar.win.update()
    assert calls == ["select", "auto"]


def test_text_button_fires_callback(make_bar):
    calls = []
    bar = make_bar(on_text=lambda: calls.append("text"))
    bar._btn_text.event_generate("<Button-1>")
    bar.win.update()
    assert calls == ["text"]


def test_direction_button_fires_and_updates_label(make_bar):
    calls = []
    bar = make_bar(on_swap=lambda: calls.append("swap"))
    bar._btn_dir.event_generate("<Button-1>")
    bar.win.update()
    assert calls == ["swap"]
    bar.set_direction("RU→EN")
    assert bar._btn_dir.cget("text") == "RU→EN"


def test_hide_and_show_cycle(make_bar):
    bar = make_bar()
    bar.win.withdraw()
    bar.win.update()
    assert not bar.win.winfo_ismapped()
    bar.win.deiconify()
    bar.win.update()
    assert bar.win.winfo_ismapped()
