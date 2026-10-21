from hh_parser.columns_v2 import COLUMNS
from hh_parser.format_values import row_to_display_dict
from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED, FinalRowV2


def make_row(**overrides) -> FinalRowV2:
    base = dict(
        education_group_2=EDUCATION_GROUP_2_REQUIRED,
        education_group_filter="higher",
        education_group_filter_label="Высшее",
        vacancy_id=1,
        link="https://hh.ru/vacancy/1",
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
        civil_law_contract_options=["SELF_EMPLOYED"],
        internship=False,
        work_formats=["HYBRID"],
        schedule=["FIVE_ON_TWO_OFF"],
        hours=["HOURS_8"],
        dms=True,
        training_mentorship=False,
        education_in_text="высшее",
        education_mismatch=False,
        is_senior_role=False,
    )
    base.update(overrides)
    return FinalRowV2(**base)


def test_columns_v2_covers_all_dataclass_fields_except_internal_raw_filter():
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(FinalRowV2)}
    column_keys = {spec.key for spec in COLUMNS}
    # education_group_filter — внутреннее raw-значение (higher/special_secondary/...),
    # пользователю показывается только его человекочитаемая метка
    # (education_group_filter_label); остальные поля должны быть колонками.
    assert field_names - column_keys == {"education_group_filter"}
    assert column_keys - field_names == set()


def test_row_to_display_dict_works_with_v2_columns():
    row = make_row()
    d = row_to_display_dict(row, columns=COLUMNS)
    assert d["Группа ВО"] == EDUCATION_GROUP_2_REQUIRED
    assert d["Исходный фильтр образования"] == "Высшее"
    assert d["C-level роль"] == "нет"
    assert d["Варианты ГПХ"] == "самозанятость"
    assert d["Формат работы"] == "гибрид"


def test_row_to_display_dict_v2_no_bool_or_none_leak():
    row = make_row(employer=None, is_senior_role=True)
    d = row_to_display_dict(row, columns=COLUMNS)
    assert d["C-level роль"] == "да"
    assert d["Работодатель"] == ""
    assert "None" not in str(d.values())
    assert "True" not in str(d.values())
    assert "False" not in str(d.values())


def test_sphere_none_becomes_empty_string():
    row = make_row(sphere=None, role_category=None)
    d = row_to_display_dict(row, columns=COLUMNS)
    assert d["Сфера (белый список)"] == ""
    assert d["Категория профроли (справочник)"] == ""
