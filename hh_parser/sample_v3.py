"""Часть Б v3 (сплошное обследование, запрос пользователя от 2026-10-07):
ВСЕ вакансии белого списка под фильтрами части Б (без опыта, с зарплатой за
месяц, полная занятость, Тюмень, 30 дней) — без квот и без лимита «не более
3 на работодателя» (он явно отключён: employer_cap=None).

Раздельные запросы по каждому из трёх значений education (та же причина,
что в sample_v2.py: страница вакансии не содержит поля "education") —
приоритет при пересечении пулов: higher > special_secondary >
not_required_or_not_specified (тот же порядок, что и везде в проекте).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from hh_parser.fetch import BlockedError
from hh_parser.filters import base_params, with_education, with_professional_roles
from hh_parser.parse_vacancy import VacancyDetail, parse_vacancy_detail
from hh_parser.sample import PageFetcher, check_exclusion, collect_pool_generic, normalize_name
from hh_parser.ssr import extract_initial_state

EDUCATION_VALUES_PRIORITY = ["higher", "special_secondary", "not_required_or_not_specified"]


@dataclass
class ExhaustiveAllEducationResult:
    collected: list[VacancyDetail] = field(default_factory=list)
    raw_filter_by_vacancy_id: dict[int, str] = field(default_factory=dict)
    pool_size_by_raw_filter: dict[str, int] = field(default_factory=dict)
    excluded_counts: Counter[str] = field(default_factory=Counter)
    blocked_reason: str | None = None


def collect_exhaustive_all_education(
    fetcher: PageFetcher,
    whitelist_role_ids: list[int],
    area: int,
    search_period: int,
) -> ExhaustiveAllEducationResult:
    result = ExhaustiveAllEducationResult()

    pool: list[int] = []
    seen_in_pool: set[int] = set()
    raw_filter_by_id: dict[int, str] = {}
    for raw_value in EDUCATION_VALUES_PRIORITY:
        extra_params = with_professional_roles(
            with_education(base_params(area, search_period), raw_value), whitelist_role_ids
        )
        try:
            sub_pool = collect_pool_generic(fetcher, extra_params)
        except BlockedError as exc:
            result.blocked_reason = str(exc)
            return result
        result.pool_size_by_raw_filter[raw_value] = len(sub_pool)
        for vacancy_id in sub_pool:
            if vacancy_id not in seen_in_pool:
                seen_in_pool.add(vacancy_id)
                pool.append(vacancy_id)
                raw_filter_by_id[vacancy_id] = raw_value

    employer_counts: Counter[int] = Counter()
    seen_keys: set[tuple[int | None, str]] = set()

    for vacancy_id in pool:
        try:
            html, _ = fetcher.fetch_vacancy_page(vacancy_id)
        except BlockedError as exc:
            result.blocked_reason = str(exc)
            return result
        detail = parse_vacancy_detail(extract_initial_state(html))

        reason = check_exclusion(detail, area, employer_counts, seen_keys, employer_cap=None)
        if reason is not None:
            result.excluded_counts[reason] += 1
            continue

        employer_counts[detail.company_id] += 1
        seen_keys.add((detail.company_id, normalize_name(detail.name)))
        result.collected.append(detail)
        result.raw_filter_by_vacancy_id[vacancy_id] = raw_filter_by_id[vacancy_id]

    return result
