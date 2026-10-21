import pytest

from hh_parser.text_rules import (
    EDU_HIGHER,
    EDU_HIGHER_SOFT,
    EDU_NOT_REQUIRED,
    EDU_NOT_SPECIFIED,
    EDU_SPO,
    check_education_mismatch,
    classify_education_mention,
    has_dms_mention,
    has_training_mention,
)


def test_has_dms_mention_true():
    assert has_dms_mention("После испытательного срока оформляем ДМС со стоматологией")
    assert has_dms_mention("Добровольное медицинское страхование для всех сотрудников")


def test_has_dms_mention_false():
    assert not has_dms_mention("Оклад и премии, график 5/2")
    assert not has_dms_mention("")


def test_has_training_mention_true():
    assert has_training_mention("Проводим корпоративное обучение новых сотрудников")
    assert has_training_mention("Закрепим наставника на первые три месяца")
    assert has_training_mention("Система наставничества для новичков")
    assert has_training_mention("Регулярные тренинги по продажам")


def test_has_training_mention_false():
    assert not has_training_mention("Оплата труда 2 раза в месяц, оформление по ТК РФ")
    assert not has_training_mention("")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Требуется высшее образование, обязательно профильное", EDU_HIGHER),
        ("Высшее образование обязательно", EDU_HIGHER),
        ("Высшее образование приветствуется, но не обязательно", EDU_HIGHER_SOFT),
        ("Высшее образование будет плюсом", EDU_HIGHER_SOFT),
        ("Среднее профессиональное образование", EDU_SPO),
        ("Нужен диплом СПО по специальности", EDU_SPO),
        ("Образование не требуется, обучим с нуля", EDU_NOT_REQUIRED),
        ("Оклад 50000, график 5/2, оформление по ТК РФ", EDU_NOT_SPECIFIED),
        ("", EDU_NOT_SPECIFIED),
    ],
)
def test_classify_education_mention(text, expected):
    assert classify_education_mention(text) == expected


def test_classify_education_prioritizes_not_required_over_soft_mentions_elsewhere():
    text = "Образование не требуется. Опыт работы приветствуется."
    assert classify_education_mention(text) == EDU_NOT_REQUIRED


@pytest.mark.parametrize(
    "filter_group,text_category,expected",
    [
        ("higher", EDU_NOT_REQUIRED, True),
        ("higher", EDU_SPO, True),
        ("higher", EDU_HIGHER, False),
        ("higher", EDU_HIGHER_SOFT, False),
        ("not_required_or_not_specified", EDU_HIGHER, True),
        ("not_required_or_not_specified", EDU_NOT_SPECIFIED, False),
        ("special_secondary", EDU_HIGHER, True),
        ("special_secondary", EDU_SPO, False),
        ("higher", EDU_NOT_SPECIFIED, False),
    ],
)
def test_check_education_mismatch(filter_group, text_category, expected):
    assert check_education_mismatch(filter_group, text_category) == expected
