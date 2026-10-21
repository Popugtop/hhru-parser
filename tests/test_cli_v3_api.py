from pathlib import Path

import pytest

from hh_parser.cli_v3_api import build_self_check_table, load_v2_counts_with_salary


def test_load_v2_counts_with_salary_excludes_no_salary_variant(tmp_path, monkeypatch):
    """Regression: 'counts_by_sphere_v2_no_salary_2026-10-07.csv' sorts AFTER the
    plain 'counts_by_sphere_v2_2026-10-07.csv' alphabetically ('n' > '2'), so a
    naive glob + sorted()[-1] used to pick the wrong (no-salary) baseline file."""
    v2_dir = tmp_path / "output" / "v2_matched"
    v2_dir.mkdir(parents=True)
    (v2_dir / "counts_by_sphere_v2_2026-10-07.csv").write_text(
        "Сфера;Всего вакансий;Высшее;СПО;Не требуется или не указано;Доля «Высшее», %\n"
        "IT;12;4;2;8;33.3\n",
        encoding="utf-8-sig",
    )
    (v2_dir / "counts_by_sphere_v2_no_salary_2026-10-07.csv").write_text(
        "Сфера;Всего вакансий;Высшее;СПО;Не требуется или не указано;Доля «Высшее», %\n"
        "IT;17;7;2;10;41.2\n",
        encoding="utf-8-sig",
    )

    monkeypatch.chdir(tmp_path)
    counts = load_v2_counts_with_salary()
    assert counts["IT"] == 12  # не 17 (no_salary)


def test_load_v2_counts_with_salary_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_v2_counts_with_salary()


class FakeSphereRow:
    def __init__(self, label, total_found):
        self.label = label
        self.total_found = total_found


def test_build_self_check_table_flags_rows_exceeding_tolerance():
    api_rows = [FakeSphereRow("IT", 13), FakeSphereRow("Право", 12)]
    web_counts = {"IT": 17, "Право": 12}

    table = build_self_check_table(api_rows, web_counts, tolerance=0.10)

    it_row = next(r for r in table if r["sphere"] == "IT")
    law_row = next(r for r in table if r["sphere"] == "Право")
    assert it_row["exceeds"] is True
    assert law_row["exceeds"] is False
    assert law_row["diff_pct"] == 0.0


def test_build_self_check_table_skips_spheres_missing_from_baseline():
    api_rows = [FakeSphereRow("Новая сфера", 5)]
    table = build_self_check_table(api_rows, web_counts={}, tolerance=0.10)
    assert table == []
