"""
Утилиты форматирования текста и данных
"""
from typing import Dict, List, Optional, Union
from decimal import Decimal
from datetime import datetime, date
from bot.utils.language import get_text


def format_currency(amount: Union[float, Decimal, int], currency: str = 'RUB') -> str:
    """
    Форматирование суммы с валютой
    
    Args:
        amount: Сумма
        currency: Код валюты
        
    Returns:
        str: Отформатированная строка
    """
    # Словарь символов валют
    currency_symbols = {
        'RUB': '₽',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'CNY': '¥',
        'JPY': '¥',
        'KRW': '₩',
        'INR': '₹',
        'BRL': 'R$',
        'CAD': 'C$',
        'AUD': 'A$',
        'CHF': 'Fr',
        'SEK': 'kr',
        'NOK': 'kr',
        'DKK': 'kr',
        'PLN': 'zł',
        'CZK': 'Kč',
        'HUF': 'Ft',
        'TRY': '₺',
        'MXN': '$',
        'ARS': '$',
        'CLP': '$',
        'COP': '$',
        'PEN': 'S/',
        'UYU': '$U',
        'ZAR': 'R',
        'THB': '฿',
        'SGD': 'S$',
        'HKD': 'HK$',
        'TWD': 'NT$',
        'NZD': 'NZ$',
        'PHP': '₱',
        'IDR': 'Rp',
        'MYR': 'RM',
        'VND': '₫',
        'KZT': '₸',
        'UAH': '₴',
        'BYN': 'Br',
        'AZN': '₼',
        'GEL': '₾',
        'AMD': '֏',
        'MDL': 'L',
        'RON': 'lei',
        'BGN': 'лв',
        'HRK': 'kn',
        'RSD': 'дин',
        'ISK': 'kr',
        'ILS': '₪',
        'EGP': 'E£',
        'MAD': 'DH',
        'AED': 'AED',
        'SAR': 'SAR',
        'QAR': 'QR',
        'OMR': 'OMR',
        'KWD': 'KD',
        'BHD': 'BD',
        'JOD': 'JD',
        'LBP': 'LL',
        'ALL': 'L',
        'MKD': 'ден',
        'BAM': 'KM',
        'DZD': 'DA',
        'TND': 'DT',
        'LYD': 'LD',
        'NGN': '₦',
        'GHS': '₵',
        'KES': 'KSh',
        'UGX': 'USh',
        'TZS': 'TSh',
        'ETB': 'Br',
        'XAF': 'FCFA',
        'XOF': 'CFA',
        'ZMW': 'ZK',
        'BWP': 'P',
        'MZN': 'MT',
        'AOA': 'Kz',
        'MUR': '₨',
        'SCR': '₨',
        'PKR': '₨',
        'LKR': '₨',
        'NPR': '₨',
        'BTN': 'Nu.',
        'MVR': 'Rf',
        'BDT': '৳',
        'MMK': 'K',
        'LAK': '₭',
        'KHR': '៛',
        'MNT': '₮',
        'FJD': 'F$',
        'PGK': 'K',
        'WST': 'T',
        'SBD': 'SI$',
        'TOP': 'T$',
        'VUV': 'VT',
        'XPF': '₣',
        'GMD': 'D',
        'GNF': 'FG',
        'SLL': 'Le',
        'LRD': 'L$',
        'RWF': 'FRw',
        'BIF': 'FBu',
        'MWK': 'MK',
        'LSL': 'L',
        'NAD': 'N$',
        'SZL': 'E',
        'SOS': 'Sh',
        'DJF': 'Fdj',
        'KMF': 'CF',
        'MRU': 'UM',
        'STN': 'Db',
        'CVE': 'Esc',
        'ERN': 'Nfk',
        'TMT': 'm',
        'AFN': '؋',
        'TJS': 'SM',
        'KGS': 'с',
        'UZS': "so'm",
        'YER': '﷼',
        'IQD': 'ID',
        'SYP': '£S',
        'XCD': 'EC$',
        'BBD': 'Bds$',
        'BSD': 'B$',
        'BZD': 'BZ$',
        'BMD': 'BD$',
        'AWG': 'Afl',
        'CUP': '₱',
        'CUC': 'CUC$',
        'DOP': 'RD$',
        'GTQ': 'Q',
        'HNL': 'L',
        'JMD': 'J$',
        'NIO': 'C$',
        'PAB': 'B/.',
        'HTG': 'G',
        'SRD': 'Sr$',
        'TTD': 'TT$',
        'KYD': 'CI$',
        'GIP': '£',
        'SHP': '£',
        'FKP': '£',
        'SDG': 'SDG',
        'SSP': 'SSP',
        'GYD': 'G$',
        'BOB': 'Bs.',
        'PYG': '₲',
        'VES': 'Bs',
        'IRR': '﷼',
        'CRC': '₡',
        'SVC': '$',
        'LVL': 'Ls',
        'LTL': 'Lt',
        'EEK': 'kr'
    }
    
    # Специальная обработка для рублей и других валют без дробной части
    if currency in ['RUB', 'JPY', 'KRW', 'CLP', 'ISK', 'TWD', 'HUF', 'COP', 'IDR', 'VND', 'KHR', 'LAK', 'MMK', 'PYG', 'BIF', 'XAF', 'XOF', 'XPF', 'CLP', 'DJF', 'GNF', 'KMF', 'MGA', 'RWF', 'VUV', 'XAF', 'XOF', 'XPF']:
        formatted_amount = f"{float(amount):,.0f}".replace(',', ' ')
    else:
        formatted_amount = f"{float(amount):,.2f}".replace(',', ' ')
    
    # Получаем символ валюты
    symbol = currency_symbols.get(currency, currency)
    
    # Для некоторых валют символ идет после суммы
    if currency in ['RUB', 'CZK', 'PLN', 'BGN', 'HRK', 'RON', 'RSD', 'UAH', 'KZT', 'BYN', 'MDL', 'ALL', 'MKD', 'BAM', 'TRY', 'ISK', 'NOK', 'SEK', 'DKK']:
        return f"{formatted_amount} {symbol}"
    else:
        return f"{symbol}{formatted_amount}"


def format_expenses_summary(summary: Dict, lang: str = 'ru') -> str:
    """
    Форматирование сводки расходов
    
    Args:
        summary: Словарь с данными сводки
        lang: Язык
        
    Returns:
        str: Отформатированный текст
    """
    if not summary or summary.get('total', 0) == 0:
        return get_text('no_expenses_text', lang)
    
    currency = summary.get('currency', 'RUB')
    total = summary.get('total', 0)
    
    text = f"💰 {get_text('total', lang)}: {format_currency(total, currency)}\n"
    
    # Добавляем количество расходов
    count = summary.get('count', 0)
    if count:
        text += f"📊 {get_text('expenses_count', lang)}: {count}\n"
    
    # Средний чек
    if count > 0:
        avg = total / count
        text += f"📈 {get_text('average_expense', lang)}: {format_currency(avg, currency)}\n"
    
    # Категории
    categories = summary.get('categories', [])
    if categories:
        text += f"\n📂 {get_text('by_categories', lang)}:\n"
        
        for cat in categories:
            percent = (cat['amount'] / total) * 100 if total > 0 else 0
            text += f"{cat.get('icon', '💰')} {cat['name']}: {format_currency(cat['amount'], currency)} ({percent:.1f}%)\n"
    
    return text.strip()


def format_date(date_obj: Union[date, datetime], lang: str = 'ru', format_type: str = 'short') -> str:
    """
    Форматирование даты
    
    Args:
        date_obj: Объект даты
        lang: Язык
        format_type: 'short', 'long', 'full'
        
    Returns:
        str: Отформатированная дата
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    
    months_ru = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ]
    
    months_en = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    if format_type == 'short':
        return date_obj.strftime('%d.%m.%Y')
    elif format_type == 'long':
        if lang == 'ru':
            return f"{date_obj.day} {months_ru[date_obj.month - 1]} {date_obj.year}"
        else:
            return f"{date_obj.day} {months_en[date_obj.month - 1]} {date_obj.year}"
    elif format_type == 'full':
        weekdays_ru = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
        weekdays_en = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        if lang == 'ru':
            weekday = weekdays_ru[date_obj.weekday()]
            return f"{weekday}, {date_obj.day} {months_ru[date_obj.month - 1]} {date_obj.year}"
        else:
            weekday = weekdays_en[date_obj.weekday()]
            return f"{weekday}, {date_obj.day} {months_en[date_obj.month - 1]} {date_obj.year}"
    
    return str(date_obj)


def format_list_items(items: List[str], bullet: str = "•", indent: int = 2) -> str:
    """
    Форматирование списка с буллетами
    
    Args:
        items: Список элементов
        bullet: Символ буллета
        indent: Количество пробелов для отступа
        
    Returns:
        str: Отформатированный список
    """
    indent_str = " " * indent
    return "\n".join([f"{indent_str}{bullet} {item}" for item in items])


def format_percentage(value: float, total: float, decimals: int = 1) -> str:
    """
    Форматирование процентов
    
    Args:
        value: Значение
        total: Общая сумма
        decimals: Количество знаков после запятой
        
    Returns:
        str: Отформатированный процент
    """
    if total == 0:
        return "0%"
    
    percentage = (value / total) * 100
    return f"{percentage:.{decimals}f}%"


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Обрезка текста с добавлением суффикса
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста
        
    Returns:
        str: Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_number(number: Union[int, float], lang: str = 'ru') -> str:
    """
    Форматирование чисел с разделителями тысяч
    
    Args:
        number: Число
        lang: Язык для определения разделителя
        
    Returns:
        str: Отформатированное число
    """
    if lang == 'ru':
        # Для русского языка используем пробел как разделитель
        if isinstance(number, float):
            return f"{number:,.2f}".replace(',', ' ').replace('.', ',')
        else:
            return f"{number:,}".replace(',', ' ')
    else:
        # Для английского используем запятую
        if isinstance(number, float):
            return f"{number:,.2f}"
        else:
            return f"{number:,}"