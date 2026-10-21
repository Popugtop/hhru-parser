"""Часть Б v2 (изменение дизайна, запрос пользователя от 2026-10-07):

- «ВО требуется» (education=higher, все роли белого списка разом) —
  сплошной отбор (все подходящие вакансии), но не больше 100.
- «ВО не требуется» (education IN {special_secondary, not_required_or_not_specified})
  — случайный отбор (seed), с ТЕМ ЖЕ составом по сферам, что получился в
  «ВО требуется» после отсева (не до!): для каждой сферы отдельный пул +
  отдельное перемешивание, но лимит работодателя и дубли по
  работодателю+названию общие на всю группу «ВО не требуется» (не по сферам).

Дубли между группами (одна вакансия — одна группа) исключаются через общий
claimed_ids, как в v1 — группа «ВО требуется» обрабатывается первой.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from hh_parser.fetch import BlockedError
from hh_parser.filters import base_params, with_education, with_professional_roles
from hh_parser.parse_vacancy import VacancyDetail, parse_vacancy_detail
from hh_parser.sample import (
    REASON_DUPLICATE_ACROSS_GROUPS,
    PageFetcher,
    check_exclusion,
    collect_pool_generic,
    normalize_name,
)
from hh_parser.ssr import extract_initial_state
from hh_parser.whitelist import ALL_SPHERES

REASON_SPHERE_NOT_RESOLVED = "Сфера не определена (нет в белом списке)"

GROUP_VO_REQUIRED = "vo_required"
GROUP_VO_NOT_REQUIRED = "vo_not_required"

VO_NOT_REQUIRED_EDUCATION_VALUES = ["special_secondary", "not_required_or_not_specified"]


def resolve_sphere(professional_role_ids: list[int], sphere_map: dict[int, str]) -> str | None:
    """Сфера вакансии — по первой её профроли, которая есть в белом списке."""
    for role_id in professional_role_ids:
        sphere = sphere_map.get(role_id)
        if sphere is not None:
            return sphere
    return None


@dataclass
class MatchedSampleResult:
    group_label: str
    collected: list[VacancyDetail] = field(default_factory=list)
    sphere_by_vacancy_id: dict[int, str] = field(default_factory=dict)
    pool_size_by_sphere: dict[str, int] = field(default_factory=dict)
    target_by_sphere: dict[str, int] = field(default_factory=dict)
    shortfall_by_sphere: dict[str, int] = field(default_factory=dict)
    excluded_counts: Counter[str] = field(default_factory=Counter)
    raw_filter_by_vacancy_id: dict[int, str] = field(default_factory=dict)
    blocked_reason: str | None = None

    def sphere_counts(self) -> Counter[str]:
        return Counter(self.sphere_by_vacancy_id.values())


def collect_exhaustive_group(
    fetcher: PageFetcher,
    whitelist_role_ids: list[int],
    sphere_map: dict[int, str],
    area: int,
    search_period: int,
    seed: int,
    cap: int,
    claimed_ids: set[int],
    employer_cap: int = 3,
) -> MatchedSampleResult:
    result = MatchedSampleResult(group_label=GROUP_VO_REQUIRED)

    extra_params = with_professional_roles(
        with_education(base_params(area, search_period), "higher"), whitelist_role_ids
    )
    try:
        pool = collect_pool_generic(fetcher, extra_params)
    except BlockedError as exc:
        result.blocked_reason = str(exc)
        return result

    shuffled = pool[:]
    random.Random(seed).shuffle(shuffled)

    employer_counts: Counter[int] = Counter()
    seen_keys: set[tuple[int | None, str]] = set()

    for vacancy_id in shuffled:
        if len(result.collected) >= cap:
            break
        try:
            html, _ = fetcher.fetch_vacancy_page(vacancy_id)
        except BlockedError as exc:
            result.blocked_reason = str(exc)
            break
        detail = parse_vacancy_detail(extract_initial_state(html))

        reason = check_exclusion(detail, area, employer_counts, seen_keys)
        if reason is not None:
            result.excluded_counts[reason] += 1
            continue

        sphere = resolve_sphere(detail.professional_role_ids, sphere_map)
        if sphere is None:
            result.excluded_counts[REASON_SPHERE_NOT_RESOLVED] += 1
            continue

        claimed_ids.add(vacancy_id)
        employer_counts[detail.company_id] += 1
        seen_keys.add((detail.company_id, normalize_name(detail.name)))
        result.collected.append(detail)
        result.sphere_by_vacancy_id[vacancy_id] = sphere

    return result


def collect_matched_group(
    fetcher: PageFetcher,
    role_ids_by_sphere: dict[str, list[int]],
    target_by_sphere: dict[str, int],
    sphere_map: dict[int, str],
    area: int,
    search_period: int,
    seed: int,
    claimed_ids: set[int],
    employer_cap: int = 3,
) -> MatchedSampleResult:
    result = MatchedSampleResult(group_label=GROUP_VO_NOT_REQUIRED, target_by_sphere=dict(target_by_sphere))

    employer_counts: Counter[int] = Counter()
    seen_keys: set[tuple[int | None, str]] = set()

    for sphere in ALL_SPHERES:
        target = target_by_sphere.get(sphere, 0)
        if target <= 0:
            continue
        role_ids = role_ids_by_sphere.get(sphere, [])
        if not role_ids:
            continue

        # Страница вакансии не содержит поля "education" — нельзя узнать
        # исходный фильтр по самой вакансии. Поэтому опрашиваем оба значения
        # РАЗДЕЛЬНО (не одним OR-запросом) и запоминаем, из какого пула
        # пришёл каждый ID, чтобы сохранить исходное значение в колонке.
        pool: list[int] = []
        seen_in_pool: set[int] = set()
        raw_filter_by_id: dict[int, str] = {}
        for raw_value in VO_NOT_REQUIRED_EDUCATION_VALUES:
            extra_params = with_professional_roles(
                with_education(base_params(area, search_period), raw_value), role_ids
            )
            try:
                sub_pool = collect_pool_generic(fetcher, extra_params)
            except BlockedError as exc:
                result.blocked_reason = str(exc)
                return result
            for vacancy_id in sub_pool:
                if vacancy_id not in seen_in_pool:
                    seen_in_pool.add(vacancy_id)
                    pool.append(vacancy_id)
                    raw_filter_by_id[vacancy_id] = raw_value
        result.pool_size_by_sphere[sphere] = len(pool)

        shuffled = pool[:]
        random.Random(seed).shuffle(shuffled)

        accepted_for_sphere = 0
        for vacancy_id in shuffled:
            if accepted_for_sphere >= target:
                break
            if vacancy_id in claimed_ids:
                result.excluded_counts[REASON_DUPLICATE_ACROSS_GROUPS] += 1
                continue
            try:
                html, _ = fetcher.fetch_vacancy_page(vacancy_id)
            except BlockedError as exc:
                result.blocked_reason = str(exc)
                return result
            detail = parse_vacancy_detail(extract_initial_state(html))

            reason = check_exclusion(detail, area, employer_counts, seen_keys)
            if reason is not None:
                result.excluded_counts[reason] += 1
                continue

            claimed_ids.add(vacancy_id)
            employer_counts[detail.company_id] += 1
            seen_keys.add((detail.company_id, normalize_name(detail.name)))
            result.collected.append(detail)
            result.sphere_by_vacancy_id[vacancy_id] = sphere
            result.raw_filter_by_vacancy_id[vacancy_id] = raw_filter_by_id[vacancy_id]
            accepted_for_sphere += 1

        shortfall = target - accepted_for_sphere
        if shortfall > 0:
            result.shortfall_by_sphere[sphere] = shortfall

    return result
