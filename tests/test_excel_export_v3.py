import openpyxl
import pytest

from hh_parser.aggregate import SphereCounts
from hh_parser.excel_export_v3 import export_workbook_v3, prepare_rows_for_export
from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED
from hh_parser.rows_v3 import FinalRowV3


def make_row(**overrides) -> FinalRowV3:
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
        in_v2_subsample=False,
    )
    base.update(overrides)
    return FinalRowV3(**base)


@pytest.fixture
def workbook_path(tmp_path):
    rows = [
        make_row(vacancy_id=1, sphere="IT", employer_id=10, in_v2_subsample=True),
        make_row(vacancy_id=2, sphere="IT", employer_id=10, salary_net_estimate=90000),
        make_row(
            vacancy_id=3, education_group_2=EDUCATION_GROUP_2_NOT_REQUIRED,
            education_group_filter="not_required_or_not_specified",
            education_group_filter_label="Не требуется или не указано",
            sphere="Право", employer_id=20, salary_net_estimate=50000,
        ),
    ]
    sphere_rows = [SphereCounts("IT", 50, 20, 10, 20)]
    excluded_counts = {"Зарплата не в рублях или не за месяц": 2}
    pool_size_by_raw_filter = {"higher": 10, "special_secondary": 5, "not_required_or_not_specified": 8}
    run_info = {"seed": 42, "area": 95}

    path = tmp_path / "vacancies_v3_test.xlsx"
    export_workbook_v3(rows, sphere_rows, excluded_counts, pool_size_by_raw_filter, run_info, path)
    return path


def test_all_sheets_present(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    assert wb.sheetnames == [
        "Выборка", "Количества по сферам", "Сферы x Группы ВО", "Отсев", "Параметры сбора", "Словарь колонок",
    ]


def test_vacancies_sheet_has_v3_columns(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert "В подвыборке v2" in headers
    assert "Номер вакансии работодателя в выборке" in headers


def test_employer_sequence_numbers_assigned_correctly(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    id_col = headers.index("ID вакансии") + 1
    seq_col = headers.index("Номер вакансии работодателя в выборке") + 1

    by_id = {}
    for r in range(2, ws.max_row + 1):
        vid = ws.cell(row=r, column=id_col).value
        seq = ws.cell(row=r, column=seq_col).value
        by_id[vid] = seq
    # вакансии 1 и 2 — один работодатель (10), employer cap в v3 не применяется
    assert sorted([by_id[1], by_id[2]]) == [1, 2]
    assert by_id[3] == 1  # другой работодатель


def test_in_v2_subsample_column_values(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    id_col = headers.index("ID вакансии") + 1
    subsample_col = headers.index("В подвыборке v2") + 1
    values = {
        ws.cell(row=r, column=id_col).value: ws.cell(row=r, column=subsample_col).value
        for r in range(2, ws.max_row + 1)
    }
    assert values[1] == "да"
    assert values[2] == "нет"
    assert values[3] == "нет"


def test_sphere_group_counts_sheet(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Сферы x Группы ВО"]
    rows_values = [
        [ws.cell(row=r, column=c).value for c in range(1, 5)]
        for r in range(2, ws.max_row + 1)
    ]
    it_row = next(r for r in rows_values if r[0] == "IT")
    assert it_row == ["IT", 2, 0, 2]
    pravo_row = next(r for r in rows_values if r[0] == "Право")
    assert pravo_row == ["Право", 0, 1, 1]
    total_row = rows_values[-1]
    assert total_row == ["ИТОГО", 2, 1, 3]


def test_exclusions_sheet_has_pool_sizes_and_reasons(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Отсев"]
    rows_values = [
        [ws.cell(row=r, column=c).value for c in range(1, 4)]
        for r in range(2, ws.max_row + 1)
    ]
    assert ["Размер пула (до отбора)", "higher", 10] in rows_values
    assert ["Причина отсева", "Зарплата не в рублях или не за месяц", 2] in rows_values


def test_no_bool_or_none_leak(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            assert cell.value is not True
            assert cell.value is not False


def test_prepare_rows_for_export_is_idempotent():
    rows = [make_row(vacancy_id=1, employer_id=10), make_row(vacancy_id=2, employer_id=10)]
    once = prepare_rows_for_export(rows)
    numbers_once = [r.employer_sequence_number for r in once]
    twice = prepare_rows_for_export(once)
    numbers_twice = [r.employer_sequence_number for r in twice]
    assert numbers_once == numbers_twice
