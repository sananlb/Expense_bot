"""
Утилиты валидации данных
"""
import re
from typing import Optional, Dict, Any
import logging

from .expense_parser import detect_currency

logger = logging.getLogger(__name__)


async def validate_amount(text: str) -> Optional[float]:
    """
    Валидация и парсинг суммы
    
    Args:
        text: Строка с суммой
        
    Returns:
        float: Сумма или None если невалидная
        
    Raises:
        ValueError: Если сумма невалидная
    """
    try:
        # Очищаем строку
        cleaned = text.replace(',', '.').replace(' ', '').strip()
        amount = float(cleaned)
        
        if amount <= 0:
            raise ValueError("Сумма должна быть больше нуля")
            
        # Проверяем на слишком большое значение
        if amount > 999999999:
            raise ValueError("Сумма слишком большая")
            
        return amount
        
    except ValueError as e:
        raise ValueError(f"Неверный формат суммы: {str(e)}")
    except Exception as e:
        logger.error(f"Error validating amount '{text}': {e}")
        raise ValueError("Неверный формат суммы")


def parse_description_amount(text: str, allow_only_amount: bool = False) -> Dict[str, Any]:
    """
    Парсит текст в формате 'Описание Сумма' или просто 'Сумма'
    Поддерживает суммы с пробелами: "48 000", "1 000 000"
    Поддерживает знак + или слово "плюс" для определения доходов

    Args:
        text: Текст для парсинга
        allow_only_amount: Разрешить ввод только суммы без описания

    Returns:
        dict: {'description': str или None, 'amount': float, 'is_income': bool}

    Raises:
        ValueError: Если формат неверный
    """
    # Проверяем на пустой ввод
    if not text or not text.strip():
        raise ValueError("Пустой ввод. Отправьте сумму или название и сумму.")

    text = text.strip()

    # Проверяем знак дохода
    is_income = False

    # Точное совпадение слова "плюс" через границы слов
    if re.search(r'\bплюс\b', text, re.IGNORECASE):
        is_income = True
        text = re.sub(r'\bплюс\b', '', text, flags=re.IGNORECASE)
        text = ' '.join(text.split())

    # Знак + распознается как доход только если перед ним ничего или пробел,
    # и после него (с опциональными пробелами) сразу идут цифры.
    # НЕ матчит "C++" или "abc+500".
    if re.search(r'(^|\s)\+\s*(?=\d)', text):
        is_income = True
        text = re.sub(r'(^|\s)\+\s*(?=\d)', r'\1', text)
        text = ' '.join(text.split())

    # Regex поддерживает суммы с разделителями и без + опциональную валюту в конце
    number_pattern = r'((?:\d{1,3}(?:[\s\xa0,]\d{3})+|\d+)(?:[.,]\d+)?)(?:\s*(?P<currency>[^\d\s].*))?$'
    match = re.search(number_pattern, text, re.IGNORECASE)

    if not match:
        if allow_only_amount:
            if len(text.split()) > 1:
                raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
            raise ValueError("Неверный формат суммы")
        else:
            raise ValueError("Неверный формат. Отправьте название и сумму через пробел.")

    currency_suffix = match.group('currency')
    if currency_suffix:
        currency_suffix = currency_suffix.strip()
        if currency_suffix:
            detected = detect_currency(f"1 {currency_suffix}", user_currency="XXX")
            if detected == "XXX":
                description_end = match.start()
                has_description = bool(text[:description_end].strip())
                if allow_only_amount and has_description:
                    raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
                raise ValueError("Неверный формат суммы")

    amount_str = match.group(1)
    amount_str = amount_str.replace(' ', '').replace('\xa0', '')

    if '.' in amount_str and ',' in amount_str:
        amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        comma_parts = amount_str.split(',')
        if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
            amount_str = amount_str.replace(',', '.')
        else:
            amount_str = amount_str.replace(',', '')

    try:
        amount = float(amount_str)
    except (ValueError, Exception):
        description_end = match.start()
        has_description = bool(text[:description_end].strip())
        if allow_only_amount and has_description:
            raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
        raise ValueError("Неверный формат суммы")

    if amount <= 0:
        raise ValueError("Сумма должна быть больше 0")

    description_end = match.start()
    description = text[:description_end].strip()

    if description:
        words = description.split()
        if len(words) >= 2:
            candidate = " ".join(words[-2:])
            if detect_currency(f"1 {candidate}", user_currency="XXX") != "XXX":
                description = " ".join(words[:-2]).strip()
        if description:
            candidate = description.split()[-1]
            if detect_currency(f"1 {candidate}", user_currency="XXX") != "XXX":
                description = " ".join(description.split()[:-1]).strip()

    if not description and not allow_only_amount:
        raise ValueError("Неверный формат. Отправьте название и сумму через пробел.")

    if description:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    else:
        description = None

    return {
        'description': description,
        'amount': amount,
        'is_income': is_income
    }


def validate_date_format(date_str: str) -> bool:
    """
    Проверка формата даты DD.MM.YYYY
    
    Args:
        date_str: Строка с датой
        
    Returns:
        bool: True если формат правильный
    """
    pattern = r'^\d{2}\.\d{2}\.\d{4}$'
    return bool(re.match(pattern, date_str))


def validate_phone_number(phone: str) -> Optional[str]:
    """
    Валидация и нормализация телефонного номера
    
    Args:
        phone: Номер телефона
        
    Returns:
        str: Нормализованный номер или None
    """
    # Убираем все кроме цифр
    cleaned = re.sub(r'\D', '', phone)
    
    # Проверяем длину
    if len(cleaned) < 10 or len(cleaned) > 15:
        return None
        
    # Если начинается с 8, заменяем на 7 (для РФ)
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '7' + cleaned[1:]
    
    # Добавляем + если нет
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
        
    return cleaned


def validate_email(email: str) -> bool:
    """
    Валидация email адреса
    
    Args:
        email: Email адрес
        
    Returns:
        bool: True если валидный
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
