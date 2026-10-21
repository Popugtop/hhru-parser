import json
from pathlib import Path

import pytest

from hh_parser.parse_vacancy import parse_vacancy_detail
from hh_parser.roles import build_role_dictionary
from hh_parser.rows import build_row, compute_net_salary_estimate
from tests.helpers import make_vacancy_detail

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def role_dict():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    return build_role_dictionary(data)


@pytest.mark.parametrize(
    "salary_from,salary_to,gross,expected",
    [
        (40000, 60000, False, 50000),
        (50000, None, False, 50000),
        (None, 60000, False, 60000),
        (100000, 100000, True, 87000),
        (None, None, False, None),
    ],
)
def test_compute_net_salary_estimate(salary_from, salary_to, gross, expected):
    assert compute_net_salary_estimate(salary_from, salary_to, gross) == expected


def test_build_row_basic_fields(role_dict):
    state = make_vacancy_detail(
        1,
        name="Программист",
        company_id=10,
        company_name="ООО Рога и копыта",
        salary_from=80000,
        salary_to=120000,
        description="Высшее образование обязательно. Оформление ДМС после испытательного срока. Наставник на старте.",
    )
    detail = parse_vacancy_detail(state)
    row = build_row(detail, "higher", role_dict)

    assert row.education_group == "Высшее"
    assert row.vacancy_id == 1
    assert row.employer == "ООО Рога и копыта"
    assert row.employer_id == 10
    assert row.sector == "коммерческий"
    assert row.sphere == "IT"
    assert row.profession_role == "Программист, разработчик"
    assert row.salary_net_estimate == 100000
    assert row.dms is True
    assert row.training_mentorship is True
    assert row.education_in_text == "высшее"
    assert row.education_mismatch is False  # фильтр higher и текст "высшее" согласованы


def test_build_row_detects_education_mismatch(role_dict):
    state = make_vacancy_detail(
        2,
        description="Образование не требуется, всему научим на месте.",
    )
    detail = parse_vacancy_detail(state)
    row = build_row(detail, "higher", role_dict)
    assert row.education_mismatch is True


def test_build_row_budget_sector(role_dict):
    state = make_vacancy_detail(3, company_name='МАОУ СОШ №5 г. Тюмени')
    detail = parse_vacancy_detail(state)
    row = build_row(detail, "not_required_or_not_specified", role_dict)
    assert row.sector == "бюджетный"


def test_build_row_unknown_professional_role(role_dict):
    state = make_vacancy_detail(4)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = []
    detail = parse_vacancy_detail(state)
    row = build_row(detail, "special_secondary", role_dict)
    assert row.sphere == "Прочие"
    assert row.role_category is None
