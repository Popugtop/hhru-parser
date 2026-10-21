import json

from hh_parser.cli import build_arg_parser, fetch_professional_roles, main


def test_build_arg_parser_defaults():
    args = build_arg_parser().parse_args([])
    assert args.area == 95
    assert args.search_period == 30
    assert args.seed == 42
    assert args.pause_min == 2.0
    assert args.pause_max == 4.0
    assert args.quota_higher == 80
    assert args.quota_not_required == 80
    assert args.quota_special_secondary == 40
    assert args.probe is False
    assert args.source == "hh"


def test_build_arg_parser_overrides():
    args = build_arg_parser().parse_args(
        ["--quota-higher", "5", "--quota-not-required", "5", "--quota-special-secondary", "5", "--probe"]
    )
    assert args.quota_higher == 5
    assert args.probe is True


def test_source_tv_not_implemented_returns_error(tmp_path, capsys):
    exit_code = main(["--source", "tv", "--cache-dir", str(tmp_path / "cache"), "--output-dir", str(tmp_path / "out")])
    assert exit_code == 1
    assert not (tmp_path / "cache").exists()  # не должно создавать сетевых объектов для tv


def test_fetch_professional_roles_uses_cache_without_network(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_data = {"categories": [{"id": 1, "name": "Тест", "roles": []}]}
    (cache_dir / "professional_roles.json").write_text(json.dumps(cached_data), encoding="utf-8")

    def fail_get(*args, **kwargs):
        raise AssertionError("Не должно обращаться к сети при наличии кэша")

    monkeypatch.setattr("hh_parser.cli.requests.get", fail_get)
    data = fetch_professional_roles(cache_dir)
    assert data == cached_data


def test_fetch_professional_roles_fetches_and_writes_cache(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"categories": []}

    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr("hh_parser.cli.requests.get", fake_get)
    data = fetch_professional_roles(cache_dir)

    assert data == {"categories": []}
    assert len(calls) == 1
    assert (cache_dir / "professional_roles.json").exists()
