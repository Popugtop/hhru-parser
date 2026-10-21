import json
from pathlib import Path

import pytest

from hh_parser.parse_vacancy import parse_vacancy_detail
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED
from hh_parser.rows_v3 import FinalRowV3, assign_employer_sequence_numbers, build_row_v3
from hh_parser.whitelist import SPHERE_IT
from tests.helpers import make_vacancy_detail

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def role_dict():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    return build_role_dictionary(data)


SPHERE_MAP = {96: SPHERE_IT}


def test_build_row_v3_inherits_v2_fields(role_dict):
    state = make_vacancy_detail(1, name="Программист", salary_from=80000, salary_to=120000)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [96]
    detail = parse_vacancy_detail(state)

    row = build_row_v3(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP, in_v2_subsample=True)

    assert isinstance(row, FinalRowV3)
    assert row.sphere == SPHERE_IT
    assert row.salary_net_estimate == 100000
    assert row.in_v2_subsample is True
    assert row.employer_sequence_number == 0  # проставляется позже


def test_build_row_v3_not_in_subsample(role_dict):
    state = make_vacancy_detail(2)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [96]
    detail = parse_vacancy_detail(state)

    row = build_row_v3(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP, in_v2_subsample=False)
    assert row.in_v2_subsample is False


def test_employer_sequence_number_mutable_after_construction(role_dict):
    state = make_vacancy_detail(3)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [96]
    detail = parse_vacancy_detail(state)
    row = build_row_v3(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP, in_v2_subsample=False)
    row.employer_sequence_number = 3
    assert row.employer_sequence_number == 3


def make_simple_row(vacancy_id, employer_id) -> FinalRowV3:
    return FinalRowV3(
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
        sphere=SPHERE_IT,
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
        make_simple_row(5, employer_id=20),
    ]
    assign_employer_sequence_numbers(rows)
    numbers = {r.vacancy_id: r.employer_sequence_number for r in rows}
    assert numbers == {1: 1, 2: 1, 3: 2, 4: 3, 5: 2}


def test_assign_employer_sequence_numbers_none_employer_id():
    rows = [make_simple_row(1, employer_id=None), make_simple_row(2, employer_id=None)]
    assign_employer_sequence_numbers(rows)
    assert rows[0].employer_sequence_number == 1
    assert rows[1].employer_sequence_number == 2
