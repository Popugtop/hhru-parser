"""Колонки листа «Выборка» для v3 (сплошное обследование) — те же колонки,
что в columns_v2.COLUMNS, плюс две новые: «В подвыборке v2» (сразу после
исходного фильтра образования) и «Номер вакансии работодателя в выборке»
(сразу после ID работодателя)."""
from __future__ import annotations

from hh_parser.columns_v2 import COLUMNS as COLUMNS_V2
from hh_parser.columns_v2 import ColumnSpec

_IN_V2_SUBSAMPLE_COLUMN = ColumnSpec(
    "in_v2_subsample", "В подвыборке v2", "bool_yn",
    lambda r: r.in_v2_subsample,
    "Да, если id вакансии входит в подобранную выборку v2 (74 строки: output/v2_matched)",
)

_EMPLOYER_SEQUENCE_COLUMN = ColumnSpec(
    "employer_sequence_number", "Номер вакансии работодателя в выборке", "int",
    lambda r: r.employer_sequence_number,
    "Порядковый номер вакансии этого работодателя в итоговой (отсортированной) таблице — 1,2,3…; лимит на работодателя в v3 не применяется",
)


def _build_columns() -> list[ColumnSpec]:
    columns: list[ColumnSpec] = []
    for spec in COLUMNS_V2:
        columns.append(spec)
        if spec.key == "education_group_filter_label":
            columns.append(_IN_V2_SUBSAMPLE_COLUMN)
        elif spec.key == "employer_id":
            columns.append(_EMPLOYER_SEQUENCE_COLUMN)
    return columns


COLUMNS: list[ColumnSpec] = _build_columns()
