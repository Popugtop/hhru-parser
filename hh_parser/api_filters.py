"""Параметры поиска для официального API api.hh.ru/vacancies (запрос
пользователя 2026-10-09). Сверено с документацией api.hh.ru/openapi/redoc
(реально — YAML по ссылке Redoc.init: /openapi/specification/public), а не
угадано по сайту. Отличия от параметров сайта (filters.py), которые нужно
знать:

- период поиска называется `period`, а не `search_period` (сайт использует
  `search_period` только в своём HTML-клиенте, в официальном API параметр
  называется иначе);
- современный способ отобрать вакансии «только с зарплатой» — `label=with_salary`
  (старый `only_with_salary=true` помечен в документации как deprecated, но
  по факту тоже работает);
- `employment` (тип занятости) заменён на `employment_form` — его мы и
  использовали изначально, так что здесь без изменений;
- `area`, `experience`, `professional_role`, `education`, `salary_mode`
  называются и принимают ровно те же значения id, что и на сайте (проверено
  запросами к api.hh.ru/dictionaries и живыми вызовами).
"""
from __future__ import annotations

Params = list[tuple[str, str]]


def base_params_api(area: int, period: int, with_salary_filters: bool = True) -> Params:
    """with_salary_filters=False — вариант без label=with_salary/salary_mode
    (часть А, вариант 2 задания 2026-10-09): даёт больше вакансий, доли по
    образованию надёжнее."""
    params: Params = [
        ("area", str(area)),
        ("experience", "noExperience"),
        ("employment_form", "FULL"),
        ("period", str(period)),
    ]
    if with_salary_filters:
        params += [("salary_mode", "MONTH"), ("label", "with_salary")]
    return params


def with_education(params: Params, education_value: str) -> Params:
    return params + [("education", education_value)]


def with_professional_roles(params: Params, role_ids: list[int]) -> Params:
    return params + [("professional_role", str(rid)) for rid in role_ids]


def with_clusters(params: Params) -> Params:
    return params + [("clusters", "true")]


def with_page(params: Params, page: int, per_page: int = 100) -> Params:
    return params + [("page", str(page)), ("per_page", str(per_page))]
