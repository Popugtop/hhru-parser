import pytest

from hh_parser.fetch import BlockedError, Fetcher


class FakeResponse:
    def __init__(self, status_code=200, text="<html>ok</html>"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code not in (403, 429):
            raise RuntimeError(f"HTTP {self.status_code}")


def make_fetcher(tmp_path, pause_min=0.0, pause_max=0.0):
    return Fetcher(cache_dir=tmp_path / "cache", pause_min=pause_min, pause_max=pause_max)


def test_cache_miss_fetches_and_writes_cache(tmp_path, monkeypatch):
    fetcher = make_fetcher(tmp_path)
    calls = []

    def fake_get(url, timeout, allow_redirects):
        calls.append(url)
        return FakeResponse(text="<html>search page</html>")

    fetcher.session.get = fake_get
    html_text, from_cache = fetcher.fetch_search_page([("area", "95"), ("page", "0")])

    assert html_text == "<html>search page</html>"
    assert from_cache is False
    assert len(calls) == 1
    cached_files = list((tmp_path / "cache" / "search").glob("*.html"))
    assert len(cached_files) == 1


def test_cache_hit_skips_network(tmp_path):
    fetcher = make_fetcher(tmp_path)
    cache_dir = tmp_path / "cache" / "search"
    cache_dir.mkdir(parents=True, exist_ok=True)

    from hh_parser.fetch import _cache_key

    params = [("area", "95"), ("page", "0"), ("items_on_page", "50")]
    key = _cache_key(params)
    (cache_dir / f"{key}.html").write_text("<html>from cache</html>", encoding="utf-8")

    def fail_get(*args, **kwargs):
        raise AssertionError("Сеть не должна вызываться при попадании в кэш")

    fetcher.session.get = fail_get
    html_text, from_cache = fetcher.fetch_search_page([("area", "95"), ("page", "0")])

    assert html_text == "<html>from cache</html>"
    assert from_cache is True


def test_cache_key_independent_of_param_order(tmp_path):
    from hh_parser.fetch import _cache_key

    key_a = _cache_key([("area", "95"), ("page", "0")])
    key_b = _cache_key([("page", "0"), ("area", "95")])
    assert key_a == key_b


def test_403_raises_blocked_error(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=403)
    with pytest.raises(BlockedError):
        fetcher.fetch_search_page([("area", "95")])


def test_429_raises_blocked_error(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=429)
    with pytest.raises(BlockedError):
        fetcher.fetch_vacancy_page(123)


def test_captcha_like_page_raises_blocked_error(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(
        text="<html><head><title>Доступ ограничен</title></head></html>"
    )
    with pytest.raises(BlockedError):
        fetcher.fetch_vacancy_page(123)


def test_blocked_response_not_cached(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=403)
    with pytest.raises(BlockedError):
        fetcher.fetch_vacancy_page(123)
    assert not list((tmp_path / "cache" / "vacancy").glob("*.html"))


def test_polite_wait_skipped_on_first_request_and_applied_on_second(tmp_path, monkeypatch):
    fetcher = make_fetcher(tmp_path, pause_min=2.0, pause_max=4.0)
    fetcher.session.get = lambda *a, **k: FakeResponse(text="<html>ok</html>")

    sleep_calls = []
    monkeypatch.setattr("hh_parser.fetch.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr("hh_parser.fetch.random.uniform", lambda a, b: 3.0)

    fetcher.fetch_vacancy_page(1)
    assert sleep_calls == []  # первый запрос без паузы

    fetcher.fetch_vacancy_page(2)
    assert sleep_calls == [3.0]  # перед вторым запросом пауза применена
