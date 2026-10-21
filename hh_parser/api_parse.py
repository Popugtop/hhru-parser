"""Разбор ответов официального API api.hh.ru/vacancies (переход с SSR-парсинга
сайта на официальный API, запрос пользователя 2026-10-09).

Важная особенность API, подтверждённая живыми запросами 2026-10-09: id вакансии,
id работодателя и id профроли приходят СТРОКАМИ ("137024523", не 137024523),
а такие поля, как employment_form/experience/salary_range.mode — объектами
{"id": ..., "name": ...}, а не голыми кодами, как в SSR-выдаче сайта. Здесь всё
это приводится к тем же типам, что ожидает остальной пайплайн (VacancyDetail,
employer_counts: Counter[int], ...), поэтому rows_v2.build_row_v2 и далее не
отличают API-данные от старых SSR-данных.

contacts (контакты рекрутёра) сюда никогда не читаются — не нужны (раздел 7
задания) и уже вырезаны на уровне api_client.ApiFetcher.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from hh_parser.parse_vacancy import VacancyDetail, html_to_text


def get_found(response: dict[str, Any]) -> int:
    """found — общее число найденных вакансий (аналог searchCounts.value на сайте)."""
    return int(response.get("found", 0))


def get_vacancy_ids(response: dict[str, Any]) -> list[int]:
    return [int(item["id"]) for item in response.get("items", [])]


def get_education_cluster_counts(response: dict[str, Any]) -> dict[str, int]:
    """{'higher': N, 'special_secondary': N, 'not_required_or_not_specified': N}
    из clusters (нужен clusters=true в запросе). В отличие от сайта
    (searchClusters.education.groups — словарь с готовым id группы), в API
    clusters — список, а значение фильтра education лежит в query-строке
    поля url каждого элемента кластера, а не в отдельном ключе id."""
    clusters = response.get("clusters") or []
    edu_cluster = next((c for c in clusters if c.get("id") == "education"), None)
    if edu_cluster is None:
        return {}
    counts: dict[str, int] = {}
    for item in edu_cluster.get("items", []):
        qs = parse_qs(urlsplit(item.get("url", "")).query)
        values = qs.get("education")
        if not values:
            continue
        counts[values[0]] = int(item.get("count", 0))
    return counts


def _ids_list(raw: list[dict[str, Any]] | None) -> list[int]:
    if not raw:
        return []
    return [int(item["id"]) for item in raw if item.get("id") is not None]


def _code_list(raw: list[dict[str, Any]] | None) -> list[str]:
    """Для work_format/work_schedule_by_days/working_hours/civil_law_contracts
    API отдаёт [{"id": "ON_SITE", "name": "На месте работодателя"}, ...] — нас
    интересует только id (коды переводятся в читаемый вид на этапе экспорта,
    hh_parser.codes, как и для старых SSR-данных)."""
    if not raw:
        return []
    return [item["id"] for item in raw if item.get("id") is not None]


def parse_vacancy_detail_api(detail: dict[str, Any]) -> VacancyDetail:
    employer = detail.get("employer") or {}
    salary_range = detail.get("salary_range") or {}
    area = detail.get("area") or {}
    employment_form = detail.get("employment_form") or {}
    experience = detail.get("experience") or {}
    salary_mode = salary_range.get("mode") or {}

    vacancy_id = int(detail["id"])
    published_at = detail.get("published_at") or ""

    return VacancyDetail(
        vacancy_id=vacancy_id,
        name=detail.get("name", ""),
        link=detail.get("alternate_url") or f"https://hh.ru/vacancy/{vacancy_id}",
        company_id=int(employer["id"]) if employer.get("id") is not None else None,
        company_name=employer.get("name"),
        area_id=int(area["id"]) if area.get("id") is not None else None,
        area_name=area.get("name"),
        salary_from=salary_range.get("from"),
        salary_to=salary_range.get("to"),
        currency=salary_range.get("currency"),
        gross=salary_range.get("gross"),
        salary_mode=salary_mode.get("id"),
        employment_form=employment_form.get("id"),
        work_experience=experience.get("id"),
        professional_role_ids=_ids_list(detail.get("professional_roles")),
        accredited_it_employer=bool(employer.get("accredited_it_employer", False)),
        publication_date=published_at[:10] if published_at else None,
        accept_labor_contract=bool(detail.get("accept_labor_contract", False)),
        civil_law_contracts=_code_list(detail.get("civil_law_contracts")),
        internship=bool(detail.get("internship", False)),
        work_formats=_code_list(detail.get("work_format")),
        work_schedule_by_days=_code_list(detail.get("work_schedule_by_days")),
        working_hours=_code_list(detail.get("working_hours")),
        description_text=html_to_text(detail.get("description")),
    )
