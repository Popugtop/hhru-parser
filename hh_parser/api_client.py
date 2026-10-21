"""Вежливый клиент официального API api.hh.ru/vacancies (переход с SSR-парсинга
сайта на официальный API, запрос пользователя от 2026-10-09): токен приложения
и HH-User-Agent читаются из .env (HH_ACCESS_TOKEN/HH_USER_AGENT) вызывающим
кодом (cli_v3_api.py) и передаются сюда как обычные строки — этот модуль их
никогда не печатает и не включает в сообщения об ошибках.

Правила вежливости для API (отличаются от --source web, раздел 7 задания):
пауза 0.5-1 с между запросами; 429 — подождать (Retry-After или экспоненциальный
backoff) и повторить; 401/403 — немедленно остановиться (BlockedError), как и
в веб-режиме.

Кэш — сырые JSON-ответы на диск (cache/api_search/*.json,
cache/api_vacancy/<id>.json), чтобы повторный запуск не скачивал то же самое.
Поле contacts (контакты рекрутёра) вырезается перед кэшированием и перед
возвратом вызывающему коду — персональные данные не сохраняем (раздел 7
задания).
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

from hh_parser.fetch import BlockedError

API_BASE = "https://api.hh.ru"
MAX_RETRIES_429 = 5


def load_env(env_path: str | Path = ".env") -> dict[str, str]:
    """Простой .env-парсер (без внешней зависимости python-dotenv):
    построчно KEY=VALUE, '#' — комментарий. Значения не логируются вызывающим
    кодом и не должны печататься."""
    env: dict[str, str] = {}
    path = Path(env_path)
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _strip_private_fields(data: Any) -> Any:
    """Убирает contacts (контакты рекрутёра) из ответа API перед кэшированием
    и перед использованием — персональные данные не нужны и не должны
    попадать на диск (раздел 7 задания)."""
    if isinstance(data, dict):
        return {key: _strip_private_fields(value) for key, value in data.items() if key != "contacts"}
    if isinstance(data, list):
        return [_strip_private_fields(item) for item in data]
    return data


def _cache_key(url: str, params: list[tuple[str, str]], date_tag: str | None = None) -> str:
    """date_tag — только для search(): без него одинаковый запрос в любой
    день попадал бы в тот же файл кэша, и повторный сбор через недели молча
    отдавал бы счётчики части А из прошлого (баг, найден 2026-10-21 — запуск
    через 12 дней вернул побайтово те же числа, что и первый раз, потому что
    сеть не трогали вообще). get_vacancy() кэшируется без даты осознанно —
    детали вакансии не меняются от запуска к запуску, и кэш должен переживать
    прерванный сбор части Б (раздел 7 задания)."""
    canonical = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params))
    if date_tag:
        canonical += f"#date={date_tag}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class ApiFetcher:
    def __init__(
        self,
        access_token: str,
        user_agent: str,
        cache_dir: str | Path = "cache",
        pause_min: float = 0.5,
        pause_max: float = 1.0,
        timeout: float = 30.0,
    ):
        self.cache_dir = Path(cache_dir)
        (self.cache_dir / "api_search").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "api_vacancy").mkdir(parents=True, exist_ok=True)
        self.pause_min = pause_min
        self.pause_max = pause_max
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "HH-User-Agent": user_agent,
            }
        )
        self._requests_made = 0
        self.request_log: list[dict] = []

    def _polite_wait(self) -> None:
        if self._requests_made > 0:
            time.sleep(random.uniform(self.pause_min, self.pause_max))

    def _get_json(self, url: str, params: list[tuple[str, str]]) -> dict:
        retries = 0
        while True:
            self._polite_wait()
            response = self.session.get(url, params=params, timeout=self.timeout)
            self._requests_made += 1
            self.request_log.append({"url": response.url, "status": response.status_code})

            if response.status_code in (401, 403):
                raise BlockedError(
                    f"api.hh.ru вернул {response.status_code} на {url} — доступ запрещён "
                    "(неверный, просроченный или отозванный токен?)",
                    status_code=response.status_code,
                )
            if response.status_code == 429:
                retries += 1
                if retries > MAX_RETRIES_429:
                    raise BlockedError(
                        f"api.hh.ru вернул 429 ({retries} попыток подряд) на {url} — "
                        "слишком много запросов",
                        status_code=429,
                    )
                retry_after = response.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after else min(2**retries, 30)
                time.sleep(wait_s)
                continue
            response.raise_for_status()
            return response.json()

    def search(self, params: list[tuple[str, str]]) -> dict:
        key = _cache_key(f"{API_BASE}/vacancies", params, date_tag=date.today().isoformat())
        cache_path = self.cache_dir / "api_search" / f"{key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        data = _strip_private_fields(self._get_json(f"{API_BASE}/vacancies", params))
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def get_vacancy(self, vacancy_id: int) -> dict:
        cache_path = self.cache_dir / "api_vacancy" / f"{vacancy_id}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        data = _strip_private_fields(self._get_json(f"{API_BASE}/vacancies/{vacancy_id}", []))
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
