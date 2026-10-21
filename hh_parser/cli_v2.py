#!/usr/bin/env python3
"""CLI v2 — изменение дизайна сбора (запрос пользователя от 2026-10-07):
узкий белый список специалистских профролей, 2 группы по образованию
(«ВО требуется» сплошным отбором vs «ВО не требуется» подбором с тем же
составом по сферам), часть А в двух вариантах фильтров.

Старый пайплайн (hh_parser.cli, часть А/Б v1) не затронут и продолжает
работать как раньше — все файлы v2 сохраняются с суффиксом _v2.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from hh_parser.aggregate_v2 import (
    MIN_VO_REQUIRED_TOTAL,
    build_vo_comparison_table,
    collect_sphere_counts_v2,
    total_vo_not_required,
    total_vo_required,
)
from hh_parser.cli import build_arg_parser as build_v1_arg_parser
from hh_parser.cli import fetch_professional_roles
from hh_parser.csv_export import export_counts_by_sphere_csv, export_vacancies_csv_v2
from hh_parser.excel_export_v2 import export_workbook_v2, sort_key_v2
from hh_parser.fetch import BlockedError, Fetcher
from hh_parser.manual_overrides import apply_manual_override
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED, build_row_v2
from hh_parser.sample_v2 import (
    GROUP_VO_NOT_REQUIRED,
    GROUP_VO_REQUIRED,
    collect_exhaustive_group,
    collect_matched_group,
)
from hh_parser.summary_v2 import compute_group_summaries_v2
from hh_parser.whitelist import build_whitelist, role_ids_by_sphere, sphere_by_role_id

VO_REQUIRED_CAP = 100


def build_arg_parser():
    """Переиспользует флаги из v1 (area/seed/pause/cache-dir/output-dir),
    квоты не нужны — «ВО требуется» сплошной (до VO_REQUIRED_CAP),
    «ВО не требуется» подбирается по факту."""
    parser = build_v1_arg_parser()
    parser.description = "Сбор вакансий hh.ru v2 — узкий белый список профролей, 2 группы по образованию"
    parser.add_argument(
        "--min-vo-required", type=int, default=MIN_VO_REQUIRED_TOTAL,
        help=(
            f"Минимум вакансий в группе «ВО требуется», ниже которого сбор части Б "
            f"останавливается (по умолчанию {MIN_VO_REQUIRED_TOTAL}). Проверено: "
            "search_period у hh.ru не влияет на объём выдачи (клэмпится на ~30 дней), "
            "так что при нехватке реалистичный выход — расширить белый список или "
            "осознанно принять меньший порог."
        ),
    )
    return parser


def save_whitelist_csv(whitelist, output_path: Path) -> None:
    import csv

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID", "Роль", "Сфера", "Примечание"])
        for entry in whitelist:
            writer.writerow([entry.role_id, entry.role_name, entry.sphere, entry.note])


def print_vo_comparison_table(comparison) -> None:
    print(f"{'Сфера':<25} {'ВО требуется':>14} {'ВО не требуется':>17}")
    for row in comparison:
        print(f"{row.sphere:<25} {row.vo_required:>14} {row.vo_not_required:>17}")
    print(f"{'ИТОГО':<25} {total_vo_required(comparison):>14} {total_vo_not_required(comparison):>17}")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.source == "tv":
        print("Источник --source tv (Работа России) в этой команде не реализован.", file=sys.stderr)
        return 1

    fetcher = Fetcher(cache_dir=args.cache_dir, pause_min=args.pause_min, pause_max=args.pause_max)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Загружаю справочник профролей (api.hh.ru/professional_roles)...")
    role_dict_json = fetch_professional_roles(args.cache_dir)
    role_dict = build_role_dictionary(role_dict_json)
    whitelist = build_whitelist(role_dict_json)
    by_sphere = role_ids_by_sphere(whitelist)
    sphere_map = sphere_by_role_id(whitelist)
    all_whitelist_ids = [entry.role_id for entry in whitelist]

    whitelist_path = args.output_dir / "roles_whitelist.csv"
    save_whitelist_csv(whitelist, whitelist_path)
    print(f"Белый список ({len(whitelist)} ролей) сохранён: {whitelist_path}")

    started_at = datetime.now().isoformat(timespec="seconds")

    print("\n=== Часть А v2, вариант 1: с фильтрами части Б (только с зарплатой) ===")
    try:
        sphere_rows_with_salary = collect_sphere_counts_v2(
            fetcher, whitelist, role_dict, args.area, args.search_period, with_salary_filters=True
        )
    except BlockedError as exc:
        print(f"ОСТАНОВКА во время части А: {exc}", file=sys.stderr)
        return 1
    for row in sphere_rows_with_salary:
        print(f"  {row.label}: всего {row.total_found}, высшее {row.higher}, "
              f"СПО {row.special_secondary}, не требуется/не указано {row.not_required_or_not_specified}")

    print("\n=== Часть А v2, вариант 2: без фильтра по зарплате ===")
    try:
        sphere_rows_no_salary = collect_sphere_counts_v2(
            fetcher, whitelist, role_dict, args.area, args.search_period, with_salary_filters=False
        )
    except BlockedError as exc:
        print(f"ОСТАНОВКА во время части А (вариант 2): {exc}", file=sys.stderr)
        return 1
    for row in sphere_rows_no_salary:
        print(f"  {row.label}: всего {row.total_found}, высшее {row.higher}, "
              f"СПО {row.special_secondary}, не требуется/не указано {row.not_required_or_not_specified}")

    comparison = build_vo_comparison_table(sphere_rows_with_salary)
    print("\n=== «ВО требуется» vs «ВО не требуется» по сферам (фильтры части Б) ===")
    print_vo_comparison_table(comparison)

    vo_required_total = total_vo_required(comparison)
    if vo_required_total < args.min_vo_required:
        print(
            f"\nОСТАНОВКА: в группе «ВО требуется» всего {vo_required_total} вакансий "
            f"(меньше порога {args.min_vo_required}). Часть Б не запускаю — решим, что делать "
            "(расширить белый список/сферы, снизить порог через --min-vo-required?).",
            file=sys.stderr,
        )
        return 1
    if vo_required_total < MIN_VO_REQUIRED_TOTAL:
        print(
            f"\nПОРОГ ПОНИЖЕН ВРУЧНУЮ: «ВО требуется» = {vo_required_total} "
            f"(меньше стандартного порога {MIN_VO_REQUIRED_TOTAL}, но >= --min-vo-required="
            f"{args.min_vo_required}) — продолжаю по решению пользователя."
        )

    date_tag = datetime.now().strftime("%Y-%m-%d")
    counts_csv_with = args.output_dir / f"counts_by_sphere_v2_{date_tag}.csv"
    counts_csv_without = args.output_dir / f"counts_by_sphere_v2_no_salary_{date_tag}.csv"
    export_counts_by_sphere_csv(sphere_rows_with_salary, counts_csv_with)
    export_counts_by_sphere_csv(sphere_rows_no_salary, counts_csv_without)
    print(f"\nСохранено: {counts_csv_with}")
    print(f"Сохранено: {counts_csv_without}")

    print("\n=== Часть Б v2: «ВО требуется» — сплошной отбор (до 100) ===")
    claimed_ids: set[int] = set()
    required_result = collect_exhaustive_group(
        fetcher, all_whitelist_ids, sphere_map, args.area, args.search_period,
        args.seed, VO_REQUIRED_CAP, claimed_ids,
    )
    if required_result.blocked_reason:
        print(f"ОСТАНОВЛЕНО: {required_result.blocked_reason}", file=sys.stderr)

    target_by_sphere = dict(required_result.sphere_counts())
    print(f"  Собрано: {len(required_result.collected)} (цель для «ВО не требуется» по сферам: {target_by_sphere})")

    print("\n=== Часть Б v2: «ВО не требуется» — подбор по составу сфер ===")
    not_required_result = collect_matched_group(
        fetcher, by_sphere, target_by_sphere, sphere_map,
        args.area, args.search_period, args.seed, claimed_ids,
    )
    if not_required_result.blocked_reason:
        print(f"ОСТАНОВЛЕНО: {not_required_result.blocked_reason}", file=sys.stderr)
    print(f"  Собрано: {len(not_required_result.collected)}")
    if not_required_result.shortfall_by_sphere:
        print(f"  Нехватка по сферам: {not_required_result.shortfall_by_sphere}")

    blocked = bool(required_result.blocked_reason or not_required_result.blocked_reason)

    all_rows = [
        build_row_v2(detail, EDUCATION_GROUP_2_REQUIRED, "higher", role_dict, sphere_map)
        for detail in required_result.collected
    ] + [
        build_row_v2(
            detail,
            EDUCATION_GROUP_2_NOT_REQUIRED,
            not_required_result.raw_filter_by_vacancy_id[detail.vacancy_id],
            role_dict,
            sphere_map,
        )
        for detail in not_required_result.collected
    ]
    for row in all_rows:
        apply_manual_override(row)
    all_rows.sort(key=sort_key_v2)  # CSV и Excel должны идти в одном порядке

    senior_rows = [r for r in all_rows if r.is_senior_role]

    finished_at = datetime.now().isoformat(timespec="seconds")
    run_info = {
        "Дата и время сбора (начало)": started_at,
        "Дата и время сбора (конец)": finished_at,
        "area": args.area,
        "search_period": args.search_period,
        "seed": args.seed,
        "размер белого списка": len(whitelist),
        "ВО требуется — собрано": len(required_result.collected),
        "ВО требуется — цель по сферам": target_by_sphere,
        "ВО не требуется — собрано": len(not_required_result.collected),
        "ВО не требуется — нехватка по сферам": not_required_result.shortfall_by_sphere,
        "остановлено блокировкой": "да" if blocked else "нет",
        "C-level ролей в выборке": len(senior_rows),
    }

    sample_results_v2 = {GROUP_VO_REQUIRED: required_result, GROUP_VO_NOT_REQUIRED: not_required_result}

    xlsx_path = args.output_dir / f"vacancies_v2_{date_tag}.xlsx"
    csv_path = args.output_dir / f"vacancies_v2_{date_tag}.csv"
    run_info_path = args.output_dir / "run_info_v2.json"

    export_workbook_v2(all_rows, sphere_rows_with_salary, sample_results_v2, run_info, xlsx_path)
    export_vacancies_csv_v2(all_rows, csv_path)

    run_info_for_json = dict(run_info)
    run_info_for_json["отсев_по_причинам"] = {
        GROUP_VO_REQUIRED: dict(required_result.excluded_counts),
        GROUP_VO_NOT_REQUIRED: dict(not_required_result.excluded_counts),
    }
    run_info_path.write_text(json.dumps(run_info_for_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nСохранено: {xlsx_path}")
    print(f"Сохранено: {csv_path}")
    print(f"Сохранено: {run_info_path}")

    print("\n=== Сводка по группам ===")
    for s in compute_group_summaries_v2(all_rows):
        print(
            f"  {s.group_label}: вакансий {s.count}, медиана зп на руки {s.median_salary_net}, "
            f"ТК РФ {s.share_labor_contract}%, ДМС {s.share_dms}%, обучение {s.share_training}%, "
            f"удалёнка {s.share_remote}%, бюджетный сектор {s.share_budget}%"
        )

    if senior_rows:
        print(f"\n=== C-level роли в выборке ({len(senior_rows)}) — проверить вручную ===")
        for r in senior_rows:
            print(f"  [{r.vacancy_id}] {r.name} — {r.employer} ({r.profession_role}) — {r.link}")

    if blocked:
        print(
            "\nСБОР ОСТАНОВЛЕН из-за капчи/блокировки hh.ru — см. сообщения выше. "
            "Уже собранные данные сохранены в output/.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
