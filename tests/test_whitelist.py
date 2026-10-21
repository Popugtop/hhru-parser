import json
from pathlib import Path

import pytest

from hh_parser.whitelist import (
    SPHERE_ENGINEERING,
    SPHERE_FINANCE,
    SPHERE_IT,
    SPHERE_LAW,
    SPHERE_OFFICE,
    SPHERE_SALES,
    build_whitelist,
    role_ids_by_sphere,
    sphere_by_role_id,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_synthetic_dictionary() -> dict:
    """Минимальный справочник, воспроизводящий реальные конфликты hh.ru:
    роль 10 'Аналитик' в IT и в Маркетинге (должна остаться в IT); роль 34
    'Дизайнер' и роль 107 'Руководитель проектов' в IT И в другой категории
    (должны уехать в Управление и офис — правка пользователя, и это должно
    сработать ДО разбора целых категорий IT/Финансы, иначе 107 утёк бы в
    Финансы через Стратегию); роль 158 'Комплаенс-менеджер' в Юристах и в
    Финансах (остаётся в Право); роль 70 явно в Продажи(офисные), хотя
    лежит в Маркетинге; 'Промоутер' формально в Маркетинге, но исключён;
    роль 80 — явно исключённая руководящая роль; роль 112 'Сетевой инженер'
    в IT (не должна уехать в Инженеры); роль 48 'Инженер-конструктор' в
    производстве (должна уехать в Инженеры); 'Офис-менеджер' из
    административного персонала."""
    return {
        "categories": [
            {
                "id": 11,
                "name": "Информационные технологии",
                "roles": [
                    {"id": 10, "name": "Аналитик"},
                    {"id": 96, "name": "Программист, разработчик"},
                    {"id": 112, "name": "Сетевой инженер"},
                    {"id": 34, "name": "Дизайнер, художник"},
                    {"id": 12, "name": "Арт-директор, креативный директор"},
                    {"id": 107, "name": "Руководитель проектов"},
                ],
            },
            {
                "id": 6,
                "name": "Маркетинг, реклама, PR",
                "roles": [
                    {"id": 10, "name": "Аналитик"},
                    {"id": 34, "name": "Дизайнер, художник"},
                    {"id": 70, "name": "Менеджер по продажам, менеджер по работе с клиентами"},
                    {"id": 99, "name": "Промоутер"},
                    {"id": 2, "name": "PR-менеджер"},
                ],
            },
            {
                "id": 1,
                "name": "Продажи, обслуживание клиентов",
                "roles": [
                    {"id": 70, "name": "Менеджер по продажам, менеджер по работе с клиентами"},
                    {"id": 97, "name": "Продавец-консультант, продавец-кассир"},
                ],
            },
            {
                "id": 13,
                "name": "Юристы",
                "roles": [
                    {"id": 158, "name": "Комплаенс-менеджер"},
                    {"id": 146, "name": "Юрист"},
                ],
            },
            {
                "id": 3,
                "name": "Финансы, бухгалтерия",
                "roles": [
                    {"id": 158, "name": "Комплаенс-менеджер"},
                    {"id": 18, "name": "Бухгалтер"},
                ],
            },
            {
                "id": 22,
                "name": "Страхование",
                "roles": [{"id": 122, "name": "Страховой агент"}],
            },
            {
                "id": 4,
                "name": "Стратегия, инвестиции, консалтинг",
                "roles": [
                    {"id": 75, "name": "Менеджер/консультант по стратегии"},
                    {"id": 107, "name": "Руководитель проектов"},  # тот же ID, что и в IT
                ],
            },
            {
                "id": 7,
                "name": "Производство, сервисное обслуживание",
                "roles": [
                    {"id": 48, "name": "Инженер-конструктор, инженер-проектировщик"},
                    {"id": 80, "name": "Начальник производства, Главный инженер производства"},
                ],
            },
            {
                "id": 12,
                "name": "Управление персоналом, тренинги",
                "roles": [{"id": 118, "name": "Специалист по подбору персонала"}],
            },
            {
                "id": 14,
                "name": "Закупки",
                "roles": [{"id": 66, "name": "Менеджер по закупкам"}],
            },
            {
                "id": 5,
                "name": "Административный персонал",
                "roles": [
                    {"id": 88, "name": "Офис-менеджер"},
                    {"id": 8, "name": "Администратор"},
                ],
            },
            {
                "id": 25,
                "name": "Наука, образование",
                "roles": [{"id": 132, "name": "Учитель, преподаватель, педагог"}],
            },
        ]
    }


@pytest.fixture
def whitelist():
    return build_whitelist(make_synthetic_dictionary())


def entry_map(whitelist):
    return {e.role_id: e for e in whitelist}


def test_shared_role_goes_to_it_not_marketing(whitelist):
    entries = entry_map(whitelist)
    assert entries[10].sphere == SPHERE_IT  # Аналитик: IT и Маркетинг -> IT побеждает


def test_network_engineer_stays_in_it_not_engineering(whitelist):
    entries = entry_map(whitelist)
    assert entries[112].sphere == SPHERE_IT  # Сетевой инженер — несмотря на слово "инженер"


def test_production_engineer_goes_to_engineering(whitelist):
    entries = entry_map(whitelist)
    assert entries[48].sphere == SPHERE_ENGINEERING


def test_senior_production_role_excluded_entirely(whitelist):
    entries = entry_map(whitelist)
    assert 80 not in entries  # "Начальник производства..." убран по правке пользователя


def test_designer_and_art_director_moved_to_office_not_it(whitelist):
    entries = entry_map(whitelist)
    assert entries[34].sphere == SPHERE_OFFICE  # Дизайнер — перенесён из IT
    assert entries[12].sphere == SPHERE_OFFICE  # Арт-директор — перенесён из IT


def test_project_manager_moved_to_office_not_it_or_finance(whitelist):
    entries = entry_map(whitelist)
    # Руководитель проектов формально есть и в IT, и в Стратегии (->Финансы) —
    # явное правило "Управление и офис" должно сработать раньше обоих
    assert entries[107].sphere == SPHERE_OFFICE


def test_explicit_sales_role_overrides_category_membership(whitelist):
    entries = entry_map(whitelist)
    assert entries[70].sphere == SPHERE_SALES  # не Маркетинг и не Продажи-категория


def test_promoter_is_excluded_entirely(whitelist):
    entries = entry_map(whitelist)
    assert 99 not in entries  # Промоутер исключён, хотя формально в Маркетинге


def test_line_staff_not_in_whitelist(whitelist):
    entries = entry_map(whitelist)
    assert 97 not in entries  # Продавец-консультант не входит
    assert 8 not in entries  # Администратор не входит (только явные админ-роли)


def test_compliance_manager_assigned_to_law_with_note(whitelist):
    entries = entry_map(whitelist)
    assert entries[158].sphere == SPHERE_LAW
    assert "Финансы" in entries[158].note


def test_pure_law_role_unaffected(whitelist):
    entries = entry_map(whitelist)
    assert entries[146].sphere == SPHERE_LAW
    assert entries[146].note == ""


def test_finance_categories_assigned(whitelist):
    entries = entry_map(whitelist)
    assert entries[18].sphere == SPHERE_FINANCE  # Бухгалтер
    assert entries[122].sphere == SPHERE_FINANCE  # Страховой агент
    assert entries[75].sphere == SPHERE_FINANCE  # Стратегия


def test_office_categories_and_explicit_admin_roles(whitelist):
    entries = entry_map(whitelist)
    assert entries[118].sphere == SPHERE_OFFICE  # HR
    assert entries[66].sphere == SPHERE_OFFICE  # Закупки
    assert entries[88].sphere == SPHERE_OFFICE  # Офис-менеджер (явная роль)
    assert entries[2].sphere == SPHERE_OFFICE  # PR-менеджер (остаток Маркетинга)


def test_science_education_category_entirely_excluded(whitelist):
    entries = entry_map(whitelist)
    assert 132 not in entries


def test_role_ids_by_sphere_helper(whitelist):
    mapping = role_ids_by_sphere(whitelist)
    assert 10 in mapping[SPHERE_IT]
    assert 70 in mapping[SPHERE_SALES]
    assert set(mapping.keys()) >= {SPHERE_IT, SPHERE_LAW, SPHERE_FINANCE, SPHERE_OFFICE, SPHERE_ENGINEERING, SPHERE_SALES}


def test_sphere_by_role_id_helper(whitelist):
    mapping = sphere_by_role_id(whitelist)
    assert mapping[146] == SPHERE_LAW


def test_no_role_assigned_to_two_spheres(whitelist):
    ids = [e.role_id for e in whitelist]
    assert len(ids) == len(set(ids))


# --- Интеграционная проверка на реальном справочнике hh.ru -----------------

def test_build_whitelist_against_real_professional_roles_dictionary():
    data = json.loads((FIXTURES / "professional_roles.json").read_text(encoding="utf-8"))
    whitelist = build_whitelist(data)
    entries = entry_map(whitelist)

    # IT — вся категория, включая роли, общие с другими категориями
    assert entries[96].sphere == SPHERE_IT  # Программист, разработчик
    assert entries[10].sphere == SPHERE_IT  # Аналитик (общая с Маркетинг/Стратегия/Продажи)
    assert entries[150].sphere == SPHERE_IT  # Бизнес-аналитик (общая со Стратегией)
    assert entries[155].sphere == SPHERE_IT  # Методолог (общая с Финансами)
    assert entries[121].sphere == SPHERE_IT  # Специалист технической поддержки

    # Правка пользователя: эти роли перенесены из IT в "Управление и офис"
    assert entries[34].sphere == SPHERE_OFFICE  # Дизайнер, художник
    assert entries[12].sphere == SPHERE_OFFICE  # Арт-директор, креативный директор
    assert entries[107].sphere == SPHERE_OFFICE  # Руководитель проектов

    # Инженеры — по имени, кроме IT-шных "инженеров"
    assert entries[112].sphere == SPHERE_IT  # Сетевой инженер — остаётся IT
    assert entries[48].sphere == SPHERE_ENGINEERING  # Инженер-конструктор
    assert entries[111].sphere == SPHERE_ENGINEERING  # Сервисный инженер, инженер-механик
    assert 80 not in entries  # "Начальник производства..." убран по правке пользователя

    # Право + пограничный случай
    assert entries[146].sphere == SPHERE_LAW  # Юрист
    assert entries[158].sphere == SPHERE_LAW  # Комплаенс-менеджер (пограничный случай)

    # Экономика и финансы
    assert entries[18].sphere == SPHERE_FINANCE  # Бухгалтер
    assert entries[122].sphere == SPHERE_FINANCE  # Страховой агент

    # Продажи (офисные) — явные роли, не вся категория
    assert entries[70].sphere == SPHERE_SALES
    assert entries[129].sphere == SPHERE_SALES  # Торговый представитель
    assert 97 not in entries  # Продавец-консультант не входит

    # Управление и офис — явные админ-роли
    assert entries[88].sphere == SPHERE_OFFICE  # Офис-менеджер
    assert entries[110].sphere == SPHERE_OFFICE  # Секретарь
    assert entries[67].sphere == SPHERE_OFFICE  # Менеджер по логистике/ВЭД

    # Явно исключённые
    assert 99 not in entries  # Промоутер
    assert 8 not in entries  # Администратор (не входит в явный список)
    assert 132 not in entries  # Учитель — Наука/образование не в белом списке вообще
    assert 24 not in entries  # Врач — Медицина не в белом списке вообще
