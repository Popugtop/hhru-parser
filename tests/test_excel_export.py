from collections import Counter

import openpyxl
import pytest

from hh_parser.aggregate import SphereCounts
from hh_parser.excel_export import export_workbook
from hh_parser.rows import FinalRow
from hh_parser.sample import SampleResult


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


@pytest.fixture
def workbook_path(tmp_path):
    rows = [
        make_row(vacancy_id=1, education_group_filter="higher", sphere="IT", salary_net_estimate=100000),
        make_row(
            vacancy_id=2, education_group_filter="higher", sphere="Право", salary_net_estimate=50000,
            education_mismatch=True, education_in_text="не требуется",
        ),
        make_row(
            vacancy_id=3, education_group_filter="not_required_or_not_specified", sphere="Прочие",
            salary_net_estimate=30000, employer=None, role_category=None,
        ),
    ]
    sphere_rows = [
        SphereCounts("Все вакансии", 2183, 182, 106, 1944),
        SphereCounts("Информационные технологии", 182, 100, 20, 62),
    ]
    sample_results = {
        "higher": SampleResult(
            group="higher", requested_quota=2, pool_size=50,
            collected=[], excluded_counts=Counter({"Требуется опыт работы": 3}),
        ),
        "not_required_or_not_specified": SampleResult(
            group="not_required_or_not_specified", requested_quota=1, pool_size=20,
            collected=[], excluded_counts=Counter(),
        ),
    }
    run_info = {
        "Дата и время сбора": "2026-10-07 12:00:00",
        "area": 95,
        "seed": 42,
        "квоты": {"higher": 80, "special_secondary": 40},
    }

    path = tmp_path / "vacancies_test.xlsx"
    export_workbook(rows, sphere_rows, sample_results, run_info, path)
    return path


def test_all_sheets_present(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    assert wb.sheetnames == [
        "Выборка", "Количества по сферам", "Сводка", "Отсев", "Параметры сбора", "Словарь колонок",
    ]


def test_header_row_is_bold_and_frozen(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    assert ws.cell(row=1, column=1).font.bold is True
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref is not None


def test_no_python_none_or_bool_literals_in_vacancies_sheet(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            assert cell.value is not True
            assert cell.value is not False
            assert str(cell.value) != "nan"


def test_mismatch_row_is_highlighted(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    # вакансия 2 (расхождение=True) должна быть подсвечена, вакансия 1 (False) — нет
    highlighted_rows = []
    for row in ws.iter_rows(min_row=2):
        fill = row[0].fill
        if fill and fill.fgColor and fill.fgColor.rgb == "FFFCE8B2":
            highlighted_rows.append(row[0].row)
    assert len(highlighted_rows) == 1


def test_salary_and_id_are_numeric_with_format(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    salary_col = headers.index("Зарплата на руки, расчётная, руб.") + 1
    id_col = headers.index("ID вакансии") + 1
    for row_idx in range(2, ws.max_row + 1):
        salary_cell = ws.cell(row=row_idx, column=salary_col)
        id_cell = ws.cell(row=row_idx, column=id_col)
        assert isinstance(salary_cell.value, (int, float))
        assert salary_cell.number_format == "#,##0"
        assert isinstance(id_cell.value, int)


def test_link_cell_is_hyperlink(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    link_col = headers.index("Ссылка") + 1
    cell = ws.cell(row=2, column=link_col)
    assert cell.hyperlink is not None


def test_verified_manually_column_has_dropdown(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    validations = ws.data_validations.dataValidation
    assert len(validations) == 1
    assert validations[0].formula1 == '"да,нет"'


def test_vacancies_sorted_by_group_then_sphere_then_salary(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    id_col = headers.index("ID вакансии") + 1
    ids = [ws.cell(row=r, column=id_col).value for r in range(2, ws.max_row + 1)]
    # higher/IT (id1), higher/Право (id2) -> higher идёт первым (т.к. выше в EDUCATION_GROUP_ORDER),
    # not_required идёт последним по порядку групп
    assert ids == [1, 2, 3]


def test_description_column_is_narrow_and_no_wrap(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Выборка"]
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    desc_col = headers.index("Описание") + 1
    from openpyxl.utils import get_column_letter

    letter = get_column_letter(desc_col)
    assert ws.column_dimensions[letter].width == 50
    # openpyxl не пишет в XML wrap_text=False (значение по умолчанию), после
    # перезагрузки книги это читается как None — оба значения означают "без переноса"
    assert ws.cell(row=2, column=desc_col).alignment.wrap_text in (False, None)


def test_counts_sheet_values(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Количества по сферам"]
    assert ws.cell(row=2, column=1).value == "Все вакансии"
    assert ws.cell(row=2, column=2).value == 2183


def test_summary_sheet_has_three_education_groups(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Сводка"]
    labels = [ws.cell(row=r, column=1).value for r in range(2, 5)]
    assert labels == ["Высшее", "Не требуется или не указано", "СПО"]


def test_exclusions_sheet_contains_reason(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Отсев"]
    reasons = [ws.cell(row=r, column=5).value for r in range(2, ws.max_row + 1)]
    assert "Требуется опыт работы" in reasons


def test_params_sheet_contains_seed(workbook_path):
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Параметры сбора"]
    keys = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    assert "seed" in keys


def test_dictionary_sheet_has_one_row_per_column(workbook_path):
    from hh_parser.columns import COLUMNS

    wb = openpyxl.load_workbook(workbook_path)
    ws = wb["Словарь колонок"]
    assert ws.max_row - 1 == len(COLUMNS)
