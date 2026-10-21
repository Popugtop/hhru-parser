from pathlib import Path

from hh_parser.parse_search import (
    get_education_counts,
    get_total_found,
    parse_search_page,
)
from hh_parser.ssr import extract_initial_state

FIXTURES = Path(__file__).parent / "fixtures"


def load_search_state():
    page_html = (FIXTURES / "search_page.html").read_text(encoding="utf-8")
    return extract_initial_state(page_html)


def test_get_total_found():
    state = load_search_state()
    assert get_total_found(state) == 2183


def test_get_education_counts():
    state = load_search_state()
    counts = get_education_counts(state)
    assert counts == {
        "not_required_or_not_specified": 1944,
        "higher": 182,
        "special_secondary": 106,
    }


def test_parse_search_page_vacancies():
    state = load_search_state()
    result = parse_search_page(state)
    assert result.total_found == 2183
    assert len(result.vacancies) == 5
    ids = {v.vacancy_id for v in result.vacancies}
    assert 137413813 in ids
    assert 125200349 in ids  # вакансия с civilLawContracts


def test_vacancy_listing_basic_fields():
    state = load_search_state()
    result = parse_search_page(state)
    courier = next(v for v in result.vacancies if v.vacancy_id == 137413813)
    assert courier.name == "Курьер в Додо Пицца"
    assert courier.company_id == 3612099
    assert courier.area_id == 95
    assert courier.area_name == "Тюмень"
    assert courier.salary_from == 97000
    assert courier.salary_to == 183050
    assert courier.currency == "RUR"
    assert courier.gross is False
    assert courier.salary_mode == "MONTH"
    assert courier.employment_form == "FULL"
    assert courier.work_experience == "noExperience"
    assert courier.professional_role_ids == [58]
    assert "hh.ru/vacancy/137413813" in courier.link


def test_vacancy_listing_link_falls_back_when_missing():
    from hh_parser.parse_search import parse_vacancy_listing

    raw = {
        "vacancyId": 999,
        "name": "Test",
        "company": {},
        "compensation": {},
        "area": {},
    }
    listing = parse_vacancy_listing(raw)
    assert listing.link == "https://hh.ru/vacancy/999"
