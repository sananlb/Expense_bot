"""Общие валидаторы для категорий расходов и доходов.

Обе модели (ExpenseCategory, IncomeCategory) имеют одинаковые поля:
name, name_ru, name_en, icon, is_active, profile.
Это позволяет использовать единый набор функций для валидации.
"""

import re
import logging
from typing import Type

from django.db import models
from django.db.models import Q

from bot.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)

MAX_CATEGORIES_PER_USER = 50


def validate_category_name(raw_name: str) -> str:
    """
    Валидация и очистка названия категории.

    Args:
        raw_name: сырое название (без иконки)

    Returns:
        Очищенное название

    Raises:
        ValueError: если название невалидно (слишком длинное или пустое)
    """
    if len(raw_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        raise ValueError(
            f"Название категории слишком длинное "
            f"(максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов)"
        )

    sanitized = InputSanitizer.sanitize_category_name(raw_name).strip()
    if not sanitized:
        raise ValueError("Название категории не может быть пустым")

    return sanitized


def detect_category_language(text: str, fallback_lang: str = 'ru') -> str:
    """
    Определяет язык текста категории.

    Args:
        text: текст названия категории
        fallback_lang: язык по умолчанию если не удалось определить

    Returns:
        'ru', 'en' или fallback_lang
    """
    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))

    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    return fallback_lang


def check_category_duplicate(
    model_class: Type[models.Model],
    profile,
    text: str,
    display_name: str,
    exclude_id: int = None,
) -> bool:
    """
    Проверяет наличие дубликата категории.

    Проверяет по name_ru/name_en (iexact) без учёта иконки,
    + fallback на legacy name (с иконкой, для старых записей без name_ru/name_en).
    Фильтрует только активные категории.

    Args:
        model_class: ExpenseCategory или IncomeCategory
        profile: объект профиля пользователя
        text: название без иконки (для проверки name_ru/name_en)
        display_name: полное название с иконкой (для проверки legacy name)
        exclude_id: ID текущей категории (исключить при update)

    Returns:
        True если дубликат найден
    """
    qs = model_class.objects.filter(
        profile=profile,
        is_active=True,
    ).filter(
        Q(name_ru__iexact=text)
        | Q(name_en__iexact=text)
        | Q(name__iexact=display_name)
    )

    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)

    return qs.exists()


def validate_category_limit(
    model_class: Type[models.Model],
    profile,
    limit: int = MAX_CATEGORIES_PER_USER,
) -> None:
    """
    Проверяет лимит количества активных категорий.

    Args:
        model_class: ExpenseCategory или IncomeCategory
        profile: объект профиля пользователя
        limit: максимальное количество категорий

    Raises:
        ValueError: если лимит превышен
    """
    count = model_class.objects.filter(profile=profile, is_active=True).count()
    if count >= limit:
        logger.warning(
            "User %s reached categories limit (%d)",
            profile.telegram_id, limit,
        )
        raise ValueError(f"Достигнут лимит категорий (максимум {limit})")
