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