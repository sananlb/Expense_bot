"""
Утилиты валидации данных
"""
import re
from typing import Optional, Dict, Any
from decimal import Decimal, InvalidOperation
import logging

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
    
    Args:
        text: Текст для парсинга
        allow_only_amount: Разрешить ввод только суммы без описания
        
    Returns:
        dict: {'description': str или None, 'amount': float}
        
    Raises:
        ValueError: Если формат неверный
    """
    parts = text.strip().split()
    
    if len(parts) == 0:
        raise ValueError("Пустой ввод. Отправьте сумму или название и сумму.")
    
    # Если только одна часть
    if len(parts) == 1:
        if allow_only_amount:
            # Пробуем парсить как сумму
            try:
                amount = float(parts[0].replace(',', '.'))
                if amount <= 0:
                    raise ValueError("Сумма должна быть больше 0")
                return {
                    'description': None,  # Описания нет
                    'amount': amount
                }
            except ValueError:
                raise ValueError("Неверный формат суммы")
        else:
            raise ValueError("Неверный формат. Отправьте название и сумму через пробел.")
    
    # Если несколько частей - последняя это сумма
    amount_str = parts[-1]
    
    try:
        amount = float(amount_str.replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть больше 0")
    except ValueError:
        # Может быть это всё описание без суммы?
        if allow_only_amount:
            raise ValueError("Неверный формат. Отправьте сумму или название и сумму.")
        else:
            raise ValueError("Неверный формат суммы")
    
    # Собираем описание из всех частей кроме последней
    description = " ".join(parts[:-1])
    
    # Капитализируем первую букву
    if description:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    return {
        'description': description if description else None,
        'amount': amount
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