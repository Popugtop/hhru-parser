#!/usr/bin/env python3
"""CLI сбора вакансий hh.ru для учебного исследования (см. README.md)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

from hh_parser.aggregate import collect_sphere_counts
from hh_parser.codes import EDUCATION_FILTER
from hh_parser.csv_export import export_counts_by_sphere_csv, export_vacancies_csv
from hh_parser.excel_export import export_counts_workbook, export_workbook, sort_key_v1
from hh_parser.fetch import USER_AGENT, BlockedError, Fetcher
from hh_parser.filters import base_params, with_page
from hh_parser.parse_search import parse_search_page
from hh_parser.roles import build_role_dictionary
from hh_parser.rows import build_row
from hh_parser.sample import run_part_b
from hh_parser.ssr import extract_initial_state
from hh_parser.summary import compute_group_summaries

PROFESSIONAL_ROLES_URL = "https://api.hh.ru/professional_roles"
GROUP_IDS = ["higher", "not_required_or_not_specified", "special_secondary"]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сбор вакансий hh.ru (Тюмень, без опыта) для учебного исследования рынка труда"
    )
    parser.add_argument("--area", type=int, default=95, help="Код региона hh.ru (по умолчанию 95 — Тюмень)")
    parser.add_argument("--search-period", type=int, default=30, help="Период поиска в днях")
    parser.add_argument("--seed", type=int, default=42, help="Seed для перемешивания пула вакансий")
    parser.add_argument("--pause-min", type=float, default=2.0, help="Минимальная пауза между запросами, сек")
    parser.add_argument("--pause-max", type=float, default=4.0, help="Максимальная пауза между запросами, сек")
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--quota-higher", type=int, default=80, help="Квота для группы «Высшее»")
    parser.add_argument(
        "--quota-not-required", type=int, default=80,
        help="Квота для группы «Не требуется или не указано»",
    )
    parser.add_argument("--quota-special-secondary", type=int, default=40, help="Квота для группы «СПО»")
    parser.add_argument(
        "--probe", action="store_true",
        help="Пробный режим: одна страница поиска + одна вакансия, вывести ключи и разбор",
    )
    parser.add_argument(
        "--source", choices=["hh", "tv"], default="hh",
        help="hh (по умолчанию) — hh.ru; tv — опционально «Работа России» (раздел 9 задания)",
    )
    return parser


def fetch_professional_roles(cache_dir: Path) -> dict:
    cache_path = cache_dir / "professional_roles.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    response = requests.get(
        PROFESSIONAL_ROLES_URL,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def run_probe(fetcher: Fetcher, area: int, search_period: int) -> None:
    print("--- Пробный запрос: страница поиска ---")
    html, from_cache = fetcher.fetch_search_page(with_page(base_params(area, search_period), 0))
    print(f"(из кэша: {from_cache})")
    state = extract_initial_state(html)
    print("Верхнеуровневые ключи state:", sorted(state.keys())[:15], "...")
    result = parse_search_page(state)
    print(f"Всего найдено (searchCounts.value): {result.total_found}")
    print(f"Вакансий на странице: {len(result.vacancies)}")
    print(f"Счётчики по образованию: {result.education_counts}")
    if not result.vacancies:
        print("Нет вакансий в ответе — проверьте фильтры.")
        return
    for listing in result.vacancies[:3]:
        print(
            f"  [{listing.vacancy_id}] {listing.name} — {listing.company_name}, "
            f"{listing.salary_from}-{listing.salary_to} {listing.currency}"
        )

    first_id = result.vacancies[0].vacancy_id
    print(f"\n--- Пробный запрос: страница вакансии {first_id} ---")
    vac_html, vac_from_cache = fetcher.fetch_vacancy_page(first_id)
    print(f"(из кэша: {vac_from_cache})")
    vac_state = extract_initial_state(vac_html)
    vac = vac_state["vacancyView"]["vacancyFull"]["vacancy"]
    print("Ключи vacancyView.vacancyFull.vacancy:", sorted(vac.keys()))
    print(f"Название: {vac.get('name')}")
    print(f"Компания: {(vac.get('company') or {}).get('name')}")
    print(f"Зарплата: {vac.get('compensation')}")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.source == "tv":
        print("Источник --source tv (Работа России) в этой команде не реализован.", file=sys.stderr)
        return 1

    fetcher = Fetcher(cache_dir=args.cache_dir, pause_min=args.pause_min, pause_max=args.pause_max)

    if args.probe:
        try:
            run_probe(fetcher, args.area, args.search_period)
        except BlockedError as exc:
            print(f"ОСТАНОВКА: {exc}", file=sys.stderr)
            return 1
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Загружаю справочник профролей (api.hh.ru/professional_roles)...")
    role_dict = build_role_dictionary(fetch_professional_roles(args.cache_dir))

    started_at = datetime.now().isoformat(timespec="seconds")

    print("\n=== Часть А: агрегированные количества по сферам ===")
    try:
        sphere_rows = collect_sphere_counts(fetcher, role_dict, args.area, args.search_period)
    except BlockedError as exc:
        print(f"ОСТАНОВКА во время части А: {exc}", file=sys.stderr)
        print("Ничего не сохранено — часть А не была завершена.", file=sys.stderr)
        return 1

    for row in sphere_rows:
        mark = " (!) сумма групп образования не совпадает с общим числом" if row.education_sum_diverges else ""
        print(
            f"  {row.label}: всего {row.total_found}, высшее {row.higher}, "
            f"СПО {row.special_secondary}, не требуется/не указано {row.not_required_or_not_specified}{mark}"
        )

    print("\n=== Часть Б: стратифицированная выборка вакансий ===")
    group_quotas = [
        ("higher", args.quota_higher),
        ("not_required_or_not_specified", args.quota_not_required),
        ("special_secondary", args.quota_special_secondary),
    ]
    sample_results = run_part_b(fetcher, group_quotas, args.area, args.search_period, args.seed)

    blocked = False
    for group_id, quota in group_quotas:
        result = sample_results.get(group_id)
        if result is None:
            print(f"  {EDUCATION_FILTER[group_id]}: не начато (сбор остановлен раньше)")
            continue
        quota_note = "" if result.quota_met else " — КВОТА НЕ ДОБРАНА (пул кончился раньше)"
        print(
            f"  {EDUCATION_FILTER[group_id]}: пул {result.pool_size}, "
            f"собрано {len(result.collected)} из {quota}{quota_note}"
        )
        if result.blocked_reason:
            blocked = True
            print(f"    ОСТАНОВЛЕНО: {result.blocked_reason}")

    all_rows = [
        build_row(detail, group_id, role_dict)
        for group_id, result in sample_results.items()
        for detail in result.collected
    ]
    all_rows.sort(key=sort_key_v1)  # CSV и Excel должны идти в одном порядке

    finished_at = datetime.now().isoformat(timespec="seconds")
    run_info: dict = {
        "Дата и время сбора (начало)": started_at,
        "Дата и время сбора (конец)": finished_at,
        "area": args.area,
        "search_period": args.search_period,
        "seed": args.seed,
        "pause_min": args.pause_min,
        "pause_max": args.pause_max,
        "квота — higher": args.quota_higher,
        "квота — not_required_or_not_specified": args.quota_not_required,
        "квота — special_secondary": args.quota_special_secondary,
        "остановлено блокировкой": "да" if blocked else "нет",
    }
    for group_id, _ in group_quotas:
        result = sample_results.get(group_id)
        label = EDUCATION_FILTER[group_id]
        run_info[f"размер пула — {label}"] = result.pool_size if result else 0
        run_info[f"собрано — {label}"] = len(result.collected) if result else 0

    date_tag = datetime.now().strftime("%Y-%m-%d")
    xlsx_path = args.output_dir / f"vacancies_{date_tag}.xlsx"
    csv_path = args.output_dir / f"vacancies_{date_tag}.csv"
    counts_csv_path = args.output_dir / f"counts_by_sphere_{date_tag}.csv"
    run_info_path = args.output_dir / "run_info.json"

    export_workbook(all_rows, sphere_rows, sample_results, run_info, xlsx_path)
    export_vacancies_csv(all_rows, csv_path)
    export_counts_by_sphere_csv(sphere_rows, counts_csv_path)

    # Имена файлов без даты — как перечислено в разделе 2 задания (копии тех же данных)
    shutil.copy(xlsx_path, args.output_dir / "sample_vacancies.xlsx")
    shutil.copy(csv_path, args.output_dir / "sample_vacancies.csv")
    shutil.copy(counts_csv_path, args.output_dir / "counts_by_sphere.csv")
    export_counts_workbook(sphere_rows, args.output_dir / "counts_by_sphere.xlsx")

    run_info_for_json = dict(run_info)
    run_info_for_json["отсев_по_причинам"] = {
        group_id: dict(result.excluded_counts) for group_id, result in sample_results.items()
    }
    run_info_path.write_text(json.dumps(run_info_for_json, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nСохранено: {xlsx_path}")
    print(f"Сохранено: {csv_path}")
    print(f"Сохранено: {counts_csv_path}")
    print(f"Сохранено: {run_info_path}")

    print("\n=== Сводка по группам образования ===")
    summaries = compute_group_summaries(all_rows)
    for s in summaries:
        print(
            f"  {s.group_label}: вакансий {s.count}, медиана зп на руки {s.median_salary_net}, "
            f"ТК РФ {s.share_labor_contract}%, ДМС {s.share_dms}%, обучение {s.share_training}%, "
            f"удалёнка {s.share_remote}%, бюджетный сектор {s.share_budget}%"
        )

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
