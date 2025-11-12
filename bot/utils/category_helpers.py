"""
Helper функции для работы с мультиязычными категориями
"""
from typing import Optional
from bot.utils.language import get_text
from bot.utils.emoji_utils import strip_leading_emoji, EMOJI_PREFIX_RE


def get_category_display_name(category, language_code: str = 'ru') -> str:
    """
    Получить отображаемое имя категории на нужном языке

    Эта функция работает как с объектами категорий, так и со строками.
    Для объектов использует новый метод get_display_name().
    Для строк возвращает как есть (для обратной совместимости).

    Args:
        category: Объект ExpenseCategory, IncomeCategory или строка с названием
        language_code: Код языка ('ru' или 'en')

    Returns:
        Название категории на нужном языке
    """
    try:
        # Duck typing: проверяем наличие метода get_display_name
        # Это работает для ExpenseCategory, IncomeCategory и любых других объектов с этим методом
        if hasattr(category, 'get_display_name') and callable(getattr(category, 'get_display_name')):
            result = category.get_display_name(language_code)
            return result if result else get_text('no_category', language_code)
        elif isinstance(category, str):
            # Для строк возвращаем как есть (обратная совместимость)
            return category if category else get_text('no_category', language_code)
        elif hasattr(category, 'name'):
            # Fallback для объектов с полем name но без метода get_display_name
            name = getattr(category, 'name', None)
            return name if name else get_text('no_category', language_code)
        else:
            return str(category) if category else get_text('no_category', language_code)
    except Exception as e:
        # В случае любых проблем возвращаем fallback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_category_display_name: {e}")
        return get_text('no_category', language_code)


def get_category_name_without_emoji(category, language_code: str = 'ru') -> str:
    """
    Получить название категории без эмодзи

    Args:
        category: Объект ExpenseCategory или строка
        language_code: Код языка

    Returns:
        Название без эмодзи
    """
    try:
        # Получаем полное название
        full_name = get_category_display_name(category, language_code)
        if not full_name:
            return get_text('no_category', language_code)

        # Удаляем эмодзи используя централизованную функцию (включает ZWJ/VS-16)
        result = strip_leading_emoji(full_name)
        return result if result else get_text('no_category', language_code)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_category_name_without_emoji: {e}")
        return get_text('no_category', language_code)


def get_category_emoji(category) -> Optional[str]:
    """
    Получить эмодзи категории

    Args:
        category: Объект ExpenseCategory, IncomeCategory или строка

    Returns:
        Эмодзи или None
    """
    try:
        # Duck typing: проверяем наличие поля icon
        # Работает для ExpenseCategory, IncomeCategory и других объектов с полем icon
        if hasattr(category, 'icon'):
            icon = getattr(category, 'icon', None)
            return icon if icon else None
        elif isinstance(category, str):
            # Для строк извлекаем эмодзи используя централизованный паттерн (включает ZWJ/VS-16)
            match = EMOJI_PREFIX_RE.match(category)
            return match.group(0).strip() if match else None
        else:
            return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_category_emoji: {e}")
        return None