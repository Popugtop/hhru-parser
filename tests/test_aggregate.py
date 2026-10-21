from hh_parser.aggregate import ALL_VACANCIES_LABEL, collect_sphere_counts
from hh_parser.roles import build_role_dictionary
from tests.helpers import make_search_state, wrap_state_as_html

IT_ROLE_IDS = [96, 113]  # Программист + Системный администратор


def make_role_dict():
    data = {
        "categories": [
            {
                "id": 11,
                "name": "Информационные технологии",
                "roles": [
                    {"id": 96, "name": "Программист, разработчик"},
                    {"id": 113, "name": "Системный администратор"},
                ],
            },
            {
                "id": 13,
                "name": "Юристы",
                "roles": [{"id": 146, "name": "Юрист"}],
            },
            {
                "id": 3,
                "name": "Финансы, бухгалтерия",
                "roles": [{"id": 18, "name": "Бухгалтер"}],
            },
            {
                "id": 25,
                "name": "Наука, образование",
                "roles": [{"id": 132, "name": "Учитель, преподаватель, педагог"}],
            },
            {
                "id": 23,
                "name": "Медицина, фармацевтика",
                "roles": [{"id": 24, "name": "Врач"}],
            },
            {
                "id": 1,
                "name": "Продажи, обслуживание клиентов",
                "roles": [{"id": 97, "name": "Продавец-консультант, продавец-кассир"}],
            },
        ]
    }
    return build_role_dictionary(data)


class FakeFetcher:
    """Возвращает разные счётчики в зависимости от того, есть ли professional_role."""

    def __init__(self):
        self.calls: list[list[tuple[str, str]]] = []

    def fetch_search_page(self, params):
        self.calls.append(params)
        param_dict = dict(params)
        if "professional_role" not in param_dict:
            state = make_search_state(total_found=2183, higher=182, special_secondary=106, not_required=1944)
        else:
            role_values = {v for k, v in params if k == "professional_role"}
            if role_values == {"96", "113"}:
                state = make_search_state(total_found=182, higher=100, special_secondary=20, not_required=62)
            elif role_values == {"146"}:
                state = make_search_state(total_found=30, higher=25, special_secondary=2, not_required=3)
            else:
                state = make_search_state(total_found=10, higher=5, special_secondary=2, not_required=3)
        return wrap_state_as_html(state), False


def test_collect_sphere_counts_all_vacancies_row_first():
    fetcher = FakeFetcher()
    role_dict = make_role_dict()
    rows = collect_sphere_counts(fetcher, role_dict, area=95, search_period=30)

    assert rows[0].label == ALL_VACANCIES_LABEL
    assert rows[0].total_found == 2183
    assert rows[0].higher == 182


def test_collect_sphere_counts_includes_all_part_a_categories():
    fetcher = FakeFetcher()
    role_dict = make_role_dict()
    rows = collect_sphere_counts(fetcher, role_dict, area=95, search_period=30)

    labels = [r.label for r in rows]
    assert labels == [
        ALL_VACANCIES_LABEL,
        "Информационные технологии",
        "Юристы",
        "Финансы, бухгалтерия",
        "Наука, образование",
        "Медицина, фармацевтика",
        "Продажи, обслуживание клиентов",
    ]


def test_it_category_uses_all_its_role_ids_in_one_request():
    fetcher = FakeFetcher()
    role_dict = make_role_dict()
    collect_sphere_counts(fetcher, role_dict, area=95, search_period=30)

    it_call = fetcher.calls[1]
    role_params = [v for k, v in it_call if k == "professional_role"]
    assert set(role_params) == {"96", "113"}


def test_sphere_counts_properties():
    from hh_parser.aggregate import SphereCounts

    row = SphereCounts(label="x", total_found=100, higher=50, special_secondary=20, not_required_or_not_specified=20)
    assert row.education_sum == 90
    assert row.education_sum_diverges is True
    assert row.higher_share_pct == 50.0


def test_sphere_counts_zero_total_found_share_is_none():
    from hh_parser.aggregate import SphereCounts

    row = SphereCounts(label="x", total_found=0, higher=0, special_secondary=0, not_required_or_not_specified=0)
    assert row.higher_share_pct is None
