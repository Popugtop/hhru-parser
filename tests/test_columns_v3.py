from hh_parser.columns_v2 import COLUMNS as COLUMNS_V2
from hh_parser.columns_v3 import COLUMNS as COLUMNS_V3
from hh_parser.format_values import row_to_display_dict
from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED
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
        in_v2_subsample=True,
        employer_sequence_number=2,
    )
    base.update(overrides)
    return FinalRowV3(**base)


def test_columns_v3_has_two_more_columns_than_v2():
    assert len(COLUMNS_V3) == len(COLUMNS_V2) + 2


def test_new_columns_present_at_expected_positions():
    keys = [spec.key for spec in COLUMNS_V3]
    idx_filter_label = keys.index("education_group_filter_label")
    idx_in_subsample = keys.index("in_v2_subsample")
    assert idx_in_subsample == idx_filter_label + 1

    idx_employer_id = keys.index("employer_id")
    idx_seq = keys.index("employer_sequence_number")
    assert idx_seq == idx_employer_id + 1


def test_row_to_display_dict_v3():
    row = make_row()
    d = row_to_display_dict(row, columns=COLUMNS_V3)
    assert d["В подвыборке v2"] == "да"
    assert d["Номер вакансии работодателя в выборке"] == 2


def test_row_to_display_dict_v3_false_subsample():
    row = make_row(in_v2_subsample=False)
    d = row_to_display_dict(row, columns=COLUMNS_V3)
    assert d["В подвыборке v2"] == "нет"
