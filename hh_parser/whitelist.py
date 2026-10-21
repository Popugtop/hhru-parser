"""Белый список «специалистских» профролей (изменение дизайна v2, см. запрос
пользователя от 2026-10-07): узкий набор ролей уровня начинающего специалиста,
на которые реально претендует выпускник вуза, разбитый на сферы анализа.
Список подтверждён пользователем 2026-10-07 с правками (см. ниже).

Одна профроль может входить в несколько категорий справочника hh.ru —
поэтому сфера назначается явным role_id -> сфера маппингом (функция
build_whitelist), а не по первой попавшейся категории. ВАЖНО: явные
именованные роли (пункты 1-2 ниже) разрешаются ПЕРВЫМИ, до разборов целых
категорий — иначе, например, «Руководитель проектов» (который формально
лежит и в «Информационные технологии», и в «Стратегия, инвестиции,
консалтинг») мог бы утечь в IT или в «Экономика и финансы» вместо
«Управление и офис». Порядок приоритета:

  1) явно именованные роли «Продажи (офисные)» — даже если формально роль
     лежит в категории «Маркетинг, реклама, PR» или
     «Продажи, обслуживание клиентов»;
  2) явно именованные роли «Управление и офис» — админ-роли (офис-менеджер,
     секретарь/ассистент, делопроизводитель), «менеджер по логистике/ВЭД»,
     а также (правка пользователя) «Дизайнер, художник», «Арт-директор,
     креативный директор» и «Руководитель проектов» — перенесены из IT,
     чтобы не размывать IT творческими/управленческими ролями;
  3) IT — категория «Информационные технологии» целиком, за вычетом того,
     что уже забрал пункт 2. Общие с другими категориями роли (Аналитик,
     Бизнес-аналитик, Методолог, Специалист техподержки) остаются в IT;
  4) «Инженеры» — роли со словом «инженер» в названии из ЛЮБЫХ категорий,
     кроме уже занятых IT (DevOps/Сетевой/Системный инженер остаются IT) и
     кроме явно исключённой «Начальник производства, Главный инженер
     производства» (правка пользователя: руководящая роль, не для
     выпускника — убрана из белого списка целиком);
  5) «Право» — категория «Юристы» целиком, включая «Комплаенс-менеджер»
     (подтверждено пользователем, несмотря на формальное присутствие и в
     «Финансы, бухгалтерия»);
  6) «Экономика и финансы» — «Финансы, бухгалтерия» + «Страхование» +
     «Стратегия, инвестиции, консалтинг» (то, что не забрали пункты выше);
  7) «Управление и офис» (продолжение) — остаток «Маркетинг, реклама, PR» +
     «Управление персоналом, тренинги» + «Закупки», минус явно исключённый
     линейный персонал («Промоутер», подтверждено пользователем).

C-level/директорские роли (CIO, CMO, HRD, CTO, CFO, CLO) оставлены в белом
списке по решению пользователя — на практике почти никогда не встречаются
как «без опыта», но если встретятся, build_row() в rows.py помечает такие
строки в колонке «Комментарий» для ручной проверки (см. SENIOR_ROLE_IDS).

Категории «Медицина, фармацевтика» и «Наука, образование» в белый список не
входят вообще (образование там задано законом — нужны только для контекста
в части А).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SPHERE_IT = "IT"
SPHERE_LAW = "Право"
SPHERE_FINANCE = "Экономика и финансы"
SPHERE_OFFICE = "Управление и офис"
SPHERE_ENGINEERING = "Инженеры"
SPHERE_SALES = "Продажи (офисные)"

ALL_SPHERES = (SPHERE_IT, SPHERE_LAW, SPHERE_FINANCE, SPHERE_OFFICE, SPHERE_ENGINEERING, SPHERE_SALES)

_IT_CATEGORY = "Информационные технологии"
_LAW_CATEGORY = "Юристы"
_FINANCE_CATEGORIES = ("Финансы, бухгалтерия", "Страхование", "Стратегия, инвестиции, консалтинг")
_OFFICE_CATEGORIES = ("Маркетинг, реклама, PR", "Управление персоналом, тренинги", "Закупки")
_SALES_SOURCE_CATEGORIES = ("Маркетинг, реклама, PR", "Продажи, обслуживание клиентов")

_EXPLICIT_SALES_ROLE_NAMES = {
    "Менеджер по продажам, менеджер по работе с клиентами",
    "Менеджер по работе с партнерами",
    "Торговый представитель",
    "Менеджер маркетплейсов",
}

_EXPLICIT_OFFICE_ROLE_NAMES = {
    "Офис-менеджер",
    "Секретарь, помощник руководителя, ассистент",
    "Делопроизводитель, архивариус",
    "Менеджер по логистике, менеджер по ВЭД, начальник транспортного отдела",
    # Правка пользователя 2026-10-07: перенесены из IT, чтобы не размывать
    # IT творческими/управленческими ролями.
    "Дизайнер, художник",
    "Арт-директор, креативный директор",
    "Руководитель проектов",
}

# Исключаем явный линейный персонал/руководящие роли "не для выпускника",
# даже если формально попадают в разрешённую категорию.
_EXCLUDED_ROLE_NAMES = {
    "Промоутер",
    "Начальник производства, Главный инженер производства",  # правка пользователя
}

_COMPLIANCE_ROLE_NAME = "Комплаенс-менеджер"  # подтверждено пользователем: остаётся в "Право"

# C-level/директорские роли — оставлены в белом списке по решению пользователя,
# но build_row() в rows.py помечает такие вакансии в "Комментарий" для ручной проверки.
SENIOR_ROLE_IDS = {
    36,  # Директор по информационным технологиям (CIO)
    37,  # Директор по маркетингу и PR (CMO)
    38,  # Директор по персоналу (HRD)
    125,  # Технический директор (CTO)
    135,  # Финансовый директор (CFO)
    166,  # Директор юридического департамента (CLO)
}


@dataclass
class WhitelistEntry:
    role_id: int
    role_name: str
    sphere: str
    note: str = ""


def build_whitelist(professional_roles_json: dict[str, Any]) -> list[WhitelistEntry]:
    categories = professional_roles_json["categories"]
    by_name = {c["name"]: c for c in categories}
    assigned: dict[int, WhitelistEntry] = {}

    def assign(role_id: int, role_name: str, sphere: str, note: str = "") -> None:
        if role_id in assigned:
            return  # первый вызов выигрывает — порядок вызовов ниже и есть приоритет
        assigned[role_id] = WhitelistEntry(role_id, role_name, sphere, note)

    # 1) явные «Продажи (офисные)» — наивысший приоритет
    for cat_name in _SALES_SOURCE_CATEGORIES:
        for role in by_name[cat_name]["roles"]:
            if role["name"] in _EXPLICIT_SALES_ROLE_NAMES:
                assign(int(role["id"]), role["name"], SPHERE_SALES)

    # 2) явные «Управление и офис» (до разбора целых категорий IT/Финансы!)
    for cat in categories:
        for role in cat["roles"]:
            if role["name"] in _EXPLICIT_OFFICE_ROLE_NAMES:
                assign(int(role["id"]), role["name"], SPHERE_OFFICE)

    # 3) IT — целиком (минус уже занятое пунктом 2)
    for role in by_name[_IT_CATEGORY]["roles"]:
        assign(int(role["id"]), role["name"], SPHERE_IT)

    # 4) Инженеры — по названию, из любых категорий, минус явно исключённые
    seen_engineer_ids: set[int] = set()
    for cat in categories:
        for role in cat["roles"]:
            role_id = int(role["id"])
            if role_id in seen_engineer_ids or role["name"] in _EXCLUDED_ROLE_NAMES:
                continue
            if "инженер" in role["name"].lower():
                seen_engineer_ids.add(role_id)
                assign(role_id, role["name"], SPHERE_ENGINEERING)

    # 5) Право — целиком (включая «Комплаенс-менеджер», подтверждено)
    for role in by_name[_LAW_CATEGORY]["roles"]:
        note = (
            " (подтверждено: остаётся в «Право», несмотря на присутствие в «Финансы, бухгалтерия»)"
            if role["name"] == _COMPLIANCE_ROLE_NAME
            else ""
        )
        assign(int(role["id"]), role["name"], SPHERE_LAW, note)

    # 6) Экономика и финансы
    for cat_name in _FINANCE_CATEGORIES:
        for role in by_name[cat_name]["roles"]:
            assign(int(role["id"]), role["name"], SPHERE_FINANCE)

    # 7) Управление и офис — остаток категорий, минус исключённые
    for cat_name in _OFFICE_CATEGORIES:
        for role in by_name[cat_name]["roles"]:
            if role["name"] in _EXCLUDED_ROLE_NAMES:
                continue
            assign(int(role["id"]), role["name"], SPHERE_OFFICE)

    return sorted(assigned.values(), key=lambda e: (e.sphere, e.role_name))


def role_ids_by_sphere(whitelist: list[WhitelistEntry]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {sphere: [] for sphere in ALL_SPHERES}
    for entry in whitelist:
        result[entry.sphere].append(entry.role_id)
    return result


def sphere_by_role_id(whitelist: list[WhitelistEntry]) -> dict[int, str]:
    return {entry.role_id: entry.sphere for entry in whitelist}
