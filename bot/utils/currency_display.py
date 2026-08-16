"""
Отображение суммы операции в валюте ввода.

Траты и доходы хранятся в валюте пользователя, а исходная сумма при
автоконвертации сохраняется в полях original_amount / original_currency.
Модуль даёт две симметричные части одной задачи:

* сбор валютных полей операции в словарь результата (слой данных);
* рендер суффикса "(10 $)" рядом с суммой (слой отображения).
"""
from typing import Any, Dict, Mapping, Optional

from bot.utils.formatters import format_currency


def operation_currency_fields(operation: Any) -> Dict[str, Any]:
    """
    Возвращает валютные поля операции для результатов AI-функций.

    Args:
        operation: объект Expense или Income

    Returns:
        Словарь с 'currency', а если операция была сконвертирована —
        дополнительно с 'original_amount' и 'original_currency'.
    """
    currency = getattr(operation, 'currency', None)
    fields: Dict[str, Any] = {'currency': currency}

    original_amount = getattr(operation, 'original_amount', None)
    original_currency = getattr(operation, 'original_currency', None)

    if original_amount is not None and original_currency and original_currency != currency:
        fields['original_amount'] = float(original_amount)
        fields['original_currency'] = original_currency

    return fields


def format_original_amount_suffix(data: Mapping[str, Any]) -> str:
    """
    Формирует суффикс с суммой в валюте ввода: " <i>($10)</i>".

    Args:
        data: словарь операции с ключами original_amount / original_currency

    Returns:
        Готовый HTML-суффикс либо пустая строка, если конвертации не было.
    """
    original_amount: Optional[Any] = data.get('original_amount')
    original_currency: Optional[str] = data.get('original_currency')

    if original_amount is None or not original_currency:
        return ''

    return f" <i>({format_currency(abs(float(original_amount)), original_currency)})</i>"
