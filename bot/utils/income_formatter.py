"""
Форматирование доходов в стиле дневника
"""
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from . import get_text
from .category_helpers import get_category_display_name


def format_incomes_diary_style(
    incomes: List[Any],
    today: date = None,
    max_incomes: int = 100,
    show_warning: bool = True,
    lang: str = 'ru',
    title: str = None
) -> str:
    """
    Форматирует список доходов в стиле дневника (аналогично тратам)
    
    Args:
        incomes: Список объектов Income
        today: Текущая дата (для определения "Сегодня")
        max_incomes: Максимальное количество доходов для показа
        show_warning: Показывать ли предупреждение о лимите
        lang: Язык
        title: Заголовок (если не указан, используется стандартный)
    
    Returns:
        Отформатированная строка с доходами
    """
    if not incomes:
        if not title:
            title = "💰 Дневник доходов"
        return f"{title}\n\nДоходов не найдено"
    
    if today is None:
        today = date.today()
    
    if not title:
        title = "💰 Дневник доходов"
    
    text = f"{title}\n\n"
    
    # Ограничиваем количество доходов
    total_count = len(incomes)
    is_limited = total_count > max_incomes
    incomes_to_show = incomes[:max_incomes]
    
    # Сортируем доходы по дате (от новых к старым для единообразия)
    incomes_to_show = sorted(
        incomes_to_show, 
        key=lambda x: (x.income_date, x.created_at),
        reverse=True
    )
    
    current_date = None
    day_total = {}  # Для подсчета суммы по валютам за текущий день
    day_incomes = []  # Список доходов текущего дня
    all_days_data = []  # Список для хранения данных по всем дням
    
    for income in incomes_to_show:
        # Если дата изменилась, сохраняем данные предыдущего дня
        if income.income_date != current_date:
            if current_date is not None and day_incomes:
                # Сохраняем данные предыдущего дня
                all_days_data.append({
                    'date': current_date,
                    'incomes': day_incomes,
                    'totals': day_total
                })
            
            # Начинаем новый день
            current_date = income.income_date
            day_total = {}
            day_incomes = []
        
        # Форматируем время, описание и сумму
        time_str = income.created_at.strftime('%H:%M') if income.created_at else '00:00'
        
        # Описание дохода
        default_desc = get_category_display_name(income.category, lang) if income.category else "Доход"
        description = income.description or default_desc
        if len(description) > 30:
            description = description[:27] + "..."
        
        # Категория  
        category_name = get_category_display_name(income.category, lang) if income.category else "Без категории"
        
        currency = 'RUB'  # Доходы всегда в рублях
        amount = float(income.amount)
        
        # Добавляем к сумме дня
        if currency not in day_total:
            day_total[currency] = 0
        day_total[currency] += amount
        
        # Добавляем доход в список дня
        day_incomes.append({
            'time': time_str,
            'description': description,
            'category': category_name,
            'amount': amount,
            'currency': currency
        })
    
    # Добавляем последний день
    if current_date is not None and day_incomes:
        all_days_data.append({
            'date': current_date,
            'incomes': day_incomes,
            'totals': day_total
        })
    
    # Формируем текст вывода
    for day_data in all_days_data:
        # Форматируем дату
        if day_data['date'] == today:
            date_str = "Сегодня"
        elif day_data['date'] == today.replace(day=today.day - 1) if today.day > 1 else None:
            date_str = "Вчера"
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
        
        # Выводим доходы дня
        for income in day_data['incomes']:
            amount_str = f"{income['amount']:,.0f}".replace(',', ' ')
            amount_str += ' ₽'
            
            # Форматируем строку дохода
            text += f"  {income['time']} — +{income['description']} {amount_str}\n"
        
        # Добавляем итог дня
        if day_data['totals']:
            text += "  💰 <b>Итого за день:</b> "
            totals_list = []
            for currency, total in day_data['totals'].items():
                total_str = f"{total:,.0f}".replace(',', ' ')
                currency_symbol = '₽'
                totals_list.append(f"+{total_str} {currency_symbol}")
            text += ", ".join(totals_list) + "\n"
    
    # Общий итог
    grand_total = sum(income.amount for income in incomes_to_show)
    text += f"\n<b>💎 Всего доходов: {grand_total:,.0f} ₽</b>"
    
    # Если было ограничение по количеству
    if is_limited and show_warning:
        text += "\n\n  ...\n"
        text += f"\n<i>💡 Показано {max_incomes} из {total_count} записей</i>"
    
    return text


def format_incomes_from_dict_list(
    incomes_data: List[Dict[str, Any]],
    title: str = None,
    subtitle: str = None,
    max_incomes: int = 100
) -> str:
    """
    Форматирует список доходов из словарей (результат функций)
    
    Args:
        incomes_data: Список словарей с данными о доходах
        title: Заголовок
        subtitle: Подзаголовок с общей информацией
        max_incomes: Максимальное количество для показа
    
    Returns:
        Отформатированная строка
    """
    if not incomes_data:
        return f"{title or '💰 Доходы'}\n\nДоходов не найдено"
    
    # Ограничиваем количество
    total_count = len(incomes_data)
    is_limited = total_count > max_incomes
    incomes_to_show = incomes_data[:max_incomes]
    
    text = f"{title or '💰 Доходы'}\n"
    if subtitle:
        text += f"\n{subtitle}\n"
    text += "\n"
    
    # Группируем по датам
    grouped_by_date = {}
    for income in incomes_to_show:
        date_str = income.get('date', '')
        if date_str not in grouped_by_date:
            grouped_by_date[date_str] = []
        grouped_by_date[date_str].append(income)
    
    # Сортируем даты в обратном порядке (новые первыми)
    sorted_dates = sorted(grouped_by_date.keys(), reverse=True)
    
    today = date.today()
    
    for date_str in sorted_dates:
        # Парсим дату для красивого вывода
        try:
            income_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if income_date == today:
                formatted_date = "Сегодня"
            elif income_date == today.replace(day=today.day - 1) if today.day > 1 else None:
                formatted_date = "Вчера"
            else:
                months_ru = {
                    1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
                    5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
                    9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
                }
                formatted_date = f"{income_date.day} {months_ru.get(income_date.month, income_date.strftime('%B'))}"
        except:
            formatted_date = date_str
        
        text += f"\n<b>📅 {formatted_date}</b>\n"
        
        day_total = 0
        for income in grouped_by_date[date_str]:
            amount = income.get('amount', 0)
            description = income.get('description', 'Доход')
            category = income.get('category', '')
            
            if len(description) > 30:
                description = description[:27] + "..."
            
            amount_str = f"{amount:,.0f}".replace(',', ' ')
            
            # Форматируем строку дохода
            text += f"  +{description} {amount_str} ₽"
            if category and category != 'Без категории':
                text += f" ({category})"
            text += "\n"
            
            day_total += amount
        
        # Итог за день
        if len(grouped_by_date[date_str]) > 1:
            text += f"  💰 <b>Итого за день: +{day_total:,.0f} ₽</b>\n"
    
    # Общий итог
    grand_total = sum(income.get('amount', 0) for income in incomes_to_show)
    text += f"\n<b>💎 Всего: +{grand_total:,.0f} ₽</b>"
    
    # Если было ограничение
    if is_limited:
        text += f"\n\n<i>💡 Показано {max_incomes} из {total_count} записей</i>"
    
    return text