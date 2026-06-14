"""
Утилиты для формирования сообщений о расходах
"""
from datetime import date
from typing import Dict, Any, Optional
from ..services.expense import get_today_summary
from ..utils.formatters import format_currency
from ..utils.category_helpers import get_category_display_name
from ..utils import get_text

# Константы для разделительных линий (зависят от языка)
SEPARATOR_LINE_RU = "_______________________"  # 23 символа для русского
SEPARATOR_LINE_EN = "_____________________"     # 21 символ для английского


def get_separator_line(lang: str = 'ru') -> str:
    """Возвращает разделительную линию подходящей длины для языка"""
    return SEPARATOR_LINE_EN if lang == 'en' else SEPARATOR_LINE_RU


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
    currency = expense.currency or expense.profile.currency or 'RUB'
    amount_text = format_currency(expense.amount, currency)

    # Проверяем была ли конвертация валюты
    original_text = ""
    if hasattr(expense, 'original_amount') and expense.original_amount and \
       hasattr(expense, 'original_currency') and expense.original_currency:
        original_formatted = format_currency(expense.original_amount, expense.original_currency)
        original_text = f" <i>({original_formatted})</i>"

    # Делаем описание жирным и добавляем невидимые символы для расширения
    # Используем неразрывные пробелы (U+00A0) и символ нулевой ширины (U+200B)
    invisible_padding = "\u200B" * 20  # Символы нулевой ширины для расширения

    # Формируем сообщение
    message = ""

    # Убираем префикс [Ежемесячный] из описания если он есть
    description = expense.description
    if description.startswith("[Ежемесячный] "):
        description = description.replace("[Ежемесячный] ", "")
    if description.startswith("[Регулярный] "):
        description = description.replace("[Регулярный] ", "")

    message += f"✅ <b>{description}</b>{invisible_padding}\n\n"
    message += f"🧾 {amount_text}{original_text}{cashback_text}\n"
    
    # Получаем отображаемое имя категории на языке пользователя
    category_display = get_category_display_name(category, lang)
    message += category_display

    # Добавляем процент израсходованного лимита категории (если лимит установлен)
    if category is not None and getattr(category, 'id', None):
        try:
            from ..services.budget import get_limit_status
            status = await get_limit_status(expense.profile.telegram_id, category.id)
            if status is not None:
                if status.exceeded:
                    message += f" ({status.percent}% 🔴)"
                else:
                    message += f" ({status.percent}%)"
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error getting category limit status: {e}")

    # Добавляем уточнения если есть
    if confidence_text:
        message += confidence_text
    
    if similar_expense or reused_from_last:
        hint_text = "Used data from last similar record" if lang == 'en' else "Использованы данные из последней похожей записи"
        message += f"\n\n<i>💡 {hint_text}</i>"

    # Добавляем метку регулярной операции (курсивом, перед разделительной чертой)
    if is_recurring:
        recurring_label = "💡 Monthly payment" if lang == 'en' else "💡 Ежемесячный платёж"
        message += f"\n\n<i>{recurring_label}</i>"

    # Получаем сводку за дату операции
    try:
        # Определяем за какой день показывать итоги
        from datetime import date
        expense_date = expense.expense_date if hasattr(expense, 'expense_date') else date.today()
        today = date.today()

        # Если операция за сегодня - используем get_today_summary
        if expense_date == today:
            today_summary = await get_today_summary(expense.profile.telegram_id)
            date_label = get_text('spent_today', lang)
        else:
            # Для операций задним числом получаем итоги за ту дату
            from ..services.expense import get_date_summary
            today_summary = await get_date_summary(expense.profile.telegram_id, expense_date)
            # Форматируем дату для отображения
            if expense_date == today.replace(day=today.day - 1) if today.day > 1 else None:
                date_label = get_text('spent_yesterday', lang)
            else:
                spent_on = "Потрачено" if lang == 'ru' else "Spent on"
                date_label = f"{spent_on} {expense_date.strftime('%d.%m.%Y')}"

        if today_summary and today_summary.get('currency_totals'):
            message += f"\n{get_separator_line(lang)}"
            message += f"\n💸 <b>{date_label}:</b>"
            
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

            # Добавляем отступ в конце
            message += "\n"

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
    is_recurring: bool = False,
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
    currency = income.currency or income.profile.currency or 'RUB'
    amount_text = format_currency(income.amount, currency)

    # Проверяем была ли конвертация валюты
    original_text = ""
    if hasattr(income, 'original_amount') and income.original_amount and \
       hasattr(income, 'original_currency') and income.original_currency:
        original_formatted = format_currency(income.original_amount, income.original_currency)
        original_text = f" <i>({original_formatted})</i>"

    # Делаем описание жирным и добавляем невидимые символы для расширения
    invisible_padding = "\u200B" * 20  # Символы нулевой ширины для расширения

    message = ""

    description = income.description
    if description.startswith("[Регулярный] "):
        description = description.replace("[Регулярный] ", "")
    if description.startswith("[Ежемесячный] "):
        description = description.replace("[Ежемесячный] ", "")

    message += f"✅ <b>{description}</b>{invisible_padding}\n\n"
    message += f"🧾 +{amount_text}{original_text}\n"
    
    # Получаем отображаемое имя категории на языке пользователя
    if category:
        category_display = get_category_display_name(category, lang)
    else:
        category_display = 'Прочие доходы' if lang == 'ru' else 'Other Income'
    message += category_display

    # Добавляем прогресс категорийной цели дохода.
    if category is not None and getattr(category, 'id', None):
        try:
            from ..services.income_goal import get_goal_status

            status = await get_goal_status(
                income.profile.telegram_id,
                category.id,
            )
            if status is not None:
                if status.achieved:
                    message += f" ({status.percent}% 🎉)"
                else:
                    message += f" ({status.percent}%)"
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "Error getting income category goal status: %s",
                exc,
            )

    # Добавляем уточнение если использованы данные из последней похожей записи
    if similar_income:
        hint_text = "Used data from last similar record" if lang == 'en' else "Использованы данные из последней похожей записи"
        message += f"\n\n<i>💡 {hint_text}</i>"

    # Добавляем метку регулярной операции (курсивом, перед разделительной чертой)
    if is_recurring:
        recurring_label = "💡 Monthly income" if lang == 'en' else "💡 Ежемесячный доход"
        message += f"\n\n<i>{recurring_label}</i>"

    # Получаем сводку за дату операции (доходы)
    try:
        # Определяем за какой день показывать итоги
        from datetime import date
        income_date = income.income_date if hasattr(income, 'income_date') else date.today()
        today = date.today()

        # Если операция за сегодня - используем get_today_income_summary
        if income_date == today:
            from ..services.income import get_today_income_summary
            today_summary = await get_today_income_summary(income.profile.telegram_id)
            date_label = get_text('received_today', lang)
        else:
            # Для операций задним числом получаем итоги за ту дату
            from ..services.income import get_date_income_summary
            today_summary = await get_date_income_summary(income.profile.telegram_id, income_date)
            # Форматируем дату для отображения
            if income_date == today.replace(day=today.day - 1) if today.day > 1 else None:
                date_label = get_text('received_yesterday', lang)
            else:
                received_on = "Получено" if lang == 'ru' else "Received on"
                date_label = f"{received_on} {income_date.strftime('%d.%m.%Y')}"

        if today_summary and today_summary.get('currency_totals'):
            message += f"\n{get_separator_line(lang)}"
            message += f"\n💵 <b>{date_label}:</b>"
            
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

            # Добавляем отступ в конце
            message += "\n"

    except Exception as e:
        # Если не удалось получить сводку, просто не добавляем эту информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting today income summary: {e}")
    
    return message
