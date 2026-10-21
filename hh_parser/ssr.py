"""Извлечение SSR-состояния из HTML-страниц hh.ru.

hh.ru встраивает в HTML блок <template id="HH-Lux-InitialState">,
внутри которого лежит HTML-экранированный JSON с данными страницы
(выдача поиска или карточка вакансии). Порядок атрибутов тега может
отличаться (style может стоять до или после id), поэтому регулярка
не фиксирует порядок.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

_TEMPLATE_RE = re.compile(
    r'<template[^>]*\bid="HH-Lux-InitialState"[^>]*>(.*?)</template>',
    re.DOTALL,
)


class SSRExtractionError(RuntimeError):
    """Не удалось найти или разобрать блок HH-Lux-InitialState."""


def extract_initial_state(page_html: str) -> dict[str, Any]:
    """Достаёт и парсит JSON из блока HH-Lux-InitialState.

    Поднимает SSRExtractionError, если блок не найден (например, страница
    капчи/бан) или JSON повреждён.
    """
    match = _TEMPLATE_RE.search(page_html)
    if not match:
        raise SSRExtractionError("Блок HH-Lux-InitialState не найден в HTML")
    raw = html.unescape(match.group(1))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SSRExtractionError(f"Не удалось разобрать JSON: {exc}") from exc


_CAPTCHA_MARKERS = (
    "hh-captcha",
    "HH-Captcha",
    "/captcha/",
    "showcaptcha",
)


def looks_like_captcha_or_block(page_html: str) -> bool:
    """Грубая проверка на страницу капчи/блокировки (не на упоминание слова в переводах)."""
    lowered = page_html.lower()
    if "<title>" in lowered and "доступ ограничен" in lowered:
        return True
    return any(marker.lower() in lowered for marker in _CAPTCHA_MARKERS)
