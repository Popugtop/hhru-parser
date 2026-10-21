import datetime as dt
import json

import pytest

from hh_parser.api_client import ApiFetcher, _cache_key, _strip_private_fields, load_env
from hh_parser.fetch import BlockedError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, url="https://api.hh.ru/vacancies"):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.headers = headers or {}
        self.url = url

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_fetcher(tmp_path, pause_min=0.0, pause_max=0.0):
    return ApiFetcher(
        access_token="secret-token-value",
        user_agent="TestApp/1.0 (test@example.com)",
        cache_dir=tmp_path / "cache",
        pause_min=pause_min,
        pause_max=pause_max,
    )


def test_strip_private_fields_removes_contacts_at_any_depth():
    data = {
        "id": "1",
        "contacts": {"name": "Иванов", "phones": [{"number": "+7900..."}]},
        "items": [{"id": "2", "contacts": {"name": "Петров"}}],
    }
    cleaned = _strip_private_fields(data)
    assert "contacts" not in cleaned
    assert "contacts" not in cleaned["items"][0]
    assert cleaned["items"][0]["id"] == "2"


def test_load_env_parses_key_value_pairs(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("HH_ACCESS_TOKEN=abc123\nHH_USER_AGENT=MyApp/1.0 (me@example.com)\n", encoding="utf-8")
    env = load_env(env_path)
    assert env == {"HH_ACCESS_TOKEN": "abc123", "HH_USER_AGENT": "MyApp/1.0 (me@example.com)"}


def test_load_env_missing_file_returns_empty_dict(tmp_path):
    assert load_env(tmp_path / "does_not_exist.env") == {}


def test_load_env_ignores_comments_and_blank_lines(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# comment\n\nHH_ACCESS_TOKEN=xyz\n", encoding="utf-8")
    assert load_env(env_path) == {"HH_ACCESS_TOKEN": "xyz"}


def test_search_sends_bearer_and_hh_user_agent_headers(tmp_path):
    fetcher = make_fetcher(tmp_path)
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["auth_header"] = fetcher.session.headers.get("Authorization")
        captured["ua_header"] = fetcher.session.headers.get("HH-User-Agent")
        return FakeResponse(json_data={"found": 0, "items": []})

    fetcher.session.get = fake_get
    fetcher.search([("area", "95")])

    assert captured["auth_header"] == "Bearer secret-token-value"
    assert captured["ua_header"] == "TestApp/1.0 (test@example.com)"


def test_search_caches_response_to_disk(tmp_path):
    fetcher = make_fetcher(tmp_path)
    calls = []

    def fake_get(url, params, timeout):
        calls.append(1)
        return FakeResponse(json_data={"found": 5, "items": []})

    fetcher.session.get = fake_get
    data1 = fetcher.search([("area", "95")])
    data2 = fetcher.search([("area", "95")])

    assert data1 == data2 == {"found": 5, "items": []}
    assert len(calls) == 1  # второй вызов — из кэша


def test_cache_key_with_same_params_but_different_date_tag_differs():
    params = [("area", "95")]
    key_day1 = _cache_key("https://api.hh.ru/vacancies", params, date_tag="2026-10-09")
    key_day2 = _cache_key("https://api.hh.ru/vacancies", params, date_tag="2026-10-21")
    assert key_day1 != key_day2


def test_cache_key_without_date_tag_is_stable_across_calls():
    params = [("area", "95")]
    assert _cache_key("https://api.hh.ru/vacancies", params) == _cache_key(
        "https://api.hh.ru/vacancies", params
    )


class FixedDate(dt.date):
    """Фиксирует date.today() для теста (нельзя подменить time.time здесь,
    т.к. api_client использует datetime.date.today(), не time.time)."""

    _fixed: dt.date = dt.date(2026, 10, 9)

    @classmethod
    def today(cls):
        return cls._fixed


def test_search_does_not_reuse_cache_from_a_previous_day(tmp_path, monkeypatch):
    """Регрессия 2026-10-21: запуск через 12 дней вернул побайтово те же
    счётчики, что и первый раз, потому что ключ кэша search() не включал
    дату — сеть не трогали вообще, хотя отчёт выглядел как «свежий»."""
    fetcher = make_fetcher(tmp_path)
    calls = []

    def fake_get(url, params, timeout):
        calls.append(1)
        return FakeResponse(json_data={"found": len(calls), "items": []})

    fetcher.session.get = fake_get

    FixedDate._fixed = dt.date(2026, 10, 9)
    monkeypatch.setattr("hh_parser.api_client.date", FixedDate)
    data_day1 = fetcher.search([("area", "95")])
    assert data_day1 == {"found": 1, "items": []}

    FixedDate._fixed = dt.date(2026, 10, 21)
    data_day2 = fetcher.search([("area", "95")])

    assert len(calls) == 2  # второй день -> новый сетевой запрос, не кэш первого дня
    assert data_day2 == {"found": 2, "items": []}


def test_cached_response_has_contacts_stripped(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(
        json_data={"found": 1, "items": [{"id": "1", "contacts": {"name": "Секрет"}}]}
    )
    fetcher.search([("area", "95")])

    cache_files = list((tmp_path / "cache" / "api_search").glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert "contacts" not in cached["items"][0]


def test_get_vacancy_strips_contacts_before_returning(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(
        json_data={"id": "42", "contacts": {"name": "Секрет", "phones": [{"number": "+7900000"}]}}
    )
    result = fetcher.get_vacancy(42)
    assert "contacts" not in result


def test_403_raises_blocked_error(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=403)
    with pytest.raises(BlockedError):
        fetcher.search([("area", "95")])


def test_401_raises_blocked_error(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=401)
    with pytest.raises(BlockedError):
        fetcher.get_vacancy(1)


def test_403_error_message_never_contains_token(tmp_path):
    fetcher = make_fetcher(tmp_path)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=403)
    with pytest.raises(BlockedError) as exc_info:
        fetcher.search([("area", "95")])
    assert "secret-token-value" not in str(exc_info.value)


def test_429_retries_then_succeeds(tmp_path, monkeypatch):
    fetcher = make_fetcher(tmp_path)
    monkeypatch.setattr("hh_parser.api_client.time.sleep", lambda s: None)
    calls = {"n": 0}

    def fake_get(url, params, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeResponse(status_code=429, headers={"Retry-After": "1"})
        return FakeResponse(json_data={"found": 0, "items": []})

    fetcher.session.get = fake_get
    data = fetcher.search([("area", "95")])
    assert data == {"found": 0, "items": []}
    assert calls["n"] == 3


def test_429_persisting_raises_blocked_error(tmp_path, monkeypatch):
    fetcher = make_fetcher(tmp_path)
    monkeypatch.setattr("hh_parser.api_client.time.sleep", lambda s: None)
    fetcher.session.get = lambda *a, **k: FakeResponse(status_code=429)
    with pytest.raises(BlockedError):
        fetcher.search([("area", "95")])


def test_polite_wait_skipped_on_first_request_and_applied_on_second(tmp_path, monkeypatch):
    fetcher = make_fetcher(tmp_path, pause_min=0.5, pause_max=1.0)
    fetcher.session.get = lambda *a, **k: FakeResponse(json_data={"id": "1"})

    sleep_calls = []
    monkeypatch.setattr("hh_parser.api_client.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr("hh_parser.api_client.random.uniform", lambda a, b: 0.7)

    fetcher.get_vacancy(1)
    assert sleep_calls == []  # первый запрос без паузы

    fetcher.get_vacancy(2)
    assert sleep_calls == [0.7]
