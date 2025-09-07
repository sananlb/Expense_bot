"""
Утилиты для формирования сообщений о расходах
"""
from datetime import date
from typing import Dict, Any, Optional
from ..services.expense import get_today_summary
from ..utils.formatters import format_currency
from ..utils.category_helpers import get_category_display_name


async def format_expense_added_message(
    expense,
    category,
    cashback_text: str = "",
    confidence_text: str = "",
    similar_expense: bool = False,
    reused_from_last: bool = False,
    is_recurring: bool = False,
    lang: str = 'ru'
) -> str:
    """
    Форматирует сообщение о добавленном расходе с информацией о потраченном за день
    
    Args:
        expense: Объект расхода
        category: Категория расхода
        cashback_text: Текст о кешбэке (если есть)
        confidence_text: Текст об уверенности AI (если есть)
        similar_expense: Флаг, что сумма взята из похожей траты
        reused_from_last: Флаг, что использованы данные из последней траты
        is_recurring: Флаг, что это ежемесячный платеж
        
    Returns:
        Отформатированное сообщение
    """
    # Форматируем основную информацию о расходе
    currency = expense.currency or 'RUB'
    amount_text = format_currency(expense.amount, currency)
    
    # Делаем описание жирным и добавляем невидимые символы для расширения
    # Используем неразрывные пробелы (U+00A0) и символ нулевой ширины (U+200B)
    invisible_padding = "\u200B" * 20  # Символы нулевой ширины для расширения
    
    # Добавляем заголовок для ежемесячного платежа
    message = ""
    if is_recurring:
        message = "🔄 <b>Ежемесячный платеж</b>\n\n"
    
    # Убираем префикс [Ежемесячный] из описания если он есть
    description = expense.description
    if description.startswith("[Ежемесячный] "):
        description = description.replace("[Ежемесячный] ", "")
    
    message += f"✅ <b>{description}</b>{invisible_padding}\n\n"
    message += f"🧾 {amount_text}{cashback_text}\n"
    
    # Получаем отображаемое имя категории на языке пользователя
    category_display = get_category_display_name(category, lang)
    message += category_display
    
    # Добавляем уточнения если есть
    if confidence_text:
        message += confidence_text
    
    if similar_expense or reused_from_last:
        message += "\n\n<i>💡 Использованы данные из последней похожей траты</i>"
    
    # Получаем сводку за сегодня
    try:
        today_summary = await get_today_summary(expense.profile.telegram_id)
        
        if today_summary and today_summary.get('currency_totals'):
            message += "\n\n━━━━━━━━━━━━━━━"
            message += "\n💸 <b>Потрачено сегодня:</b>"
            
            # Показываем все валюты, в которых были траты
            currency_totals = today_summary.get('currency_totals', {})
            
            # Сортируем валюты: сначала основная валюта пользователя, потом остальные
            user_currency = expense.profile.currency or 'RUB'
            sorted_currencies = []
            
            # Добавляем основную валюту первой, если есть траты
            if user_currency in currency_totals:
                sorted_currencies.append(user_currency)
            
            # Добавляем остальные валюты
            for curr in sorted(currency_totals.keys()):
                if curr not in sorted_currencies:
                    sorted_currencies.append(curr)
            
            # Выводим суммы по валютам
            for curr in sorted_currencies:
                amount = currency_totals[curr]
                if amount > 0:
                    formatted = format_currency(amount, curr)
                    # Выделяем основную валюту
                    if curr == user_currency:
                        message += f"\n  {formatted}"
                    else:
                        message += f"\n  {formatted}"
    
    except Exception as e:
        # Если не удалось получить сводку, просто не добавляем эту информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting today summary: {e}")
    
    return message


async def format_income_added_message(
    income,
    category,
    similar_income: bool = False,
    lang: str = 'ru'
) -> str:
    """
    Форматирует сообщение о добавленном доходе в едином стиле с расходами
    
    Args:
        income: Объект дохода
        category: Категория дохода
        similar_income: Флаг, что сумма взята из похожего дохода
        lang: Язык пользователя
        
    Returns:
        Отформатированное сообщение
    """
    # Форматируем основную информацию о доходе
    currency = income.currency or 'RUB'
    amount_text = format_currency(income.amount, currency)
    
    # Делаем описание жирным и добавляем невидимые символы для расширения
    invisible_padding = "\u200B" * 20  # Символы нулевой ширины для расширения
    
    message = f"✅ <b>{income.description}</b>{invisible_padding}\n\n"
    message += f"🧾 +{amount_text}\n"
    
    # Получаем отображаемое имя категории на языке пользователя
    if category:
        category_display = get_category_display_name(category, lang)
    else:
        category_display = 'Прочие доходы' if lang == 'ru' else 'Other Income'
    message += category_display
    
    # Добавляем уточнение если использованы данные из последней похожей записи
    if similar_income:
        message += "\n\n<i>💡 Использованы данные из последнего похожего дохода</i>"
    
    # Получаем сводку за сегодня (доходы)
    try:
        from ..services.income import get_today_income_summary
        today_summary = await get_today_income_summary(income.profile.telegram_id)
        
        if today_summary and today_summary.get('currency_totals'):
            message += "\n\n━━━━━━━━━━━━━━━"
            message += "\n💵 <b>Получено сегодня:</b>"
            
            # Показываем все валюты, в которых были доходы
            currency_totals = today_summary.get('currency_totals', {})
            
            # Сортируем валюты: сначала основная валюта пользователя, потом остальные
            user_currency = income.profile.currency or 'RUB'
            sorted_currencies = []
            
            # Добавляем основную валюту первой, если есть доходы
            if user_currency in currency_totals:
                sorted_currencies.append(user_currency)
            
            # Добавляем остальные валюты
            for curr in sorted(currency_totals.keys()):
                if curr not in sorted_currencies:
                    sorted_currencies.append(curr)
            
            # Выводим суммы по валютам
            for curr in sorted_currencies:
                amount = currency_totals[curr]
                if amount > 0:
                    formatted = format_currency(amount, curr)
                    message += f"\n  +{formatted}"
    
    except Exception as e:
        # Если не удалось получить сводку, просто не добавляем эту информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting today income summary: {e}")
    
    return message