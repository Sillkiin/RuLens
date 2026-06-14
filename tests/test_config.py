"""Unit tests for config merge and load/save (BOM tolerance, fallbacks)."""
import json

import rulens.config as config
from rulens.config import DEFAULTS, _merge, load_config, save_config


def test_merge_overrides_leaf_and_keeps_siblings():
    merged = _merge({"a": 1, "b": {"x": 1, "y": 2}}, {"b": {"y": 9}})
    assert merged == {"a": 1, "b": {"x": 1, "y": 9}}


def test_merge_does_not_mutate_defaults():
    defaults = {"b": {"y": 2}}
    _merge(defaults, {"b": {"y": 9}})
    assert defaults == {"b": {"y": 2}}


def test_load_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "absent.json")
    assert load_config()["source_lang"] == DEFAULTS["source_lang"]


def test_load_merges_partial_override(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"target_lang": "de"}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    cfg = load_config()
    assert cfg["target_lang"] == "de"
    assert cfg["source_lang"] == DEFAULTS["source_lang"]  # untouched default


def test_load_tolerates_utf8_bom(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"interval_ms": 1234}), encoding="utf-8-sig")
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    assert load_config()["interval_ms"] == 1234


def test_load_broken_json_falls_back_to_defaults(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    assert load_config() == _merge(DEFAULTS, {})


def test_save_then_load_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    cfg = _merge(DEFAULTS, {"region": [1, 2, 3, 4]})
    save_config(cfg)
    assert load_config()["region"] == [1, 2, 3, 4]
