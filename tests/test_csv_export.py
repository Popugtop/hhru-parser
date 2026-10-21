import pandas as pd

from hh_parser.aggregate import SphereCounts
from hh_parser.csv_export import export_counts_by_sphere_csv, export_vacancies_csv
from hh_parser.rows import FinalRow


def make_row(**overrides) -> FinalRow:
    base = dict(
        education_group_filter="higher",
        education_group="Высшее",
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
        civil_law_contract_options=[],
        internship=False,
        work_formats=["HYBRID"],
        schedule=["FIVE_ON_TWO_OFF"],
        hours=["HOURS_8"],
        dms=True,
        training_mentorship=False,
        education_in_text="высшее",
        education_mismatch=False,
    )
    base.update(overrides)
    return FinalRow(**base)


def test_export_vacancies_csv_uses_semicolon_and_utf8_sig(tmp_path):
    path = tmp_path / "vacancies.csv"
    export_vacancies_csv([make_row()], path)

    raw_bytes = path.read_bytes()
    assert raw_bytes.startswith(b"\xef\xbb\xbf")  # BOM utf-8-sig

    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    assert "Название" in df.columns
    assert df.loc[0, "Название"] == "Программист"
    assert df.loc[0, "Аккредитация ИТ-компании"] == "да"


def test_export_vacancies_csv_no_bool_or_none_literals(tmp_path):
    path = tmp_path / "vacancies.csv"
    export_vacancies_csv([make_row(employer=None, internship=False)], path)
    content = path.read_text(encoding="utf-8-sig")
    assert "None" not in content
    assert "True" not in content
    assert "False" not in content
    assert "nan" not in content.lower()


def test_export_vacancies_csv_v2_uses_v2_columns(tmp_path):
    from hh_parser.csv_export import export_vacancies_csv_v2
    from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED, FinalRowV2

    row = FinalRowV2(
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
        civil_law_contract_options=[],
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
    path = tmp_path / "vacancies_v2.csv"
    export_vacancies_csv_v2([row], path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    assert "Группа ВО" in df.columns
    assert "Исходный фильтр образования" in df.columns
    assert df.loc[0, "Группа ВО"] == EDUCATION_GROUP_2_REQUIRED


def test_export_counts_by_sphere_csv(tmp_path):
    path = tmp_path / "counts.csv"
    rows = [SphereCounts("Все вакансии", 2183, 182, 106, 1944)]
    export_counts_by_sphere_csv(rows, path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    assert df.loc[0, "Сфера"] == "Все вакансии"
    assert df.loc[0, "Всего вакансий"] == 2183
