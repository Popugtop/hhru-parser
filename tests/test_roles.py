import json
from pathlib import Path

import pytest

from hh_parser.roles import DEFAULT_SPHERE, build_role_dictionary

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def role_dict():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    return build_role_dictionary(data)


def test_role_name_lookup(role_dict):
    assert role_dict.role_name(96) == "Программист, разработчик"
    assert role_dict.role_name(146) == "Юрист"


def test_category_for_role(role_dict):
    assert role_dict.category_name_for_role(96) == "Информационные технологии"
    assert role_dict.category_name_for_role(146) == "Юристы"
    assert role_dict.category_name_for_role(18) == "Финансы, бухгалтерия"  # Бухгалтер


def test_sphere_mapping(role_dict):
    assert role_dict.sphere_for_category("Информационные технологии") == "IT"
    assert role_dict.sphere_for_category("Юристы") == "Право"
    assert role_dict.sphere_for_category("Финансы, бухгалтерия") == "Экономика и финансы"
    assert role_dict.sphere_for_category("Наука, образование") == DEFAULT_SPHERE
    assert role_dict.sphere_for_category(None) == DEFAULT_SPHERE


def test_describe_roles_single(role_dict):
    profession_role, category, sphere = role_dict.describe_roles([96])
    assert profession_role == "Программист, разработчик"
    assert category == "Информационные технологии"
    assert sphere == "IT"


def test_describe_roles_empty_list(role_dict):
    profession_role, category, sphere = role_dict.describe_roles([])
    assert profession_role == ""
    assert category is None
    assert sphere == DEFAULT_SPHERE


def test_role_ids_for_category(role_dict):
    ids = role_dict.role_ids_for_category("Юристы")
    assert 146 in ids
    assert 145 in ids
    assert len(ids) == 4


def test_unknown_role_id_is_visible_not_silent(role_dict):
    profession_role, category, sphere = role_dict.describe_roles([999999])
    assert "999999" in profession_role
    assert category is None
    assert sphere == DEFAULT_SPHERE
