"""Ручные правки после проверки конкретных вакансий (решения пользователя,
раздел «Проверено вручную» / «Комментарий»). Применяется к v2 и v3 строкам
одинаково, чтобы исправленная вакансия выглядела одинаково в обоих наборах.
"""
from __future__ import annotations

MANUAL_REVIEW_OVERRIDES: dict[int, str] = {
    137188842: (
        "Проверено 2026-10-07: обычный IT-специалист («Ведущий специалист по "
        "информационным технологиям», Фармация); роль CIO указана работодателем "
        "ошибочно. Оставлена в выборке."
    ),
}


def apply_manual_override(row) -> None:
    """Мутирует row.verified_manually/row.comment, если для её vacancy_id есть
    ручная правка. Не трогает прочие поля (is_senior_role и т.п. остаются
    фактическими — комментарий только поясняет, что проверено вручную)."""
    override = MANUAL_REVIEW_OVERRIDES.get(row.vacancy_id)
    if override is not None:
        row.verified_manually = "да"
        row.comment = override
