"""Разбор SSR-состояния страницы выдачи поиска hh.ru.

Все пути к полям подтверждены на реальном ответе hh.ru (Тюмень,
area=95, experience=noExperience, only_with_salary=true,
employment_form=FULL, salary_mode=MONTH, search_period=30),
2026-10-07.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VacancyListing:
    """Один элемент выдачи поиска — используется для сбора пула ID
    и предварительной (дешёвой) фильтрации до похода на страницу вакансии."""

    vacancy_id: int
    name: str
    link: str
    company_id: int | None
    company_name: str | None
    area_id: int | None
    area_name: str | None
    salary_from: float | None
    salary_to: float | None
    currency: str | None
    gross: bool | None
    salary_mode: str | None
    employment_form: str | None
    work_experience: str | None
    professional_role_ids: list[int] = field(default_factory=list)
    accredited_it_employer: bool = False


@dataclass
class SearchPageResult:
    total_found: int
    education_counts: dict[str, int]
    vacancies: list[VacancyListing] = field(default_factory=list)


def get_total_found(state: dict[str, Any]) -> int:
    """searchCounts.value — общее число найденных вакансий по текущим фильтрам."""
    search_counts = state.get("searchCounts") or {}
    if "value" in search_counts:
        return int(search_counts["value"])
    # запасной путь, если searchCounts не пришёл
    return int(state.get("vacancySearchResult", {}).get("totalResults", 0))


def get_cluster_groups(state: dict[str, Any], cluster_name: str) -> dict[str, dict[str, Any]]:
    """Возвращает searchClusters.<cluster_name>.groups как есть (count/query/title/id)."""
    clusters = state.get("searchClusters") or {}
    cluster = clusters.get(cluster_name) or {}
    return cluster.get("groups") or {}


def get_education_counts(state: dict[str, Any]) -> dict[str, int]:
    """{'higher': N, 'special_secondary': N, 'not_required_or_not_specified': N}."""
    groups = get_cluster_groups(state, "education")
    return {gid: int(g.get("count", 0)) for gid, g in groups.items()}


def _flatten_professional_role_ids(raw: list[dict[str, Any]] | None) -> list[int]:
    """Разворачивает [{"professionalRoleId": [58]}] -> [58]."""
    if not raw:
        return []
    ids: list[int] = []
    for item in raw:
        ids.extend(item.get("professionalRoleId", []))
    return ids


def parse_vacancy_listing(raw: dict[str, Any]) -> VacancyListing:
    company = raw.get("company") or {}
    compensation = raw.get("compensation") or {}
    area = raw.get("area") or {}
    links = raw.get("links") or {}
    vacancy_id = int(raw["vacancyId"])
    return VacancyListing(
        vacancy_id=vacancy_id,
        name=raw.get("name", ""),
        link=links.get("desktop") or f"https://hh.ru/vacancy/{vacancy_id}",
        company_id=company.get("id"),
        company_name=company.get("visibleName") or company.get("name"),
        area_id=area.get("@id"),
        area_name=area.get("name"),
        salary_from=compensation.get("from"),
        salary_to=compensation.get("to"),
        currency=compensation.get("currencyCode"),
        gross=compensation.get("gross"),
        salary_mode=compensation.get("mode"),
        employment_form=raw.get("employmentForm"),
        work_experience=raw.get("workExperience"),
        professional_role_ids=_flatten_professional_role_ids(raw.get("professionalRoleIds")),
        accredited_it_employer=bool(company.get("accreditedITEmployer", False)),
    )


def parse_search_page(state: dict[str, Any]) -> SearchPageResult:
    vsr = state.get("vacancySearchResult") or {}
    raw_vacancies = vsr.get("vacancies") or []
    vacancies = [parse_vacancy_listing(v) for v in raw_vacancies]
    return SearchPageResult(
        total_found=get_total_found(state),
        education_counts=get_education_counts(state),
        vacancies=vacancies,
    )
