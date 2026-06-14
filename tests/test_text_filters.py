"""Tests for should_translate — what is worth translating vs. what is noise."""
import pytest

from rulens.text_filters import is_noop_translation, should_translate

TRANSLATE_EN = [
    "Most capable for ambitious work",
    "Find a way out of the hospital.",
    "OK",
    "Level 5",
    "Opus 4.8",                      # has a real Latin word
    "Press Enter to continue",
]

SKIP_EN = [
    "",
    "X",
    "21:46",                         # time
    "14.06.2026",                    # date
    "100%",
    "v2.1.0",                        # version (no >=2-letter word)
    "HP: 100/100",                   # mostly digits/symbols
    "—",
    "◐ ✕",
    "РУС",                           # already Russian (wrong script for EN source)
    "Привет, как дела?",             # already Russian
    "3.14159",
]


@pytest.mark.parametrize("text", TRANSLATE_EN)
def test_en_source_translates_real_english(text):
    assert should_translate(text, "en") is True


@pytest.mark.parametrize("text", SKIP_EN)
def test_en_source_skips_noise_and_russian(text):
    assert should_translate(text, "en") is False


def test_ru_source_translates_russian_skips_english():
    assert should_translate("Найти выход из больницы", "ru") is True
    assert should_translate("Find the exit", "ru") is False   # Latin when expecting Cyrillic
    assert should_translate("2026", "ru") is False


def test_unknown_source_lang_only_applies_noise_gate():
    # No script gate for an unmapped language; real words still pass, noise still fails.
    assert should_translate("Bonjour le monde", "xx") is True
    assert should_translate("123 456", "xx") is False


def test_noop_translation_detection():
    assert is_noop_translation("OK", "OK") is True
    assert is_noop_translation("GitHub", "github") is True       # case/space-insensitive
    assert is_noop_translation("Opus 4.8", "Opus 4.8") is True
    assert is_noop_translation("Hello", "Привет") is False       # real translation
    assert is_noop_translation("Hello", None) is False           # failure, not a no-op
    assert is_noop_translation("Hello", "") is False
