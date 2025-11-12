"""
AI категоризация расходов - централизованная валидация категорий
Аналог income_categorization.py для расходов
"""
import logging
from typing import Optional, List

from bot.utils.expense_category_definitions import (
    get_expense_category_display_name,
    normalize_expense_category_key,
    strip_leading_emoji,
)

logger = logging.getLogger(__name__)


async def find_best_matching_expense_category(suggested: str, available: List[str]) -> str:
    """
    Поиск наиболее подходящей категории расходов из доступных.

    ВАЖНО: Приоритет проверок (от высокого к низкому):
    1. Точное совпадение без эмодзи - для кастомных категорий с уточнениями
       Пример: "Продукты (рабочие)" точно соответствует "🛒 Продукты (рабочие)"
    2. Частичное совпадение - для похожих названий
       Пример: "продукты" найдет "🛒 Продукты (личные)"
    3. Category key - для дефолтных категорий на разных языках
       Пример: "Groceries" найдет "🛒 Продукты" через ключ "groceries"
    4. Fallback на категорию "other" или первую доступную

    Такой порядок позволяет AI точно указывать кастомные категории,
    избегая коллапса дубликатов с одинаковым category_key.

    Args:
        suggested: Категория предложенная AI (может быть на любом языке, с/без эмодзи)
        available: Список доступных категорий пользователя

    Returns:
        Наиболее подходящая категория из available

    Examples:
        >>> available = ["🛒 Продукты (личные)", "🛒 Продукты (рабочие)", "☕ Кафе"]
        >>> # Точное совпадение - найдет именно вторую
        >>> await find_best_matching_expense_category("Продукты (рабочие)", available)
        "🛒 Продукты (рабочие)"

        >>> # Category key - найдет первую (обе нормализуются к "groceries")
        >>> await find_best_matching_expense_category("Groceries", available)
        "🛒 Продукты (личные)"
    """
    if not available:
        return suggested or get_expense_category_display_name('other', 'ru')

    # 1. ПРИОРИТЕТ: Точное совпадение без эмодзи (для кастомных категорий с уточнениями)
    # Это позволяет AI различать "Продукты (личные)" и "Продукты (рабочие)"
    cleaned_suggested = strip_leading_emoji(suggested).lower()
    if cleaned_suggested:
        for cat in available:
            if cleaned_suggested == strip_leading_emoji(cat).lower():
                logger.info(
                    f"[EXPENSE CATEGORY MATCH] AI suggested '{suggested}' → "
                    f"exact match (no emoji) → matched '{cat}'"
                )
                return cat

    # 2. Частичное совпадение (для похожих названий)
    # Срабатывает если точного нет, но есть вхождение
    if cleaned_suggested:
        for cat in available:
            cleaned_cat = strip_leading_emoji(cat).lower()
            if cleaned_suggested in cleaned_cat or cleaned_cat in cleaned_suggested:
                logger.info(
                    f"[EXPENSE CATEGORY MATCH] AI suggested '{suggested}' → "
                    f"partial match → matched '{cat}'"
                )
                return cat

    # 3. Category key нормализация (для дефолтных категорий на разных языках)
    # Срабатывает когда AI возвращает общее название типа "Groceries"/"Продукты"
    normalized_suggested_key = normalize_expense_category_key(suggested)
    available_map = {}
    for cat in available:
        key = normalize_expense_category_key(cat)
        if key and key not in available_map:
            # Сохраняем первую категорию с этим ключом (для дубликатов)
            available_map[key] = cat

    if normalized_suggested_key:
        # Проверяем есть ли категория с таким ключом
        if normalized_suggested_key in available_map:
            matched_category = available_map[normalized_suggested_key]
            logger.info(
                f"[EXPENSE CATEGORY MATCH] AI suggested '{suggested}' → "
                f"key '{normalized_suggested_key}' → matched '{matched_category}'"
            )
            return matched_category

        # Пробуем найти через отображение ключа в название на разных языках
        for lang in ('ru', 'en'):
            candidate_name = get_expense_category_display_name(normalized_suggested_key, lang)
            if candidate_name in available:
                logger.info(
                    f"[EXPENSE CATEGORY MATCH] AI suggested '{suggested}' → "
                    f"key '{normalized_suggested_key}' → lang '{lang}' → matched '{candidate_name}'"
                )
                return candidate_name

    # 4. Fallback: ищем категорию "Прочие расходы" или возвращаем первую доступную
    other_candidates = [
        cat for cat in available
        if normalize_expense_category_key(cat) == 'other'
    ]
    if other_candidates:
        logger.warning(
            f"[EXPENSE CATEGORY FALLBACK] AI suggested '{suggested}' → "
            f"no match found → using 'other' category '{other_candidates[0]}'"
        )
        return other_candidates[0]

    # Последний шанс - возвращаем первую доступную категорию (если есть)
    if available:
        logger.warning(
            f"[EXPENSE CATEGORY FALLBACK] AI suggested '{suggested}' → "
            f"no match found and no 'other' category → using first available '{available[0]}'"
        )
        return available[0]

    # Совсем крайний случай (available пустой - но мы проверили это в начале)
    return suggested or get_expense_category_display_name('other', 'ru')
