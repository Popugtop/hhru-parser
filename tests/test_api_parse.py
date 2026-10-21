import json
from pathlib import Path

from hh_parser.api_parse import (
    get_education_cluster_counts,
    get_found,
    get_vacancy_ids,
    parse_vacancy_detail_api,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_get_found_reads_real_search_response():
    response = load_fixture("api_search_response.json")
    assert get_found(response) == 10


def test_get_vacancy_ids_returns_ints_not_strings():
    response = load_fixture("api_search_response.json")
    ids = get_vacancy_ids(response)
    assert ids == [137024523, 138238935, 103020339]
    assert all(isinstance(vid, int) for vid in ids)


def test_get_education_cluster_counts_parses_real_cluster():
    response = load_fixture("api_search_response.json")
    counts = get_education_cluster_counts(response)
    assert counts == {
        "not_required_or_not_specified": 5,
        "higher": 5,
        "special_secondary": 1,
    }


def test_get_education_cluster_counts_missing_clusters_returns_empty():
    assert get_education_cluster_counts({"found": 0, "items": []}) == {}


def test_parse_vacancy_detail_api_real_fixture_casts_ids_to_int():
    detail_json = load_fixture("api_vacancy_detail.json")
    detail = parse_vacancy_detail_api(detail_json)

    assert isinstance(detail.vacancy_id, int)
    assert detail.vacancy_id == 137024523
    assert isinstance(detail.company_id, int)
    assert detail.company_id == 13012813
    assert detail.area_id == 95
    assert detail.professional_role_ids == [146]
    assert all(isinstance(rid, int) for rid in detail.professional_role_ids)


def test_parse_vacancy_detail_api_extracts_nested_id_objects():
    detail_json = load_fixture("api_vacancy_detail.json")
    detail = parse_vacancy_detail_api(detail_json)

    assert detail.employment_form == "FULL"
    assert detail.work_experience == "noExperience"
    assert detail.salary_mode == "MONTH"
    assert detail.currency == "RUR"
    assert detail.gross is True
    assert detail.salary_from == 80000
    assert detail.salary_to is None


def test_parse_vacancy_detail_api_code_lists_extract_ids_only():
    detail_json = load_fixture("api_vacancy_detail.json")
    detail = parse_vacancy_detail_api(detail_json)

    assert detail.work_formats == ["ON_SITE"]
    assert set(detail.civil_law_contracts) == {
        "SELF_EMPLOYED",
        "INDIVIDUAL_ENTREPRENEUR",
        "INDIVIDUAL_PERSON",
    }
    assert "SIX_ON_ONE_OFF" in detail.work_schedule_by_days


def test_parse_vacancy_detail_api_publication_date_truncated_to_day():
    detail_json = load_fixture("api_vacancy_detail.json")
    detail = parse_vacancy_detail_api(detail_json)
    assert detail.publication_date == "2026-10-08"


def test_parse_vacancy_detail_api_description_is_plain_text():
    detail_json = load_fixture("api_vacancy_detail.json")
    detail = parse_vacancy_detail_api(detail_json)
    assert "<" not in detail.description_text
    assert "юрист" in detail.description_text.lower()


def test_parse_vacancy_detail_api_never_reads_contacts():
    detail_json = load_fixture("api_vacancy_detail.json")
    assert "contacts" in detail_json  # сырой ответ содержит поле...
    detail = parse_vacancy_detail_api(detail_json)
    assert not hasattr(detail, "contacts")  # ...но VacancyDetail его не содержит


def test_parse_vacancy_detail_api_handles_missing_salary_range():
    minimal = {
        "id": "1",
        "name": "Тест",
        "employer": {"id": "10", "name": "Компания"},
        "area": {"id": "95", "name": "Тюмень"},
    }
    detail = parse_vacancy_detail_api(minimal)
    assert detail.salary_from is None
    assert detail.salary_to is None
    assert detail.salary_mode is None
    assert detail.employment_form is None
    assert detail.work_experience is None
    assert detail.work_formats == []
