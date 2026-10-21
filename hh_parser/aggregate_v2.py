"""Часть А v2 (изменение дизайна, запрос пользователя от 2026-10-07):
количества по сферам белого списка профролей, в двух вариантах фильтров:
(1) те же фильтры, что в части Б (включая only_with_salary/salary_mode);
(2) без фильтра по зарплате — вакансий больше, доли по образованию надёжнее.

Строки: каждая сфера белого списка, «Итого специалистские», для контекста
«Медицина, фармацевтика» и «Наука, образование» (не в белом списке —
только для сравнения), и «Все вакансии».
"""
from __future__ import annotations

from dataclasses import dataclass

from hh_parser.aggregate import SphereCounts, counts_from_state
from hh_parser.filters import base_params, with_professional_roles
from hh_parser.roles import RoleDictionary
from hh_parser.ssr import extract_initial_state
from hh_parser.whitelist import ALL_SPHERES, WhitelistEntry, role_ids_by_sphere

ALL_VACANCIES_LABEL = "Все вакансии"
TOTAL_SPECIALIST_LABEL = "Итого специалистские"
CONTEXT_CATEGORIES = ("Медицина, фармацевтика", "Наука, образование")


def collect_sphere_counts_v2(
    fetcher,
    whitelist: list[WhitelistEntry],
    role_dict: RoleDictionary,
    area: int,
    search_period: int,
    with_salary_filters: bool,
) -> list[SphereCounts]:
    by_sphere = role_ids_by_sphere(whitelist)
    rows: list[SphereCounts] = []

    all_whitelist_ids: list[int] = []
    for sphere in ALL_SPHERES:
        role_ids = by_sphere[sphere]
        all_whitelist_ids.extend(role_ids)
        params = with_professional_roles(base_params(area, search_period, with_salary_filters), role_ids)
        html, _ = fetcher.fetch_search_page(params)
        rows.append(counts_from_state(sphere, extract_initial_state(html)))

    params = with_professional_roles(base_params(area, search_period, with_salary_filters), all_whitelist_ids)
    html, _ = fetcher.fetch_search_page(params)
    rows.append(counts_from_state(TOTAL_SPECIALIST_LABEL, extract_initial_state(html)))

    for category_name in CONTEXT_CATEGORIES:
        role_ids = role_dict.role_ids_for_category(category_name)
        params = with_professional_roles(base_params(area, search_period, with_salary_filters), role_ids)
        html, _ = fetcher.fetch_search_page(params)
        rows.append(counts_from_state(category_name, extract_initial_state(html)))

    html, _ = fetcher.fetch_search_page(base_params(area, search_period, with_salary_filters))
    rows.append(counts_from_state(ALL_VACANCIES_LABEL, extract_initial_state(html)))

    return rows


MIN_VO_REQUIRED_TOTAL = 50


@dataclass
class VOComparisonRow:
    sphere: str
    vo_required: int  # education=higher — группа «ВО требуется»
    vo_not_required: int  # special_secondary + not_required_or_not_specified — «ВО не требуется»


def build_vo_comparison_table(sphere_rows: list[SphereCounts]) -> list[VOComparisonRow]:
    """Таблица «ВО требуется vs ВО не требуется» по сферам белого списка —
    строится из части А, вариант 1 (те же фильтры, что в части Б), чтобы не
    делать отдельных запросов. Контекстные/итоговые строки (Медицина, Наука,
    Итого специалистские, Все вакансии) не входят."""
    return [
        VOComparisonRow(
            sphere=row.label,
            vo_required=row.higher,
            vo_not_required=row.special_secondary + row.not_required_or_not_specified,
        )
        for row in sphere_rows
        if row.label in ALL_SPHERES
    ]


def total_vo_required(comparison: list[VOComparisonRow]) -> int:
    return sum(r.vo_required for r in comparison)


def total_vo_not_required(comparison: list[VOComparisonRow]) -> int:
    return sum(r.vo_not_required for r in comparison)
