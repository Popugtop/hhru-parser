"""Построение параметров поиска hh.ru (раздел 4 задания).

Базовые фильтры одинаковы для частей А и Б:
area, experience=noExperience, only_with_salary=true, employment_form=FULL,
salary_mode=MONTH, search_period=<N>, order_by=publication_time.
"""
from __future__ import annotations

Params = list[tuple[str, str]]


def base_params(area: int, search_period: int, with_salary_filters: bool = True) -> Params:
    """with_salary_filters=False — вариант без only_with_salary/salary_mode
    (раздел «Часть А — пересчитать», вариант 2 изменения дизайна v2):
    даёт больше вакансий, доли по образованию надёжнее."""
    params: Params = [
        ("area", str(area)),
        ("experience", "noExperience"),
        ("employment_form", "FULL"),
        ("search_period", str(search_period)),
        ("order_by", "publication_time"),
    ]
    if with_salary_filters:
        params += [("only_with_salary", "true"), ("salary_mode", "MONTH")]
    return params


def with_education(params: Params, education_group: str) -> Params:
    return params + [("education", education_group)]


def with_education_values(params: Params, education_groups: list[str]) -> Params:
    """Несколько значений education сразу — hh.ru объединяет их через OR
    (ored_clusters), так же как повторные professional_role."""
    return params + [("education", value) for value in education_groups]


def with_professional_roles(params: Params, role_ids: list[int]) -> Params:
    return params + [("professional_role", str(rid)) for rid in role_ids]


def with_page(params: Params, page: int) -> Params:
    return params + [("page", str(page))]
