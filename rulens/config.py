"""Configuration loading/saving for RuLens."""
import json
import logging
import os

from .paths import user_data_dir

CONFIG_PATH = user_data_dir() / "config.json"

DEFAULTS = {
    "source_lang": "en",
    "target_lang": "ru",
    "region": None,  # [x, y, w, h]; None = primary monitor
    "interval_ms": 350,  # auto-mode refresh; network is ~75ms so this drives responsiveness
    "control_pos": [40, 40],  # control-bar position [x, y]
    # Hide the UI from screen capture (WDA_EXCLUDEFROMCAPTURE). Default off so the
    # window is visible over AnyDesk / OBS / screen-share; the overlay briefly hides
    # during each grab instead. Set true for a flicker-free LOCAL-only experience.
    "capture_exclusion": False,
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
            _backup_corrupt_config()
    return _merge(DEFAULTS, {})


def _backup_corrupt_config() -> None:
    """Keep the unreadable config as .bak so the user's settings aren't lost forever."""
    try:
        backup = CONFIG_PATH.with_suffix(".bak")
        os.replace(CONFIG_PATH, backup)
        logger.error("Повреждённый config.json сохранён как %s", backup.name)
    except OSError:
        pass


def save_config(config: dict) -> None:
    # Atomic write: a crash mid-write must not leave a truncated/corrupt config.
    tmp = CONFIG_PATH.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except OSError as exc:
        logger.error("Не удалось сохранить config.json: %s", exc)
