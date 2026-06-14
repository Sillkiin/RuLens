"""Unit tests for the translator: cache, Bing path, Google fallback, alignment.

A fake session stands in for requests.Session so no network is touched.
"""
import time

import pytest
import requests

from rulens.translate import (
    BING_TRANSLATE_URL,
    Translator,
)


class FakeResp:
    def __init__(self, *, status_code=200, text="", payload=None, raise_exc=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, get_handler=None, post_handler=None):
        self.headers = {}
        self._get = get_handler
        self._post = post_handler

    def get(self, url, **kw):
        return self._get(url, kw)

    def post(self, url, **kw):
        return self._post(url, kw)


def _boom(*_a, **_k):
    raise AssertionError("no network call expected")


def _translator(get_handler=_boom, post_handler=_boom):
    t = Translator("en", "ru")
    t._session = FakeSession(get_handler, post_handler)
    return t


def test_cache_hit_skips_network():
    t = _translator()
    t._cache["Hello"] = "Привет"
    assert t.translate_many(["Hello"]) == ["Привет"]


def test_empty_strings_pass_through_without_network():
    t = _translator()
    assert t.translate_many(["", "   "]) == ["", ""]


def test_bing_batch_success_is_aligned():
    def post(url, kw):
        assert url == BING_TRANSLATE_URL
        texts = [d["Text"] for d in kw["json"]]
        return FakeResp(payload=[{"translations": [{"text": s.upper()}]} for s in texts])

    t = _translator(get_handler=lambda *_: FakeResp(text="TOKEN"), post_handler=post)
    assert t.translate_many(["a", "b"]) == ["A", "B"]


def test_bing_failure_falls_back_to_google():
    def post(url, kw):
        if url == BING_TRANSLATE_URL:
            return FakeResp(raise_exc=requests.RequestException("bing down"))
        q = kw["data"]["q"]
        joined = "\n".join("ru:" + p for p in q.split("\n"))
        return FakeResp(payload=[[[joined]]])

    t = _translator(get_handler=lambda *_: FakeResp(text="TOKEN"), post_handler=post)
    assert t.translate_many(["a", "b"]) == ["ru:a", "ru:b"]


def test_google_alignment_mismatch_falls_back_per_line():
    def post(url, kw):
        q = kw["data"]["q"]
        if "\n" in q:                      # batched request: return mismatched parts
            return FakeResp(payload=[[["one-blob-no-newlines"]]])
        return FakeResp(payload=[[["ru:" + q]]])   # per-line retry

    t = _translator(post_handler=post)
    t._bing_down_until = time.monotonic() + 100   # force Bing skipped
    assert t.translate_many(["a", "b"]) == ["ru:a", "ru:b"]


def test_set_languages_swaps_direction_and_clears_cache():
    t = _translator()
    t._cache["Hello"] = "Привет"
    t.set_languages("ru", "en")
    assert t.source_lang == "ru"
    assert t.target_lang == "en"
    assert not t._cache  # direction-specific results dropped


def test_translation_is_cached_after_first_call():
    calls = {"n": 0}

    def post(url, kw):
        calls["n"] += 1
        texts = [d["Text"] for d in kw["json"]]
        return FakeResp(payload=[{"translations": [{"text": "X"}]} for _ in texts])

    t = _translator(get_handler=lambda *_: FakeResp(text="TOKEN"), post_handler=post)
    t.translate_many(["repeat"])
    t.translate_many(["repeat"])
    assert calls["n"] == 1  # second call served from cache
