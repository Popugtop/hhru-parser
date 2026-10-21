import dataclasses
from pathlib import Path

from hh_parser.parse_vacancy import html_to_text, parse_vacancy_detail
from hh_parser.ssr import extract_initial_state

FIXTURES = Path(__file__).parent / "fixtures"


def load_vacancy_state(filename: str):
    page_html = (FIXTURES / filename).read_text(encoding="utf-8")
    return extract_initial_state(page_html)


def test_parse_courier_vacancy():
    state = load_vacancy_state("vacancy_page.html")
    detail = parse_vacancy_detail(state)

    assert detail.vacancy_id == 137413813
    assert detail.name == "Курьер в Додо Пицца"
    assert detail.link == "https://hh.ru/vacancy/137413813"
    assert detail.company_id == 3612099
    assert detail.company_name == "Додо Пицца Тюмень"
    assert detail.area_id == 95
    assert detail.area_name == "Тюмень"
    assert detail.salary_from == 97000
    assert detail.salary_to == 183050
    assert detail.currency == "RUR"
    assert detail.gross is False
    assert detail.salary_mode == "MONTH"
    assert detail.employment_form == "FULL"
    assert detail.work_experience == "noExperience"
    assert detail.professional_role_ids == [58]
    assert detail.accept_labor_contract is False
    assert detail.civil_law_contracts == []
    assert detail.internship is False
    assert detail.work_formats == ["FIELD_WORK"]
    assert detail.work_schedule_by_days == ["OTHER"]
    assert detail.working_hours == ["OTHER"]
    assert detail.publication_date == "2026-09-16"


def test_parse_vacancy_with_civil_law_contracts():
    state = load_vacancy_state("vacancy_page_2.html")
    detail = parse_vacancy_detail(state)
    assert detail.civil_law_contracts == [
        "SELF_EMPLOYED",
        "INDIVIDUAL_ENTREPRENEUR",
        "INDIVIDUAL_PERSON",
    ]
    assert detail.work_formats == ["FIELD_WORK"]
    assert detail.salary_from == 104000
    assert detail.salary_to == 200000


def test_description_html_is_converted_to_plain_text():
    state = load_vacancy_state("vacancy_page.html")
    detail = parse_vacancy_detail(state)
    assert "<" not in detail.description_text
    assert "Додо" in detail.description_text or len(detail.description_text) > 0


def test_personal_data_not_present_in_parsed_detail():
    """employerManager (ФИО менеджера) не должен попасть ни в одно поле VacancyDetail."""
    state = load_vacancy_state("vacancy_page.html")
    vac_raw = state["vacancyView"]["vacancyFull"]["vacancy"]
    assert "employerManager" in vac_raw  # сверяем, что фикстура реально его содержит

    detail = parse_vacancy_detail(state)
    field_names = {f.name for f in dataclasses.fields(detail)}
    assert "employerManager" not in field_names
    assert "contactInfo" not in field_names

    manager_name = vac_raw["employerManager"].get("firstName", "")
    serialized = " ".join(str(v) for v in dataclasses.asdict(detail).values())
    assert manager_name not in serialized


def test_html_to_text_strips_tags_and_entities():
    raw = "<p>Привет &amp; пока</p><br/><div>Вторая строка</div>"
    text = html_to_text(raw)
    assert text == "Привет & пока\nВторая строка"


def test_html_to_text_empty_input():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_html_to_text_truncates_long_description():
    long_html = "<p>" + ("a" * 50_000) + "</p>"
    text = html_to_text(long_html)
    assert len(text) == 30_000
