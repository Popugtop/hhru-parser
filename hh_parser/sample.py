"""Часть Б: стратифицированная случайная выборка вакансий (разделы 4-5 задания).

Для каждой группы образования:
1) собираем пул ID через пагинацию выдачи поиска;
2) перемешиваем пул с фиксированным seed;
3) идём по перемешанному списку, открываем вакансию, применяем правила
   отбора (раздел 5), пока не наберём квоту или не кончится пул.
Дубли между группами (одна вакансия — одна группа) исключаются через
общий claimed_ids, передаваемый между вызовами select_group_sample.
"""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from hh_parser.fetch import BlockedError
from hh_parser.filters import base_params, with_education, with_page
from hh_parser.parse_search import parse_search_page
from hh_parser.parse_vacancy import VacancyDetail, parse_vacancy_detail
from hh_parser.ssr import extract_initial_state

MAX_PAGES = 40  # hh.ru отдаёт не больше ~2000 результатов (40 страниц * 50)
EMPLOYER_CAP = 3

REASON_BAD_SALARY = "Зарплата не в рублях или не за месяц"
REASON_PART_EMPLOYMENT = "Занятость не полная"
REASON_REQUIRES_EXPERIENCE = "Требуется опыт работы"
REASON_WRONG_AREA = "Город не Тюмень"
REASON_EMPLOYER_CAP = "Больше 3 вакансий этого работодателя в группе"
REASON_DUPLICATE_WITHIN_GROUP = "Дубль по работодателю и названию в группе"
REASON_DUPLICATE_ACROSS_GROUPS = "Дубль между группами образования"


class PageFetcher(Protocol):
    def fetch_search_page(self, params: list[tuple[str, str]]) -> tuple[str, bool]: ...
    def fetch_vacancy_page(self, vacancy_id: int) -> tuple[str, bool]: ...


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(name.strip().lower().split())


def collect_pool_generic(fetcher: PageFetcher, extra_params: list[tuple[str, str]]) -> list[int]:
    """Собирает ID всех вакансий по готовому набору параметров (area/фильтры
    уже внутри extra_params) — пагинация, вакансии не открываем. Используется
    и v1 (collect_pool ниже), и v2 (sample_v2.py) с разными наборами фильтров."""
    pool: list[int] = []
    seen: set[int] = set()
    total_found: int | None = None

    for page in range(MAX_PAGES):
        params = with_page(extra_params, page)
        html, _ = fetcher.fetch_search_page(params)
        result = parse_search_page(extract_initial_state(html))
        if total_found is None:
            total_found = result.total_found
        if not result.vacancies:
            break
        for listing in result.vacancies:
            if listing.vacancy_id not in seen:
                seen.add(listing.vacancy_id)
                pool.append(listing.vacancy_id)
        if len(pool) >= total_found or len(result.vacancies) < 50:
            break

    return pool


def collect_pool(
    fetcher: PageFetcher, group_filter_id: str, area: int, search_period: int
) -> list[int]:
    """Собирает ID всех вакансий по фильтру образования (вакансии не открываем)."""
    extra_params = with_education(base_params(area, search_period), group_filter_id)
    return collect_pool_generic(fetcher, extra_params)


def check_exclusion(
    detail: VacancyDetail,
    area_id: int,
    employer_counts: Counter[int],
    seen_keys: set[tuple[int | None, str]],
    employer_cap: int | None = EMPLOYER_CAP,
) -> str | None:
    """Возвращает причину исключения или None, если вакансия проходит все правила.
    Без побочных эффектов — учёт employer_counts/seen_keys делает вызывающий код
    после того, как вакансия принята. employer_cap=None отключает лимит
    работодателя (используется в v3 — сплошное обследование без квот)."""
    if (
        detail.currency != "RUR"
        or detail.salary_mode != "MONTH"
        or (detail.salary_from is None and detail.salary_to is None)
    ):
        return REASON_BAD_SALARY
    if detail.employment_form != "FULL":
        return REASON_PART_EMPLOYMENT
    if detail.work_experience != "noExperience":
        return REASON_REQUIRES_EXPERIENCE
    if detail.area_id != area_id:
        return REASON_WRONG_AREA
    if (
        employer_cap is not None
        and detail.company_id is not None
        and employer_counts[detail.company_id] >= employer_cap
    ):
        return REASON_EMPLOYER_CAP
    key = (detail.company_id, normalize_name(detail.name))
    if key in seen_keys:
        return REASON_DUPLICATE_WITHIN_GROUP
    return None


@dataclass
class SampleResult:
    group: str
    requested_quota: int
    pool_size: int
    collected: list[VacancyDetail] = field(default_factory=list)
    excluded_counts: Counter[str] = field(default_factory=Counter)
    blocked_reason: str | None = None

    @property
    def quota_met(self) -> bool:
        return len(self.collected) >= self.requested_quota


def select_group_sample(
    fetcher: PageFetcher,
    group_filter_id: str,
    quota: int,
    area: int,
    search_period: int,
    seed: int,
    claimed_ids: set[int],
) -> SampleResult:
    """Если hh.ru вернёт капчу/403/429 (BlockedError) в любой момент — не
    поднимаем исключение дальше, а возвращаем то, что успели собрать
    (result.blocked_reason укажет причину), чтобы вызывающий код мог
    сохранить прогресс и остановиться (раздел 7 задания)."""
    result = SampleResult(group=group_filter_id, requested_quota=quota, pool_size=0)

    try:
        pool = collect_pool(fetcher, group_filter_id, area, search_period)
    except BlockedError as exc:
        result.blocked_reason = str(exc)
        return result
    result.pool_size = len(pool)

    shuffled = pool[:]
    random.Random(seed).shuffle(shuffled)
    employer_counts: Counter[int] = Counter()
    seen_keys: set[tuple[int | None, str]] = set()

    for vacancy_id in shuffled:
        if len(result.collected) >= quota:
            break
        if vacancy_id in claimed_ids:
            result.excluded_counts[REASON_DUPLICATE_ACROSS_GROUPS] += 1
            continue

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

        claimed_ids.add(vacancy_id)
        employer_counts[detail.company_id] += 1
        seen_keys.add((detail.company_id, normalize_name(detail.name)))
        result.collected.append(detail)

    return result


def run_part_b(
    fetcher: PageFetcher,
    group_quotas: list[tuple[str, int]],
    area: int,
    search_period: int,
    seed: int,
) -> dict[str, SampleResult]:
    """Группы обрабатываются по очереди; если какая-то группа была прервана
    блокировкой (result.blocked_reason), последующие группы не начинаются —
    но всё собранное по уже обработанным группам возвращается как есть."""
    claimed_ids: set[int] = set()
    results: dict[str, SampleResult] = {}
    for group_filter_id, quota in group_quotas:
        result = select_group_sample(
            fetcher, group_filter_id, quota, area, search_period, seed, claimed_ids
        )
        results[group_filter_id] = result
        if result.blocked_reason is not None:
            break
    return results
