"""Перевод кодов hh.ru в читаемые русские подписи.

Значения сверены вживую 2026-10-07 с человекочитаемыми title из
searchClusters реального поиска по Тюмени (не угаданы), кроме
CIVIL_LAW_CONTRACTS — для них в кластерах поиска нет отдельного
счётчика, формулировки взяты из общепринятой терминологии hh.ru
("самозанятость, ИП, физлицо" в фильтрах вакансии).
"""
from __future__ import annotations

WORK_FORMAT = {
    "ON_SITE": "на месте работодателя",
    "FIELD_WORK": "разъездной",
    "REMOTE": "удалённо",
    "HYBRID": "гибрид",
}

WORK_SCHEDULE_BY_DAYS = {
    "FIVE_ON_TWO_OFF": "5/2",
    "TWO_ON_TWO_OFF": "2/2",
    "OTHER": "другое",
    "FOUR_ON_TWO_OFF": "4/2",
    "THREE_ON_TWO_OFF": "3/2",
    "THREE_ON_THREE_OFF": "3/3",
    "SIX_ON_ONE_OFF": "6/1",
    "FOUR_ON_THREE_OFF": "4/3",
    "FLEXIBLE": "свободный график",
    "ONE_ON_THREE_OFF": "1/3",
    "FOUR_ON_FOUR_OFF": "4/4",
    "ONE_ON_TWO_OFF": "1/2",
    "WEEKEND": "по выходным",
    "TWO_ON_ONE_OFF": "2/1",
}

WORKING_HOURS = {
    "HOURS_2": "2 часа",
    "HOURS_3": "3 часа",
    "HOURS_4": "4 часа",
    "HOURS_5": "5 часов",
    "HOURS_6": "6 часов",
    "HOURS_7": "7 часов",
    "HOURS_8": "8 часов",
    "HOURS_9": "9 часов",
    "HOURS_10": "10 часов",
    "HOURS_11": "11 часов",
    "HOURS_12": "12 часов",
    "HOURS_24": "24 часа",
    "OTHER": "другое",
    "FLEXIBLE": "по договорённости",
}

EMPLOYMENT_FORM = {
    "FULL": "полная занятость",
    "PART": "частичная занятость",
    "FLY_IN_FLY_OUT": "вахта",
    "PROJECT": "подработка",
    "SIDE_JOB": "подработка",
}

CIVIL_LAW_CONTRACTS = {
    "SELF_EMPLOYED": "самозанятость",
    "INDIVIDUAL_ENTREPRENEUR": "ИП",
    "INDIVIDUAL_PERSON": "физлицо",
}

EDUCATION_FILTER = {
    "higher": "Высшее",
    "special_secondary": "СПО",
    "not_required_or_not_specified": "Не требуется или не указано",
}


def translate(mapping: dict[str, str], code: str | None) -> str | None:
    """Переводит один код. Неизвестный код возвращает как есть с префиксом,
    чтобы было заметно при проверке, а не тихо терялось."""
    if code is None:
        return None
    return mapping.get(code, f"[неизвестный код: {code}]")


def translate_list(mapping: dict[str, str], codes: list[str] | None, sep: str = ", ") -> str:
    """Переводит список кодов в одну строку через запятую. Пустой список/None -> ''."""
    if not codes:
        return ""
    return sep.join(translate(mapping, c) for c in codes)
