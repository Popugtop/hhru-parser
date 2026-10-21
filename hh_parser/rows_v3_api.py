"""Строка выборки v3 через официальный API (запрос пользователя 2026-10-09):
те же поля, что rows_v3.FinalRowV3, но «подвыборка» теперь вычисляется внутри
этого же запуска по тому же составу сфер (sample_api.compute_matched_subsample),
а не читается из внешнего файла v2 (как было в in_v2_subsample) — поэтому
поле и колонка переименованы.
"""
from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass

from hh_parser.parse_vacancy import VacancyDetail
from hh_parser.roles import RoleDictionary
from hh_parser.rows_v2 import FinalRowV2, build_row_v2


@dataclass
class FinalRowV3Api(FinalRowV2):
    in_matched_subsample: bool = False
    employer_sequence_number: int = 0


def build_row_v3_api(
    detail: VacancyDetail,
    group_2_label: str,
    raw_education_filter: str,
    role_dict: RoleDictionary,
    sphere_map: dict[int, str],
    in_matched_subsample: bool,
) -> FinalRowV3Api:
    row2 = build_row_v2(detail, group_2_label, raw_education_filter, role_dict, sphere_map)
    data = {f.name: getattr(row2, f.name) for f in dataclasses.fields(row2)}
    return FinalRowV3Api(**data, in_matched_subsample=in_matched_subsample)


def assign_employer_sequence_numbers(rows: list[FinalRowV3Api]) -> None:
    """Мутирует row.employer_sequence_number по порядку элементов в rows —
    вызывать на уже отсортированном в финальном (отображаемом) порядке
    списке, чтобы номер совпадал с тем, что видно в Excel/CSV сверху вниз."""
    counts: Counter[int | None] = Counter()
    for row in rows:
        counts[row.employer_id] += 1
        row.employer_sequence_number = counts[row.employer_id]
