from hh_parser.fetch import BlockedError
from hh_parser.sample import REASON_BAD_SALARY, REASON_DUPLICATE_ACROSS_GROUPS, REASON_EMPLOYER_CAP, REASON_WRONG_AREA
from hh_parser.sample_v2 import (
    GROUP_VO_NOT_REQUIRED,
    GROUP_VO_REQUIRED,
    REASON_SPHERE_NOT_RESOLVED,
    collect_exhaustive_group,
    collect_matched_group,
    resolve_sphere,
)
from tests.helpers import make_listing, make_search_page_with_listings, make_vacancy_detail, wrap_state_as_html

SPHERE_MAP = {
    10: "IT",
    96: "IT",
    146: "Право",
    18: "Экономика и финансы",
}


# --- resolve_sphere ---------------------------------------------------------

def test_resolve_sphere_first_match_wins():
    assert resolve_sphere([999, 96, 10], SPHERE_MAP) == "IT"


def test_resolve_sphere_none_when_no_role_in_whitelist():
    assert resolve_sphere([999, 888], SPHERE_MAP) is None


def test_resolve_sphere_empty_list():
    assert resolve_sphere([], SPHERE_MAP) is None


# --- collect_exhaustive_group -----------------------------------------------

class ExhaustiveFakeFetcher:
    def __init__(self, pool_ids, vacancy_states):
        self.pool_ids = pool_ids
        self.vacancy_states = vacancy_states

    def fetch_search_page(self, params):
        param_dict = dict(params)
        page = int(param_dict["page"])
        assert param_dict["education"] == "higher"
        start, end = page * 50, page * 50 + 50
        ids = self.pool_ids[start:end]
        listings = [make_listing(vid) for vid in ids]
        state = make_search_page_with_listings(len(self.pool_ids), listings)
        return wrap_state_as_html(state), False

    def fetch_vacancy_page(self, vacancy_id):
        return wrap_state_as_html(self.vacancy_states[vacancy_id]), False


def make_detail_state(vid, role_ids, **kwargs):
    state = make_vacancy_detail(vid, **kwargs)
    state["vacancyView"]["vacancyFull"]["vacancy"]["professionalRoleIds"] = role_ids
    return state


def test_collect_exhaustive_group_caps_at_limit():
    pool_ids = list(range(1, 11))
    states = {vid: make_detail_state(vid, [96], company_id=vid) for vid in pool_ids}
    fetcher = ExhaustiveFakeFetcher(pool_ids, states)

    result = collect_exhaustive_group(
        fetcher, whitelist_role_ids=[96, 146], sphere_map=SPHERE_MAP,
        area=95, search_period=30, seed=42, cap=5, claimed_ids=set(),
    )
    assert len(result.collected) == 5
    assert result.group_label == GROUP_VO_REQUIRED


def test_collect_exhaustive_group_resolves_spheres_correctly():
    pool_ids = [1, 2, 3]
    states = {
        1: make_detail_state(1, [96], company_id=1),  # IT
        2: make_detail_state(2, [146], company_id=2),  # Право
        3: make_detail_state(3, [18], company_id=3),  # Экономика и финансы
    }
    fetcher = ExhaustiveFakeFetcher(pool_ids, states)
    result = collect_exhaustive_group(
        fetcher, [96, 146, 18], SPHERE_MAP, 95, 30, seed=42, cap=10, claimed_ids=set(),
    )
    assert result.sphere_counts() == {"IT": 1, "Право": 1, "Экономика и финансы": 1}


def test_collect_exhaustive_group_excludes_unresolvable_sphere():
    pool_ids = [1]
    states = {1: make_detail_state(1, [999], company_id=1)}  # роль не в белом списке
    fetcher = ExhaustiveFakeFetcher(pool_ids, states)
    result = collect_exhaustive_group(
        fetcher, [96], SPHERE_MAP, 95, 30, seed=42, cap=10, claimed_ids=set(),
    )
    assert len(result.collected) == 0
    assert result.excluded_counts[REASON_SPHERE_NOT_RESOLVED] == 1


def test_collect_exhaustive_group_applies_standard_exclusion_rules():
    pool_ids = [1, 2]
    states = {
        1: make_detail_state(1, [96], currency="USD"),  # плохая зарплата
        2: make_detail_state(2, [96], area_id=1, area_name="Москва"),  # не Тюмень
    }
    fetcher = ExhaustiveFakeFetcher(pool_ids, states)
    result = collect_exhaustive_group(
        fetcher, [96], SPHERE_MAP, 95, 30, seed=42, cap=10, claimed_ids=set(),
    )
    assert result.excluded_counts[REASON_BAD_SALARY] == 1
    assert result.excluded_counts[REASON_WRONG_AREA] == 1
    assert len(result.collected) == 0


def test_collect_exhaustive_group_populates_claimed_ids():
    pool_ids = [1, 2]
    states = {vid: make_detail_state(vid, [96], company_id=vid) for vid in pool_ids}
    fetcher = ExhaustiveFakeFetcher(pool_ids, states)
    claimed_ids: set[int] = set()
    collect_exhaustive_group(fetcher, [96], SPHERE_MAP, 95, 30, seed=42, cap=10, claimed_ids=claimed_ids)
    assert claimed_ids == {1, 2}


def test_collect_exhaustive_group_blocked_mid_collection_saves_progress():
    pool_ids = [1, 2, 3]
    states = {vid: make_detail_state(vid, [96], company_id=vid) for vid in pool_ids}

    class BlockingFetcher(ExhaustiveFakeFetcher):
        def __init__(self, *a, block_after, **kw):
            super().__init__(*a, **kw)
            self.calls = 0
            self.block_after = block_after

        def fetch_vacancy_page(self, vacancy_id):
            self.calls += 1
            if self.calls > self.block_after:
                raise BlockedError("403")
            return super().fetch_vacancy_page(vacancy_id)

    fetcher = BlockingFetcher(pool_ids, states, block_after=1)
    result = collect_exhaustive_group(fetcher, [96], SPHERE_MAP, 95, 30, seed=42, cap=10, claimed_ids=set())
    assert result.blocked_reason is not None
    assert len(result.collected) == 1


# --- collect_matched_group ---------------------------------------------------

class MatchedFakeFetcher:
    """pools: {sphere: [vacancy_id, ...]} — все эти ID возвращаются под ОБОИМИ
    raw-значениями образования, если not split_by_raw_value не задан явно;
    pools_by_raw_value (опционально): {(sphere, raw_value): [ids]} для теста
    провенанса, когда разные ID должны прийти из разных raw-запросов."""

    def __init__(self, pools, role_ids_by_sphere, states, pools_by_raw_value=None):
        self.pools = pools
        self.role_ids_by_sphere = role_ids_by_sphere
        self.states = states
        self.pools_by_raw_value = pools_by_raw_value

    def _sphere_for_params(self, params):
        role_values = {v for k, v in params if k == "professional_role"}
        for sphere, role_ids in self.role_ids_by_sphere.items():
            if role_values == {str(r) for r in role_ids}:
                return sphere
        raise AssertionError(f"No sphere matches role_values={role_values}")

    def fetch_search_page(self, params):
        param_dict = dict(params)
        page = int(param_dict["page"])
        education_values = [v for k, v in params if k == "education"]
        assert len(education_values) == 1, "запрос должен идти по ОДНОМУ raw-значению за раз"
        raw_value = education_values[0]
        assert raw_value in {"special_secondary", "not_required_or_not_specified"}
        sphere = self._sphere_for_params(params)

        if self.pools_by_raw_value is not None:
            pool = self.pools_by_raw_value.get((sphere, raw_value), [])
        else:
            pool = self.pools.get(sphere, [])
        start, end = page * 50, page * 50 + 50
        ids = pool[start:end]
        listings = [make_listing(vid) for vid in ids]
        state = make_search_page_with_listings(len(pool), listings)
        return wrap_state_as_html(state), False

    def fetch_vacancy_page(self, vacancy_id):
        return wrap_state_as_html(self.states[vacancy_id]), False


def test_collect_matched_group_meets_targets_per_sphere():
    role_ids_by_sphere = {"IT": [96], "Право": [146]}
    pools = {"IT": [1, 2, 3], "Право": [10, 11]}
    states = {}
    for vid in pools["IT"]:
        states[vid] = make_detail_state(vid, [96], company_id=vid)
    for vid in pools["Право"]:
        states[vid] = make_detail_state(vid, [146], company_id=vid)

    fetcher = MatchedFakeFetcher(pools, role_ids_by_sphere, states)
    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 2, "Право": 1},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=set(),
    )
    assert result.sphere_counts() == {"IT": 2, "Право": 1}
    assert result.group_label == GROUP_VO_NOT_REQUIRED
    assert result.shortfall_by_sphere == {}


def test_collect_matched_group_reports_shortfall_when_pool_too_small():
    role_ids_by_sphere = {"IT": [96]}
    pools = {"IT": [1, 2]}
    states = {vid: make_detail_state(vid, [96], company_id=vid) for vid in pools["IT"]}
    fetcher = MatchedFakeFetcher(pools, role_ids_by_sphere, states)

    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 5},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=set(),
    )
    assert len(result.collected) == 2
    assert result.shortfall_by_sphere == {"IT": 3}


def test_collect_matched_group_employer_cap_shared_across_spheres():
    role_ids_by_sphere = {"IT": [96], "Право": [146]}
    # тот же работодатель (id=1) во всех вакансиях обеих сфер -> лимит 3 на группу
    # (разные названия, чтобы не схлопнуться по правилу дублей раньше лимита)
    pools = {"IT": [1, 2, 3], "Право": [10, 11]}
    states = {}
    for vid in pools["IT"]:
        states[vid] = make_detail_state(vid, [96], company_id=1, name=f"Вакансия IT {vid}")
    for vid in pools["Право"]:
        states[vid] = make_detail_state(vid, [146], company_id=1, name=f"Вакансия Право {vid}")

    fetcher = MatchedFakeFetcher(pools, role_ids_by_sphere, states)
    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 3, "Право": 2},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=set(),
    )
    # всего максимум 3 вакансии этого работодателя на ВСЮ группу (IT+Право вместе)
    assert len(result.collected) == 3
    assert result.excluded_counts[REASON_EMPLOYER_CAP] == 2  # 3(IT) + 2(Право) запрошено - 3 принято = 2 исключено


def test_collect_matched_group_skips_claimed_cross_group_ids():
    role_ids_by_sphere = {"IT": [96]}
    pools = {"IT": [1, 2, 3]}
    states = {vid: make_detail_state(vid, [96], company_id=vid) for vid in pools["IT"]}
    fetcher = MatchedFakeFetcher(pools, role_ids_by_sphere, states)

    claimed = {1}  # уже забрана группой "ВО требуется"
    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 2},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=claimed,
    )
    assert 1 not in {d.vacancy_id for d in result.collected}
    assert result.excluded_counts[REASON_DUPLICATE_ACROSS_GROUPS] == 1


def test_collect_matched_group_tracks_raw_filter_provenance():
    role_ids_by_sphere = {"IT": [96]}
    pools_by_raw_value = {
        ("IT", "special_secondary"): [1, 2],
        ("IT", "not_required_or_not_specified"): [3],
    }
    states = {
        1: make_detail_state(1, [96], company_id=1, name="Вакансия 1"),
        2: make_detail_state(2, [96], company_id=2, name="Вакансия 2"),
        3: make_detail_state(3, [96], company_id=3, name="Вакансия 3"),
    }
    fetcher = MatchedFakeFetcher({}, role_ids_by_sphere, states, pools_by_raw_value=pools_by_raw_value)

    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 3},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=set(),
    )
    assert result.raw_filter_by_vacancy_id[1] == "special_secondary"
    assert result.raw_filter_by_vacancy_id[2] == "special_secondary"
    assert result.raw_filter_by_vacancy_id[3] == "not_required_or_not_specified"


def test_collect_matched_group_skips_sphere_with_zero_target():
    role_ids_by_sphere = {"IT": [96], "Право": [146]}
    pools = {"IT": [1], "Право": [10]}
    states = {
        1: make_detail_state(1, [96], company_id=1),
        10: make_detail_state(10, [146], company_id=10),
    }

    class StrictFetcher(MatchedFakeFetcher):
        def fetch_search_page(self, params):
            sphere = self._sphere_for_params(params)
            if sphere == "Право":
                raise AssertionError("Сфера с target=0 не должна запрашиваться вовсе")
            return super().fetch_search_page(params)

    fetcher = StrictFetcher(pools, role_ids_by_sphere, states)
    result = collect_matched_group(
        fetcher, role_ids_by_sphere, target_by_sphere={"IT": 1, "Право": 0},
        sphere_map=SPHERE_MAP, area=95, search_period=30, seed=42, claimed_ids=set(),
    )
    assert result.sphere_counts() == {"IT": 1}
