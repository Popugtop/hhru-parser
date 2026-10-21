"""CSV-экспорт для анализа в Python (раздел 2а): ';' как разделитель,
utf-8-sig (чтобы Excel открывал кириллицу без кракозябр), числа без
разделителей тысяч (в отличие от Excel-листа «Выборка»)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from hh_parser.aggregate import SphereCounts
from hh_parser.columns_v2 import COLUMNS as COLUMNS_V2
from hh_parser.columns_v3 import COLUMNS as COLUMNS_V3
from hh_parser.columns_v3_api import COLUMNS as COLUMNS_V3_API
from hh_parser.format_values import row_to_display_dict
from hh_parser.rows import FinalRow
from hh_parser.rows_v2 import FinalRowV2
from hh_parser.rows_v3 import FinalRowV3
from hh_parser.rows_v3_api import FinalRowV3Api

CSV_SEP = ";"
CSV_ENCODING = "utf-8-sig"


def export_vacancies_csv(rows: list[FinalRow], output_path: str | Path) -> None:
    records = [row_to_display_dict(row) for row in rows]
    df = pd.DataFrame.from_records(records)
    df.to_csv(output_path, sep=CSV_SEP, encoding=CSV_ENCODING, index=False)


def export_vacancies_csv_v2(rows: list[FinalRowV2], output_path: str | Path) -> None:
    records = [row_to_display_dict(row, columns=COLUMNS_V2) for row in rows]
    df = pd.DataFrame.from_records(records)
    df.to_csv(output_path, sep=CSV_SEP, encoding=CSV_ENCODING, index=False)


def export_vacancies_csv_v3(rows: list[FinalRowV3], output_path: str | Path) -> None:
    """rows должны быть уже подготовлены excel_export_v3.prepare_rows_for_export
    (сортировка + номера работодателя), чтобы CSV совпадал с листом «Выборка»."""
    records = [row_to_display_dict(row, columns=COLUMNS_V3) for row in rows]
    df = pd.DataFrame.from_records(records)
    df.to_csv(output_path, sep=CSV_SEP, encoding=CSV_ENCODING, index=False)


def export_vacancies_csv_v3_api(rows: list[FinalRowV3Api], output_path: str | Path) -> None:
    """rows должны быть уже подготовлены excel_export_v3_api.prepare_rows_for_export
    (сортировка + номера работодателя), чтобы CSV совпадал с листом «Выборка»."""
    records = [row_to_display_dict(row, columns=COLUMNS_V3_API) for row in rows]
    df = pd.DataFrame.from_records(records)
    df.to_csv(output_path, sep=CSV_SEP, encoding=CSV_ENCODING, index=False)


def export_counts_by_sphere_csv(sphere_rows: list[SphereCounts], output_path: str | Path) -> None:
    records = [
        {
            "Сфера": row.label,
            "Всего вакансий": row.total_found,
            "Высшее": row.higher,
            "СПО": row.special_secondary,
            "Не требуется или не указано": row.not_required_or_not_specified,
            "Доля «Высшее», %": row.higher_share_pct if row.higher_share_pct is not None else "",
        }
        for row in sphere_rows
    ]
    df = pd.DataFrame.from_records(records)
    df.to_csv(output_path, sep=CSV_SEP, encoding=CSV_ENCODING, index=False)
