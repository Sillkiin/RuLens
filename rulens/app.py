"""RuLens application: hotkeys, worker pipeline, overlay orchestration."""
import ctypes
import logging
import os
import queue
import threading
import time
import tkinter as tk

import keyboard
import numpy as np

from .capture import ScreenCapture, changed_enough, thumbprint
from .colors import block_colors, block_weight
from .config import load_config, save_config
from .controlbar import ControlBar
from .ocr import group_blocks, recognize
from .overlay import Overlay, RenderBlock
from .paths import resource_path
from .selector import RegionSelector
from .text_filters import is_noop_translation, should_translate
from .textwindow import TextPanel
from .translate import ENGINE_LABEL, Translator
from .tray import Tray

logger = logging.getLogger(__name__)

UI_POLL_MS = 60
FALLBACK_HIDE_DELAY_S = 0.12
UNTRANSLATED_PLACEHOLDER = "⚠ перевод недоступен"
HOTKEY_DEBOUNCE_S = 0.3
ICON_PATH = resource_path("rulens.ico")


def primary_screen() -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


class RuLensApp:
    def __init__(self, single_instance=None) -> None:
        self.single_instance = single_instance
        self.config = load_config()
        self.screen = primary_screen()
        self.region = tuple(self.config["region"]) if self.config["region"] else self.screen

        self.root = tk.Tk()
        try:
            self.root.iconbitmap(default=ICON_PATH)  # default icon for all windows (taskbar)
        except tk.TclError as exc:
            logger.warning("Не удалось установить иконку окна: %s", exc)
        self.overlay = Overlay(self.root, self.region, self.config["style"])
        self.capture_excluded = self.overlay.set_capture_exclusion(True)
        self.controlbar: ControlBar | None = None
        self.tray: Tray | None = None
        self.text_panel: TextPanel | None = None

        self.translator = Translator(self.config["source_lang"], self.config["target_lang"])

        self.ui_queue: queue.Queue = queue.Queue()
        self.auto_mode = threading.Event()
        self.run_once = threading.Event()
        self.stopping = threading.Event()
        self.selector_open = False
        self._last_hotkey: tuple[str, float] | None = None
        self._dirty = threading.Event()  # force the worker to re-process even on a static screen

        self.worker = threading.Thread(target=self._worker_loop, daemon=True)

    # ---------- lifecycle ----------

    def run(self) -> None:
        self._verify_capture_exclusion()
        self.controlbar = ControlBar(
            self.root, self.config.get("control_pos"),
            on_select=self.act_select,
            on_toggle_auto=self.act_toggle_auto,
            on_toggle_visibility=self.act_toggle_visibility,
            on_quit=self.act_quit,
            on_close=self.act_hide_to_tray,
            on_swap=self.act_swap_direction,
            on_text=self.act_toggle_text,
            direction_label=self._direction_label(),
        )
        self._start_tray()
        self._register_hotkeys()
        if self.single_instance is not None:
            # A second launch pings us instead of starting a duplicate; surface the bar.
            self.single_instance.start_listener(
                lambda: self.ui_queue.put(("show_bar", None)))
        self.worker.start()
        self._log_banner()
        self.root.after(UI_POLL_MS, self._poll_ui_queue)
        self.root.mainloop()

    def _log_banner(self) -> None:
        hk = self.config["hotkeys"]
        logger.info("RuLens запущен. Перевод: %s -> %s (%s)",
                    self.config["source_lang"], self.config["target_lang"], ENGINE_LABEL)
        logger.info("Горячие клавиши: %s — выбрать область | %s — перевести (линза) | "
                    "%s — авторежим | %s — скрыть/показать | %s — выход",
                    hk["select_area"], hk["lens_once"], hk["auto_toggle"],
                    hk["visibility_toggle"], hk["quit"])
        if not self.capture_excluded:
            logger.info("Оверлей будет кратко скрываться на время захвата экрана (режим совместимости)")

    def _register_hotkeys(self) -> None:
        from .config import DEFAULTS

        hk = self.config["hotkeys"]
        for name, action in (("select_area", "select"), ("lens_once", "lens"),
                             ("auto_toggle", "auto"), ("visibility_toggle", "visibility"),
                             ("quit", "quit")):
            combo = hk.get(name) or DEFAULTS["hotkeys"][name]
            try:
                keyboard.add_hotkey(combo, lambda a=action: self.ui_queue.put(("hotkey", a)))
            except ValueError:
                fallback = DEFAULTS["hotkeys"][name]
                logger.error("Некорректная горячая клавиша '%s' для '%s' — использую '%s'",
                             combo, name, fallback)
                keyboard.add_hotkey(fallback, lambda a=action: self.ui_queue.put(("hotkey", a)))

    def _start_tray(self) -> None:
        try:
            self.tray = Tray(ICON_PATH, {
                "show_bar": lambda: self.ui_queue.put(("show_bar", None)),
                "open_text": lambda: self.ui_queue.put(("open_text", None)),
                "select": lambda: self.ui_queue.put(("hotkey", "select")),
                "auto": lambda: self.ui_queue.put(("hotkey", "auto")),
                "visibility": lambda: self.ui_queue.put(("hotkey", "visibility")),
                "swap": lambda: self.ui_queue.put(("hotkey", "swap")),
                "quit": lambda: self.ui_queue.put(("hotkey", "quit")),
            }, is_auto=self.auto_mode.is_set)
            self.tray.start()
        except Exception as exc:  # noqa: BLE001 - tray is optional, never block startup
            logger.warning("Не удалось запустить значок в трее: %s", exc)
            self.tray = None

    def shutdown(self) -> None:
        logger.info("Завершение работы…")
        self.stopping.set()
        self.auto_mode.clear()
        if self.tray:
            self.tray.stop()
        try:
            keyboard.unhook_all()
        except Exception:  # noqa: BLE001 - keyboard cleanup must never block exit
            pass
        if self.single_instance is not None:
            self.single_instance.close()
        self.root.quit()

    # ---------- capture exclusion self-test ----------

    def _verify_capture_exclusion(self) -> None:
        """Draw a magenta probe and check whether it leaks into a screen grab."""
        if os.environ.get("RULENS_NO_CAPTURE_EXCLUDE"):
            return  # test mode: keep the overlay continuously visible (no compat hiding)
        if not self.capture_excluded:
            return
        probe = "#ff00ff"
        self.overlay.canvas.create_rectangle(0, 0, 160, 90, fill=probe, outline=probe)
        self.root.update()
        time.sleep(0.05)
        cap = ScreenCapture()
        try:
            img = cap.grab((self.region[0], self.region[1], 160, 90))
        finally:
            cap.close()
        self.overlay.clear()
        self.root.update()
        for pixel in img.getdata():
            if pixel[0] > 220 and pixel[1] < 40 and pixel[2] > 220:
                self.capture_excluded = False
                logger.info("Исключение из захвата не поддерживается — включаю режим совместимости")
                return

    # ---------- UI thread ----------

    def _poll_ui_queue(self) -> None:
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                # One bad frame or hotkey must never tear down the Tk mainloop.
                try:
                    self._dispatch_ui(kind, payload)
                except Exception as exc:  # noqa: BLE001 - keep the UI alive
                    logger.error("Ошибка в UI-обработчике '%s': %s", kind, exc)
        except queue.Empty:
            pass
        if not self.stopping.is_set():
            self.root.after(UI_POLL_MS, self._poll_ui_queue)

    def _dispatch_ui(self, kind: str, payload) -> None:
        if kind == "hotkey":
            self._handle_hotkey(payload)
        elif kind == "blocks":
            self.overlay.show_blocks(payload)
        elif kind == "status":
            logger.info("%s", payload)
        elif kind == "hide_for_capture":
            self.overlay.hide_temporarily()
            payload.set()
        elif kind == "show_after_capture":
            self.overlay.restore_after_capture()
        elif kind == "show_bar":
            self._show_bar()
        elif kind == "open_text":
            self.act_toggle_text()

    def _handle_hotkey(self, action: str) -> None:
        # Keyboard auto-repeat re-fires hotkeys while held — drop the repeats.
        now = time.monotonic()
        last = self._last_hotkey
        self._last_hotkey = (action, now)
        if last and last[0] == action and now - last[1] < HOTKEY_DEBOUNCE_S:
            return
        actions = {
            "select": self.act_select,
            "lens": self.act_lens,
            "auto": self.act_toggle_auto,
            "visibility": self.act_toggle_visibility,
            "swap": self.act_swap_direction,
            "quit": self.act_quit,
        }
        handler = actions.get(action)
        if handler:
            handler()

    # ---------- actions (shared by hotkeys and the control bar) ----------

    def act_select(self) -> None:
        self._open_selector()

    def act_lens(self) -> None:
        if self.auto_mode.is_set():
            self.auto_mode.clear()
            self._sync_auto_button()
        self.overlay.clear()
        self.run_once.set()

    def act_toggle_auto(self) -> None:
        if self.auto_mode.is_set():
            self.auto_mode.clear()
            self.overlay.clear()
            logger.info("Авторежим выключен")
        else:
            self.auto_mode.set()
            logger.info("Авторежим включён (обновление каждые %d мс)", self.config["interval_ms"])
        self._sync_auto_button()

    def act_toggle_visibility(self) -> None:
        visible = self.overlay.toggle_visibility()
        logger.info("Оверлей %s", "показан" if visible else "скрыт")
        if self.controlbar:
            self.controlbar.set_visible(visible)

    def act_swap_direction(self) -> None:
        src, tgt = self.config["target_lang"], self.config["source_lang"]
        self.config["source_lang"] = src
        self.config["target_lang"] = tgt
        self.translator.set_languages(src, tgt)
        save_config(self.config)
        self.overlay.clear()
        self._dirty.set()  # re-translate current screen in the new direction
        if self.controlbar:
            self.controlbar.set_direction(self._direction_label())
        logger.info("Направление перевода: %s → %s", src.upper(), tgt.upper())

    def _direction_label(self) -> str:
        return f"{self.config['source_lang'].upper()}→{self.config['target_lang'].upper()}"

    def act_hide_to_tray(self) -> None:
        if self.controlbar:
            self._save_control_pos()
            self.controlbar.win.withdraw()
            logger.info("Свёрнуто в трей (закрыть). Свернуть на панель задач — кнопкой «—» в заголовке")

    def _show_bar(self) -> None:
        if not self.controlbar:
            return
        win = self.controlbar.win
        try:
            win.deiconify()  # restores from the tray (withdrawn) or taskbar (iconic)
            win.lift()
            win.attributes("-topmost", True)
            win.focus_force()
        except tk.TclError as exc:
            logger.warning("Не удалось показать панель: %s", exc)
            return
        logger.info("Панель показана")

    def act_toggle_text(self) -> None:
        if not self.controlbar:
            return
        if self.text_panel is None:  # build once, into the control bar's container
            translator = Translator(self.config["source_lang"], self.config["target_lang"])
            self.text_panel = TextPanel(self.controlbar.text_container, translator,
                                        self.config["source_lang"], self.config["target_lang"])
        # If the bar is hidden in the tray, bring it back before showing the panel.
        if self.controlbar.win.state() == "withdrawn":
            self._show_bar()
        visible = self.controlbar.toggle_text()
        logger.info("Окно перевода текста %s", "открыто" if visible else "закрыто")

    def _save_control_pos(self) -> None:
        if not self.controlbar:
            return
        try:
            x, y = self.controlbar.win.winfo_x(), self.controlbar.win.winfo_y()
            if x > -10000 and y > -10000:  # ignore the off-screen coords of a hidden window
                self.config["control_pos"] = [x, y]
                save_config(self.config)
        except tk.TclError:
            pass

    def act_quit(self) -> None:
        self.shutdown()

    def _sync_auto_button(self) -> None:
        if self.controlbar:
            self.controlbar.set_auto(self.auto_mode.is_set())

    def _open_selector(self) -> None:
        if self.selector_open:
            return
        self.selector_open = True
        was_auto = self.auto_mode.is_set()
        self.auto_mode.clear()
        self.overlay.clear()
        # Hide the control bar so its always-on-top window can't intercept the
        # selection drag. The overlay is click-through, so it stays as-is.
        bar_was_open = self.controlbar and self.controlbar.win.state() != "withdrawn"
        if bar_was_open:
            self.controlbar.win.withdraw()

        def done(region: tuple[int, int, int, int] | None) -> None:
            self.selector_open = False
            if bar_was_open:
                self.controlbar.win.deiconify()
                self.controlbar.win.attributes("-topmost", True)
            if region:
                self.region = region
                self.overlay.set_region(region)
                self.config["region"] = list(region)
                save_config(self.config)
                self._dirty.set()  # process the new region immediately
                # Pick an area -> translation just starts. Simplest mental model.
                self.auto_mode.set()
                logger.info("Область выбрана: x=%d y=%d %dx%d — авторежим включён", *region)
            else:
                logger.info("Выбор области отменён")
                if was_auto:
                    self.auto_mode.set()
            self._sync_auto_button()

        RegionSelector(self.root, self.screen, done)

    # ---------- worker thread ----------

    def _worker_loop(self) -> None:
        cap = ScreenCapture()
        last_sig: bytes | None = None
        last_text: str | None = None
        interval = self.config["interval_ms"] / 1000

        while not self.stopping.is_set():
            triggered_once = self.run_once.is_set()
            if not triggered_once and not self.auto_mode.is_set():
                last_sig = last_text = None
                time.sleep(0.08)
                continue
            self.run_once.clear()
            if self._dirty.is_set():
                # Direction swap / new region: re-process even if the screen is unchanged.
                last_sig = last_text = None
                self._dirty.clear()

            started = time.monotonic()
            try:
                img = self._grab(cap)
                sig = thumbprint(img)
                if triggered_once or changed_enough(sig, last_sig):
                    last_sig = sig
                    lines = recognize(img, self.config["source_lang"])
                    blocks = [b for b in group_blocks(lines)
                              if should_translate(b.text, self.config["source_lang"])]
                    text_key = "\n".join(b.text for b in blocks)
                    if triggered_once or text_key != last_text:
                        last_text = text_key
                        translations = self.translator.translate_many([b.text for b in blocks])
                        arr = np.asarray(img)  # convert once, reuse across all blocks
                        rendered = []
                        for block, translated in zip(blocks, translations):
                            if is_noop_translation(block.text, translated):
                                continue  # engine returned it unchanged — leave the original
                            bg, fg = block_colors(arr, block.bbox)
                            weight = block_weight(
                                arr, [line.bbox for line in block.lines], bg, fg)
                            rendered.append(RenderBlock(
                                bbox=block.bbox,
                                text=translated or UNTRANSLATED_PLACEHOLDER,
                                line_height=block.line_height,
                                bg=bg, fg=fg, weight=weight,
                            ))
                        self.ui_queue.put(("blocks", rendered))
                        if triggered_once:
                            self.ui_queue.put(("status",
                                               f"Линза: найдено блоков текста — {len(rendered)}"))
            except Exception as exc:  # noqa: BLE001 - keep the loop alive, surface the error
                logger.error("Сбой обработки кадра: %s", exc)

            if self.auto_mode.is_set():
                elapsed = time.monotonic() - started
                time.sleep(max(0.05, interval - elapsed))

        cap.close()

    def _grab(self, cap: ScreenCapture):
        if self.capture_excluded:
            return cap.grab(self.region)
        hidden = threading.Event()
        self.ui_queue.put(("hide_for_capture", hidden))
        hidden.wait(timeout=1)
        time.sleep(FALLBACK_HIDE_DELAY_S)
        try:
            return cap.grab(self.region)
        finally:
            self.ui_queue.put(("show_after_capture", None))
