from pathlib import Path

import pytest

from hh_parser.ssr import SSRExtractionError, extract_initial_state, looks_like_captcha_or_block

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_from_search_fixture():
    page_html = (FIXTURES / "search_page.html").read_text(encoding="utf-8")
    data = extract_initial_state(page_html)
    assert "vacancySearchResult" in data
    assert "searchClusters" in data
    assert "searchCounts" in data


def test_extract_from_vacancy_fixture():
    page_html = (FIXTURES / "vacancy_page.html").read_text(encoding="utf-8")
    data = extract_initial_state(page_html)
    assert "vacancyView" in data


def test_extract_missing_template_raises():
    with pytest.raises(SSRExtractionError):
        extract_initial_state("<html><body>no template here</body></html>")


def test_extract_broken_json_raises():
    broken = '<template id="HH-Lux-InitialState">{not valid json</template>'
    with pytest.raises(SSRExtractionError):
        extract_initial_state(broken)


def test_attribute_order_independent():
    # style перед id, как в реальном hh.ru, и id перед style — оба должны работать
    page_a = '<template style="display:none" id="HH-Lux-InitialState">{"a": 1}</template>'
    page_b = '<template id="HH-Lux-InitialState" style="display:none">{"a": 1}</template>'
    assert extract_initial_state(page_a) == {"a": 1}
    assert extract_initial_state(page_b) == {"a": 1}


def test_looks_like_captcha_or_block_false_for_normal_page():
    page_html = (FIXTURES / "search_page.html").read_text(encoding="utf-8")
    assert looks_like_captcha_or_block(page_html) is False


def test_looks_like_captcha_or_block_true():
    page_html = '<html><head><title>Доступ ограничен</title></head><body>Доступ ограничен</body></html>'
    assert looks_like_captcha_or_block(page_html) is True
