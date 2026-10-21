"""Справочник профессиональных ролей hh.ru (api.hh.ru/professional_roles)
и их группировка в "сферы" для анализа (раздел 6 задания)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SPHERE_BY_CATEGORY = {
    "Информационные технологии": "IT",
    "Юристы": "Право",
    "Финансы, бухгалтерия": "Экономика и финансы",
}
DEFAULT_SPHERE = "Прочие"

# Категории для части А (п.3 задания): обязательные IT/Юристы/Финансы +
# дополнительные Наука-образование/Медицина/Продажи.
PART_A_CATEGORY_NAMES = (
    "Информационные технологии",
    "Юристы",
    "Финансы, бухгалтерия",
    "Наука, образование",
    "Медицина, фармацевтика",
    "Продажи, обслуживание клиентов",
)


@dataclass
class RoleDictionary:
    role_to_name: dict[int, str]
    role_to_category_id: dict[int, int]
    category_id_to_name: dict[int, str]
    category_name_to_role_ids: dict[str, list[int]]

    def category_name_for_role(self, role_id: int) -> str | None:
        cat_id = self.role_to_category_id.get(role_id)
        if cat_id is None:
            return None
        return self.category_id_to_name.get(cat_id)

    def sphere_for_category(self, category_name: str | None) -> str:
        return SPHERE_BY_CATEGORY.get(category_name or "", DEFAULT_SPHERE)

    def role_name(self, role_id: int) -> str | None:
        return self.role_to_name.get(role_id)

    def role_ids_for_category(self, category_name: str) -> list[int]:
        return self.category_name_to_role_ids.get(category_name, [])

    def describe_roles(self, role_ids: list[int]) -> tuple[str, str | None, str]:
        """Для списка professional_role_ids вакансии возвращает
        (профроль — имена через запятую, категория_профроли первой роли, сфера)."""
        names = [self.role_name(rid) or f"[неизвестная роль {rid}]" for rid in role_ids]
        profession_role_str = ", ".join(names)
        primary_category = self.category_name_for_role(role_ids[0]) if role_ids else None
        sphere = self.sphere_for_category(primary_category)
        return profession_role_str, primary_category, sphere


def build_role_dictionary(professional_roles_json: dict[str, Any]) -> RoleDictionary:
    role_to_name: dict[int, str] = {}
    role_to_category_id: dict[int, int] = {}
    category_id_to_name: dict[int, str] = {}
    category_name_to_role_ids: dict[str, list[int]] = {}

    for category in professional_roles_json.get("categories", []):
        cat_id = int(category["id"])
        cat_name = category["name"]
        category_id_to_name[cat_id] = cat_name
        role_ids: list[int] = []
        for role in category.get("roles", []):
            role_id = int(role["id"])
            role_to_name[role_id] = role["name"]
            role_to_category_id[role_id] = cat_id
            role_ids.append(role_id)
        category_name_to_role_ids[cat_name] = role_ids

    return RoleDictionary(
        role_to_name=role_to_name,
        role_to_category_id=role_to_category_id,
        category_id_to_name=category_id_to_name,
        category_name_to_role_ids=category_name_to_role_ids,
    )
