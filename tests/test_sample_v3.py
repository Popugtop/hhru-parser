from hh_parser.fetch import BlockedError
from hh_parser.sample import REASON_BAD_SALARY, REASON_EMPLOYER_CAP
from hh_parser.sample_v3 import collect_exhaustive_all_education
from tests.helpers import make_listing, make_search_page_with_listings, make_vacancy_detail, wrap_state_as_html


class FakeFetcherV3:
    """pools_by_raw_value: {raw_value: [vacancy_id, ...]}"""

    def __init__(self, pools_by_raw_value, states):
        self.pools_by_raw_value = pools_by_raw_value
        self.states = states

    def fetch_search_page(self, params):
        param_dict = dict(params)
        page = int(param_dict["page"])
        raw_value = param_dict["education"]
        pool = self.pools_by_raw_value.get(raw_value, [])
        start, end = page * 50, page * 50 + 50
        ids = pool[start:end]
        listings = [make_listing(vid) for vid in ids]
        state = make_search_page_with_listings(len(pool), listings)
        return wrap_state_as_html(state), False

    def fetch_vacancy_page(self, vacancy_id):
        return wrap_state_as_html(self.states[vacancy_id]), False


def test_collects_all_three_raw_education_pools_combined():
    pools = {"higher": [1, 2], "special_secondary": [3], "not_required_or_not_specified": [4, 5]}
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in [1, 2, 3, 4, 5]}
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert len(result.collected) == 5
    assert result.raw_filter_by_vacancy_id[1] == "higher"
    assert result.raw_filter_by_vacancy_id[3] == "special_secondary"
    assert result.raw_filter_by_vacancy_id[5] == "not_required_or_not_specified"


def test_prioritizes_higher_over_other_raw_values_on_overlap():
    # id=1 появляется и в higher, и в special_secondary -> должен остаться higher
    pools = {"higher": [1], "special_secondary": [1], "not_required_or_not_specified": []}
    states = {1: make_vacancy_detail(1, company_id=1)}
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert len(result.collected) == 1
    assert result.raw_filter_by_vacancy_id[1] == "higher"


def test_no_employer_cap_applied():
    # 5 вакансий одного работодателя — лимита 3 здесь нет
    pools = {"higher": [1, 2, 3, 4, 5], "special_secondary": [], "not_required_or_not_specified": []}
    states = {
        vid: make_vacancy_detail(vid, company_id=1, name=f"Вакансия {vid}") for vid in [1, 2, 3, 4, 5]
    }
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert len(result.collected) == 5
    assert result.excluded_counts[REASON_EMPLOYER_CAP] == 0


def test_standard_exclusion_rules_still_apply():
    pools = {"higher": [1], "special_secondary": [], "not_required_or_not_specified": []}
    states = {1: make_vacancy_detail(1, currency="USD")}
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert len(result.collected) == 0
    assert result.excluded_counts[REASON_BAD_SALARY] == 1


def test_duplicate_name_dedup_applies_globally():
    pools = {"higher": [1], "special_secondary": [2], "not_required_or_not_specified": []}
    states = {
        1: make_vacancy_detail(1, company_id=1, name="Продавец"),
        2: make_vacancy_detail(2, company_id=1, name="Продавец"),
    }
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert len(result.collected) == 1  # второй — дубль по работодателю+названию


def test_blocked_mid_collection_saves_progress():
    pools = {"higher": [1, 2, 3], "special_secondary": [], "not_required_or_not_specified": []}
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in [1, 2, 3]}

    class BlockingFetcher(FakeFetcherV3):
        def __init__(self, *a, block_after, **kw):
            super().__init__(*a, **kw)
            self.calls = 0
            self.block_after = block_after

        def fetch_vacancy_page(self, vacancy_id):
            self.calls += 1
            if self.calls > self.block_after:
                raise BlockedError("403")
            return super().fetch_vacancy_page(vacancy_id)

    fetcher = BlockingFetcher(pools, states, block_after=1)
    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert result.blocked_reason is not None
    assert len(result.collected) == 1


def test_pool_size_by_raw_filter_tracked():
    pools = {"higher": [1, 2], "special_secondary": [3], "not_required_or_not_specified": []}
    states = {vid: make_vacancy_detail(vid, company_id=vid) for vid in [1, 2, 3]}
    fetcher = FakeFetcherV3(pools, states)

    result = collect_exhaustive_all_education(fetcher, [96], area=95, search_period=30)
    assert result.pool_size_by_raw_filter == {"higher": 2, "special_secondary": 1, "not_required_or_not_specified": 0}
