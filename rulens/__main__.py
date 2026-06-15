"""RuLens entry point: `python -m rulens`."""
import ctypes
import logging
import sys

from .paths import user_data_dir


def _setup_logging() -> None:
    log_path = user_data_dir() / "rulens.log"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if sys.stdout is not None:  # windowed .exe has no console -> stdout is None
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def main() -> None:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    # Distinct AppUserModelID -> Windows groups the taskbar/tray under our own icon.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RuLens.ScreenTranslator")
    _setup_logging()

    from .single_instance import SingleInstance

    guard = SingleInstance()
    if not guard.acquire():
        # Already running: ping the live instance to surface its window, then exit
        # instead of stacking a duplicate process (the old "click does nothing" bug).
        logging.getLogger(__name__).info("RuLens уже запущен — активирую существующее окно.")
        guard.signal_existing()
        return

    from .app import RuLensApp

    app = RuLensApp(single_instance=guard)
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()


if __name__ == "__main__":
    main()
