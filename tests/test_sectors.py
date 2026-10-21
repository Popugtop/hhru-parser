import pytest

from hh_parser.sectors import BUDGET, COMMERCIAL, classify_sector


@pytest.mark.parametrize(
    "name",
    [
        'МАОУ СОШ №5 г. Тюмени',
        'МБОУ "Лицей №34"',
        'МАДОУ детский сад №10',
        'ГБУЗ ТО "Областная клиническая больница №1"',
        'ГАУЗ ТО "Поликлиника №5"',
        'ГАПОУ ТО "Тюменский колледж"',
        'ФГБУ "Национальный медицинский центр"',
        'ФГАОУ ВО "Тюменский государственный университет"',
        "Администрация города Тюмени",
        "Департамент образования и науки Тюменской области",
        "Министерство здравоохранения Тюменской области",
        "Государственное автономное учреждение культуры",
        "Муниципальное казённое учреждение",
    ],
)
def test_budget_employers(name):
    assert classify_sector(name) == BUDGET


@pytest.mark.parametrize(
    "name",
    [
        "Додо Пицца Тюмень",
        "Маркет Деливери",
        'ООО "Рога и копыта"',
        "Сбербанк",
        "Яндекс",
        "ИП Иванов Иван Иванович",
    ],
)
def test_commercial_employers(name):
    assert classify_sector(name) == COMMERCIAL


def test_empty_or_none_name_is_commercial():
    assert classify_sector(None) == COMMERCIAL
    assert classify_sector("") == COMMERCIAL


def test_does_not_false_positive_on_similar_substrings():
    # "градостроительн" содержит "страительн" но не должно триггерить
    # случайным совпадением с "государственн"/"муниципальн" и т.п.
    assert classify_sector("Градостроительная компания Квартал") == COMMERCIAL
