"""Decide whether an OCR'd text block is worth translating.

Filters out what should NOT be translated:
  • noise: pure numbers, timestamps, dates, percentages, version strings, symbols,
  • fragments with too few real letters,
  • text already in the target language / wrong script for the chosen direction
    (e.g. EN→RU shouldn't re-translate text that is already Russian).
"""
import re

_LATIN = re.compile(r"[a-zA-Z]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)       # any unicode letter
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)     # a run of >=2 letters

_CYRILLIC_LANGS = {"ru", "uk", "be", "bg", "sr", "mk", "kk"}
_LATIN_LANGS = {"en", "de", "fr", "es", "it", "pt", "nl", "pl", "tr", "cs",
                "sv", "da", "no", "fi", "ro", "hu", "id", "vi"}

MIN_LETTERS = 2
MIN_LETTER_RATIO = 0.3


def is_noop_translation(source: str, translated: str | None) -> bool:
    """True when the translation is effectively identical to the source.

    The engine returns text unchanged for proper nouns and untranslatable tokens
    ("OK", "GitHub", "Opus") — no point covering the original with an identical copy.
    """
    if not translated:
        return False  # None/empty = failure, handled separately
    norm = lambda s: re.sub(r"[\W_]+", "", s).casefold()
    return norm(source) == norm(translated)


def _script(lang: str) -> str | None:
    if lang in _CYRILLIC_LANGS:
        return "cyrillic"
    if lang in _LATIN_LANGS:
        return "latin"
    return None  # unknown language: skip the script gate, keep only the noise gate


def should_translate(text: str, source_lang: str) -> bool:
    t = text.strip()
    if len(t) < 2:
        return False

    letters = _LETTER.findall(t)
    if len(letters) < MIN_LETTERS or not _WORD.search(t):
        return False  # no real word — numbers, "v2.1", "21:46", symbols

    compact = re.sub(r"\s+", "", t)
    if compact and len(letters) / len(compact) < MIN_LETTER_RATIO:
        return False  # mostly digits/punctuation — "HP: 100/100", "4.8 GB / 16 GB"

    script = _script(source_lang)
    if script == "latin":
        lat, cyr = len(_LATIN.findall(t)), len(_CYRILLIC.findall(t))
        if lat == 0 or cyr > lat:
            return False  # no Latin / already mostly Cyrillic (already translated)
    elif script == "cyrillic":
        lat, cyr = len(_LATIN.findall(t)), len(_CYRILLIC.findall(t))
        if cyr == 0 or lat > cyr:
            return False
    return True
