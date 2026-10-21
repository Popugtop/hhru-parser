"""Перевод значений FinalRow в отображаемый вид для CSV/Excel (раздел 2а):
да/нет вместо True/False, пустая ячейка вместо None/NaN/[], коды hh.ru
переведены на русский, даты в формате ДД.ММ.ГГГГ."""
from __future__ import annotations

from typing import Any

from hh_parser.columns import COLUMNS, ColumnSpec
from hh_parser.rows import FinalRow

# display_value/row_to_display_dict работают по утиной типизации (spec.kind/
# spec.getter/spec.mapping) — тот же код переиспользуется в v2 с columns_v2.COLUMNS
# и FinalRowV2, передавая columns= в row_to_display_dict.


def _translate_list(mapping: dict[str, str], codes: list[str] | None) -> str:
    if not codes:
        return ""
    return ", ".join(mapping.get(c, f"[неизвестный код: {c}]") for c in codes)


def _bool_to_yn(value: bool | None) -> str:
    if value is None:
        return ""
    return "да" if value else "нет"


def _date_to_ddmmyyyy(iso_date: str | None) -> str:
    if not iso_date:
        return ""
    year, month, day = iso_date.split("-")
    return f"{day}.{month}.{year}"


def display_value(spec: ColumnSpec, row: FinalRow) -> Any:
    """Итоговое значение ячейки для данной колонки: число/строка/пустая строка —
    то, что пойдёт прямо в Excel-ячейку или CSV-поле."""
    raw = spec.getter(row)

    if spec.kind == "text":
        return raw if raw not in (None, "") else ""
    if spec.kind == "link":
        return raw or ""
    if spec.kind in ("int", "money"):
        return raw if raw is not None else ""
    if spec.kind == "bool_yn":
        return _bool_to_yn(raw)
    if spec.kind == "date":
        return _date_to_ddmmyyyy(raw)
    if spec.kind == "list":
        return _translate_list(spec.mapping or {}, raw)
    if spec.kind == "empty_text":
        return raw or ""
    raise ValueError(f"Неизвестный kind колонки: {spec.kind}")


def row_to_display_dict(row: FinalRow, columns: list[ColumnSpec] = COLUMNS) -> dict[str, Any]:
    return {spec.header: display_value(spec, row) for spec in columns}
