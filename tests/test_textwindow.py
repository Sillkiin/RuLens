"""Tests for the embedded text-translator panel (no network — fake translator)."""
import time
import tkinter as tk

import pytest

from rulens.textwindow import PLACEHOLDER, TextPanel, lang_name


class FakeTranslator:
    def __init__(self):
        self.source_lang = self.target_lang = None

    def set_languages(self, src, tgt):
        self.source_lang, self.target_lang = src, tgt

    def translate(self, text):
        return "RU:" + text


@pytest.fixture
def make_panel(tk_root):
    made = []

    def _make(src="en", tgt="ru"):
        host = tk.Frame(tk_root)
        host.pack()
        panel = TextPanel(host, FakeTranslator(), src, tgt)
        made.append(host)
        tk_root.update()
        return panel

    yield _make
    for host in made:
        try:
            host.destroy()
        except Exception:
            pass


def test_lang_name_maps_known_and_falls_back():
    assert lang_name("en") == "Английский"
    assert lang_name("ru") == "Русский"
    assert lang_name("xx") == "XX"


def test_placeholder_visible_on_open(make_panel):
    panel = make_panel()
    assert panel._placeholder is True
    assert PLACEHOLDER in panel.inp.get("1.0", "end")
    assert panel._input_text() == ""


def test_swap_swaps_labels_and_languages(make_panel):
    panel = make_panel("en", "ru")
    panel._swap()
    assert panel._lbl_src.cget("text") == "Русский"
    assert panel._lbl_tgt.cget("text") == "Английский"
    assert panel.translator.source_lang == "ru"


def test_typing_produces_translation_in_output(make_panel):
    panel = make_panel()
    panel._clear_placeholder()
    panel.inp.insert("1.0", "Hello")
    panel._translate_now()
    deadline = time.time() + 2
    while time.time() < deadline:
        panel.host.update()
        if panel.out.get("1.0", "end").strip():
            break
        time.sleep(0.02)
    assert panel.out.get("1.0", "end").strip() == "RU:Hello"


def test_copy_and_select_all_put_text_on_clipboard(make_panel):
    panel = make_panel()
    panel._set_output("Переведённый текст")
    panel._select_all(panel.out)
    panel._copy(panel.out)
    panel.host.update()
    assert panel.host.clipboard_get() == "Переведённый текст"


def test_paste_inserts_clipboard_into_input(make_panel):
    panel = make_panel()
    panel.host.clipboard_clear()
    panel.host.clipboard_append("вставленный текст")
    panel._paste(panel.inp)
    assert panel._input_text() == "вставленный текст"
