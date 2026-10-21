from hh_parser.rows import FinalRow
from hh_parser.summary import compute_group_summaries


def make_row(**overrides) -> FinalRow:
    base = dict(
        education_group_filter="higher",
        education_group="Высшее",
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
    )
    base.update(overrides)
    return FinalRow(**base)


def test_compute_group_summaries_counts_and_order():
    rows = [
        make_row(vacancy_id=1, education_group_filter="higher"),
        make_row(vacancy_id=2, education_group_filter="higher"),
        make_row(vacancy_id=3, education_group_filter="special_secondary"),
    ]
    summaries = compute_group_summaries(rows)
    labels = [s.group_filter for s in summaries]
    assert labels == ["higher", "not_required_or_not_specified", "special_secondary"]
    by_filter = {s.group_filter: s for s in summaries}
    assert by_filter["higher"].count == 2
    assert by_filter["not_required_or_not_specified"].count == 0
    assert by_filter["special_secondary"].count == 1


def test_compute_group_summaries_median_and_mean():
    rows = [
        make_row(vacancy_id=1, salary_net_estimate=40000),
        make_row(vacancy_id=2, salary_net_estimate=60000),
        make_row(vacancy_id=3, salary_net_estimate=80000),
    ]
    summaries = compute_group_summaries(rows)
    higher = next(s for s in summaries if s.group_filter == "higher")
    assert higher.median_salary_net == 60000
    assert higher.mean_salary_net == 60000


def test_compute_group_summaries_shares():
    rows = [
        make_row(vacancy_id=1, labor_contract=True, dms=True, training_mentorship=True, work_formats=["REMOTE"], sector="бюджетный"),
        make_row(vacancy_id=2, labor_contract=False, dms=False, training_mentorship=False, work_formats=["ON_SITE"], sector="коммерческий"),
    ]
    summaries = compute_group_summaries(rows)
    higher = next(s for s in summaries if s.group_filter == "higher")
    assert higher.share_labor_contract == 50.0
    assert higher.share_dms == 50.0
    assert higher.share_training == 50.0
    assert higher.share_remote == 50.0
    assert higher.share_budget == 50.0


def test_compute_group_summaries_empty_group_has_none_stats():
    summaries = compute_group_summaries([])
    for s in summaries:
        assert s.count == 0
        assert s.median_salary_net is None
        assert s.mean_salary_net is None
        assert s.share_labor_contract is None
