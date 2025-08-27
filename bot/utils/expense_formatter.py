"""
Форматирование трат в стиле дневника
"""
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from . import get_text


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
        
        description = expense.description or "Без описания"
        if len(description) > 30:
            description = description[:27] + "..."
        
        currency = expense.currency or 'RUB'
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
            'currency': currency
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
            date_str = "Сегодня"
        else:
            months_ru = {
                1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
                5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
                9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
            }
            day = day_data['date'].day
            month_name = months_ru.get(day_data['date'].month, day_data['date'].strftime('%B'))
            date_str = f"{day} {month_name}"
        
        text += f"\n<b>📅 {date_str}</b>\n"
        
        # Выводим траты дня
        for expense in day_data['expenses']:
            amount_str = f"{expense['amount']:,.0f}".replace(',', ' ')
            if expense['currency'] == 'RUB':
                amount_str += ' ₽'
            elif expense['currency'] == 'USD':
                amount_str += ' $'
            elif expense['currency'] == 'EUR':
                amount_str += ' €'
            else:
                amount_str += f" {expense['currency']}"
            
            text += f"  {expense['time']} — {expense['description']} {amount_str}\n"
        
        # Добавляем итог дня
        if day_data['totals']:
            text += "  💰 <b>Итого за день:</b> "
            totals_list = []
            for currency, total in day_data['totals'].items():
                total_str = f"{total:,.0f}".replace(',', ' ')
                currency_symbol = {'RUB': '₽', 'USD': '$', 'EUR': '€'}.get(currency, currency)
                totals_list.append(f"{total_str} {currency_symbol}")
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
            f"📋 <b>Траты {period_description}</b>"
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
        Отформатированная строка в стиле дневника (без HTML тегов)
    """
    if title is None:
        title = get_text('expense_list_title', lang)
    
    if not expenses_data:
        return f"{title}\n\nТраты не найдены."
    
    from datetime import datetime
    from types import SimpleNamespace
    import re
    
    # Преобразуем словари в объекты-заглушки
    expense_objects = []
    for exp_data in expenses_data[:max_expenses]:
        expense_obj = SimpleNamespace()
        
        # Парсим дату
        date_str = exp_data.get('date', '2024-01-01')
        try:
            expense_obj.expense_date = datetime.fromisoformat(date_str).date()
        except:
            expense_obj.expense_date = datetime.now().date()
        
        # Парсим время
        time_str = exp_data.get('time', '')
        if time_str:
            try:
                expense_obj.expense_time = datetime.strptime(time_str, '%H:%M').time()
            except:
                expense_obj.expense_time = None
        else:
            expense_obj.expense_time = None
        
        expense_obj.created_at = datetime.now()
        expense_obj.description = exp_data.get('description', 'Без описания')
        expense_obj.amount = exp_data.get('amount', 0)
        expense_obj.currency = exp_data.get('currency', 'RUB')
        
        expense_objects.append(expense_obj)
    
    # Форматируем с помощью стандартного форматтера
    if show_warning is None:
        show_warning = len(expenses_data) > max_expenses
    
    result = format_expenses_diary_style(
        expense_objects,
        max_expenses=max_expenses,
        show_warning=show_warning
    )
    
    # Заменяем заголовок
    full_title = f"{title}"
    if subtitle:
        full_title += f"\n<i>{subtitle}</i>"
    
    result = result.replace(
        get_text('diary_title', lang),
        f"<b>{full_title}</b>"
    )
    
    # Убираем HTML теги для чистого текста
    result = re.sub(r'<[^>]+>', '', result)
    
    return result


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