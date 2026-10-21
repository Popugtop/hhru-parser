from hh_parser.manual_overrides import MANUAL_REVIEW_OVERRIDES, apply_manual_override
from hh_parser.rows_v2 import EDUCATION_GROUP_2_REQUIRED, SENIOR_ROLE_COMMENT, FinalRowV2


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


def test_apply_manual_override_known_vacancy():
    row = make_row(
        vacancy_id=137188842, is_senior_role=True, comment=SENIOR_ROLE_COMMENT,
    )
    apply_manual_override(row)
    assert row.verified_manually == "да"
    assert row.comment == MANUAL_REVIEW_OVERRIDES[137188842]
    assert row.is_senior_role is True  # фактический флаг не меняется


def test_apply_manual_override_unknown_vacancy_is_noop():
    row = make_row(vacancy_id=999, comment="", verified_manually="")
    apply_manual_override(row)
    assert row.verified_manually == ""
    assert row.comment == ""
