"""Часть Б через официальный API (запрос пользователя 2026-10-09).

Сбор — в два этапа, как и везде в проекте: сначала пагинация /vacancies для
сбора ID пула (вакансии не открываем), затем /vacancies/{id} для деталей.
Глубина пагинации у API тоже ограничена: "глубина возвращаемых результатов не
может быть больше 2000" (api.hh.ru/openapi/specification/public) — тот же
порядок величины, что и на сайте, поэтому MAX_PAGES*PER_PAGE = 2000.

Раздельные запросы по каждому из трёх значений education — та же причина, что
в sample_v2/sample_v3 (vacancies/{id} не содержит поля "education", нельзя
узнать исходный фильтр по самой вакансии); порядок приоритета при пересечении
пулов: higher > special_secondary > not_required_or_not_specified.

compute_matched_subsample реализует ту же методологию подбора, что
sample_v2.collect_exhaustive_group + collect_matched_group (все «ВО требуется»
после лимита 3 на работодателя целиком + «ВО не требуется» случайно, seed, с
тем же составом по сферам) — но на уже собранных данных (без повторных
запросов), поскольку в v3-api сбор сплошной и дальше только переразмечается.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

from hh_parser.api_client import ApiFetcher
from hh_parser.api_filters import Params, base_params_api, with_education, with_page, with_professional_roles
from hh_parser.api_parse import get_found, get_vacancy_ids, parse_vacancy_detail_api
from hh_parser.fetch import BlockedError
from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.sample import check_exclusion, normalize_name

MAX_PAGES = 20  # per_page=100 * 20 = 2000 — тот же потолок глубины, что у сайта
PER_PAGE = 100

EDUCATION_VALUES_PRIORITY = ["higher", "special_secondary", "not_required_or_not_specified"]

REASON_EMPLOYER_CAP = "Больше 3 вакансий этого работодателя в группе"
REASON_DUPLICATE_WITHIN_GROUP = "Дубль по работодателю и названию в группе"


def collect_pool_api(fetcher: ApiFetcher, params: Params) -> list[int]:
    pool: list[int] = []
    seen: set[int] = set()
    found: int | None = None
    for page in range(MAX_PAGES):
        response = fetcher.search(with_page(params, page, PER_PAGE))
        if found is None:
            found = get_found(response)
        ids = get_vacancy_ids(response)
        if not ids:
            break
        for vacancy_id in ids:
            if vacancy_id not in seen:
                seen.add(vacancy_id)
                pool.append(vacancy_id)
        if len(pool) >= found or len(ids) < PER_PAGE:
            break
    return pool


@dataclass
class ExhaustiveApiResult:
    collected: list[VacancyDetail] = field(default_factory=list)
    raw_filter_by_vacancy_id: dict[int, str] = field(default_factory=dict)
    pool_size_by_raw_filter: dict[str, int] = field(default_factory=dict)
    excluded_counts: Counter[str] = field(default_factory=Counter)
    blocked_reason: str | None = None


def collect_exhaustive_all_education_api(
    fetcher: ApiFetcher,
    whitelist_role_ids: list[int],
    area: int,
    period: int,
) -> ExhaustiveApiResult:
    """Собирает ВСЕ вакансии белого списка по трём значениям education, без
    лимита на работодателя (сплошное обследование, как sample_v3.py, но через
    официальный API)."""
    result = ExhaustiveApiResult()

    pool: list[int] = []
    seen_in_pool: set[int] = set()
    raw_filter_by_id: dict[int, str] = {}
    for raw_value in EDUCATION_VALUES_PRIORITY:
        params = with_professional_roles(
            with_education(base_params_api(area, period), raw_value), whitelist_role_ids
        )
        try:
            sub_pool = collect_pool_api(fetcher, params)
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
            detail_json = fetcher.get_vacancy(vacancy_id)
        except BlockedError as exc:
            result.blocked_reason = str(exc)
            return result
        detail = parse_vacancy_detail_api(detail_json)

        reason = check_exclusion(detail, area, employer_counts, seen_keys, employer_cap=None)
        if reason is not None:
            result.excluded_counts[reason] += 1
            continue

        employer_counts[detail.company_id] += 1
        seen_keys.add((detail.company_id, normalize_name(detail.name)))
        result.collected.append(detail)
        result.raw_filter_by_vacancy_id[vacancy_id] = raw_filter_by_id[vacancy_id]

    return result


@dataclass
class MatchedSubsampleResult:
    in_subsample_ids: set[int] = field(default_factory=set)
    target_by_sphere: dict[str, int] = field(default_factory=dict)
    shortfall_by_sphere: dict[str, int] = field(default_factory=dict)
    required_excluded_counts: Counter[str] = field(default_factory=Counter)
    not_required_excluded_counts: Counter[str] = field(default_factory=Counter)


def _resolve_sphere(detail: VacancyDetail, sphere_map: dict[int, str]) -> str | None:
    for role_id in detail.professional_role_ids:
        sphere = sphere_map.get(role_id)
        if sphere is not None:
            return sphere
    return None


def compute_matched_subsample(
    collected: list[VacancyDetail],
    raw_filter_by_vacancy_id: dict[int, str],
    sphere_map: dict[int, str],
    seed: int,
    employer_cap: int | None = 3,
) -> MatchedSubsampleResult:
    """Повторяет методологию v2 (sample_v2.collect_exhaustive_group +
    collect_matched_group) на уже собранных данных, без повторных запросов:

    1) «ВО требуется» (raw_filter == "higher") — перемешать (seed), принять
       все, что проходят лимит 3 на работодателя и дубли по
       работодателю+названию (без квоты сверху — «все», как попросил
       пользователь);
    2) цель по сферам для «ВО не требуется» = фактический состав по сферам
       группы 1 после отбора;
    3) «ВО не требуется» — для каждой сферы отдельный пул, перемешать (seed),
       принимать пока не наберётся цель или пул не кончится; лимит
       работодателя и дубли общие на всю группу (не по сферам), как в v2.
    """
    result = MatchedSubsampleResult()

    required = [d for d in collected if raw_filter_by_vacancy_id.get(d.vacancy_id) == "higher"]
    not_required = [d for d in collected if raw_filter_by_vacancy_id.get(d.vacancy_id) != "higher"]

    shuffled_required = required[:]
    random.Random(seed).shuffle(shuffled_required)

    employer_counts: Counter[int] = Counter()
    seen_keys: set[tuple[int | None, str]] = set()
    accepted_required: list[VacancyDetail] = []
    for detail in shuffled_required:
        if (
            employer_cap is not None
            and detail.company_id is not None
            and employer_counts[detail.company_id] >= employer_cap
        ):
            result.required_excluded_counts[REASON_EMPLOYER_CAP] += 1
            continue
        key = (detail.company_id, normalize_name(detail.name))
        if key in seen_keys:
            result.required_excluded_counts[REASON_DUPLICATE_WITHIN_GROUP] += 1
            continue
        employer_counts[detail.company_id] += 1
        seen_keys.add(key)
        accepted_required.append(detail)
        result.in_subsample_ids.add(detail.vacancy_id)

    target_by_sphere: Counter[str] = Counter()
    for detail in accepted_required:
        sphere = _resolve_sphere(detail, sphere_map)
        if sphere is not None:
            target_by_sphere[sphere] += 1
    result.target_by_sphere = dict(target_by_sphere)

    pool_by_sphere: dict[str, list[VacancyDetail]] = {}
    for detail in not_required:
        sphere = _resolve_sphere(detail, sphere_map)
        if sphere is None:
            continue
        pool_by_sphere.setdefault(sphere, []).append(detail)

    employer_counts_nr: Counter[int] = Counter()
    seen_keys_nr: set[tuple[int | None, str]] = set()
    for sphere, target in target_by_sphere.items():
        pool = pool_by_sphere.get(sphere, [])
        shuffled = pool[:]
        random.Random(seed).shuffle(shuffled)

        accepted = 0
        for detail in shuffled:
            if accepted >= target:
                break
            if (
                employer_cap is not None
                and detail.company_id is not None
                and employer_counts_nr[detail.company_id] >= employer_cap
            ):
                result.not_required_excluded_counts[REASON_EMPLOYER_CAP] += 1
                continue
            key = (detail.company_id, normalize_name(detail.name))
            if key in seen_keys_nr:
                result.not_required_excluded_counts[REASON_DUPLICATE_WITHIN_GROUP] += 1
                continue
            employer_counts_nr[detail.company_id] += 1
            seen_keys_nr.add(key)
            result.in_subsample_ids.add(detail.vacancy_id)
            accepted += 1

        if accepted < target:
            result.shortfall_by_sphere[sphere] = target - accepted

    return result
