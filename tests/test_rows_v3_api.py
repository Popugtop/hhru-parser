import json
from pathlib import Path

import pytest

from hh_parser.api_parse import parse_vacancy_detail_api
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED
from hh_parser.rows_v3_api import FinalRowV3Api, assign_employer_sequence_numbers, build_row_v3_api
from hh_parser.whitelist import SPHERE_LAW

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def role_dict():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    return build_role_dictionary(data)


SPHERE_MAP = {146: SPHERE_LAW}


def test_build_row_v3_api_from_real_fixture(role_dict):
    detail_json = json.loads((FIXTURES / "api_vacancy_detail.json").read_text(encoding="utf-8"))
    detail = parse_vacancy_detail_api(detail_json)

    row = build_row_v3_api(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP, in_matched_subsample=True)

    assert isinstance(row, FinalRowV3Api)
    assert row.sphere == SPHERE_LAW
    assert row.in_matched_subsample is True
    assert row.employer_sequence_number == 0  # проставляется позже
    assert row.salary_net_estimate == 69600  # одна граница (80000, to=None), gross=True -> *0.87


def test_build_row_v3_api_not_in_subsample(role_dict):
    detail_json = json.loads((FIXTURES / "api_vacancy_detail.json").read_text(encoding="utf-8"))
    detail = parse_vacancy_detail_api(detail_json)
    row = build_row_v3_api(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP, in_matched_subsample=False)
    assert row.in_matched_subsample is False


def make_simple_row(vacancy_id, employer_id) -> FinalRowV3Api:
    return FinalRowV3Api(
        education_group_2=EDUCATION_GROUP_2_REQUIRED,
        education_group_filter="higher",
        education_group_filter_label="Высшее",
        vacancy_id=vacancy_id,
        link=f"https://hh.ru/vacancy/{vacancy_id}",
        name="Вакансия",
        employer="Компания",
        employer_id=employer_id,
        sector="коммерческий",
        profession_role="Роль",
        role_category=None,
        sphere=SPHERE_LAW,
        it_accreditation=False,
        publication_date=None,
        salary_from=None,
        salary_to=None,
        gross=None,
        salary_net_estimate=None,
        labor_contract=False,
        civil_law_contract_options=[],
        internship=False,
        work_formats=[],
        schedule=[],
        hours=[],
        dms=False,
        training_mentorship=False,
        education_in_text="не указано",
        education_mismatch=False,
        is_senior_role=False,
    )


def test_assign_employer_sequence_numbers_counts_per_employer_in_order():
    rows = [
        make_simple_row(1, employer_id=10),
        make_simple_row(2, employer_id=20),
        make_simple_row(3, employer_id=10),
        make_simple_row(4, employer_id=10),
    ]
    assign_employer_sequence_numbers(rows)
    numbers = {r.vacancy_id: r.employer_sequence_number for r in rows}
    assert numbers == {1: 1, 2: 1, 3: 2, 4: 3}
