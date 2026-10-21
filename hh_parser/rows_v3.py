"""Строка выборки v3 (сплошное обследование) — все поля v2 плюс:
- in_v2_subsample: входит ли вакансия в подвыборку v2 (74 строки);
- employer_sequence_number: номер вакансии этого работодателя по порядку в
  итоговой (отсортированной) таблице — 1, 2, 3… — чтобы потом можно было
  отфильтровать вручную (лимит 3 на работодателя здесь не применяется).
employer_sequence_number проставляется позже, после финальной сортировки
(см. excel_export_v3.assign_employer_sequence_numbers) — тут всегда 0.
"""
from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass

from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.roles import RoleDictionary
from hh_parser.rows_v2 import FinalRowV2, build_row_v2


@dataclass
class FinalRowV3(FinalRowV2):
    in_v2_subsample: bool = False
    employer_sequence_number: int = 0


def build_row_v3(
    detail: VacancyDetail,
    group_2_label: str,
    raw_education_filter: str,
    role_dict: RoleDictionary,
    sphere_map: dict[int, str],
    in_v2_subsample: bool,
) -> FinalRowV3:
    row2 = build_row_v2(detail, group_2_label, raw_education_filter, role_dict, sphere_map)
    data = {f.name: getattr(row2, f.name) for f in dataclasses.fields(row2)}
    return FinalRowV3(**data, in_v2_subsample=in_v2_subsample)


def assign_employer_sequence_numbers(rows: list[FinalRowV3]) -> None:
    """Мутирует row.employer_sequence_number по порядку элементов в rows —
    вызывать на уже отсортированном в финальном (отображаемом) порядке
    списке, чтобы номер совпадал с тем, что видно в Excel/CSV сверху вниз."""
    counts: Counter[int | None] = Counter()
    for row in rows:
        counts[row.employer_id] += 1
        row.employer_sequence_number = counts[row.employer_id]
