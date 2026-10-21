"""Общие тестовые утилиты."""
import html
import json
from typing import Any


def wrap_state_as_html(state: dict[str, Any]) -> str:
    """Оборачивает dict в HTML с блоком HH-Lux-InitialState — как настоящая
    страница hh.ru, для сквозных тестов без реальных HTTP-запросов."""
    raw_json = json.dumps(state, ensure_ascii=False)
    escaped = html.escape(raw_json, quote=True)
    return (
        "<!doctype html><html><body>"
        f'<template style="display:none" id="HH-Lux-InitialState">{escaped}</template>'
        "</body></html>"
    )


def make_search_state(total_found: int, higher: int, special_secondary: int, not_required: int) -> dict:
    return {
        "searchCounts": {"value": total_found},
        "searchClusters": {
            "education": {
                "groups": {
                    "higher": {"count": higher, "title": "Высшее"},
                    "special_secondary": {"count": special_secondary, "title": "СПО"},
                    "not_required_or_not_specified": {
                        "count": not_required,
                        "title": "Не требуется или не указано",
                    },
                }
            }
        },
        "vacancySearchResult": {"totalResults": total_found, "vacancies": []},
    }


def make_listing(vacancy_id: int, company_id: int = 1, company_name: str = "ООО Компания") -> dict:
    """Минимальный элемент vacancySearchResult.vacancies[] (реальная форма полей)."""
    return {
        "vacancyId": vacancy_id,
        "name": f"Вакансия {vacancy_id}",
        "company": {"id": company_id, "visibleName": company_name},
        "compensation": {"from": 40000, "to": 60000, "currencyCode": "RUR", "gross": False, "mode": "MONTH"},
        "area": {"@id": 95, "name": "Тюмень"},
        "links": {"desktop": f"https://hh.ru/vacancy/{vacancy_id}"},
        "employmentForm": "FULL",
        "workExperience": "noExperience",
        "professionalRoleIds": [{"professionalRoleId": [96]}],
    }


def make_search_page_with_listings(total_found: int, listings: list[dict]) -> dict:
    return {
        "searchCounts": {"value": total_found},
        "searchClusters": {"education": {"groups": {}}},
        "vacancySearchResult": {"totalResults": total_found, "vacancies": listings},
    }


def make_vacancy_detail(
    vacancy_id: int,
    *,
    name: str = "Вакансия",
    company_id: int = 1,
    company_name: str = "ООО Компания",
    area_id: int = 95,
    area_name: str = "Тюмень",
    salary_from: float | None = 40000,
    salary_to: float | None = 60000,
    currency: str = "RUR",
    gross: bool = False,
    salary_mode: str = "MONTH",
    employment_form: str = "FULL",
    work_experience: str = "noExperience",
    description: str = "",
) -> dict:
    """Минимальная state['vacancyView']['vacancyFull']['vacancy'] (реальная форма полей)."""
    return {
        "vacancyView": {
            "vacancyFull": {
                "vacancy": {
                    "vacancyId": vacancy_id,
                    "name": name,
                    "description": description,
                    "company": {"id": company_id, "visibleName": company_name},
                    "area": {"id": area_id, "name": area_name},
                    "compensation": {
                        "from": salary_from,
                        "to": salary_to,
                        "currencyCode": currency,
                        "gross": gross,
                        "mode": salary_mode,
                    },
                    "employmentForm": employment_form,
                    "workExperience": work_experience,
                    "publicationTimeIso": "2026-10-01T10:00:00.000+03:00",
                    "acceptLaborContract": True,
                    "civilLawContracts": [],
                    "internship": False,
                    "workFormats": ["ON_SITE"],
                    "workScheduleByDays": ["FIVE_ON_TWO_OFF"],
                    "workingHours": ["HOURS_8"],
                    "professionalRoleIds": [96],
                }
            }
        }
    }
