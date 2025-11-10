"""
Helper функции для работы с мультиязычными категориями
"""
from typing import Optional
from expenses.models import ExpenseCategory
from bot.utils.language import get_text


def get_category_display_name(category, language_code: str = 'ru') -> str:
    """
    Получить отображаемое имя категории на нужном языке
    
    Эта функция работает как с объектами категорий, так и со строками.
    Для объектов использует новый метод get_display_name().
    Для строк возвращает как есть (для обратной совместимости).
    
    Args:
        category: Объект ExpenseCategory или строка с названием
        language_code: Код языка ('ru' или 'en')
        
    Returns:
        Название категории на нужном языке
    """
    try:
        if isinstance(category, ExpenseCategory):
            # Используем новый метод для объектов категорий
            result = category.get_display_name(language_code)
            return result if result else get_text('no_category', language_code)
        elif isinstance(category, str):
            # Для строк возвращаем как есть (обратная совместимость)
            return category if category else get_text('no_category', language_code)
        elif hasattr(category, 'name'):
            # Если это объект с полем name но не ExpenseCategory
            # (например, IncomeCategory)
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
        import re
        
        # Получаем полное название
        full_name = get_category_display_name(category, language_code)
        if not full_name:
            return get_text('no_category', language_code)
        
        # Удаляем эмодзи
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        
        result = emoji_pattern.sub('', full_name).strip()
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
        category: Объект ExpenseCategory или строка
        
    Returns:
        Эмодзи или None
    """
    try:
        import re
        
        if isinstance(category, ExpenseCategory):
            # Для объектов категорий используем поле icon
            icon = getattr(category, 'icon', None)
            return icon if icon else None
        elif isinstance(category, str):
            # Для строк извлекаем эмодзи
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"
                "\U0001F300-\U0001F5FF"
                "\U0001F680-\U0001F6FF"
                "\U0001F1E0-\U0001F1FF"
                "\U00002702-\U000027B0"
                "\U000024C2-\U0001F251"
                "]+", flags=re.UNICODE
            )
            emojis = emoji_pattern.findall(category)
            return emojis[0] if emojis else None
        elif hasattr(category, 'icon'):
            icon = getattr(category, 'icon', None)
            return icon if icon else None
        else:
            return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_category_emoji: {e}")
        return None