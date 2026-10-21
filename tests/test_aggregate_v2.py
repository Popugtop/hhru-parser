from hh_parser.aggregate import SphereCounts
from hh_parser.aggregate_v2 import (
    ALL_VACANCIES_LABEL,
    MIN_VO_REQUIRED_TOTAL,
    TOTAL_SPECIALIST_LABEL,
    build_vo_comparison_table,
    collect_sphere_counts_v2,
    total_vo_not_required,
    total_vo_required,
)
from hh_parser.roles import build_role_dictionary
from hh_parser.whitelist import SPHERE_ENGINEERING, SPHERE_IT, SPHERE_LAW, WhitelistEntry
from tests.helpers import make_search_state, wrap_state_as_html


def make_whitelist():
    return [
        WhitelistEntry(96, "Программист, разработчик", SPHERE_IT),
        WhitelistEntry(146, "Юрист", SPHERE_LAW),
        WhitelistEntry(48, "Инженер-конструктор", SPHERE_ENGINEERING),
    ]


def make_role_dict():
    data = {
        "categories": [
            {"id": 23, "name": "Медицина, фармацевтика", "roles": [{"id": 24, "name": "Врач"}]},
            {"id": 25, "name": "Наука, образование", "roles": [{"id": 132, "name": "Учитель"}]},
        ]
    }
    return build_role_dictionary(data)


class FakeFetcher:
    def __init__(self):
        self.calls: list[list[tuple[str, str]]] = []

    def fetch_search_page(self, params):
        self.calls.append(params)
        param_dict = dict(params)
        role_values = {v for k, v in params if k == "professional_role"}
        with_salary = "only_with_salary" in param_dict

        if not role_values:
            total = 2183 if with_salary else 3000
            state = make_search_state(total_found=total, higher=182, special_secondary=106, not_required=1894)
        elif role_values == {"96"}:
            state = make_search_state(total_found=16 if with_salary else 25, higher=4, special_secondary=2, not_required=10)
        elif role_values == {"146"}:
            state = make_search_state(total_found=12, higher=7, special_secondary=1, not_required=4)
        elif role_values == {"48"}:
            state = make_search_state(total_found=5, higher=1, special_secondary=1, not_required=3)
        elif role_values == {"96", "146", "48"}:
            state = make_search_state(total_found=33, higher=12, special_secondary=4, not_required=17)
        elif role_values == {"24"}:
            state = make_search_state(total_found=223, higher=97, special_secondary=31, not_required=95)
        elif role_values == {"132"}:
            state = make_search_state(total_found=49, higher=22, special_secondary=19, not_required=8)
        else:
            raise AssertionError(f"Unexpected role_values: {role_values}")
        return wrap_state_as_html(state), False


def test_collect_sphere_counts_v2_row_order_and_labels():
    fetcher = FakeFetcher()
    whitelist = make_whitelist()
    role_dict = make_role_dict()

    rows = collect_sphere_counts_v2(fetcher, whitelist, role_dict, area=95, search_period=30, with_salary_filters=True)
    labels = [r.label for r in rows]
    assert labels == [
        "IT", "Право", "Экономика и финансы", "Управление и офис", "Инженеры", "Продажи (офисные)",
        TOTAL_SPECIALIST_LABEL, "Медицина, фармацевтика", "Наука, образование", ALL_VACANCIES_LABEL,
    ]


def test_collect_sphere_counts_v2_sphere_values():
    fetcher = FakeFetcher()
    rows = collect_sphere_counts_v2(fetcher, make_whitelist(), make_role_dict(), 95, 30, True)
    by_label = {r.label: r for r in rows}
    assert by_label["IT"].total_found == 16
    assert by_label["Право"].total_found == 12
    assert by_label["Инженеры"].total_found == 5
    assert by_label[TOTAL_SPECIALIST_LABEL].total_found == 33
    assert by_label["Медицина, фармацевтика"].total_found == 223
    assert by_label["Наука, образование"].total_found == 49
    assert by_label[ALL_VACANCIES_LABEL].total_found == 2183


def test_empty_sphere_in_whitelist_queries_with_no_role_filter_gracefully():
    # Сферы, которых вообще нет в тестовом белом списке (например "Продажи"),
    # должны давать пустой role_ids -> запрос без professional_role -> это
    # совпадёт с запросом "Все вакансии" в фейковом фетчере, что нормально
    # для теста (в реальности with_professional_roles([]) просто не добавляет фильтр).
    fetcher = FakeFetcher()
    rows = collect_sphere_counts_v2(fetcher, make_whitelist(), make_role_dict(), 95, 30, True)
    by_label = {r.label: r for r in rows}
    assert by_label["Продажи (офисные)"].total_found == 2183


def test_with_salary_filters_false_uses_different_filter_variant():
    fetcher = FakeFetcher()
    rows_with = collect_sphere_counts_v2(fetcher, make_whitelist(), make_role_dict(), 95, 30, True)
    rows_without = collect_sphere_counts_v2(fetcher, make_whitelist(), make_role_dict(), 95, 30, False)

    with_total = next(r for r in rows_with if r.label == ALL_VACANCIES_LABEL).total_found
    without_total = next(r for r in rows_without if r.label == ALL_VACANCIES_LABEL).total_found
    assert with_total == 2183
    assert without_total == 3000
    assert with_total != without_total


# --- build_vo_comparison_table / gate check --------------------------------

def test_build_vo_comparison_table_only_includes_whitelist_spheres():
    fetcher = FakeFetcher()
    rows = collect_sphere_counts_v2(fetcher, make_whitelist(), make_role_dict(), 95, 30, True)
    comparison = build_vo_comparison_table(rows)
    spheres = {r.sphere for r in comparison}
    assert spheres == {"IT", "Право", "Экономика и финансы", "Управление и офис", "Инженеры", "Продажи (офисные)"}
    assert TOTAL_SPECIALIST_LABEL not in spheres
    assert "Медицина, фармацевтика" not in spheres
    assert ALL_VACANCIES_LABEL not in spheres


def test_vo_comparison_values_split_correctly():
    sphere_rows = [
        SphereCounts(label="IT", total_found=16, higher=4, special_secondary=2, not_required_or_not_specified=10),
        SphereCounts(label="Право", total_found=12, higher=7, special_secondary=1, not_required_or_not_specified=4),
    ]
    comparison = build_vo_comparison_table(sphere_rows)
    by_sphere = {r.sphere: r for r in comparison}
    assert by_sphere["IT"].vo_required == 4
    assert by_sphere["IT"].vo_not_required == 12  # 2 + 10
    assert by_sphere["Право"].vo_required == 7
    assert by_sphere["Право"].vo_not_required == 5  # 1 + 4


def test_total_vo_required_and_not_required():
    sphere_rows = [
        SphereCounts(label="IT", total_found=16, higher=4, special_secondary=2, not_required_or_not_specified=10),
        SphereCounts(label="Право", total_found=12, higher=7, special_secondary=1, not_required_or_not_specified=4),
    ]
    comparison = build_vo_comparison_table(sphere_rows)
    assert total_vo_required(comparison) == 11  # 4 + 7
    assert total_vo_not_required(comparison) == 17  # 12 + 5


def test_min_vo_required_gate_threshold_is_50():
    assert MIN_VO_REQUIRED_TOTAL == 50
