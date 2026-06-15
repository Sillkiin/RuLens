"""Embedded text-translator panel docked under the control bar.

Type or paste text; the translation appears below automatically (no buttons —
clean translator style). Clipboard shortcuts work on any keyboard layout because
they are bound by physical key code, not by keysym (so Ctrl+С/М/Ч/Ф on a Russian
layout copy/paste/cut/select-all just like Ctrl+C/V/X/A).

Network calls run on a daemon thread; results return to the Tk thread via a queue
polled with after(), and a request id drops stale results during fast typing.
"""
import queue
import threading
import tkinter as tk

from .translate import Translator

_BG = "#15151f"
_PANEL = "#1d1d2a"
_FG = "#e8e8f0"
_MUTED = "#9a9aa8"
_ACCENT = "#7c5cff"

LANG_NAMES = {
    "en": "Английский", "ru": "Русский", "de": "Немецкий", "fr": "Французский",
    "es": "Испанский", "it": "Итальянский", "uk": "Украинский", "pl": "Польский",
    "pt": "Португальский", "tr": "Турецкий", "zh": "Китайский", "ja": "Японский",
}
DEBOUNCE_MS = 550
PLACEHOLDER = "Введите или вставьте текст для перевода…"

# Windows virtual key codes (layout-independent): A, C, V, X
_VK_A, _VK_C, _VK_V, _VK_X = 65, 67, 86, 88


def lang_name(code: str) -> str:
    return LANG_NAMES.get(code, code.upper())


class TextPanel:
    """Builds the translator UI into a parent frame (the control bar's container)."""

    def __init__(self, parent: tk.Misc, translator: Translator,
                 source_lang: str, target_lang: str) -> None:
        self.host = parent
        self.translator = translator
        self.src = source_lang
        self.tgt = target_lang
        self.translator.set_languages(self.src, self.tgt)
        self._results: queue.Queue = queue.Queue()
        self._req = 0
        self._stopped = False
        self._after_id: str | None = None
        self._placeholder = False

        head = tk.Frame(parent, bg=_BG)
        head.pack(fill="x", padx=12, pady=(10, 4))
        self._lbl_src = tk.Label(head, text=lang_name(self.src), bg=_BG, fg=_FG,
                                 font=("Segoe UI", 10, "bold"))
        self._lbl_src.pack(side="left")
        swap = tk.Label(head, text="   ⇄   ", bg=_BG, fg=_ACCENT,
                        font=("Segoe UI", 12, "bold"), cursor="hand2")
        swap.pack(side="left")
        swap.bind("<Button-1>", lambda _e: self._swap())
        self._lbl_tgt = tk.Label(head, text=lang_name(self.tgt), bg=_BG, fg=_FG,
                                 font=("Segoe UI", 10, "bold"))
        self._lbl_tgt.pack(side="left")
        self._status = tk.Label(head, text="", bg=_BG, fg=_MUTED, font=("Segoe UI", 9))
        self._status.pack(side="right")

        self.inp = self._textbox()
        self.inp.pack(fill="both", expand=True, padx=12, pady=4)
        self.inp.bind("<KeyRelease>", self._on_type)
        self.inp.bind("<FocusIn>", self._clear_placeholder)
        self._bind_clipboard(self.inp, editable=True)
        self._show_placeholder()

        self.out = self._textbox()
        self.out.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        self._make_readonly(self.out)
        self._bind_clipboard(self.out, editable=False)

        self.host.after(120, self._poll)

    # ---------- widgets ----------

    def _textbox(self) -> tk.Text:
        return tk.Text(self.host, height=4, width=44, bg=_PANEL, fg=_FG, insertbackground=_FG,
                       relief="flat", font=("Segoe UI", 11), padx=10, pady=8, wrap="word",
                       highlightthickness=1, highlightbackground="#2a2a3d", highlightcolor=_ACCENT)

    # ---------- clipboard (layout-independent, by key code) ----------

    def _bind_clipboard(self, widget: tk.Text, editable: bool) -> None:
        def handler(event):
            if not (event.state & 0x4):  # Control must be held
                return None
            kc = event.keycode
            if kc == _VK_C:
                self._copy(widget)
                return "break"
            if kc == _VK_A:
                self._select_all(widget)
                return "break"
            if editable and kc == _VK_V:
                self._paste(widget)
                self._schedule()
                return "break"
            if editable and kc == _VK_X:
                self._copy(widget)
                self._delete_selection(widget)
                self._schedule()
                return "break"
            return None
        widget.bind("<Control-KeyPress>", handler)

    def _make_readonly(self, widget: tk.Text) -> None:
        nav = {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
               "Shift_L", "Shift_R", "Control_L", "Control_R"}

        def block(event):
            if event.state & 0x4 or event.keysym in nav:
                return None
            return "break"
        widget.bind("<KeyPress>", block)

    def _copy(self, w: tk.Text) -> None:
        try:
            text = w.get("sel.first", "sel.last")
        except tk.TclError:
            text = w.get("1.0", "end").strip() if w is self.out else ""
        if text:
            self.host.clipboard_clear()
            self.host.clipboard_append(text)

    def _paste(self, w: tk.Text) -> None:
        try:
            data = self.host.clipboard_get()
        except tk.TclError:
            return
        self._clear_placeholder()
        self._delete_selection(w)
        w.insert("insert", data)

    def _delete_selection(self, w: tk.Text) -> None:
        try:
            w.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def _select_all(self, w: tk.Text) -> None:
        w.tag_add("sel", "1.0", "end-1c")

    # ---------- placeholder ----------

    def _show_placeholder(self) -> None:
        self.inp.delete("1.0", "end")
        self.inp.insert("1.0", PLACEHOLDER)
        self.inp.configure(fg=_MUTED)
        self._placeholder = True

    def _clear_placeholder(self, _event=None) -> None:
        if self._placeholder:
            self.inp.delete("1.0", "end")
            self.inp.configure(fg=_FG)
            self._placeholder = False

    def _input_text(self) -> str:
        return "" if self._placeholder else self.inp.get("1.0", "end").strip()

    # ---------- translation flow ----------

    def _on_type(self, _event=None) -> None:
        self._schedule()

    def _schedule(self) -> None:
        if self._after_id:
            self.host.after_cancel(self._after_id)
        self._after_id = self.host.after(DEBOUNCE_MS, self._translate_now)

    def _translate_now(self) -> None:
        if self._after_id:
            self.host.after_cancel(self._after_id)
            self._after_id = None
        text = self._input_text()
        if not text:
            self._set_output("")
            self._status.config(text="")
            return
        self._req += 1
        req = self._req
        self._status.config(text="Перевод…")
        threading.Thread(target=self._worker, args=(req, text), daemon=True).start()

    def _worker(self, req: int, text: str) -> None:
        self._results.put((req, self.translator.translate(text)))

    def stop(self) -> None:
        self._stopped = True

    def _poll(self) -> None:
        if self._stopped:
            return
        try:
            while True:
                req, result = self._results.get_nowait()
                if req == self._req:
                    if result is None:
                        self._status.config(text="Ошибка сети")
                    else:
                        self._set_output(result)
                        self._status.config(text="")
        except queue.Empty:
            pass
        self.host.after(120, self._poll)

    def _set_output(self, text: str) -> None:
        self.out.delete("1.0", "end")
        self.out.insert("1.0", text)

    def _swap(self) -> None:
        self.src, self.tgt = self.tgt, self.src
        self.translator.set_languages(self.src, self.tgt)
        self._lbl_src.config(text=lang_name(self.src))
        self._lbl_tgt.config(text=lang_name(self.tgt))
        translated = self.out.get("1.0", "end").strip()
        if translated:
            self._clear_placeholder()
            self.inp.delete("1.0", "end")
            self.inp.insert("1.0", translated)
        self._translate_now()
