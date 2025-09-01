"""
Утилиты для работы с языками
"""
from typing import Optional
from asgiref.sync import sync_to_async
from bot.texts import get_text as _get_text, TEXTS
import logging

logger = logging.getLogger(__name__)


async def get_user_language(telegram_id: int) -> str:
    """
    Получить язык пользователя из БД
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Код языка ('ru' или 'en')
    """
    try:
        from expenses.models import Profile
        profile = await sync_to_async(Profile.objects.filter(telegram_id=telegram_id).first)()
        
        if profile and profile.language_code:
            return profile.language_code
            
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        
    return 'ru'  # По умолчанию русский


async def set_user_language(telegram_id: int, language_code: str) -> bool:
    """
    Установить язык пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        language_code: Код языка ('ru' или 'en')
        
    Returns:
        True если успешно, False если ошибка
    """
    if language_code not in ['ru', 'en']:
        return False
        
    try:
        from expenses.models import Profile
        profile = await sync_to_async(Profile.objects.filter(telegram_id=telegram_id).first)()
        
        if profile:
            profile.language_code = language_code
            await sync_to_async(profile.save)()
            return True
            
    except Exception as e:
        logger.error(f"Error setting user language: {e}")
        
    return False


def get_text(key: str, lang: str = 'ru', **kwargs) -> str:
    """
    Получить локализованный текст с поддержкой форматирования
    
    Args:
        key: Ключ текста
        lang: Код языка
        **kwargs: Параметры для форматирования текста
        
    Returns:
        Локализованный текст
    """
    text = _get_text(key, lang)
    
    # Если есть параметры для форматирования
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing format parameter {e} for text key '{key}'")
        except Exception as e:
            logger.error(f"Error formatting text for key '{key}': {e}")
            
    return text


def get_month_name(month: int, lang: str = 'ru') -> str:
    """
    Получить название месяца
    
    Args:
        month: Номер месяца (1-12)
        lang: Код языка
        
    Returns:
        Название месяца
    """
    month_keys = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]
    
    if 1 <= month <= 12:
        return get_text(month_keys[month - 1], lang)
        
    return str(month)


def get_weekday_name(weekday: int, lang: str = 'ru') -> str:
    """
    Получить название дня недели
    
    Args:
        weekday: День недели (0=понедельник, 6=воскресенье)
        lang: Код языка
        
    Returns:
        Название дня недели
    """
    weekday_keys = [
        'monday', 'tuesday', 'wednesday', 'thursday',
        'friday', 'saturday', 'sunday'
    ]
    
    if 0 <= weekday <= 6:
        return get_text(weekday_keys[weekday], lang)
        
    return str(weekday)


def get_currency_symbol(currency: str) -> str:
    """
    Получить символ валюты
    
    Args:
        currency: Код валюты (RUB, USD, EUR)
        
    Returns:
        Символ валюты
    """
    symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'CNY': '¥',
        'JPY': '¥',
        # Latin American currencies
        'ARS': '$',    # Аргентинское песо
        'COP': '$',    # Колумбийское песо
        'PEN': 'S/',   # Перуанский соль
        'CLP': '$',    # Чилийское песо
        'MXN': '$',    # Мексиканское песо
        'BRL': 'R$',   # Бразильский реал
        'UYU': '$U',   # Уругвайское песо
        'BOB': 'Bs',   # Боливийский боливиано
        'CRC': '₡',    # Костариканский колон
        'GTQ': 'Q',    # Гватемальский кетсаль
        'HNL': 'L',    # Гондурасская лемпира
        'NIO': 'C$',   # Никарагуанская кордоба
        'PAB': 'B/.',  # Панамское бальбоа
        'PYG': '₲',    # Парагвайский гуарани
        'DOP': 'RD$',  # Доминиканское песо
        'JMD': 'J$',   # Ямайский доллар
        'TTD': 'TT$',  # Доллар Тринидада и Тобаго
        'BBD': 'Bds$', # Барбадосский доллар
        'BSD': 'B$',   # Багамский доллар
        'BZD': 'BZ$',  # Белизский доллар
        'XCD': 'EC$',  # Восточнокарибский доллар
        # CIS currencies
        'KZT': '₸',
        'UAH': '₴',
        'BYN': 'Br',
        'AMD': '֏',
        'AZN': '₼',
        'GEL': '₾',
        'TRY': '₺',
        'CHF': 'CHF',
        'INR': '₹',
    }
    
    return symbols.get(currency.upper(), currency)


def format_amount(amount: float, currency: str = 'RUB', lang: str = 'ru') -> str:
    """
    Форматировать сумму с валютой
    
    Args:
        amount: Сумма
        currency: Код валюты
        lang: Код языка
        
    Returns:
        Отформатированная строка
    """
    symbol = get_currency_symbol(currency)
    
    # Для рублей и некоторых других валют округляем до целых
    if currency in ['RUB', 'JPY', 'KRW', 'CLP', 'ISK', 'TWD', 'HUF', 'COP', 'IDR', 'VND']:
        if lang == 'en':
            # В английском символ валюты идет перед суммой
            if currency in ['USD', 'EUR', 'GBP']:
                return f"{symbol}{amount:,.0f}"
            else:
                return f"{amount:,.0f} {symbol}"
        else:
            # В русском символ валюты идет после суммы
            return f"{amount:,.0f} {symbol}"
    else:
        if lang == 'en':
            # В английском символ валюты идет перед суммой
            if currency in ['USD', 'EUR', 'GBP']:
                return f"{symbol}{amount:,.2f}"
            else:
                return f"{amount:,.2f} {symbol}"
        else:
            # В русском символ валюты идет после суммы
            return f"{amount:,.2f} {symbol}"


def get_available_languages() -> list:
    """
    Получить список доступных языков
    
    Returns:
        Список кортежей (код, название)
    """
    return [
        ('ru', 'Русский'),
        ('en', 'English')
    ]


def translate_category_name(category_name: str, to_lang: str = 'en') -> str:
    """
    Перевести название категории
    
    Args:
        category_name: Название категории с эмодзи
        to_lang: Целевой язык
        
    Returns:
        Переведенное название с той же эмодзи
    """
    # Словарь переводов стандартных категорий
    translations = {
        # Русский -> Английский (только стандартные категории из DEFAULT_CATEGORIES)
        'Продукты': 'Products',
        'Кафе и рестораны': 'Restaurants and Cafes',
        'АЗС': 'Gas Stations',
        'Транспорт': 'Transport',
        'Автомобиль': 'Car',
        'Жилье': 'Housing',
        'Аптеки': 'Pharmacies',
        'Медицина': 'Medicine',
        'Красота': 'Beauty',
        'Спорт и фитнес': 'Sports and Fitness',
        'Одежда и обувь': 'Clothes and Shoes',
        'Развлечения': 'Entertainment',
        'Образование': 'Education',
        'Подарки': 'Gifts',
        'Путешествия': 'Travel',
        'Родственники': 'Relatives',
        'Коммунальные услуги и подписки': 'Utilities and Subscriptions',
        'Прочие расходы': 'Other Expenses',
        # Английский -> Русский (обратные переводы)
        'Products': 'Продукты',
        'Restaurants and Cafes': 'Кафе и рестораны',
        'Gas Stations': 'АЗС',
        'Transport': 'Транспорт',
        'Car': 'Автомобиль',
        'Housing': 'Жилье',
        'Pharmacies': 'Аптеки',
        'Medicine': 'Медицина',
        'Beauty': 'Красота',
        'Sports and Fitness': 'Спорт и фитнес',
        'Clothes and Shoes': 'Одежда и обувь',
        'Entertainment': 'Развлечения',
        'Education': 'Образование',
        'Gifts': 'Подарки',
        'Travel': 'Путешествия',
        'Relatives': 'Родственники',
        'Utilities and Subscriptions': 'Коммунальные услуги и подписки',
        'Other Expenses': 'Прочие расходы'
    }
    
    # Извлекаем эмодзи и текст из названия
    emoji = ''
    text = category_name
    
    # Находим эмодзи в начале строки (расширенный паттерн для всех эмодзи)
    import re
    # Более полный паттерн для эмодзи
    emoji_pattern = re.compile(
        r'^['
        r'\U0001F000-\U0001F9FF'  # Основные эмодзи
        r'\U00002600-\U000027BF'  # Разные символы
        r'\U0001F300-\U0001F5FF'  # Символы и пиктограммы
        r'\U0001F600-\U0001F64F'  # Эмоции
        r'\U0001F680-\U0001F6FF'  # Транспорт и символы
        r'\u2600-\u27BF'          # Разные символы (короткий диапазон)
        r'\u2300-\u23FF'          # Технические символы
        r'\u2B00-\u2BFF'          # Стрелки и символы
        r'\u26A0-\u26FF'          # Предупреждающие знаки
        r']+'
    )
    match = emoji_pattern.match(category_name)
    
    if match:
        emoji = match.group()
        text = category_name[len(emoji):].strip()
    
    # Для отладки
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"translate_category_name: input='{category_name}', emoji='{emoji}', text='{text}', to_lang='{to_lang}'")
    
    # Если целевой язык русский и текст на английском
    if to_lang == 'ru' and text in translations:
        translated = translations[text]
        result = f"{emoji} {translated}" if emoji else translated
        logger.debug(f"Translated EN->RU: '{text}' -> '{translated}', result='{result}'")
        return result
    
    # Если целевой язык английский и текст на русском
    if to_lang == 'en' and text in translations:
        translated = translations[text]
        result = f"{emoji} {translated}" if emoji else translated
        logger.debug(f"Translated RU->EN: '{text}' -> '{translated}', result='{result}'")
        return result
    
    # Если перевод не найден, возвращаем как есть
    logger.debug(f"No translation found for '{text}' to '{to_lang}'")
    return category_name