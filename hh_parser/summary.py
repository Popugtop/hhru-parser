"""Сводная статистика по группам образования (раздел 2 п.5 и лист «Сводка»).
Используется и для консольной сводки, и для листа «Сводка» в Excel —
единая логика, чтобы цифры не расходились."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable

from hh_parser.codes import EDUCATION_FILTER
from hh_parser.rows import FinalRow

EDUCATION_GROUP_ORDER = ["higher", "not_required_or_not_specified", "special_secondary"]


@dataclass
class GroupSummary:
    group_filter: str
    group_label: str
    count: int
    median_salary_net: float | None
    mean_salary_net: float | None
    share_labor_contract: float | None
    share_dms: float | None
    share_training: float | None
    share_remote: float | None
    share_budget: float | None


def share_pct(group_rows: list, predicate: Callable) -> float | None:
    if not group_rows:
        return None
    return round(100 * sum(1 for r in group_rows if predicate(r)) / len(group_rows), 1)


def compute_group_summaries(rows: list[FinalRow]) -> list[GroupSummary]:
    summaries: list[GroupSummary] = []
    for group_filter in EDUCATION_GROUP_ORDER:
        group_rows = [r for r in rows if r.education_group_filter == group_filter]
        salaries = [r.salary_net_estimate for r in group_rows if r.salary_net_estimate is not None]
        summaries.append(
            GroupSummary(
                group_filter=group_filter,
                group_label=EDUCATION_FILTER.get(group_filter, group_filter),
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
