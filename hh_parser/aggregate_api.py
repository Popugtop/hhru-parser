"""Часть А через официальный API (запрос пользователя 2026-10-09): clusters=true
даёт те же счётчики по образованию, что searchClusters.education на сайте —
один запрос на строку (per_page=1, вакансии не читаем, только found/clusters).

Строки — те же, что в aggregate_v2.collect_sphere_counts_v2 (сферы белого
списка + «Итого специалистские» + контекстные категории + «Все вакансии»),
чтобы часть А была напрямую сравнима с website-версией (self-check в
cli_v3_api.py)."""
from __future__ import annotations

from hh_parser.aggregate import SphereCounts
from hh_parser.api_client import ApiFetcher
from hh_parser.api_filters import Params, base_params_api, with_clusters, with_professional_roles
from hh_parser.api_parse import get_education_cluster_counts, get_found
from hh_parser.roles import RoleDictionary
from hh_parser.whitelist import ALL_SPHERES, WhitelistEntry, role_ids_by_sphere

ALL_VACANCIES_LABEL = "Все вакансии"
TOTAL_SPECIALIST_LABEL = "Итого специалистские"
CONTEXT_CATEGORIES = ("Медицина, фармацевтика", "Наука, образование")


def _counts_for_params(fetcher: ApiFetcher, label: str, params: Params) -> SphereCounts:
    response = fetcher.search(with_clusters(params) + [("per_page", "1")])
    edu = get_education_cluster_counts(response)
    return SphereCounts(
        label=label,
        total_found=get_found(response),
        higher=edu.get("higher", 0),
        special_secondary=edu.get("special_secondary", 0),
        not_required_or_not_specified=edu.get("not_required_or_not_specified", 0),
    )


def collect_sphere_counts_api(
    fetcher: ApiFetcher,
    whitelist: list[WhitelistEntry],
    role_dict: RoleDictionary,
    area: int,
    period: int,
    with_salary_filters: bool,
) -> list[SphereCounts]:
    by_sphere = role_ids_by_sphere(whitelist)
    rows: list[SphereCounts] = []
    all_whitelist_ids: list[int] = []

    for sphere in ALL_SPHERES:
        role_ids = by_sphere[sphere]
        all_whitelist_ids.extend(role_ids)
        params = with_professional_roles(base_params_api(area, period, with_salary_filters), role_ids)
        rows.append(_counts_for_params(fetcher, sphere, params))

    params = with_professional_roles(base_params_api(area, period, with_salary_filters), all_whitelist_ids)
    rows.append(_counts_for_params(fetcher, TOTAL_SPECIALIST_LABEL, params))

    for category_name in CONTEXT_CATEGORIES:
        role_ids = role_dict.role_ids_for_category(category_name)
        params = with_professional_roles(base_params_api(area, period, with_salary_filters), role_ids)
        rows.append(_counts_for_params(fetcher, category_name, params))

    params = base_params_api(area, period, with_salary_filters)
    rows.append(_counts_for_params(fetcher, ALL_VACANCIES_LABEL, params))

    return rows
