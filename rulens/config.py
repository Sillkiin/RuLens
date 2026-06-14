"""Configuration loading/saving for RuLens."""
import json
import logging

from .paths import user_data_dir

CONFIG_PATH = user_data_dir() / "config.json"

DEFAULTS = {
    "source_lang": "en",
    "target_lang": "ru",
    "region": None,  # [x, y, w, h]; None = primary monitor
    "interval_ms": 350,  # auto-mode refresh; network is ~75ms so this drives responsiveness
    "control_pos": [40, 40],  # control-bar position [x, y]
    "hotkeys": {
        "select_area": "ctrl+q",
        "lens_once": "ctrl+alt+l",
        "auto_toggle": "ctrl+alt+a",
        "visibility_toggle": "ctrl+alt+h",
        "quit": "ctrl+alt+x",
    },
    "style": {
        "opacity": 1.0,
        "font_family": "Segoe UI",
        "padding": 4,
    },
}

logger = logging.getLogger(__name__)


def _merge(defaults: dict, override: dict) -> dict:
    result = dict(defaults)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(defaults.get(key), dict):
            result[key] = _merge(defaults[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            # utf-8-sig: tolerate a BOM left by external editors (e.g. PowerShell)
            with open(CONFIG_PATH, encoding="utf-8-sig") as fh:
                return _merge(DEFAULTS, json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Не удалось прочитать config.json (%s) — использую настройки по умолчанию", exc)
    return _merge(DEFAULTS, {})


def save_config(config: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error("Не удалось сохранить config.json: %s", exc)
