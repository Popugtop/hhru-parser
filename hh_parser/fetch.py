"""Вежливый HTTP-клиент для hh.ru с диск-кэшем и паузами между запросами.

Правила вежливости (обязательны, см. задание):
- один запрос за раз, случайная пауза 2-4 секунды между любыми запросами;
- браузерный User-Agent, Accept-Language: ru-RU;
- без прокси, без логина/куков аутентификации, без обхода капчи;
- при капче/403/429 — немедленно останавливаемся (BlockedError), чтобы
  вызывающий код мог сохранить уже собранное и сообщить пользователю.
"""
from __future__ import annotations

import hashlib
import random
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from hh_parser.ssr import looks_like_captcha_or_block

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

SEARCH_BASE_URL = "https://hh.ru/search/vacancy"
VACANCY_BASE_URL = "https://hh.ru/vacancy"


class BlockedError(RuntimeError):
    """hh.ru вернул капчу, 403 или 429 — сбор нужно немедленно остановить."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _cache_key(params: list[tuple[str, str]]) -> str:
    canonical = "&".join(f"{k}={v}" for k, v in sorted(params))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class Fetcher:
    def __init__(
        self,
        cache_dir: str | Path = "cache",
        pause_min: float = 2.0,
        pause_max: float = 4.0,
        timeout: float = 30.0,
    ):
        self.cache_dir = Path(cache_dir)
        (self.cache_dir / "search").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "vacancy").mkdir(parents=True, exist_ok=True)
        self.pause_min = pause_min
        self.pause_max = pause_max
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/webp,*/*;q=0.8"
                ),
            }
        )
        self._requests_made = 0
        self.request_log: list[dict] = []

    def _polite_wait(self) -> None:
        if self._requests_made > 0:
            time.sleep(random.uniform(self.pause_min, self.pause_max))

    def _get(self, url: str) -> str:
        self._polite_wait()
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        self._requests_made += 1
        self.request_log.append({"url": url, "status": response.status_code})

        if response.status_code in (403, 429):
            raise BlockedError(
                f"hh.ru вернул {response.status_code} на {url} — похоже на блокировку/капчу",
                status_code=response.status_code,
            )
        response.raise_for_status()
        page_html = response.text
        if looks_like_captcha_or_block(page_html):
            raise BlockedError(f"Страница похожа на капчу/блокировку: {url}")
        return page_html

    def fetch_search_page(self, params: list[tuple[str, str]]) -> tuple[str, bool]:
        """params — список (ключ, значение) без items_on_page; он добавляется тут.
        Возвращает (html, пришло_из_кэша)."""
        full_params = list(params) + [("items_on_page", "50")]
        key = _cache_key(full_params)
        cache_path = self.cache_dir / "search" / f"{key}.html"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8"), True

        url = f"{SEARCH_BASE_URL}?{urlencode(full_params)}"
        page_html = self._get(url)
        cache_path.write_text(page_html, encoding="utf-8")
        return page_html, False

    def fetch_vacancy_page(self, vacancy_id: int) -> tuple[str, bool]:
        cache_path = self.cache_dir / "vacancy" / f"{vacancy_id}.html"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8"), True

        url = f"{VACANCY_BASE_URL}/{vacancy_id}"
        page_html = self._get(url)
        cache_path.write_text(page_html, encoding="utf-8")
        return page_html, False
