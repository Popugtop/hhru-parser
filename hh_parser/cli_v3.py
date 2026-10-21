#!/usr/bin/env python3
"""CLI v3 — сплошное обследование всех вакансий белого списка (запрос
пользователя от 2026-10-07): те же фильтры части Б (без опыта, с зарплатой
за месяц, полная занятость, Тюмень, 30 дней), но БЕЗ квот и БЕЗ лимита «не
более 3 на работодателя» — все ~257 вакансий, а не выборка.

Требует, чтобы output/v2_matched уже был собран (hh_parser.cli_v2) — оттуда
берётся список ID подвыборки v2 для колонки «В подвыборке v2».
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from hh_parser.aggregate import SphereCounts
from hh_parser.cli import fetch_professional_roles
from hh_parser.csv_export import export_vacancies_csv_v3
from hh_parser.excel_export_v3 import export_workbook_v3, prepare_rows_for_export
from hh_parser.fetch import BlockedError, Fetcher
from hh_parser.manual_overrides import apply_manual_override
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED
from hh_parser.rows_v3 import build_row_v3
from hh_parser.sample_v3 import collect_exhaustive_all_education
from hh_parser.whitelist import build_whitelist, sphere_by_role_id


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сплошное обследование вакансий белого списка hh.ru (v3)"
    )
    parser.add_argument("--area", type=int, default=95)
    parser.add_argument("--search-period", type=int, default=30)
    parser.add_argument("--pause-min", type=float, default=2.0)
    parser.add_argument("--pause-max", type=float, default=4.0)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/v3_all_specialists"))
    parser.add_argument(
        "--v2-csv", type=Path, default=None,
        help="CSV подвыборки v2 (по умолчанию ищется output/v2_matched/vacancies_v2_*.csv)",
    )
    return parser


def load_v2_subsample_ids(v2_csv_path: Path | None) -> set[int]:
    if v2_csv_path is None:
        matches = sorted(glob.glob("output/v2_matched/vacancies_v2_*.csv"))
        if not matches:
            raise FileNotFoundError(
                "Не найден output/v2_matched/vacancies_v2_*.csv — сначала запустите hh_parser.cli_v2"
            )
        v2_csv_path = Path(matches[-1])
    df = pd.read_csv(v2_csv_path, sep=";", encoding="utf-8-sig")
    return set(int(v) for v in df["ID вакансии"])


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    fetcher = Fetcher(cache_dir=args.cache_dir, pause_min=args.pause_min, pause_max=args.pause_max)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Загружаю справочник профролей (api.hh.ru/professional_roles)...")
    role_dict_json = fetch_professional_roles(args.cache_dir)
    role_dict = build_role_dictionary(role_dict_json)
    whitelist = build_whitelist(role_dict_json)
    sphere_map = sphere_by_role_id(whitelist)
    all_whitelist_ids = [entry.role_id for entry in whitelist]

    v2_subsample_ids = load_v2_subsample_ids(args.v2_csv)
    print(f"Подвыборка v2: {len(v2_subsample_ids)} вакансий (для колонки «В подвыборке v2»)")

    started_at = datetime.now().isoformat(timespec="seconds")

    print("\n=== Часть Б v3: сплошное обследование белого списка (все education, без лимита работодателя) ===")
    result = collect_exhaustive_all_education(fetcher, all_whitelist_ids, args.area, args.search_period)
    if result.blocked_reason:
        print(f"ОСТАНОВЛЕНО: {result.blocked_reason}", file=sys.stderr)

    print(f"  Размеры пулов по исходному фильтру: {result.pool_size_by_raw_filter}")
    print(f"  Собрано: {len(result.collected)}")
    if result.excluded_counts:
        print(f"  Отсеяно: {dict(result.excluded_counts)}")

    all_rows = []
    for detail in result.collected:
        raw_filter = result.raw_filter_by_vacancy_id[detail.vacancy_id]
        group_2 = EDUCATION_GROUP_2_REQUIRED if raw_filter == "higher" else EDUCATION_GROUP_2_NOT_REQUIRED
        in_subsample = detail.vacancy_id in v2_subsample_ids
        row = build_row_v3(detail, group_2, raw_filter, role_dict, sphere_map, in_subsample)
        apply_manual_override(row)
        all_rows.append(row)

    all_rows = prepare_rows_for_export(all_rows)

    # «Количества по сферам» для v3 — из фактически собранных (после отсева)
    # строк, а не из приблизительных кластеров части А: точнее отражает
    # реальный сплошной сбор.
    raw_filter_counts: dict[str, Counter[str]] = {}
    for row in all_rows:
        raw_filter_counts.setdefault(row.sphere or "[не определена]", Counter())[row.education_group_filter] += 1
    sphere_rows_v3 = [
        SphereCounts(
            label=sphere,
            total_found=sum(c.values()),
            higher=c.get("higher", 0),
            special_secondary=c.get("special_secondary", 0),
            not_required_or_not_specified=c.get("not_required_or_not_specified", 0),
        )
        for sphere, c in sorted(raw_filter_counts.items())
    ]

    finished_at = datetime.now().isoformat(timespec="seconds")
    run_info = {
        "Дата и время сбора (начало)": started_at,
        "Дата и время сбора (конец)": finished_at,
        "area": args.area,
        "search_period": args.search_period,
        "размер белого списка": len(whitelist),
        "лимит на работодателя": "не применяется (сплошное обследование)",
        "размеры пулов по фильтру образования": result.pool_size_by_raw_filter,
        "собрано всего": len(all_rows),
        "подвыборка v2 (источник)": str(args.v2_csv) if args.v2_csv else "output/v2_matched/vacancies_v2_*.csv (последний)",
        "подвыборка v2 (размер)": len(v2_subsample_ids),
        "остановлено блокировкой": "да" if result.blocked_reason else "нет",
    }

    date_tag = datetime.now().strftime("%Y-%m-%d")
    xlsx_path = args.output_dir / f"vacancies_v3_all_{date_tag}.xlsx"
    csv_path = args.output_dir / f"vacancies_v3_all_{date_tag}.csv"
    run_info_path = args.output_dir / "run_info_v3.json"

    export_workbook_v3(
        all_rows, sphere_rows_v3, dict(result.excluded_counts), result.pool_size_by_raw_filter, run_info, xlsx_path
    )
    export_vacancies_csv_v3(all_rows, csv_path)

    run_info_for_json = dict(run_info)
    run_info_for_json["отсев_по_причинам"] = dict(result.excluded_counts)
    run_info_path.write_text(json.dumps(run_info_for_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nСохранено: {xlsx_path}")
    print(f"Сохранено: {csv_path}")
    print(f"Сохранено: {run_info_path}")

    print("\n=== Количества по сферам и группам ВО ===")
    counts: Counter[tuple[str, str]] = Counter()
    for row in all_rows:
        counts[(row.sphere or "[не определена]", row.education_group_2)] += 1
    spheres = sorted({s for s, _ in counts})
    print(f"{'Сфера':<25} {EDUCATION_GROUP_2_REQUIRED:>14} {EDUCATION_GROUP_2_NOT_REQUIRED:>17} {'Итого':>8}")
    total_req = total_not_req = 0
    for sphere in spheres:
        req = counts.get((sphere, EDUCATION_GROUP_2_REQUIRED), 0)
        not_req = counts.get((sphere, EDUCATION_GROUP_2_NOT_REQUIRED), 0)
        total_req += req
        total_not_req += not_req
        print(f"{sphere:<25} {req:>14} {not_req:>17} {req + not_req:>8}")
    print(f"{'ИТОГО':<25} {total_req:>14} {total_not_req:>17} {total_req + total_not_req:>8}")

    in_subsample_count = sum(1 for r in all_rows if r.in_v2_subsample)
    print(f"\nИз них в подвыборке v2: {in_subsample_count} из {len(all_rows)}")

    if result.blocked_reason:
        print(
            "\nСБОР ОСТАНОВЛЕН из-за капчи/блокировки hh.ru — см. сообщения выше. "
            "Уже собранные данные сохранены.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
