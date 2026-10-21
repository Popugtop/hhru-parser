"""Сводная статистика v2 — то же самое, что summary.py, но по 2 группам
(«ВО требуется» / «ВО не требуется») вместо трёх."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED, FinalRowV2
from hh_parser.summary import share_pct

EDUCATION_GROUP_2_ORDER = [EDUCATION_GROUP_2_REQUIRED, EDUCATION_GROUP_2_NOT_REQUIRED]


@dataclass
class GroupSummaryV2:
    group_label: str
    count: int
    median_salary_net: float | None
    mean_salary_net: float | None
    share_labor_contract: float | None
    share_dms: float | None
    share_training: float | None
    share_remote: float | None
    share_budget: float | None


def compute_group_summaries_v2(rows: list[FinalRowV2]) -> list[GroupSummaryV2]:
    summaries: list[GroupSummaryV2] = []
    for group_label in EDUCATION_GROUP_2_ORDER:
        group_rows = [r for r in rows if r.education_group_2 == group_label]
        salaries = [r.salary_net_estimate for r in group_rows if r.salary_net_estimate is not None]
        summaries.append(
            GroupSummaryV2(
                group_label=group_label,
                count=len(group_rows),
                median_salary_net=round(statistics.median(salaries)) if salaries else None,
                mean_salary_net=round(statistics.mean(salaries)) if salaries else None,
                share_labor_contract=share_pct(group_rows, lambda r: r.labor_contract),
                share_dms=share_pct(group_rows, lambda r: r.dms),
                share_training=share_pct(group_rows, lambda r: r.training_mentorship),
                share_remote=share_pct(group_rows, lambda r: "REMOTE" in r.work_formats),
                share_budget=share_pct(group_rows, lambda r: r.sector == "бюджетный"),
            )
        )
    return summaries
