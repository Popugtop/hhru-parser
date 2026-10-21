#!/usr/bin/env python3
"""CLI v3-api — переход на официальный API api.hh.ru/vacancies (запрос
пользователя 2026-10-09): те же фильтры части Б (без опыта, зарплата за
месяц, полная занятость, Тюмень, 30 дней), белый список ролей из
output/v2_matched/roles_whitelist.csv, но:

- источник данных — официальный API (Bearer-токен из .env), не HTML-страницы
  сайта (--source web переключает на старый Fetcher/SSR-парсинг — часть Б в
  этом режиме пока не перенесена, доступна только часть А для сверки);
- часть А считается в двух вариантах (с фильтром зарплаты и без);
- самопроверка: часть А (API, с фильтром ЗП) сравнивается с website-версией
  v2 (output/v2_matched/counts_by_sphere_v2_*.csv) — если расхождение по
  какой-то сфере больше ±10%, сбор части Б НЕ запускается, печатается
  таблица расхождений;
- часть Б — сплошной сбор ВСЕХ вакансий белого списка (без лимита на
  работодателя), с колонкой «Номер вакансии работодателя в выборке», и
  отдельно вычисленная (seed=42) подвыборка «все ВО требуется (макс. 3 на
  работодателя) + столько же ВО не требуется с тем же составом сфер» —
  помечена колонкой «В подвыборке с одинаковым составом сфер».

Токен и HH-User-Agent читаются из .env и никогда не печатаются и не пишутся
в кэш/логи.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from hh_parser.aggregate_api import collect_sphere_counts_api
from hh_parser.api_client import ApiFetcher, load_env
from hh_parser.cli import fetch_professional_roles
from hh_parser.csv_export import export_counts_by_sphere_csv, export_vacancies_csv_v3_api
from hh_parser.excel_export_v3_api import export_workbook_v3_api
from hh_parser.fetch import BlockedError
from hh_parser.manual_overrides import apply_manual_override
from hh_parser.roles import build_role_dictionary
from hh_parser.rows_v2 import EDUCATION_GROUP_2_NOT_REQUIRED, EDUCATION_GROUP_2_REQUIRED
from hh_parser.rows_v3_api import build_row_v3_api
from hh_parser.sample_api import collect_exhaustive_all_education_api, compute_matched_subsample
from hh_parser.summary_v2 import compute_group_summaries_v2
from hh_parser.whitelist import build_whitelist, sphere_by_role_id

SELF_CHECK_TOLERANCE = 0.10
V2_COUNTS_GLOB = "output/v2_matched/counts_by_sphere_v2_[0-9]*.csv"  # [0-9] excludes the *_no_salary_* variant


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сбор вакансий hh.ru (Тюмень, без опыта) через официальный API v3"
    )
    parser.add_argument("--area", type=int, default=95)
    parser.add_argument("--search-period", type=int, default=30, help="Период поиска в днях (параметр API — period)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pause-min", type=float, default=0.5)
    parser.add_argument("--pause-max", type=float, default=1.0)
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=None, help="По умолчанию output/v3_api_<дата>")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--self-check-tolerance", type=float, default=SELF_CHECK_TOLERANCE,
        help="Допустимое относительное расхождение часть А API vs сайт v2 (по умолчанию 0.10 = ±10%%)",
    )
    parser.add_argument(
        "--skip-self-check", action="store_true",
        help="Пропустить самопроверку и продолжить сбор части Б, даже если расхождение больше порога "
        "(использовать только после того, как расхождение вручную проверено и объяснено)",
    )
    return parser


def save_whitelist_csv(whitelist, output_path: Path) -> None:
    import csv

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID", "Роль", "Сфера", "Примечание"])
        for entry in whitelist:
            writer.writerow([entry.role_id, entry.role_name, entry.sphere, entry.note])


def load_v2_counts_with_salary() -> dict[str, int]:
    import glob

    matches = sorted(glob.glob(V2_COUNTS_GLOB))
    if not matches:
        raise FileNotFoundError(
            f"Не найден {V2_COUNTS_GLOB} — самопроверка части А требует website-версию v2 "
            "(запустите hh_parser.cli_v2 хотя бы раз, или используйте --skip-self-check)"
        )
    df = pd.read_csv(matches[-1], sep=";", encoding="utf-8-sig")
    return dict(zip(df["Сфера"], df["Всего вакансий"]))


def build_self_check_table(api_rows, web_counts: dict[str, int], tolerance: float) -> list[dict]:
    table = []
    for row in api_rows:
        web_total = web_counts.get(row.label)
        if web_total is None:
            continue
        diff_pct = round(100 * abs(row.total_found - web_total) / web_total, 1) if web_total else None
        exceeds = diff_pct is not None and diff_pct > tolerance * 100
        table.append(
            {
                "sphere": row.label,
                "api_total": row.total_found,
                "web_total": web_total,
                "diff_pct": diff_pct,
                "exceeds": exceeds,
            }
        )
    return table


def print_self_check_table(table: list[dict]) -> None:
    print(f"{'Сфера':<28} {'API (ЗП)':>10} {'Сайт v2 (ЗП)':>14} {'Расхожд., %':>12} {'Порог':>7}")
    for r in table:
        mark = " ПРЕВЫШЕН" if r["exceeds"] else ""
        print(f"{r['sphere']:<28} {r['api_total']:>10} {r['web_total']:>14} {r['diff_pct']:>12} {mark}")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    env = load_env(args.env_file)
    access_token = env.get("HH_ACCESS_TOKEN")
    user_agent = env.get("HH_USER_AGENT")
    if not access_token or not user_agent:
        print(
            f"ОСТАНОВКА: в {args.env_file} нет HH_ACCESS_TOKEN и/или HH_USER_AGENT. "
            "Новый токен запрашивать не нужно — проверьте файл .env.",
            file=sys.stderr,
        )
        return 1

    date_tag = datetime.now().strftime("%Y-%m-%d")
    output_dir = args.output_dir or Path(f"output/v3_api_{date_tag}")
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = ApiFetcher(
        access_token=access_token,
        user_agent=user_agent,
        cache_dir=args.cache_dir,
        pause_min=args.pause_min,
        pause_max=args.pause_max,
    )

    print("Загружаю справочник профролей (api.hh.ru/professional_roles)...")
    role_dict_json = fetch_professional_roles(args.cache_dir)
    role_dict = build_role_dictionary(role_dict_json)
    whitelist = build_whitelist(role_dict_json)
    sphere_map = sphere_by_role_id(whitelist)
    all_whitelist_ids = [entry.role_id for entry in whitelist]

    whitelist_path = output_dir / "roles_whitelist.csv"
    save_whitelist_csv(whitelist, whitelist_path)
    print(f"Белый список ({len(whitelist)} ролей) сохранён: {whitelist_path}")

    started_at = datetime.now().isoformat(timespec="seconds")

    print("\n=== Часть А (API), вариант 1: с фильтром зарплаты ===")
    try:
        sphere_rows_with_salary = collect_sphere_counts_api(
            fetcher, whitelist, role_dict, args.area, args.search_period, with_salary_filters=True
        )
    except BlockedError as exc:
        print(f"ОСТАНОВКА во время части А: {exc}", file=sys.stderr)
        return 1
    for row in sphere_rows_with_salary:
        print(
            f"  {row.label}: всего {row.total_found}, высшее {row.higher}, "
            f"СПО {row.special_secondary}, не требуется/не указано {row.not_required_or_not_specified}"
        )

    print("\n=== Часть А (API), вариант 2: без фильтра зарплаты ===")
    try:
        sphere_rows_no_salary = collect_sphere_counts_api(
            fetcher, whitelist, role_dict, args.area, args.search_period, with_salary_filters=False
        )
    except BlockedError as exc:
        print(f"ОСТАНОВКА во время части А (вариант 2): {exc}", file=sys.stderr)
        return 1
    for row in sphere_rows_no_salary:
        print(
            f"  {row.label}: всего {row.total_found}, высшее {row.higher}, "
            f"СПО {row.special_secondary}, не требуется/не указано {row.not_required_or_not_specified}"
        )

    counts_csv_with = output_dir / f"counts_by_sphere_v3_api_{date_tag}.csv"
    counts_csv_without = output_dir / f"counts_by_sphere_v3_api_no_salary_{date_tag}.csv"
    export_counts_by_sphere_csv(sphere_rows_with_salary, counts_csv_with)
    export_counts_by_sphere_csv(sphere_rows_no_salary, counts_csv_without)
    print(f"\nСохранено: {counts_csv_with}")
    print(f"Сохранено: {counts_csv_without}")

    print(f"\n=== Самопроверка: часть А (API) vs сайт (output/v2_matched), допуск ±{args.self_check_tolerance*100:.0f}% ===")
    try:
        web_counts = load_v2_counts_with_salary()
    except FileNotFoundError as exc:
        if args.skip_self_check:
            print(f"ПРЕДУПРЕЖДЕНИЕ: {exc} — продолжаю из-за --skip-self-check.", file=sys.stderr)
            self_check_table: list[dict] = []
        else:
            print(f"ОСТАНОВКА: {exc}", file=sys.stderr)
            return 1
    else:
        self_check_table = build_self_check_table(sphere_rows_with_salary, web_counts, args.self_check_tolerance)
        print_self_check_table(self_check_table)
        if any(r["exceeds"] for r in self_check_table) and not args.skip_self_check:
            print(
                "\nОСТАНОВКА: часть А (API) расходится с website-версией v2 больше, чем на "
                f"±{args.self_check_tolerance*100:.0f}% хотя бы по одной сфере (см. таблицу выше). "
                "Часть Б не запускаю. Проверьте таблицу — если расхождение объяснимо (обычная "
                "ротация вакансий за несколько дней), повторите запуск с --skip-self-check.",
                file=sys.stderr,
            )
            return 1

    print("\n=== Часть Б (API): сплошной сбор всех вакансий белого списка ===")
    try:
        exhaustive = collect_exhaustive_all_education_api(fetcher, all_whitelist_ids, args.area, args.search_period)
    except BlockedError as exc:
        print(f"ОСТАНОВКА: {exc}", file=sys.stderr)
        return 1
    if exhaustive.blocked_reason:
        print(f"ОСТАНОВЛЕНО: {exhaustive.blocked_reason}", file=sys.stderr)
    print(f"  Размеры пулов по исходному фильтру: {exhaustive.pool_size_by_raw_filter}")
    print(f"  Собрано: {len(exhaustive.collected)}")
    if exhaustive.excluded_counts:
        print(f"  Отсеяно: {dict(exhaustive.excluded_counts)}")

    print("\n=== Подвыборка с одинаковым составом сфер (seed=42, макс. 3 на работодателя) ===")
    matched = compute_matched_subsample(
        exhaustive.collected, exhaustive.raw_filter_by_vacancy_id, sphere_map, args.seed
    )
    print(f"  Цель по сферам (= состав «ВО требуется» после лимита на работодателя): {matched.target_by_sphere}")
    print(f"  В подвыборке: {len(matched.in_subsample_ids)}")
    if matched.shortfall_by_sphere:
        print(f"  Нехватка «ВО не требуется» по сферам: {matched.shortfall_by_sphere}")

    all_rows = []
    for detail in exhaustive.collected:
        raw_filter = exhaustive.raw_filter_by_vacancy_id[detail.vacancy_id]
        group_2 = EDUCATION_GROUP_2_REQUIRED if raw_filter == "higher" else EDUCATION_GROUP_2_NOT_REQUIRED
        in_subsample = detail.vacancy_id in matched.in_subsample_ids
        row = build_row_v3_api(detail, group_2, raw_filter, role_dict, sphere_map, in_subsample)
        apply_manual_override(row)
        all_rows.append(row)

    from hh_parser.excel_export_v3_api import prepare_rows_for_export

    all_rows = prepare_rows_for_export(all_rows)
    senior_rows = [r for r in all_rows if r.is_senior_role]

    finished_at = datetime.now().isoformat(timespec="seconds")
    run_info = {
        "Дата и время сбора (начало)": started_at,
        "Дата и время сбора (конец)": finished_at,
        "источник данных": "официальный API api.hh.ru/vacancies (Bearer-токен)",
        "area": args.area,
        "period (API)": args.search_period,
        "seed": args.seed,
        "лимит на работодателя (подвыборка)": 3,
        "лимит на работодателя (сплошной сбор)": "не применяется",
        "размер белого списка": len(whitelist),
        "размеры пулов по фильтру образования": exhaustive.pool_size_by_raw_filter,
        "собрано всего (сплошной сбор)": len(all_rows),
        "подвыборка — цель по сферам": matched.target_by_sphere,
        "подвыборка — размер": len(matched.in_subsample_ids),
        "подвыборка — нехватка по сферам": matched.shortfall_by_sphere,
        "самопроверка — допуск, %": args.self_check_tolerance * 100,
        "самопроверка — превышений порога": sum(1 for r in self_check_table if r["exceeds"]),
        "самопроверка — пропущена (--skip-self-check)": args.skip_self_check,
        "остановлено блокировкой": "да" if exhaustive.blocked_reason else "нет",
        "C-level ролей в выборке": len(senior_rows),
    }

    xlsx_path = output_dir / f"vacancies_v3_api_{date_tag}.xlsx"
    csv_path = output_dir / f"vacancies_v3_api_{date_tag}.csv"
    run_info_path = output_dir / "run_info_v3_api.json"

    export_workbook_v3_api(
        all_rows,
        sphere_rows_with_salary,
        dict(exhaustive.excluded_counts),
        exhaustive.pool_size_by_raw_filter,
        dict(matched.required_excluded_counts),
        dict(matched.not_required_excluded_counts),
        self_check_table,
        run_info,
        xlsx_path,
    )
    export_vacancies_csv_v3_api(all_rows, csv_path)

    run_info_for_json = dict(run_info)
    run_info_for_json["отсев_по_причинам (сплошной сбор)"] = dict(exhaustive.excluded_counts)
    run_info_for_json["отсев_по_причинам (подвыборка, ВО требуется)"] = dict(matched.required_excluded_counts)
    run_info_for_json["отсев_по_причинам (подвыборка, ВО не требуется)"] = dict(matched.not_required_excluded_counts)
    run_info_for_json["самопроверка — таблица"] = self_check_table
    run_info_path.write_text(json.dumps(run_info_for_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nСохранено: {xlsx_path}")
    print(f"Сохранено: {csv_path}")
    print(f"Сохранено: {run_info_path}")

    print("\n=== Сводка по группам (все собранные, сплошной сбор) ===")
    for s in compute_group_summaries_v2(all_rows):
        print(
            f"  {s.group_label}: вакансий {s.count}, медиана зп на руки {s.median_salary_net}, "
            f"ТК РФ {s.share_labor_contract}%, ДМС {s.share_dms}%, обучение {s.share_training}%, "
            f"удалёнка {s.share_remote}%, бюджетный сектор {s.share_budget}%"
        )

    matched_rows = [r for r in all_rows if r.in_matched_subsample]
    print(f"\n=== Сводка по подвыборке с одинаковым составом сфер ({len(matched_rows)} вакансий) ===")
    for s in compute_group_summaries_v2(matched_rows):
        print(
            f"  {s.group_label}: вакансий {s.count}, медиана зп на руки {s.median_salary_net}, "
            f"ТК РФ {s.share_labor_contract}%, ДМС {s.share_dms}%, обучение {s.share_training}%, "
            f"удалёнка {s.share_remote}%, бюджетный сектор {s.share_budget}%"
        )

    if senior_rows:
        print(f"\n=== C-level роли в выборке ({len(senior_rows)}) — проверить вручную ===")
        for r in senior_rows:
            print(f"  [{r.vacancy_id}] {r.name} — {r.employer} ({r.profession_role}) — {r.link}")

    if exhaustive.blocked_reason:
        print(
            "\nСБОР ОСТАНОВЛЕН из-за капчи/блокировки — см. сообщения выше. "
            f"Уже собранные данные сохранены в {output_dir}.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
