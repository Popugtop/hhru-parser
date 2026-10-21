from hh_parser.filters import base_params, with_education, with_education_values, with_page, with_professional_roles


def test_base_params_default_includes_salary_filters():
    params = base_params(95, 30)
    d = dict(params)
    assert d["area"] == "95"
    assert d["experience"] == "noExperience"
    assert d["employment_form"] == "FULL"
    assert d["search_period"] == "30"
    assert d["only_with_salary"] == "true"
    assert d["salary_mode"] == "MONTH"


def test_base_params_without_salary_filters_for_part_a_variant_2():
    params = base_params(95, 30, with_salary_filters=False)
    keys = [k for k, _ in params]
    assert "only_with_salary" not in keys
    assert "salary_mode" not in keys
    assert "area" in keys
    assert "experience" in keys


def test_with_education_single_value():
    params = with_education(base_params(95, 30), "higher")
    assert ("education", "higher") in params


def test_with_education_values_multiple():
    params = with_education_values(base_params(95, 30), ["special_secondary", "not_required_or_not_specified"])
    education_values = [v for k, v in params if k == "education"]
    assert education_values == ["special_secondary", "not_required_or_not_specified"]


def test_with_professional_roles():
    params = with_professional_roles(base_params(95, 30), [10, 20, 30])
    role_values = [v for k, v in params if k == "professional_role"]
    assert role_values == ["10", "20", "30"]


def test_with_page():
    params = with_page(base_params(95, 30), 3)
    assert ("page", "3") in params
