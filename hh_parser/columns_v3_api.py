"""Колонки листа «Выборка» для v3 через API (запрос пользователя 2026-10-09) —
columns_v2.COLUMNS плюс «В подвыборке с одинаковым составом сфер» (сразу после
исходного фильтра образования) и «Номер вакансии работодателя в выборке»
(сразу после ID работодателя) — те же позиции, что в columns_v3.py."""
from __future__ import annotations

from hh_parser.columns_v2 import COLUMNS as COLUMNS_V2
from hh_parser.columns_v2 import ColumnSpec

_IN_SUBSAMPLE_COLUMN = ColumnSpec(
    "in_matched_subsample", "В подвыборке с одинаковым составом сфер", "bool_yn",
    lambda r: r.in_matched_subsample,
    "Да — вакансия входит в подобранную подвыборку этого запуска: все «ВО требуется» "
    "(макс. 3 на работодателя) + столько же «ВО не требуется» с тем же составом сфер, seed=42",
)

_EMPLOYER_SEQUENCE_COLUMN = ColumnSpec(
    "employer_sequence_number", "Номер вакансии работодателя в выборке", "int",
    lambda r: r.employer_sequence_number,
    "Порядковый номер вакансии этого работодателя в итоговой (отсортированной) таблице — "
    "1,2,3…; лимит на работодателя в сплошном сборе v3 не применяется",
)


def _build_columns() -> list[ColumnSpec]:
    columns: list[ColumnSpec] = []
    for spec in COLUMNS_V2:
        columns.append(spec)
        if spec.key == "education_group_filter_label":
            columns.append(_IN_SUBSAMPLE_COLUMN)
        elif spec.key == "employer_id":
            columns.append(_EMPLOYER_SEQUENCE_COLUMN)
    return columns


COLUMNS: list[ColumnSpec] = _build_columns()
