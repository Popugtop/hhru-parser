"""Разбор SSR-состояния страницы вакансии hh.ru.

Реальный путь к данным — state['vacancyView']['vacancyFull']['vacancy']
(подтверждено на реальном ответе 2026-10-07; отличается от плоского
vacancyView, который предполагался изначально). Внутри vacancyFull.vacancy
коды уже в "плоском" виде: workFormats, workScheduleByDays, workingHours,
civilLawContracts, professionalRoleIds — простые списки (не обёрнутые
в [{"xxxElement": [...]}], как в выдаче поиска).

Персональные данные (employerManager, contactInfo) умышленно НЕ читаются
и не попадают в VacancyDetail.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape as html_unescape
from typing import Any

MAX_DESCRIPTION_LENGTH = 30_000

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t ]+")
_LINE_BREAK_RE = re.compile(r"</(p|div|li|h[1-6])\s*>|<br\s*/?>", re.IGNORECASE)


def html_to_text(raw_html: str | None) -> str:
    """Переводит HTML описания вакансии в читаемый текст с переносами строк,
    обрезая до MAX_DESCRIPTION_LENGTH символов."""
    if not raw_html:
        return ""
    text = _LINE_BREAK_RE.sub("\n", raw_html)
    text = _TAG_RE.sub("", text)
    text = html_unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)[:MAX_DESCRIPTION_LENGTH]


@dataclass
class VacancyDetail:
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
    publication_date: str | None = None  # YYYY-MM-DD
    accept_labor_contract: bool = False
    civil_law_contracts: list[str] = field(default_factory=list)
    internship: bool = False
    work_formats: list[str] = field(default_factory=list)
    work_schedule_by_days: list[str] = field(default_factory=list)
    working_hours: list[str] = field(default_factory=list)
    description_text: str = ""


def parse_vacancy_detail(state: dict[str, Any]) -> VacancyDetail:
    vacancy_full = state["vacancyView"]["vacancyFull"]
    vac = vacancy_full["vacancy"]

    company = vac.get("company") or {}
    compensation = vac.get("compensation") or {}
    area = vac.get("area") or {}
    vacancy_id = int(vac["vacancyId"])

    publication_iso = vac.get("publicationTimeIso")
    publication_date = publication_iso[:10] if publication_iso else None

    return VacancyDetail(
        vacancy_id=vacancy_id,
        name=vac.get("name", ""),
        link=f"https://hh.ru/vacancy/{vacancy_id}",
        company_id=company.get("id"),
        company_name=company.get("visibleName") or company.get("name"),
        area_id=area.get("id"),
        area_name=area.get("name"),
        salary_from=compensation.get("from"),
        salary_to=compensation.get("to"),
        currency=compensation.get("currencyCode"),
        gross=compensation.get("gross"),
        salary_mode=compensation.get("mode"),
        employment_form=vac.get("employmentForm"),
        work_experience=vac.get("workExperience"),
        professional_role_ids=list(vac.get("professionalRoleIds") or []),
        accredited_it_employer=bool(company.get("accreditedITEmployer", False)),
        publication_date=publication_date,
        accept_labor_contract=bool(vac.get("acceptLaborContract", False)),
        civil_law_contracts=list(vac.get("civilLawContracts") or []),
        internship=bool(vac.get("internship", False)),
        work_formats=list(vac.get("workFormats") or []),
        work_schedule_by_days=list(vac.get("workScheduleByDays") or []),
        working_hours=list(vac.get("workingHours") or []),
        description_text=html_to_text(vac.get("description")),
    )
