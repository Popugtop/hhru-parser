"""Сборка финальной строки выборки v2 (изменение дизайна, запрос пользователя
от 2026-10-07): 2 группы по образованию («ВО требуется» / «ВО не требуется»)
вместо трёх, исходный фильтр образования — в отдельной колонке (сам по себе
может быть higher/special_secondary/not_required_or_not_specified), сфера —
по белому списку профролей (не по категории справочника), и автоматическая
пометка C-level ролей (п.4 правок пользователя).
"""
from __future__ import annotations

from dataclasses import dataclass

from hh_parser.codes import EDUCATION_FILTER
from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.roles import RoleDictionary
from hh_parser.rows import compute_net_salary_estimate
from hh_parser.sample_v2 import resolve_sphere
from hh_parser.sectors import classify_sector
from hh_parser.text_rules import (
    check_education_mismatch,
    classify_education_mention,
    has_dms_mention,
    has_training_mention,
)
from hh_parser.whitelist import SENIOR_ROLE_IDS

EDUCATION_GROUP_2_REQUIRED = "ВО требуется"
EDUCATION_GROUP_2_NOT_REQUIRED = "ВО не требуется"

SENIOR_ROLE_COMMENT = "C-level роль, несмотря на фильтр «без опыта» — проверить вручную"


@dataclass
class FinalRowV2:
    education_group_2: str
    education_group_filter: str
    education_group_filter_label: str
    vacancy_id: int
    link: str
    name: str
    employer: str | None
    employer_id: int | None
    sector: str
    profession_role: str
    role_category: str | None
    sphere: str | None
    it_accreditation: bool
    publication_date: str | None
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
    is_senior_role: bool
    verified_manually: str = ""
    comment: str = ""
    description: str = ""


def build_row_v2(
    detail: VacancyDetail,
    group_2_label: str,
    raw_education_filter: str,
    role_dict: RoleDictionary,
    sphere_map: dict[int, str],
) -> FinalRowV2:
    profession_role, role_category, _ = role_dict.describe_roles(detail.professional_role_ids)
    sphere = resolve_sphere(detail.professional_role_ids, sphere_map)
    education_in_text = classify_education_mention(detail.description_text)
    is_senior = any(role_id in SENIOR_ROLE_IDS for role_id in detail.professional_role_ids)

    return FinalRowV2(
        education_group_2=group_2_label,
        education_group_filter=raw_education_filter,
        education_group_filter_label=EDUCATION_FILTER.get(raw_education_filter, raw_education_filter),
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
        education_mismatch=check_education_mismatch(raw_education_filter, education_in_text),
        is_senior_role=is_senior,
        comment=SENIOR_ROLE_COMMENT if is_senior else "",
        description=detail.description_text,
    )
