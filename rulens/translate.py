"""Translation engines: Bing (Edge API, primary) with Google fallback, cached."""
import logging
import threading
import time
from collections import OrderedDict

import requests

logger = logging.getLogger(__name__)

BING_AUTH_URL = "https://edge.microsoft.com/translate/auth"
BING_TRANSLATE_URL = "https://api-edge.cognitive.microsofttranslator.com/translate"
GOOGLE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
CACHE_LIMIT = 600
REQUEST_TIMEOUT_S = 8
BING_TOKEN_TTL_S = 8 * 60
ENGINE_LABEL = "Bing (резерв: Google)"


class Translator:
    """translate_many() keeps blocks in one request so the engine sees full context."""

    def __init__(self, source_lang: str, target_lang: str) -> None:
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._bing_token: str | None = None
        self._bing_token_time = 0.0
        self._bing_down_until = 0.0
        # The text panel fires a translate thread per keystroke; serialize shared
        # state (cache + token) so concurrent calls can't corrupt the OrderedDict.
        self._lock = threading.Lock()

    def set_languages(self, source_lang: str, target_lang: str) -> None:
        """Switch translation direction; cached results are direction-specific, so drop them."""
        self.source_lang = source_lang
        self.target_lang = target_lang
        with self._lock:
            self._cache.clear()

    def translate_many(self, texts: list[str]) -> list[str | None]:
        keys = [t.strip() for t in texts]
        results: list[str | None] = [self._cache_get(k) if k else "" for k in keys]
        pending = [(i, keys[i]) for i in range(len(keys)) if results[i] is None and keys[i]]
        if not pending:
            return results

        translated = self._bing_batch([key for _, key in pending])
        if translated is None:
            translated = self._google_batch([key for _, key in pending])

        if translated is not None:
            for (index, key), value in zip(pending, translated):
                value = (value or "").strip()
                if value:
                    results[index] = value
                    self._cache_put(key, value)
        return results

    def translate(self, text: str) -> str | None:
        results = self.translate_many([text])
        return results[0]

    # ---------- Bing (Edge) ----------

    def _bing_batch(self, texts: list[str]) -> list[str] | None:
        if time.monotonic() < self._bing_down_until:
            return None
        try:
            resp = self._session.post(
                BING_TRANSLATE_URL,
                params={"from": self.source_lang, "to": self.target_lang, "api-version": "3.0"},
                json=[{"Text": t} for t in texts],
                headers={"Authorization": f"Bearer {self._bing_auth()}"},
                timeout=REQUEST_TIMEOUT_S,
            )
            if resp.status_code == 401:  # expired token: refresh once and retry
                self._bing_token = None
                resp = self._session.post(
                    BING_TRANSLATE_URL,
                    params={"from": self.source_lang, "to": self.target_lang, "api-version": "3.0"},
                    json=[{"Text": t} for t in texts],
                    headers={"Authorization": f"Bearer {self._bing_auth()}"},
                    timeout=REQUEST_TIMEOUT_S,
                )
            resp.raise_for_status()
            items = resp.json()
            if len(items) != len(texts):
                raise ValueError(f"ожидалось {len(texts)} переводов, получено {len(items)}")
            return [item["translations"][0]["text"] for item in items]
        except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
            logger.warning("Bing недоступен (%s) — переключаюсь на Google на 5 минут", exc)
            self._bing_down_until = time.monotonic() + 300
            return None

    def _bing_auth(self) -> str:
        if self._bing_token and time.monotonic() - self._bing_token_time < BING_TOKEN_TTL_S:
            return self._bing_token
        resp = self._session.get(BING_AUTH_URL, timeout=REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        token = resp.text.strip()
        if not token:  # empty token -> blank Bearer -> endless 401s; fail over to Google
            raise ValueError("пустой токен авторизации Bing")
        self._bing_token = token
        self._bing_token_time = time.monotonic()
        return token

    # ---------- Google fallback ----------

    def _google_batch(self, texts: list[str]) -> list[str] | None:
        joined = self._google_request("\n".join(texts))
        if joined is None:
            return None
        parts = joined.split("\n")
        if len(parts) == len(texts):
            return parts
        logger.warning("Разметка пакетного перевода Google не совпала — перевожу по одному")
        return [self._google_request(t) or "" for t in texts]

    def _google_request(self, text: str) -> str | None:
        try:
            resp = self._session.post(
                GOOGLE_ENDPOINT,
                params={"client": "gtx", "sl": self.source_lang,
                        "tl": self.target_lang, "dt": "t"},
                data={"q": text},
                timeout=REQUEST_TIMEOUT_S,
            )
            resp.raise_for_status()
            segments = resp.json()[0] or []
            return "".join(seg[0] for seg in segments if seg and seg[0])
        except (requests.RequestException, ValueError, IndexError) as exc:
            logger.error("Ошибка перевода Google: %s", exc)
            return None

    # ---------- cache ----------

    def _cache_get(self, key: str) -> str | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def _cache_put(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = value
            while len(self._cache) > CACHE_LIMIT:
                self._cache.popitem(last=False)
