from collections import Counter

import pytest

from hh_parser.fetch import BlockedError
from hh_parser.sample import (
    REASON_BAD_SALARY,
    REASON_DUPLICATE_ACROSS_GROUPS,
    REASON_DUPLICATE_WITHIN_GROUP,
    REASON_EMPLOYER_CAP,
    REASON_PART_EMPLOYMENT,
    REASON_REQUIRES_EXPERIENCE,
    REASON_WRONG_AREA,
    check_exclusion,
    collect_pool,
    normalize_name,
    run_part_b,
    select_group_sample,
)
from hh_parser.parse_vacancy import parse_vacancy_detail
from hh_parser.ssr import extract_initial_state
from tests.helpers import make_listing, make_search_page_with_listings, make_vacancy_detail, wrap_state_as_html


def detail_from_kwargs(vacancy_id, **kwargs):
    state = make_vacancy_detail(vacancy_id, **kwargs)
    return parse_vacancy_detail(state)


# --- normalize_name ---------------------------------------------------

def test_normalize_name_collapses_whitespace_and_case():
    assert normalize_name("  Продавец   КОНСУЛЬТАНТ ") == "продавец консультант"


def test_normalize_name_handles_none_and_empty():
    assert normalize_name(None) == ""
    assert normalize_name("") == ""


# --- check_exclusion ----------------------------------------------------

def test_check_exclusion_accepts_valid_vacancy():
    detail = detail_from_kwargs(1)
    reason = check_exclusion(detail, area_id=95, employer_counts=Counter(), seen_keys=set())
    assert reason is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"currency": "USD"},
        {"salary_mode": "HOUR"},
        {"salary_from": None, "salary_to": None},
    ],
)
def test_check_exclusion_bad_salary(kwargs):
    detail = detail_from_kwargs(1, **kwargs)
    assert check_exclusion(detail, 95, Counter(), set()) == REASON_BAD_SALARY


def test_check_exclusion_part_employment():
    detail = detail_from_kwargs(1, employment_form="PART")
    assert check_exclusion(detail, 95, Counter(), set()) == REASON_PART_EMPLOYMENT


def test_check_exclusion_requires_experience():
    detail = detail_from_kwargs(1, work_experience="between1And3")
    assert check_exclusion(detail, 95, Counter(), set()) == REASON_REQUIRES_EXPERIENCE


def test_check_exclusion_wrong_area():
    detail = detail_from_kwargs(1, area_id=1, area_name="Москва")
    assert check_exclusion(detail, 95, Counter(), set()) == REASON_WRONG_AREA


def test_check_exclusion_employer_cap():
    detail = detail_from_kwargs(1, company_id=42)
    counts = Counter({42: 3})
    assert check_exclusion(detail, 95, counts, set()) == REASON_EMPLOYER_CAP


def test_check_exclusion_employer_cap_disabled_with_none():
    detail = detail_from_kwargs(1, company_id=42)
    counts = Counter({42: 50})  # далеко за обычным лимитом 3
    assert check_exclusion(detail, 95, counts, set(), employer_cap=None) is None


def test_check_exclusion_employer_cap_not_triggered_below_limit():
    detail = detail_from_kwargs(1, company_id=42)
    counts = Counter({42: 2})
    assert check_exclusion(detail, 95, counts, set()) is None


def test_check_exclusion_duplicate_within_group():
    detail = detail_from_kwargs(1, company_id=42, name="Продавец")
    seen = {(42, "продавец")}
    assert check_exclusion(detail, 95, Counter(), seen) == REASON_DUPLICATE_WITHIN_GROUP


def test_check_exclusion_order_salary_before_employer_cap():
    # Если проблем несколько — должна вернуться первая по приоритету (зарплата)
    detail = detail_from_kwargs(1, company_id=42, currency="USD")
    counts = Counter({42: 5})
    assert check_exclusion(detail, 95, counts, set()) == REASON_BAD_SALARY


# --- collect_pool ---------------------------------------------------------

class FakeSearchFetcher:
    """pages_by_group: {group_id: [[vacancy_id, ...], [vacancy_id, ...], ...]}"""

    def __init__(self, pages_by_group, total_found_by_group):
        self.pages_by_group = pages_by_group
        self.total_found_by_group = total_found_by_group

    def fetch_search_page(self, params):
        param_dict = dict(params)
        group = param_dict["education"]
        page = int(param_dict["page"])
        pages = self.pages_by_group.get(group, [])
        ids = pages[page] if page < len(pages) else []
        listings = [make_listing(vid) for vid in ids]
        state = make_search_page_with_listings(self.total_found_by_group.get(group, 0), listings)
        return wrap_state_as_html(state), False


def test_collect_pool_single_page_under_50():
    fetcher = FakeSearchFetcher(
        pages_by_group={"higher": [[1, 2, 3]]},
        total_found_by_group={"higher": 3},
    )
    pool = collect_pool(fetcher, "higher", area=95, search_period=30)
    assert pool == [1, 2, 3]


def test_collect_pool_stops_at_total_found_without_extra_page():
    ids_page0 = list(range(1, 51))  # ровно 50
    fetcher = FakeSearchFetcher(
        pages_by_group={"higher": [ids_page0, [999]]},  # вторая страница не должна понадобиться
        total_found_by_group={"higher": 50},
    )
    pool = collect_pool(fetcher, "higher", area=95, search_period=30)
    assert pool == ids_page0
    assert 999 not in pool


def test_collect_pool_multi_page():
    page0 = list(range(1, 51))
    page1 = [51, 52]
    fetcher = FakeSearchFetcher(
        pages_by_group={"higher": [page0, page1]},
        total_found_by_group={"higher": 52},
    )
    pool = collect_pool(fetcher, "higher", area=95, search_period=30)
    assert pool == page0 + page1


def test_collect_pool_dedups_ids_across_pages():
    page0 = list(range(1, 51))  # полная страница (50), значит есть следующая
    page1 = [50, 51]  # id 50 повторно встретился на двух страницах
    fetcher = FakeSearchFetcher(
        pages_by_group={"higher": [page0, page1]},
        total_found_by_group={"higher": 51},
    )
    pool = collect_pool(fetcher, "higher", area=95, search_period=30)
    assert pool == page0 + [51]
    assert pool.count(50) == 1


# --- select_group_sample / run_part_b --------------------------------------

class FakeFullFetcher:
    def __init__(self, pool_ids, vacancy_states):
        self.pool_ids = pool_ids
        self.vacancy_states = vacancy_states  # {id: state_dict}

    def fetch_search_page(self, params):
        param_dict = dict(params)
        page = int(param_dict["page"])
        start, end = page * 50, page * 50 + 50
        ids = self.pool_ids[start:end]
        listings = [make_listing(vid) for vid in ids]
        state = make_search_page_with_listings(len(self.pool_ids), listings)
        return wrap_state_as_html(state), False

    def fetch_vacancy_page(self, vacancy_id):
        state = self.vacancy_states[vacancy_id]
        return wrap_state_as_html(state), False


def test_select_group_sample_meets_quota():
    pool_ids = list(range(1, 11))
    states = {vid: make_vacancy_detail(vid, company_id=vid, name=f"Вакансия {vid}") for vid in pool_ids}
    fetcher = FakeFullFetcher(pool_ids, states)

    result = select_group_sample(
        fetcher, "higher", quota=5, area=95, search_period=30, seed=42, claimed_ids=set()
    )

    assert result.pool_size == 10
    assert len(result.collected) == 5
    assert result.quota_met is True


def test_select_group_sample_pool_exhausted_before_quota():
    pool_ids = [1, 2, 3]
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in pool_ids}
    fetcher = FakeFullFetcher(pool_ids, states)

    result = select_group_sample(
        fetcher, "higher", quota=10, area=95, search_period=30, seed=42, claimed_ids=set()
    )

    assert len(result.collected) == 3
    assert result.quota_met is False


def test_select_group_sample_excludes_and_counts_reasons():
    pool_ids = [1, 2, 3]
    states = {
        1: make_vacancy_detail(1, currency="USD"),  # исключится по зарплате
        2: make_vacancy_detail(2, area_id=1, area_name="Москва"),  # не Тюмень
        3: make_vacancy_detail(3),  # ок
    }
    fetcher = FakeFullFetcher(pool_ids, states)

    result = select_group_sample(
        fetcher, "higher", quota=5, area=95, search_period=30, seed=42, claimed_ids=set()
    )

    assert len(result.collected) == 1
    assert result.excluded_counts[REASON_BAD_SALARY] == 1
    assert result.excluded_counts[REASON_WRONG_AREA] == 1


def test_select_group_sample_is_reproducible_with_same_seed():
    pool_ids = list(range(1, 21))
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in pool_ids}

    fetcher_a = FakeFullFetcher(pool_ids, states)
    result_a = select_group_sample(fetcher_a, "higher", 5, 95, 30, seed=42, claimed_ids=set())

    fetcher_b = FakeFullFetcher(pool_ids, states)
    result_b = select_group_sample(fetcher_b, "higher", 5, 95, 30, seed=42, claimed_ids=set())

    ids_a = [d.vacancy_id for d in result_a.collected]
    ids_b = [d.vacancy_id for d in result_b.collected]
    assert ids_a == ids_b


def test_select_group_sample_saves_progress_when_blocked_mid_group():
    pool_ids = [1, 2, 3, 4, 5]
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in pool_ids}

    class BlockingAfterNFetcher(FakeFullFetcher):
        def __init__(self, pool_ids, states, block_after):
            super().__init__(pool_ids, states)
            self.block_after = block_after
            self.calls = 0

        def fetch_vacancy_page(self, vacancy_id):
            self.calls += 1
            if self.calls > self.block_after:
                raise BlockedError("hh.ru вернул 403 — похоже на блокировку")
            return super().fetch_vacancy_page(vacancy_id)

    fetcher = BlockingAfterNFetcher(pool_ids, states, block_after=2)
    result = select_group_sample(
        fetcher, "higher", quota=5, area=95, search_period=30, seed=42, claimed_ids=set()
    )

    assert result.blocked_reason is not None
    assert len(result.collected) == 2  # успели собрать 2 до блокировки
    assert result.quota_met is False


def test_select_group_sample_blocked_during_pool_collection():
    class AlwaysBlockedSearchFetcher:
        def fetch_search_page(self, params):
            raise BlockedError("403")

        def fetch_vacancy_page(self, vacancy_id):
            raise AssertionError("не должно вызываться, если пул не собран")

    fetcher = AlwaysBlockedSearchFetcher()
    result = select_group_sample(
        fetcher, "higher", quota=5, area=95, search_period=30, seed=42, claimed_ids=set()
    )
    assert result.blocked_reason is not None
    assert result.pool_size == 0
    assert result.collected == []


def test_run_part_b_stops_remaining_groups_after_block_but_keeps_prior_results():
    pool_ids = list(range(1, 6))
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in pool_ids}

    class BlockOnSecondGroupFetcher:
        def __init__(self):
            self.group_calls = 0

        def fetch_search_page(self, params):
            param_dict = dict(params)
            group = param_dict["education"]
            page = int(param_dict["page"])
            if group != "higher" and page == 0:
                raise BlockedError("403")
            start, end = page * 50, page * 50 + 50
            ids = pool_ids[start:end]
            listings = [make_listing(vid) for vid in ids]
            state = make_search_page_with_listings(len(pool_ids), listings)
            return wrap_state_as_html(state), False

        def fetch_vacancy_page(self, vacancy_id):
            return wrap_state_as_html(states[vacancy_id]), False

    fetcher = BlockOnSecondGroupFetcher()
    results = run_part_b(
        fetcher,
        group_quotas=[("higher", 3), ("special_secondary", 3), ("not_required_or_not_specified", 3)],
        area=95,
        search_period=30,
        seed=42,
    )

    assert len(results["higher"].collected) == 3
    assert results["higher"].blocked_reason is None
    assert results["special_secondary"].blocked_reason is not None
    assert "not_required_or_not_specified" not in results  # не начиналась вовсе


def test_run_part_b_cross_group_duplicate_counted_once():
    # Вакансия 1 попадает в пул обеих групп (на практике не должно быть, но
    # код должен быть устойчив) — должна достаться только первой обработанной группе.
    pool_higher = [1, 2]
    pool_spo = [1, 3]
    states = {
        1: make_vacancy_detail(1, company_id=1),
        2: make_vacancy_detail(2, company_id=2),
        3: make_vacancy_detail(3, company_id=3),
    }

    class MultiGroupFetcher:
        def fetch_search_page(self, params):
            param_dict = dict(params)
            group = param_dict["education"]
            page = int(param_dict["page"])
            pool = pool_higher if group == "higher" else pool_spo
            start, end = page * 50, page * 50 + 50
            ids = pool[start:end]
            listings = [make_listing(vid) for vid in ids]
            state = make_search_page_with_listings(len(pool), listings)
            return wrap_state_as_html(state), False

        def fetch_vacancy_page(self, vacancy_id):
            return wrap_state_as_html(states[vacancy_id]), False

    fetcher = MultiGroupFetcher()
    results = run_part_b(
        fetcher,
        group_quotas=[("higher", 5), ("special_secondary", 5)],
        area=95,
        search_period=30,
        seed=42,
    )

    higher_ids = {d.vacancy_id for d in results["higher"].collected}
    spo_ids = {d.vacancy_id for d in results["special_secondary"].collected}
    assert higher_ids & spo_ids == set()  # вакансия 1 не может быть в обеих группах
    assert results["special_secondary"].excluded_counts[REASON_DUPLICATE_ACROSS_GROUPS] >= 0
