from hh_parser.columns_v2 import COLUMNS as COLUMNS_V2
from hh_parser.columns_v3_api import COLUMNS


def test_columns_v3_api_has_two_more_than_v2():
    assert len(COLUMNS) == len(COLUMNS_V2) + 2


def test_in_matched_subsample_column_right_after_education_filter_label():
    keys = [c.key for c in COLUMNS]
    idx_filter = keys.index("education_group_filter_label")
    assert keys[idx_filter + 1] == "in_matched_subsample"


def test_employer_sequence_column_right_after_employer_id():
    keys = [c.key for c in COLUMNS]
    idx_employer = keys.index("employer_id")
    assert keys[idx_employer + 1] == "employer_sequence_number"


def test_all_v2_columns_still_present_in_order():
    v3_keys = [c.key for c in COLUMNS]
    v2_keys = [c.key for c in COLUMNS_V2]
    filtered = [k for k in v3_keys if k in v2_keys]
    assert filtered == v2_keys


def test_header_text_matches_requested_wording():
    headers = {c.key: c.header for c in COLUMNS}
    assert headers["in_matched_subsample"] == "В подвыборке с одинаковым составом сфер"
    assert headers["employer_sequence_number"] == "Номер вакансии работодателя в выборке"
