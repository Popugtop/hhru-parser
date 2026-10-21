"""Эвристики по тексту описания вакансии: ДМС, обучение/наставничество,
упоминание требований к образованию и сверка с фильтром образования.

Это текстовые эвристики для предварительной разметки и отбора строк на
ручную проверку (колонка «проверено_вручную»), а не точный NLP-классификатор.
"""
from __future__ import annotations

import re

_DMS_RE = re.compile(r"\bдмс\b|добровольное\s+медицинское\s+страхование", re.IGNORECASE)

_TRAINING_RE = re.compile(
    r"обучен\w*|наставник\w*|наставничеств\w*|менторств\w*|\bментор\w*|"
    r"адаптаци\w*\s+(?:сотрудник|нов)|корпоративн\w*\s+университет|тренинг\w*",
    re.IGNORECASE,
)

_SOFT_MARKERS = (
    "приветствуется",
    "желательно",
    "будет плюсом",
    "будет преимуществом",
    "плюсом",
    "преимуществом",
    "не обязательно",
    "необязательно",
    "по желанию",
    "как плюс",
    "не является обязательным",
)

_NO_REQUIREMENT_MARKERS = (
    "не требуется",
    "без требований к образован",
    "образование не имеет значения",
    "образование не важно",
    "не важно какое образование",
    "любое образование",
    "не принципиально",
)

_SPO_MARKERS_RE = re.compile(
    r"среднее\s+проф\w*|среднее\s+специальн\w*|\bспо\b",
    re.IGNORECASE,
)

_ANCHOR_RE = re.compile(
    r"образован\w*|высш\w*|среднее\s+проф\w*|среднее\s+специальн\w*|\bспо\b",
    re.IGNORECASE,
)

_WINDOW = 60

EDU_HIGHER = "высшее"
EDU_HIGHER_SOFT = "высшее желательно"
EDU_SPO = "СПО"
EDU_NOT_REQUIRED = "не требуется"
EDU_NOT_SPECIFIED = "не указано"


def has_dms_mention(description_text: str) -> bool:
    """ДМС (да/нет) по тексту описания."""
    if not description_text:
        return False
    return bool(_DMS_RE.search(description_text))


def has_training_mention(description_text: str) -> bool:
    """Обучение/наставничество (да/нет) по тексту описания."""
    if not description_text:
        return False
    return bool(_TRAINING_RE.search(description_text))


def _classify_window(window: str) -> str | None:
    has_higher = "высш" in window
    has_no_req = any(marker in window for marker in _NO_REQUIREMENT_MARKERS)
    has_soft = any(marker in window for marker in _SOFT_MARKERS)
    has_spo = bool(_SPO_MARKERS_RE.search(window))

    if has_no_req and not has_higher:
        return EDU_NOT_REQUIRED
    if has_higher:
        return EDU_HIGHER_SOFT if has_soft else EDU_HIGHER
    if has_spo:
        return EDU_SPO
    return None


_PRIORITY = {EDU_NOT_REQUIRED: 0, EDU_HIGHER: 1, EDU_HIGHER_SOFT: 2, EDU_SPO: 3}


def classify_education_mention(description_text: str) -> str:
    """Что написано в описании про требования к образованию.

    Возвращает одно из: "высшее", "высшее желательно", "СПО",
    "не требуется", "не указано" (если ничего не упомянуто).
    Приоритет при противоречивых упоминаниях в разных местах текста:
    "не требуется" > "высшее" > "высшее желательно" > "СПО".
    """
    if not description_text:
        return EDU_NOT_SPECIFIED

    text_lower = description_text.lower()
    found: set[str] = set()
    for match in _ANCHOR_RE.finditer(text_lower):
        start = max(0, match.start() - _WINDOW)
        end = min(len(text_lower), match.end() + _WINDOW)
        window = text_lower[start:end]
        category = _classify_window(window)
        if category:
            found.add(category)

    if not found:
        return EDU_NOT_SPECIFIED

    return min(found, key=lambda c: _PRIORITY[c])


_MISMATCH_RULES = {
    # (фильтр, категория_в_тексте) -> явное противоречие
    ("higher", EDU_NOT_REQUIRED): True,
    ("higher", EDU_SPO): True,
    ("not_required_or_not_specified", EDU_HIGHER): True,
    ("special_secondary", EDU_HIGHER): True,
}


def check_education_mismatch(filter_group: str, text_category: str) -> bool:
    """Явное противоречие между фильтром образования (по которому найдена
    вакансия) и тем, что написано в тексте описания."""
    return _MISMATCH_RULES.get((filter_group, text_category), False)
