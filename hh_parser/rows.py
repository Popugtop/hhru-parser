"""Сборка финальной строки выборки (раздел 6 задания) из VacancyDetail.

Перевод кодов/булевых значений в человекочитаемый вид делается на этапе
экспорта (excel_export.py / csv_export.py), здесь — только бизнес-логика
и обычные python-типы (bool/None/str/число).
"""
from __future__ import annotations

from dataclasses import dataclass

from hh_parser.codes import EDUCATION_FILTER
from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.roles import RoleDictionary
from hh_parser.sectors import classify_sector
from hh_parser.text_rules import (
    check_education_mismatch,
    classify_education_mention,
    has_dms_mention,
    has_training_mention,
)


@dataclass
class FinalRow:
    education_group_filter: str  # исходный id фильтра: higher/special_secondary/not_required_or_not_specified
    education_group: str  # человекочитаемо: Высшее/СПО/Не требуется или не указано
    vacancy_id: int
    link: str
    name: str
    employer: str | None
    employer_id: int | None
    sector: str
    profession_role: str
    role_category: str | None
    sphere: str
    it_accreditation: bool
    publication_date: str | None  # YYYY-MM-DD
    salary_from: float | None
    salary_to: float | None
    gross: bool | None
    salary_net_estimate: float | None
    labor_contract: bool
    civil_law_contract_options: list[str]
    internship: bool
    work_formats: list[str]
    schedule: list[str]
    hours: list[str]
    dms: bool
    training_mentorship: bool
    education_in_text: str
    education_mismatch: bool
    verified_manually: str = ""
    comment: str = ""
    description: str = ""


def compute_net_salary_estimate(
    salary_from: float | None, salary_to: float | None, gross: bool | None
) -> float | None:
    """Середина вилки (или одна граница, если другой нет); если gross — умножаем на 0.87."""
    if salary_from is not None and salary_to is not None:
        mid = (salary_from + salary_to) / 2
    elif salary_from is not None:
        mid = salary_from
    elif salary_to is not None:
        mid = salary_to
    else:
        return None
    if gross:
        mid *= 0.87
    return round(mid)


def build_row(detail: VacancyDetail, group_filter_id: str, role_dict: RoleDictionary) -> FinalRow:
    profession_role, role_category, sphere = role_dict.describe_roles(detail.professional_role_ids)
    education_in_text = classify_education_mention(detail.description_text)

    return FinalRow(
        education_group_filter=group_filter_id,
        education_group=EDUCATION_FILTER.get(group_filter_id, group_filter_id),
        vacancy_id=detail.vacancy_id,
        link=detail.link,
        name=detail.name,
        employer=detail.company_name,
        employer_id=detail.company_id,
        sector=classify_sector(detail.company_name),
        profession_role=profession_role,
        role_category=role_category,
        sphere=sphere,
        it_accreditation=detail.accredited_it_employer,
        publication_date=detail.publication_date,
        salary_from=detail.salary_from,
        salary_to=detail.salary_to,
        gross=detail.gross,
        salary_net_estimate=compute_net_salary_estimate(detail.salary_from, detail.salary_to, detail.gross),
        labor_contract=detail.accept_labor_contract,
        civil_law_contract_options=detail.civil_law_contracts,
        internship=detail.internship,
        work_formats=detail.work_formats,
        schedule=detail.work_schedule_by_days,
        hours=detail.working_hours,
        dms=has_dms_mention(detail.description_text),
        training_mentorship=has_training_mention(detail.description_text),
        education_in_text=education_in_text,
        education_mismatch=check_education_mismatch(group_filter_id, education_in_text),
        description=detail.description_text,
    )
