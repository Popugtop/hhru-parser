from hh_parser.codes import (
    CIVIL_LAW_CONTRACTS,
    EMPLOYMENT_FORM,
    WORK_FORMAT,
    WORK_SCHEDULE_BY_DAYS,
    WORKING_HOURS,
    translate,
    translate_list,
)


def test_work_format_known_codes():
    assert translate(WORK_FORMAT, "HYBRID") == "гибрид"
    assert translate(WORK_FORMAT, "REMOTE") == "удалённо"
    assert translate(WORK_FORMAT, "ON_SITE") == "на месте работодателя"
    assert translate(WORK_FORMAT, "FIELD_WORK") == "разъездной"


def test_schedule_known_codes():
    assert translate(WORK_SCHEDULE_BY_DAYS, "FIVE_ON_TWO_OFF") == "5/2"
    assert translate(WORK_SCHEDULE_BY_DAYS, "TWO_ON_TWO_OFF") == "2/2"
    assert translate(WORK_SCHEDULE_BY_DAYS, "WEEKEND") == "по выходным"


def test_working_hours_known_codes():
    assert translate(WORKING_HOURS, "HOURS_8") == "8 часов"
    assert translate(WORKING_HOURS, "FLEXIBLE") == "по договорённости"


def test_employment_form_known_codes():
    assert translate(EMPLOYMENT_FORM, "FULL") == "полная занятость"
    assert translate(EMPLOYMENT_FORM, "FLY_IN_FLY_OUT") == "вахта"


def test_civil_law_contracts_known_codes():
    assert translate(CIVIL_LAW_CONTRACTS, "SELF_EMPLOYED") == "самозанятость"
    assert translate(CIVIL_LAW_CONTRACTS, "INDIVIDUAL_ENTREPRENEUR") == "ИП"
    assert translate(CIVIL_LAW_CONTRACTS, "INDIVIDUAL_PERSON") == "физлицо"


def test_unknown_code_is_visible_not_silent():
    result = translate(WORK_FORMAT, "SOME_NEW_CODE")
    assert "SOME_NEW_CODE" in result
    assert result != "SOME_NEW_CODE"  # явно помечено как неизвестное


def test_translate_none_returns_none():
    assert translate(WORK_FORMAT, None) is None


def test_translate_list_joins_with_comma():
    result = translate_list(CIVIL_LAW_CONTRACTS, ["SELF_EMPLOYED", "INDIVIDUAL_ENTREPRENEUR"])
    assert result == "самозанятость, ИП"


def test_translate_list_empty_returns_empty_string():
    assert translate_list(WORK_FORMAT, []) == ""
    assert translate_list(WORK_FORMAT, None) == ""
