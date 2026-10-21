import json
from pathlib import Path

import pytest

from hh_parser.parse_vacancy import parse_vacancy_detail
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import (
    EDUCATION_GROUP_2_NOT_REQUIRED,
    EDUCATION_GROUP_2_REQUIRED,
    SENIOR_ROLE_COMMENT,
    build_row_v2,
)
from hh_parser.whitelist import SENIOR_ROLE_IDS, SPHERE_IT, SPHERE_LAW
from tests.helpers import make_vacancy_detail

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def role_dict():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    return build_role_dictionary(data)


SPHERE_MAP = {96: SPHERE_IT, 146: SPHERE_LAW}


def test_build_row_v2_basic_fields(role_dict):
    state = make_vacancy_detail(
        1, name="Программист", company_id=10, company_name="ООО Компания",
        salary_from=80000, salary_to=120000,
    )
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [96]
    detail = parse_vacancy_detail(state)

    row = build_row_v2(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP)

    assert row.education_group_2 == EDUCATION_GROUP_2_REQUIRED
    assert row.education_group_filter == "higher"
    assert row.education_group_filter_label == "Высшее"
    assert row.sphere == SPHERE_IT
    assert row.salary_net_estimate == 100000
    assert row.is_senior_role is False
    assert row.comment == ""


def test_build_row_v2_not_required_group_preserves_raw_filter(role_dict):
    state = make_vacancy_detail(2)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [146]
    detail = parse_vacancy_detail(state)

    row = build_row_v2(
        detail, EDUCATION_GROUP_2_NOT_REQUIRED, "special_secondary", role_dict, SPHERE_MAP
    )
    assert row.education_group_2 == EDUCATION_GROUP_2_NOT_REQUIRED
    assert row.education_group_filter == "special_secondary"
    assert row.education_group_filter_label == "СПО"
    assert row.sphere == SPHERE_LAW


def test_build_row_v2_flags_senior_role_in_comment(role_dict):
    senior_role_id = next(iter(SENIOR_ROLE_IDS))
    state = make_vacancy_detail(3)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [senior_role_id]
    detail = parse_vacancy_detail(state)

    sphere_map = {senior_role_id: SPHERE_IT}
    row = build_row_v2(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, sphere_map)

    assert row.is_senior_role is True
    assert row.comment == SENIOR_ROLE_COMMENT


def test_build_row_v2_sphere_none_when_role_not_in_map(role_dict):
    state = make_vacancy_detail(4)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [999999]
    detail = parse_vacancy_detail(state)

    row = build_row_v2(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP)
    assert row.sphere is None


def test_build_row_v2_education_mismatch_uses_raw_filter(role_dict):
    state = make_vacancy_detail(
        5, description="Образование не требуется, обучим с нуля.",
    )
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = [96]
    detail = parse_vacancy_detail(state)

    row = build_row_v2(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, SPHERE_MAP)
    assert row.education_mismatch is True  # higher + "не требуется" в тексте = противоречие
