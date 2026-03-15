"""
Форматирование трат в стиле дневника
"""
import logging
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from . import get_text


logger = logging.getLogger(__name__)


def format_expenses_diary_style(
    expenses: List[Any],
    today: date = None,
    max_expenses: int = 100,
    show_warning: bool = True,
    lang: str = 'ru'
) -> str:
    """
    Форматирует список трат в стиле дневника
    
    Args:
        expenses: Список объектов Expense
        today: Текущая дата (для определения "Сегодня")
        max_expenses: Максимальное количество трат для показа
        show_warning: Показывать ли предупреждение о лимите
    
    Returns:
        Отформатированная строка с тратами
    """
    if not expenses:
        return f"{get_text('diary_title', lang)}\n\n{get_text('no_expenses_found', lang)}"
    
    if today is None:
        today = date.today()
    
    text = f"{get_text('diary_title', lang)}\n\n"
    
    # Ограничиваем количество трат
    total_count = len(expenses)
    is_limited = total_count > max_expenses
    expenses_to_show = expenses[:max_expenses]
    
    # Сортируем траты по дате (от старых к новым)
    expenses_to_show = sorted(
        expenses_to_show, 
        key=lambda x: (x.expense_date, x.expense_time or x.created_at)
    )
    
    current_date = None
    day_total = {}  # Для подсчета суммы по валютам за текущий день
    day_expenses = []  # Список трат текущего дня
    all_days_data = []  # Список для хранения данных по всем дням
    
    for expense in expenses_to_show:
        # Если дата изменилась, сохраняем данные предыдущего дня
        if expense.expense_date != current_date:
            if current_date is not None and day_expenses:
                # Сохраняем данные предыдущего дня
                all_days_data.append({
                    'date': current_date,
                    'expenses': day_expenses,
                    'totals': day_total
                })
            
            # Начинаем новый день
            current_date = expense.expense_date
            day_total = {}
            day_expenses = []
        
        # Форматируем время, описание и сумму
        if expense.expense_time:
            time_str = expense.expense_time.strftime('%H:%M')
        else:
            time_str = expense.created_at.strftime('%H:%M') if expense.created_at else '00:00'
        
        description = expense.description or get_text('no_description', lang)
        if len(description) > 30:
            description = description[:27] + "..."
        
        currency = expense.currency or expense.profile.currency or 'RUB'
        amount = float(expense.amount)
        
        # Добавляем к сумме дня
        if currency not in day_total:
            day_total[currency] = 0
        day_total[currency] += amount
        
        # Добавляем трату в список дня
        day_expenses.append({
            'time': time_str,
            'description': description,
            'amount': amount,
            'currency': currency,
            'original_amount': expense.original_amount if hasattr(expense, 'original_amount') else None,
            'original_currency': expense.original_currency if hasattr(expense, 'original_currency') else None,
        })
    
    # Добавляем последний день
    if current_date is not None and day_expenses:
        all_days_data.append({
            'date': current_date,
            'expenses': day_expenses,
            'totals': day_total
        })
    
    # Формируем текст вывода
    for day_data in all_days_data:
        # Форматируем дату
        if day_data['date'] == today:
            date_str = get_text('today', lang)
        else:
            day = day_data['date'].day
            month = day_data['date'].month
            month_keys = {
                1: 'month_january', 2: 'month_february', 3: 'month_march', 4: 'month_april',
                5: 'month_may', 6: 'month_june', 7: 'month_july', 8: 'month_august',
                9: 'month_september', 10: 'month_october', 11: 'month_november', 12: 'month_december'
            }
            month_name = get_text(month_keys.get(month, 'month_january'), lang)

            if lang == 'en':
                date_str = f"{month_name} {day}"
            else:
                date_str = f"{day} {month_name}"
        
        text += f"\n<b>📅 {date_str}</b>\n"
        
        # Выводим траты дня
        for exp in day_data['expenses']:
            from bot.utils import get_currency_symbol
            amount_str = f"{exp['amount']:,.0f}".replace(',', ' ')
            currency_symbol = get_currency_symbol(exp['currency'])
            amount_str += f' {currency_symbol}'

            # Добавляем оригинальную сумму если была конвертация
            original_suffix = ""
            if exp.get('original_amount') and exp.get('original_currency'):
                from bot.utils.formatters import format_currency
                original_formatted = format_currency(exp['original_amount'], exp['original_currency'])
                original_suffix = f" <i>({original_formatted})</i>"

            text += f"  {exp['time']} — {exp['description']} {amount_str}{original_suffix}\n"
        
        # Добавляем итог дня
        if day_data['totals']:
            text += f"  💰 <b>{get_text('total_for_day', lang)}:</b> "
            from bot.utils import get_currency_symbol
            totals_list = []
            for currency, total in day_data['totals'].items():
                total_str = f"{total:,.0f}".replace(',', ' ')
                curr_symbol = get_currency_symbol(currency)
                totals_list.append(f"{total_str} {curr_symbol}")
            text += ", ".join(totals_list) + "\n"
    
    # Если было ограничение по количеству
    if is_limited and show_warning:
        text += "\n  ...\n  ...\n"
        text += f"\n<i>💡 Я не могу показать более {max_expenses} записей за один раз</i>"
    
    return text


def format_expenses_list(
    expenses: List[Any],
    period_description: str = None,
    max_expenses: int = 100,
    lang: str = 'ru'
) -> str:
    """
    Форматирует СПИСОК трат в стиле дневника.
    Используется ТОЛЬКО когда нужно показать детальный список трат.
    НЕ используется для сводок, статистики по категориям и т.д.
    
    Args:
        expenses: Список объектов Expense
        period_description: Описание периода (например, "за июль")
        max_expenses: Максимальное количество трат
    
    Returns:
        Отформатированная строка со списком трат
    """
    # Используем стандартное форматирование дневника
    text = format_expenses_diary_style(expenses, max_expenses=max_expenses, lang=lang)
    
    # Если есть описание периода, добавляем его в заголовок
    if period_description and expenses:
        text = text.replace(
            get_text('diary_title', lang),
            f"📋 <b>{get_text('expenses_title', lang)} {period_description}</b>"
        )
    
    return text


def format_expenses_from_dict_list(
    expenses_data: List[Dict[str, Any]],
    title: str = None,
    subtitle: str = None,
    max_expenses: int = 100,
    show_warning: bool = None,
    lang: str = 'ru'
) -> str:
    """
    Универсальная функция для форматирования списка трат из словарей в стиле дневника.

    Args:
        expenses_data: Список словарей с данными трат
        title: Заголовок списка
        subtitle: Подзаголовок (например, "Всего: 100 трат на сумму 50000 ₽")
        max_expenses: Максимальное количество трат для показа
        show_warning: Показывать ли предупреждение о лимите

    Returns:
        Отформатированная строка в стиле дневника с HTML форматированием
    """
    if title is None:
        title = get_text('expense_list_title', lang)

    if not expenses_data:
        return f"<b>{title}</b>\n\n{get_text('no_expenses_found', lang)}"

    from datetime import datetime, date
    from collections import defaultdict

    # Группируем по датам
    grouped_expenses = defaultdict(list)
    for exp_data in expenses_data[:max_expenses]:
        # Парсим дату
        date_str = exp_data.get('date', '2024-01-01')
        try:
            expense_date = datetime.fromisoformat(date_str).date()
        except (TypeError, ValueError) as parse_error:
            logger.debug("Failed to parse expense date '%s', using today fallback: %s", date_str, parse_error)
            expense_date = datetime.now().date()

        grouped_expenses[expense_date].append(exp_data)

    # Сортируем даты в возрастающем порядке (старые даты вверху)
    sorted_dates = sorted(grouped_expenses.keys())

    # Форматируем результат
    result_parts = []

    # Добавляем заголовок и подзаголовок
    result_parts.append(f"<b>{title}</b>")
    if subtitle:
        result_parts.append(f"<i>{subtitle}</i>")

    # Форматируем расходы по дням
    today = date.today()
    month_keys = {
        1: 'month_january', 2: 'month_february', 3: 'month_march', 4: 'month_april',
        5: 'month_may', 6: 'month_june', 7: 'month_july', 8: 'month_august',
        9: 'month_september', 10: 'month_october', 11: 'month_november', 12: 'month_december'
    }

    for expense_date in sorted_dates:
        # Форматируем дату
        if expense_date == today:
            date_str = get_text('today', lang)
        else:
            day = expense_date.day
            month = expense_date.month
            month_name = get_text(month_keys.get(month, 'month_january'), lang)

            if lang == 'en':
                date_str = f"{month_name} {day}"
            else:
                date_str = f"{day} {month_name}"

        result_parts.append(f"\n<b>📅 {date_str}</b>")

        # Расходы за день
        day_expenses = grouped_expenses[expense_date]
        day_totals: Dict[str, float] = {}

        for exp_data in day_expenses:
            time_str = exp_data.get('time', '')
            if not time_str:
                time_str = '00:00'

            description = exp_data.get('description') or get_text('no_description', lang)
            amount = exp_data.get('amount', 0)
            currency = exp_data.get('currency') or exp_data.get('profile_currency') or exp_data.get('user_currency') or 'RUB'

            # Форматируем сумму
            from bot.utils import get_currency_symbol
            amount_str = f"{amount:,.0f}".replace(',', ' ')
            currency_symbol = get_currency_symbol(currency)
            amount_str += f' {currency_symbol}'

            result_parts.append(f"  {time_str} — {description} {amount_str}")
            day_totals[currency] = day_totals.get(currency, 0) + amount

        # Добавляем итог за день
        if day_totals:
            from bot.utils.formatters import format_currency
            totals_list = []
            for curr in sorted(day_totals.keys()):
                totals_list.append(format_currency(day_totals[curr], curr))
            result_parts.append(f"  💸 <b>{get_text('grand_total', lang)}:</b> " + ", ".join(totals_list))

    # Предупреждение о лимите
    if show_warning or len(expenses_data) > max_expenses:
        result_parts.append(f"\n⚠️ <i>Показано первые {max_expenses} трат</i>")

    return "\n".join(result_parts)


def is_list_expenses_request(text: str) -> bool:
    """
    Проверяет, запрашивает ли пользователь именно СПИСОК трат,
    а не статистику или сводку
    
    Args:
        text: Текст запроса пользователя
    
    Returns:
        True если запрос на список трат, False если на статистику/сводку
    """
    text_lower = text.lower()
    
    # Фразы, указывающие на запрос СПИСКА трат
    list_keywords = [
        'список трат', 'список расходов',
        'все траты', 'все расходы',
        'что купил', 'что покупал',
        'на что тратил', 'на что потратил',
        'детали трат', 'детали расходов',
        'подробности трат', 'подробности расходов',
        'перечень трат', 'перечень расходов'
    ]
    
    # Фразы, указывающие на запрос СТАТИСТИКИ/СВОДКИ
    summary_keywords = [
        'сколько потратил', 'сколько всего',
        'общая сумма', 'итого',
        'статистика', 'сводка',
        'по категориям', 'категории',
        'анализ', 'отчет',
        'больше всего', 'меньше всего'
    ]
    
    # Проверяем наличие ключевых слов
    has_list_keyword = any(keyword in text_lower for keyword in list_keywords)
    has_summary_keyword = any(keyword in text_lower for keyword in summary_keywords)
    
    # Если есть только list keywords - это запрос списка
    # Если есть summary keywords - это запрос статистики
    # Если нет явных указаний - по умолчанию считаем запросом статистики
    if has_list_keyword and not has_summary_keyword:
        return True
    
    return False
