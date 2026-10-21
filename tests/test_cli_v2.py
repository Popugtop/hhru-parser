import csv

from hh_parser.cli_v2 import build_arg_parser, main, save_whitelist_csv
from hh_parser.whitelist import WhitelistEntry


def test_build_arg_parser_reuses_v1_defaults():
    args = build_arg_parser().parse_args([])
    assert args.area == 95
    assert args.search_period == 30
    assert args.seed == 42
    assert args.source == "hh"


def test_build_arg_parser_min_vo_required_default_and_override():
    from hh_parser.aggregate_v2 import MIN_VO_REQUIRED_TOTAL

    args = build_arg_parser().parse_args([])
    assert args.min_vo_required == MIN_VO_REQUIRED_TOTAL

    args = build_arg_parser().parse_args(["--min-vo-required", "39"])
    assert args.min_vo_required == 39


def test_save_whitelist_csv(tmp_path):
    whitelist = [
        WhitelistEntry(96, "Программист, разработчик", "IT"),
        WhitelistEntry(158, "Комплаенс-менеджер", "Право", note=" (пограничный случай)"),
    ]
    path = tmp_path / "roles_whitelist.csv"
    save_whitelist_csv(whitelist, path)

    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[0] == ["ID", "Роль", "Сфера", "Примечание"]
    assert rows[1] == ["96", "Программист, разработчик", "IT", ""]
    assert rows[2] == ["158", "Комплаенс-менеджер", "Право", " (пограничный случай)"]


def test_source_tv_not_implemented_returns_error(tmp_path):
    exit_code = main(
        ["--source", "tv", "--cache-dir", str(tmp_path / "cache"), "--output-dir", str(tmp_path / "out")]
    )
    assert exit_code == 1
    assert not (tmp_path / "cache").exists()
