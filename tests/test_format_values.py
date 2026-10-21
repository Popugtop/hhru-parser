from hh_parser.format_values import row_to_display_dict
from hh_parser.rows import FinalRow


def make_row(**overrides) -> FinalRow:
    base = dict(
        education_group_filter="higher",
        education_group="Высшее",
        vacancy_id=123,
        link="https://hh.ru/vacancy/123",
        name="Программист",
        employer="ООО Компания",
        employer_id=10,
        sector="коммерческий",
        profession_role="Программист, разработчик",
        role_category="Информационные технологии",
        sphere="IT",
        it_accreditation=True,
        publication_date="2026-10-01",
        salary_from=80000,
        salary_to=120000,
        gross=False,
        salary_net_estimate=100000,
        labor_contract=True,
        civil_law_contract_options=["SELF_EMPLOYED", "INDIVIDUAL_ENTREPRENEUR"],
        internship=False,
        work_formats=["HYBRID"],
        schedule=["FIVE_ON_TWO_OFF"],
        hours=["HOURS_8"],
        dms=True,
        training_mentorship=False,
        education_in_text="высшее",
        education_mismatch=False,
        verified_manually="",
        comment="",
        description="Текст описания",
    )
    base.update(overrides)
    return FinalRow(**base)


def test_bool_fields_rendered_as_yes_no_words():
    row = make_row()
    d = row_to_display_dict(row)
    assert d["Аккредитация ИТ-компании"] == "да"
    assert d["Стажировка"] == "нет"
    assert "True" not in str(d.values())
    assert "False" not in str(d.values())


def test_none_values_become_empty_string_not_none_or_nan():
    row = make_row(employer=None, salary_to=None, gross=None, role_category=None)
    d = row_to_display_dict(row)
    assert d["Работодатель"] == ""
    assert d["Зарплата до, руб."] == ""
    assert d["Зарплата до вычета налогов (gross)"] == ""
    assert d["Категория профроли"] == ""
    assert "None" not in str(d.values())
    assert "nan" not in str(d.values()).lower()


def test_empty_list_becomes_empty_string_not_brackets():
    row = make_row(civil_law_contract_options=[], work_formats=[])
    d = row_to_display_dict(row)
    assert d["Варианты ГПХ"] == ""
    assert d["Формат работы"] == ""
    assert "[" not in d["Варианты ГПХ"]


def test_codes_are_translated_to_russian():
    row = make_row()
    d = row_to_display_dict(row)
    assert d["Варианты ГПХ"] == "самозанятость, ИП"
    assert d["Формат работы"] == "гибрид"
    assert d["График"] == "5/2"
    assert d["Часы"] == "8 часов"
    assert "SELF_EMPLOYED" not in d["Варианты ГПХ"]
    assert "HYBRID" not in d["Формат работы"]


def test_date_format_is_ddmmyyyy():
    row = make_row(publication_date="2026-10-01")
    d = row_to_display_dict(row)
    assert d["Дата публикации"] == "01.10.2026"


def test_numbers_stay_as_numbers_not_strings():
    row = make_row()
    d = row_to_display_dict(row)
    assert isinstance(d["Зарплата от, руб."], int)
    assert isinstance(d["ID вакансии"], int)


def test_empty_manual_fields_are_empty_strings():
    row = make_row()
    d = row_to_display_dict(row)
    assert d["Проверено вручную"] == ""
    assert d["Комментарий"] == ""
