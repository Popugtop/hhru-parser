"""Часть А: агрегированные количества вакансий по сферам (раздел 4 задания).

Для каждой строки делаем один запрос поиска с базовыми фильтрами (+ набор
professional_role для категории) и читаем searchCounts.value и
searchClusters.education.groups — вакансии при этом не открываем.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hh_parser.filters import base_params, with_professional_roles
from hh_parser.parse_search import get_education_counts, get_total_found
from hh_parser.roles import PART_A_CATEGORY_NAMES, RoleDictionary
from hh_parser.ssr import extract_initial_state

ALL_VACANCIES_LABEL = "Все вакансии"


class SearchPageFetcher(Protocol):
    def fetch_search_page(self, params: list[tuple[str, str]]) -> tuple[str, bool]: ...


@dataclass
class SphereCounts:
    label: str
    total_found: int
    higher: int
    special_secondary: int
    not_required_or_not_specified: int

    @property
    def education_sum(self) -> int:
        return self.higher + self.special_secondary + self.not_required_or_not_specified

    @property
    def education_sum_diverges(self) -> bool:
        return self.education_sum != self.total_found

    @property
    def higher_share_pct(self) -> float | None:
        if self.total_found == 0:
            return None
        return round(100 * self.higher / self.total_found, 1)


def counts_from_state(label: str, state: dict) -> SphereCounts:
    edu = get_education_counts(state)
    return SphereCounts(
        label=label,
        total_found=get_total_found(state),
        higher=edu.get("higher", 0),
        special_secondary=edu.get("special_secondary", 0),
        not_required_or_not_specified=edu.get("not_required_or_not_specified", 0),
    )


def collect_sphere_counts(
    fetcher: SearchPageFetcher,
    role_dict: RoleDictionary,
    area: int,
    search_period: int,
    category_names: tuple[str, ...] = PART_A_CATEGORY_NAMES,
) -> list[SphereCounts]:
    rows: list[SphereCounts] = []

    html, _ = fetcher.fetch_search_page(base_params(area, search_period))
    rows.append(counts_from_state(ALL_VACANCIES_LABEL, extract_initial_state(html)))

    for category_name in category_names:
        role_ids = role_dict.role_ids_for_category(category_name)
        params = with_professional_roles(base_params(area, search_period), role_ids)
        html, _ = fetcher.fetch_search_page(params)
        rows.append(counts_from_state(category_name, extract_initial_state(html)))

    return rows
