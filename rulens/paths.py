"""Filesystem locations that work both in dev and inside a PyInstaller bundle."""
import os
import sys
from pathlib import Path

APP_NAME = "RuLens"


def resource_path(name: str) -> str:
    """A read-only bundled resource (e.g. the icon).

    PyInstaller unpacks data files to sys._MEIPASS; in dev we use the project root.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = Path(__file__).resolve().parent.parent
    return str(Path(base) / name)


def user_data_dir() -> Path:
    """Writable per-user directory for config and logs (created if missing)."""
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
