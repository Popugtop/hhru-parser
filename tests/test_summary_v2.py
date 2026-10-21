from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED, FinalRowV2
from hh_parser.summary_v2 import compute_group_summaries_v2


def make_row(**overrides) -> FinalRowV2:
    base = dict(
        education_group_2=EDUCATION_GROUP_2_REQUIRED,
        education_group_filter="higher",
        education_group_filter_label="Высшее",
        vacancy_id=1,
        link="https://hh.ru/vacancy/1",
        name="Вакансия",
        employer="Компания",
        employer_id=1,
        sector="коммерческий",
        profession_role="Роль",
        role_category="Категория",
        sphere="IT",
        it_accreditation=False,
        publication_date="2026-10-01",
        salary_from=50000,
        salary_to=50000,
        gross=False,
        salary_net_estimate=50000,
        labor_contract=True,
        civil_law_contract_options=[],
        internship=False,
        work_formats=["ON_SITE"],
        schedule=["FIVE_ON_TWO_OFF"],
        hours=["HOURS_8"],
        dms=False,
        training_mentorship=False,
        education_in_text="не указано",
        education_mismatch=False,
        is_senior_role=False,
    )
    base.update(overrides)
    return FinalRowV2(**base)


def test_compute_group_summaries_v2_two_groups_in_order():
    summaries = compute_group_summaries_v2([])
    labels = [s.group_label for s in summaries]
    assert labels == [EDUCATION_GROUP_2_REQUIRED, EDUCATION_GROUP_2_NOT_REQUIRED]


def test_compute_group_summaries_v2_counts():
    rows = [
        make_row(vacancy_id=1, education_group_2=EDUCATION_GROUP_2_REQUIRED),
        make_row(vacancy_id=2, education_group_2=EDUCATION_GROUP_2_REQUIRED),
        make_row(vacancy_id=3, education_group_2=EDUCATION_GROUP_2_NOT_REQUIRED),
    ]
    summaries = compute_group_summaries_v2(rows)
    by_label = {s.group_label: s for s in summaries}
    assert by_label[EDUCATION_GROUP_2_REQUIRED].count == 2
    assert by_label[EDUCATION_GROUP_2_NOT_REQUIRED].count == 1


def test_compute_group_summaries_v2_median_and_shares():
    rows = [
        make_row(vacancy_id=1, salary_net_estimate=60000, labor_contract=True, dms=True, sector="бюджетный"),
        make_row(vacancy_id=2, salary_net_estimate=100000, labor_contract=False, dms=False, sector="коммерческий"),
    ]
    summaries = compute_group_summaries_v2(rows)
    required = next(s for s in summaries if s.group_label == EDUCATION_GROUP_2_REQUIRED)
    assert required.median_salary_net == 80000
    assert required.share_labor_contract == 50.0
    assert required.share_dms == 50.0
    assert required.share_budget == 50.0


def test_compute_group_summaries_v2_empty_group_has_none_stats():
    summaries = compute_group_summaries_v2([])
    for s in summaries:
        assert s.count == 0
        assert s.median_salary_net is None
        assert s.share_labor_contract is None
