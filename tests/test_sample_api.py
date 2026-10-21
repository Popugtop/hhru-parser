from hh_parser.fetch import BlockedError
from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.sample import REASON_BAD_SALARY, REASON_EMPLOYER_CAP
from hh_parser.sample_api import (
    REASON_DUPLICATE_WITHIN_GROUP,
    collect_exhaustive_all_education_api,
    collect_pool_api,
    compute_matched_subsample,
)


def make_api_vacancy_json(
    vacancy_id: int,
    *,
    company_id: int = 1,
    company_name: str = "ООО Компания",
    name: str = "Вакансия",
    currency: str = "RUR",
    salary_mode: str = "MONTH",
    employment_form: str = "FULL",
    work_experience: str = "noExperience",
    area_id: int = 95,
    professional_role_ids: list[int] | None = None,
) -> dict:
    return {
        "id": str(vacancy_id),
        "name": name,
        "employer": {"id": str(company_id), "name": company_name},
        "area": {"id": str(area_id), "name": "Тюмень"},
        "salary_range": {"from": 50000, "to": 70000, "currency": currency, "gross": False, "mode": {"id": salary_mode}},
        "employment_form": {"id": employment_form},
        "experience": {"id": work_experience},
        "professional_roles": [{"id": str(rid)} for rid in (professional_role_ids or [96])],
        "civil_law_contracts": [],
        "work_format": [],
        "work_schedule_by_days": [],
        "working_hours": [],
        "accept_labor_contract": True,
        "internship": False,
        "published_at": "2026-10-01T10:00:00+0300",
    }


class FakeApiFetcher:
    """pools_by_education: {raw_value: [vacancy_id, ...]}; details_by_id: {id: raw json}."""

    def __init__(self, pools_by_education, details_by_id, per_page_cap: int | None = None):
        self.pools_by_education = pools_by_education
        self.details_by_id = details_by_id
        self.per_page_cap = per_page_cap
        self.search_calls = 0
        self.vacancy_calls = 0

    def search(self, params):
        self.search_calls += 1
        param_dict: dict[str, list[str]] = {}
        for k, v in params:
            param_dict.setdefault(k, []).append(v)
        page = int(param_dict["page"][0])
        per_page = int(param_dict.get("per_page", ["100"])[0])
        if self.per_page_cap is not None:
            per_page = min(per_page, self.per_page_cap)
        education = param_dict["education"][0]
        pool = self.pools_by_education.get(education, [])
        start, end = page * per_page, page * per_page + per_page
        ids = pool[start:end]
        return {"found": len(pool), "items": [{"id": str(vid)} for vid in ids]}

    def get_vacancy(self, vacancy_id):
        self.vacancy_calls += 1
        return self.details_by_id[vacancy_id]


def test_collect_pool_api_single_page():
    fetcher = FakeApiFetcher({"higher": [1, 2, 3]}, {})
    pool = collect_pool_api(fetcher, [("education", "higher")])
    assert pool == [1, 2, 3]


def test_collect_pool_api_paginates_across_pages():
    ids = list(range(1, 251))  # 250 вакансий, per_page=100 -> 3 страницы
    fetcher = FakeApiFetcher({"higher": ids}, {}, per_page_cap=100)
    pool = collect_pool_api(fetcher, [("education", "higher")])
    assert pool == ids
    assert fetcher.search_calls == 3


def test_collect_pool_api_stops_when_no_more_items():
    fetcher = FakeApiFetcher({"higher": []}, {})
    pool = collect_pool_api(fetcher, [("education", "higher")])
    assert pool == []
    assert fetcher.search_calls == 1


def test_collect_exhaustive_combines_three_education_pools():
    pools = {"higher": [1, 2], "special_secondary": [3], "not_required_or_not_specified": [4, 5]}
    details = {vid: make_api_vacancy_json(vid, company_id=vid) for vid in [1, 2, 3, 4, 5]}
    fetcher = FakeApiFetcher(pools, details)

    result = collect_exhaustive_all_education_api(fetcher, [96], area=95, period=30)
    assert len(result.collected) == 5
    assert result.raw_filter_by_vacancy_id[1] == "higher"
    assert result.raw_filter_by_vacancy_id[3] == "special_secondary"
    assert result.raw_filter_by_vacancy_id[5] == "not_required_or_not_specified"


def test_collect_exhaustive_prioritizes_higher_on_pool_overlap():
    pools = {"higher": [1], "special_secondary": [1], "not_required_or_not_specified": []}
    details = {1: make_api_vacancy_json(1, company_id=1)}
    fetcher = FakeApiFetcher(pools, details)

    result = collect_exhaustive_all_education_api(fetcher, [96], area=95, period=30)
    assert len(result.collected) == 1
    assert result.raw_filter_by_vacancy_id[1] == "higher"


def test_collect_exhaustive_no_employer_cap():
    pools = {"higher": [1, 2, 3, 4, 5], "special_secondary": [], "not_required_or_not_specified": []}
    details = {vid: make_api_vacancy_json(vid, company_id=1, name=f"Вакансия {vid}") for vid in [1, 2, 3, 4, 5]}
    fetcher = FakeApiFetcher(pools, details)

    result = collect_exhaustive_all_education_api(fetcher, [96], area=95, period=30)
    assert len(result.collected) == 5
    assert result.excluded_counts[REASON_EMPLOYER_CAP] == 0


def test_collect_exhaustive_applies_standard_exclusion_rules():
    pools = {"higher": [1], "special_secondary": [], "not_required_or_not_specified": []}
    details = {1: make_api_vacancy_json(1, currency="USD")}
    fetcher = FakeApiFetcher(pools, details)

    result = collect_exhaustive_all_education_api(fetcher, [96], area=95, period=30)
    assert len(result.collected) == 0
    assert result.excluded_counts[REASON_BAD_SALARY] == 1


def test_collect_exhaustive_blocked_mid_collection_saves_progress():
    pools = {"higher": [1, 2, 3], "special_secondary": [], "not_required_or_not_specified": []}
    details = {vid: make_api_vacancy_json(vid, company_id=vid) for vid in [1, 2, 3]}

    class BlockingFetcher(FakeApiFetcher):
        def __init__(self, *a, block_after, **kw):
            super().__init__(*a, **kw)
            self.calls = 0
            self.block_after = block_after

        def get_vacancy(self, vacancy_id):
            self.calls += 1
            if self.calls > self.block_after:
                raise BlockedError("429")
            return super().get_vacancy(vacancy_id)

    fetcher = BlockingFetcher(pools, details, block_after=1)
    result = collect_exhaustive_all_education_api(fetcher, [96], area=95, period=30)
    assert result.blocked_reason is not None
    assert len(result.collected) == 1


SPHERE_IT = "IT"
SPHERE_LAW = "Право"
SPHERE_MAP = {96: SPHERE_IT, 146: SPHERE_LAW}


def make_detail(vacancy_id: int, *, company_id: int, name: str = "Вакансия", role_id: int = 96) -> VacancyDetail:
    return VacancyDetail(
        vacancy_id=vacancy_id,
        name=name,
        link=f"https://hh.ru/vacancy/{vacancy_id}",
        company_id=company_id,
        company_name=f"Компания {company_id}",
        area_id=95,
        area_name="Тюмень",
        salary_from=50000,
        salary_to=70000,
        currency="RUR",
        gross=False,
        salary_mode="MONTH",
        employment_form="FULL",
        work_experience="noExperience",
        professional_role_ids=[role_id],
    )


def test_matched_subsample_required_side_takes_all_within_employer_cap():
    # 5 вакансий одного работодателя, разные названия — лимит 3 именно по
    # работодателю, а не по дублю работодатель+название
    collected = [make_detail(i, company_id=1, name=f"Вакансия {i}") for i in range(1, 6)]
    raw_filter = {i: "higher" for i in range(1, 6)}

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    required_in_subsample = {vid for vid in result.in_subsample_ids if vid in raw_filter}
    assert len(required_in_subsample) == 3  # лимит 3 на работодателя
    assert result.required_excluded_counts[REASON_EMPLOYER_CAP] == 2


def test_matched_subsample_target_by_sphere_from_accepted_required():
    collected = [
        make_detail(1, company_id=1, role_id=96),
        make_detail(2, company_id=2, role_id=96),
        make_detail(3, company_id=3, role_id=146),
    ]
    raw_filter = {1: "higher", 2: "higher", 3: "higher"}

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    assert result.target_by_sphere == {SPHERE_IT: 2, SPHERE_LAW: 1}


def test_matched_subsample_not_required_side_matches_target_count():
    required = [make_detail(1, company_id=1, role_id=96)]  # цель IT = 1
    not_required_pool = [make_detail(i, company_id=i, role_id=96) for i in range(10, 15)]  # 5 кандидатов
    collected = required + not_required_pool
    raw_filter = {1: "higher"}
    for d in not_required_pool:
        raw_filter[d.vacancy_id] = "not_required_or_not_specified"

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    not_required_accepted = result.in_subsample_ids - {1}
    assert len(not_required_accepted) == 1  # ровно цель (1), а не весь пул (5)


def test_matched_subsample_shortfall_when_pool_too_small():
    required = [make_detail(1, company_id=1, role_id=96), make_detail(2, company_id=2, role_id=96)]  # цель IT = 2
    not_required_pool = [make_detail(10, company_id=10, role_id=96)]  # только 1 кандидат
    collected = required + not_required_pool
    raw_filter = {1: "higher", 2: "higher", 10: "not_required_or_not_specified"}

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    assert result.shortfall_by_sphere == {SPHERE_IT: 1}


def test_matched_subsample_not_required_employer_cap_shared_across_spheres():
    required = [
        make_detail(1, company_id=100, role_id=96),  # IT, цель=1
        make_detail(2, company_id=200, role_id=146),  # Право, цель=1
    ]
    # один и тот же работодатель (company_id=5) предлагает кандидатов в обе сферы
    not_required_pool = [
        make_detail(10, company_id=5, role_id=96, name="Вакансия IT 1"),
        make_detail(11, company_id=5, role_id=96, name="Вакансия IT 2"),
        make_detail(12, company_id=5, role_id=146, name="Вакансия Право 1"),
        make_detail(13, company_id=5, role_id=146, name="Вакансия Право 2"),
    ]
    collected = required + not_required_pool
    raw_filter = {1: "higher", 2: "higher"}
    for d in not_required_pool:
        raw_filter[d.vacancy_id] = "not_required_or_not_specified"

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42, employer_cap=3)
    not_required_accepted = [vid for vid in result.in_subsample_ids if vid not in (1, 2)]
    # лимит 3 на работодателя — но целей всего 1+1=2, так что лимит здесь не должен сработать
    assert len(not_required_accepted) == 2


def test_matched_subsample_duplicate_name_within_not_required_deduped():
    required = [make_detail(1, company_id=1, role_id=96)]  # цель IT = 1
    not_required_pool = [
        make_detail(10, company_id=2, role_id=96, name="Продавец"),
        make_detail(11, company_id=2, role_id=96, name="Продавец"),  # дубль по работодателю+названию
    ]
    collected = required + not_required_pool
    raw_filter = {1: "higher", 10: "not_required_or_not_specified", 11: "not_required_or_not_specified"}

    result = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    not_required_accepted = result.in_subsample_ids - {1}
    assert len(not_required_accepted) == 1


def test_matched_subsample_is_reproducible_with_same_seed():
    collected = [make_detail(i, company_id=i, role_id=96) for i in range(1, 10)]
    raw_filter = {i: "higher" if i <= 3 else "not_required_or_not_specified" for i in range(1, 10)}

    result_a = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    result_b = compute_matched_subsample(collected, raw_filter, SPHERE_MAP, seed=42)
    assert result_a.in_subsample_ids == result_b.in_subsample_ids
