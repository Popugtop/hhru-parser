"""Описание колонок листа «Выборка» v2 — аналог columns.py, адаптированный
под 2-группную схему (ВО требуется/не требуется), исходный фильтр в отдельной
колонке и сферы по белому списку. Источник правды для порядка колонок в
Excel/CSV и для листа «Словарь колонок»."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hh_parser.codes import CIVIL_LAW_CONTRACTS, WORK_FORMAT, WORK_SCHEDULE_BY_DAYS, WORKING_HOURS
from hh_parser.rows_v2 import FinalRowV2


@dataclass
class ColumnSpec:
    key: str
    header: str
    kind: str
    getter: Callable[[FinalRowV2], Any]
    source: str
    mapping: dict[str, str] | None = None


COLUMNS: list[ColumnSpec] = [
    ColumnSpec(
        "education_group_2", "Группа ВО", "text",
        lambda r: r.education_group_2,
        "«ВО требуется» — education=higher; «ВО не требуется» — education IN (special_secondary, not_required_or_not_specified)",
    ),
    ColumnSpec(
        "education_group_filter_label", "Исходный фильтр образования", "text",
        lambda r: r.education_group_filter_label,
        "Какое именно из трёх значений education (higher/special_secondary/not_required_or_not_specified) у вакансии",
    ),
    ColumnSpec(
        "name", "Название", "text",
        lambda r: r.name,
        "vacancyView.vacancyFull.vacancy.name на странице вакансии hh.ru",
    ),
    ColumnSpec(
        "link", "Ссылка", "link",
        lambda r: r.link,
        "Собрана из id вакансии: https://hh.ru/vacancy/<id>",
    ),
    ColumnSpec(
        "employer", "Работодатель", "text",
        lambda r: r.employer,
        "vacancy.company.visibleName (или company.name) на странице вакансии",
    ),
    ColumnSpec(
        "employer_id", "ID работодателя", "int",
        lambda r: r.employer_id,
        "vacancy.company.id на странице вакансии",
    ),
    ColumnSpec(
        "it_accreditation", "Аккредитация ИТ-компании", "bool_yn",
        lambda r: r.it_accreditation,
        "vacancy.company.accreditedITEmployer на странице вакансии",
    ),
    ColumnSpec(
        "profession_role", "Профроль", "text",
        lambda r: r.profession_role,
        "vacancy.professionalRoleIds, имена ролей из справочника api.hh.ru/professional_roles",
    ),
    ColumnSpec(
        "role_category", "Категория профроли (справочник)", "text",
        lambda r: r.role_category,
        "Категория первой профроли вакансии в справочнике api.hh.ru/professional_roles (информационно)",
    ),
    ColumnSpec(
        "sphere", "Сфера (белый список)", "text",
        lambda r: r.sphere,
        "IT/Право/Экономика и финансы/Управление и офис/Инженеры/Продажи (офисные) — по белому списку ролей, output/roles_whitelist.csv",
    ),
    ColumnSpec(
        "sector", "Сектор работодателя", "text",
        lambda r: r.sector,
        "«Бюджетный», если в названии работодателя есть признаки госучреждения (МАОУ/ГБУЗ/администрация/министерство и т.п.), иначе «коммерческий»",
    ),
    ColumnSpec(
        "salary_from", "Зарплата от, руб.", "money",
        lambda r: r.salary_from,
        "vacancy.compensation.from на странице вакансии",
    ),
    ColumnSpec(
        "salary_to", "Зарплата до, руб.", "money",
        lambda r: r.salary_to,
        "vacancy.compensation.to на странице вакансии",
    ),
    ColumnSpec(
        "gross", "Зарплата до вычета налогов (gross)", "bool_yn",
        lambda r: r.gross,
        "vacancy.compensation.gross на странице вакансии",
    ),
    ColumnSpec(
        "salary_net_estimate", "Зарплата на руки, расчётная, руб.", "money",
        lambda r: r.salary_net_estimate,
        "Середина вилки «от-до» (или одна граница, если другой нет); если gross=да — умножено на 0.87",
    ),
    ColumnSpec(
        "labor_contract", "Оформление по ТК РФ", "bool_yn",
        lambda r: r.labor_contract,
        "vacancy.acceptLaborContract на странице вакансии",
    ),
    ColumnSpec(
        "civil_law_contract_options", "Варианты ГПХ", "list",
        lambda r: r.civil_law_contract_options,
        "vacancy.civilLawContracts на странице вакансии (самозанятость/ИП/физлицо)",
        CIVIL_LAW_CONTRACTS,
    ),
    ColumnSpec(
        "internship", "Стажировка", "bool_yn",
        lambda r: r.internship,
        "vacancy.internship на странице вакансии",
    ),
    ColumnSpec(
        "work_formats", "Формат работы", "list",
        lambda r: r.work_formats,
        "vacancy.workFormats на странице вакансии",
        WORK_FORMAT,
    ),
    ColumnSpec(
        "schedule", "График", "list",
        lambda r: r.schedule,
        "vacancy.workScheduleByDays на странице вакансии",
        WORK_SCHEDULE_BY_DAYS,
    ),
    ColumnSpec(
        "hours", "Часы", "list",
        lambda r: r.hours,
        "vacancy.workingHours на странице вакансии",
        WORKING_HOURS,
    ),
    ColumnSpec(
        "dms", "ДМС", "bool_yn",
        lambda r: r.dms,
        "Разбор текста описания: упоминание «ДМС» / «добровольное медицинское страхование»",
    ),
    ColumnSpec(
        "training_mentorship", "Обучение / наставничество", "bool_yn",
        lambda r: r.training_mentorship,
        "Разбор текста описания: упоминание обучения, наставника, тренингов и т.п.",
    ),
    ColumnSpec(
        "education_in_text", "Образование в тексте", "text",
        lambda r: r.education_in_text,
        "Разбор текста описания: высшее / высшее желательно / СПО / не требуется / не указано",
    ),
    ColumnSpec(
        "publication_date", "Дата публикации", "date",
        lambda r: r.publication_date,
        "vacancy.publicationTimeIso на странице вакансии",
    ),
    ColumnSpec(
        "vacancy_id", "ID вакансии", "int",
        lambda r: r.vacancy_id,
        "vacancy.vacancyId на странице вакансии",
    ),
    ColumnSpec(
        "education_mismatch", "Расхождение образования", "bool_yn",
        lambda r: r.education_mismatch,
        "«Да», если исходный фильтр образования явно противоречит тексту описания",
    ),
    ColumnSpec(
        "is_senior_role", "C-level роль", "bool_yn",
        lambda r: r.is_senior_role,
        "«Да», если профроль вакансии — директорская (CIO/CMO/HRD/CTO/CFO/CLO), несмотря на фильтр «без опыта»",
    ),
    ColumnSpec(
        "verified_manually", "Проверено вручную", "empty_text",
        lambda r: r.verified_manually,
        "Заполняется вручную при проверке строк с расхождением образования или C-level ролью",
    ),
    ColumnSpec(
        "comment", "Комментарий", "empty_text",
        lambda r: r.comment,
        "Автоматически заполняется для C-level ролей (см. колонку «C-level роль»); иначе — для ручного заполнения",
    ),
    ColumnSpec(
        "description", "Описание", "text",
        lambda r: r.description,
        "vacancy.description на странице вакансии (HTML переведён в текст, обрезано до 30 000 символов)",
    ),
]
