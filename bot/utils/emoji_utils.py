"""
Централизованные утилиты для работы с эмодзи.

ВАЖНО: Это единственное место где определяется EMOJI_PREFIX_RE.
Все остальные модули должны импортировать отсюда.
"""
import re
from typing import Optional


# Универсальный regex для удаления эмодзи в начале строки
# Включает:
# - Все основные диапазоны эмодзи Unicode
# - Zero-Width Joiner (\u200d) для композитных эмодзи типа 👨‍💻, 👨‍👩‍👧
# - Variation Selector-16 (\ufe0f) для цветных версий эмодзи
EMOJI_PREFIX_RE = re.compile(
    r'^[\U0001F000-\U0001F9FF'  # Emoticons, symbols, pictographs
    r'\U00002600-\U000027BF'    # Miscellaneous Symbols
    r'\U0001F300-\U0001F64F'    # Miscellaneous Symbols and Pictographs
    r'\U0001F680-\U0001F6FF'    # Transport and Map Symbols
    r'\u2600-\u27BF'            # Miscellaneous Symbols (compact)
    r'\u2300-\u23FF'            # Miscellaneous Technical
    r'\u2B00-\u2BFF'            # Miscellaneous Symbols and Arrows
    r'\u26A0-\u26FF'            # Miscellaneous Symbols (warning, etc)
    r'\uFE00-\uFE0F'            # Variation Selectors (includes VS-16)
    r'\U000E0100-\U000E01EF'    # Variation Selectors Supplement
    r'\u200d'                   # Zero-Width Joiner (ZWJ) - for composite emoji
    r'\ufe0f'                   # Variation Selector-16 (makes emoji colorful)
    r']+\s*',
    re.UNICODE
)


def strip_leading_emoji(value: Optional[str]) -> str:
    """
    Удаляет эмодзи в начале строки.

    Правильно обрабатывает:
    - Простые эмодзи: "🛒 Продукты" → "Продукты"
    - Композитные (с ZWJ): "👨‍💻 Программист" → "Программист"
    - Множественные: "🛒🍎 Продукты" → "Продукты"
    - С variation selector: "❤️ Здоровье" → "Здоровье"

    Args:
        value: Строка с эмодзи или без

    Returns:
        Строка без начальных эмодзи, trimmed

    Examples:
        >>> strip_leading_emoji("🛒 Продукты")
        "Продукты"
        >>> strip_leading_emoji("👨‍👩‍👧 Семья")
        "Семья"
        >>> strip_leading_emoji("Продукты")
        "Продукты"
    """
    if not value:
        return ''
    return EMOJI_PREFIX_RE.sub('', value).strip()


def normalize_category_for_matching(category: str) -> str:
    """
    Нормализует категорию для сравнения: убирает эмодзи, lowercase, trim.

    Используется для сопоставления категорий без учета эмодзи и регистра.

    Args:
        category: Название категории

    Returns:
        Нормализованное название (lowercase, no emoji, trimmed)

    Examples:
        >>> normalize_category_for_matching("🛒 ПРОДУКТЫ")
        "продукты"
        >>> normalize_category_for_matching("  Кафе и рестораны  ")
        "кафе и рестораны"
    """
    if not category:
        return ''
    # Убираем эмодзи
    category = strip_leading_emoji(category)
    # Нормализуем пробелы и приводим к нижнему регистру
    return ' '.join(category.split()).strip().lower()
