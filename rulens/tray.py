"""System-tray icon (pystray) — keeps RuLens reachable when the bar is hidden.

pystray runs its own thread; menu callbacks marshal back to the Tk thread via the
app's ui_queue (the callables passed in here already do that).
"""
import threading
from collections.abc import Callable

import pystray
from PIL import Image


class Tray:
    def __init__(self, icon_path: str, actions: dict[str, Callable], is_auto: Callable[[], bool]) -> None:
        image = Image.open(icon_path)
        menu = pystray.Menu(
            pystray.MenuItem("Показать панель", lambda _i, _it: actions["show_bar"](), default=True),
            pystray.MenuItem("Перевод текста", lambda _i, _it: actions["open_text"]()),
            pystray.MenuItem("Перевести область", lambda _i, _it: actions["select"]()),
            pystray.MenuItem("Сменить направление (EN⇄RU)", lambda _i, _it: actions["swap"]()),
            pystray.MenuItem("Авто-перевод", lambda _i, _it: actions["auto"](),
                             checked=lambda _it: is_auto()),
            pystray.MenuItem("Скрыть/показать перевод", lambda _i, _it: actions["visibility"]()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", lambda _i, _it: actions["quit"]()),
        )
        self.icon = pystray.Icon("RuLens", image, "RuLens — экранный переводчик", menu)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:  # noqa: BLE001 - tray teardown must never block exit
            pass
