"""
Форматирование доходов в стиле дневника
"""
import logging
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from . import get_text
from .category_helpers import get_category_display_name


logger = logging.getLogger(__name__)


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
            title = f"💰 {get_text('income_diary', lang)}"
        return f"{title}\n\n{get_text('no_incomes_found', lang)}"

    if today is None:
        today = date.today()

    if not title:
        title = f"💰 {get_text('income_diary', lang)}"
    
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
        default_desc = get_category_display_name(income.category, lang) if income.category else get_text('income_default_desc', lang)
        description = income.description or default_desc
        if len(description) > 30:
            description = description[:27] + "..."

        # Категория
        category_name = get_category_display_name(income.category, lang) if income.category else get_text('no_category', lang)

        currency = income.currency or income.profile.currency or 'RUB'
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
            'currency': currency,
            'original_amount': income.original_amount if hasattr(income, 'original_amount') else None,
            'original_currency': income.original_currency if hasattr(income, 'original_currency') else None,
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
            date_str = get_text('today', lang)
        elif day_data['date'] == today.replace(day=today.day - 1) if today.day > 1 else None:
            date_str = get_text('yesterday', lang)
        else:
            day = day_data['date'].day
            month_num = day_data['date'].month

            # Получаем название месяца через get_text
            month_keys = [
                'month_january', 'month_february', 'month_march', 'month_april',
                'month_may', 'month_june', 'month_july', 'month_august',
                'month_september', 'month_october', 'month_november', 'month_december'
            ]
            month_name = get_text(month_keys[month_num - 1], lang)

            # Формат даты зависит от языка
            if lang == 'en':
                date_str = f"{month_name} {day}"
            else:
                date_str = f"{day} {month_name}"
        
        text += f"\n<b>📅 {date_str}</b>\n"
        
        # Выводим доходы дня
        for inc in day_data['incomes']:
            from bot.utils import get_currency_symbol
            amount_str = f"{inc['amount']:,.0f}".replace(',', ' ')
            currency_symbol = get_currency_symbol(inc['currency'])
            amount_str += f' {currency_symbol}'

            # Добавляем оригинальную сумму если была конвертация
            original_suffix = ""
            if inc.get('original_amount') and inc.get('original_currency'):
                from bot.utils.formatters import format_currency
                original_formatted = format_currency(inc['original_amount'], inc['original_currency'])
                original_suffix = f" <i>({original_formatted})</i>"

            # Форматируем строку дохода
            text += f"  {inc['time']} — +{inc['description']} {amount_str}{original_suffix}\n"
        
        # Добавляем итог дня
        if day_data['totals']:
            from bot.utils import get_currency_symbol
            text += f"  💰 <b>{get_text('total_for_day', lang)}:</b> "
            totals_list = []
            for curr, total in day_data['totals'].items():
                total_str = f"{total:,.0f}".replace(',', ' ')
                curr_symbol = get_currency_symbol(curr)
                totals_list.append(f"+{total_str} {curr_symbol}")
            text += ", ".join(totals_list) + "\n"

    # Общий итог
    from bot.utils.formatters import format_currency
    totals_by_currency: Dict[str, float] = {}
    for income in incomes_to_show:
        curr = income.currency or income.profile.currency or 'RUB'
        totals_by_currency[curr] = totals_by_currency.get(curr, 0) + float(income.amount)
    if totals_by_currency:
        totals_list = [format_currency(total, curr) for curr, total in sorted(totals_by_currency.items())]
        text += f"\n<b>💎 {get_text('total_income', lang)}: " + ", ".join(totals_list) + "</b>"
    
    # Если было ограничение по количеству
    if is_limited and show_warning:
        text += "\n\n  ...\n"
        text += f"\n<i>💡 Показано {max_incomes} из {total_count} записей</i>"
    
    return text


def format_incomes_from_dict_list(
    incomes_data: List[Dict[str, Any]],
    title: str = None,
    subtitle: str = None,
    max_incomes: int = 100,
    lang: str = 'ru'
) -> str:
    """
    Форматирует список доходов из словарей (результат функций)

    Args:
        incomes_data: Список словарей с данными о доходах
        title: Заголовок
        subtitle: Подзаголовок с общей информацией
        max_incomes: Максимальное количество для показа
        lang: Язык

    Returns:
        Отформатированная строка в HTML формате
    """
    if not incomes_data:
        default_title = f'💰 {get_text("incomes_title", lang)}'
        return f"<b>{title or default_title}</b>\n\n{get_text('no_incomes_found', lang)}"

    from collections import defaultdict

    # Ограничиваем количество
    total_count = len(incomes_data)
    is_limited = total_count > max_incomes
    incomes_to_show = incomes_data[:max_incomes]

    # Начинаем формировать результат
    result_parts = []
    default_title = f'💰 {get_text("incomes_title", lang)}'
    result_parts.append(f"<b>{title or default_title}</b>")
    if subtitle:
        result_parts.append(f"<i>{subtitle}</i>")

    # Группируем по датам
    grouped_by_date = defaultdict(list)
    for income in incomes_to_show:
        date_str = income.get('date', '')
        grouped_by_date[date_str].append(income)

    # Сортируем даты в возрастающем порядке (старые даты вверху)
    sorted_dates = sorted(grouped_by_date.keys())

    today = date.today()

    # Ключи для получения названий месяцев
    month_keys = [
        'month_january', 'month_february', 'month_march', 'month_april',
        'month_may', 'month_june', 'month_july', 'month_august',
        'month_september', 'month_october', 'month_november', 'month_december'
    ]

    for date_str in sorted_dates:
        # Парсим дату для красивого вывода
        try:
            income_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            if income_date == today:
                formatted_date = get_text('today', lang)
            else:
                day = income_date.day
                month_name = get_text(month_keys[income_date.month - 1], lang)

                # Формат даты зависит от языка
                if lang == 'en':
                    formatted_date = f"{month_name} {day}"
                else:
                    formatted_date = f"{day} {month_name}"
        except (TypeError, ValueError) as parse_error:
            logger.debug("Failed to parse income date '%s', using raw string fallback: %s", date_str, parse_error)
            formatted_date = date_str

        result_parts.append(f"\n<b>📅 {formatted_date}</b>")

        day_totals_by_currency = {}
        for income in grouped_by_date[date_str]:
            from bot.utils import get_currency_symbol
            time_str = income.get('time', '00:00')
            amount = income.get('amount', 0)
            description = income.get('description', get_text('income_default_desc', lang))
            currency = income.get('currency') or income.get('profile_currency') or income.get('user_currency') or 'RUB'

            # Форматируем сумму
            amount_str = f"{amount:,.0f}".replace(',', ' ')
            curr_symbol = get_currency_symbol(currency)

            # Добавляем оригинальную сумму если была конвертация
            original_suffix = ""
            if income.get('original_amount') and income.get('original_currency'):
                from bot.utils.formatters import format_currency
                original_formatted = format_currency(income['original_amount'], income['original_currency'])
                original_suffix = f" <i>({original_formatted})</i>"

            # Доходы делаем жирными (как в дневнике)
            result_parts.append(f"  {time_str} — <b>{description}</b> <b>+{amount_str} {curr_symbol}</b>{original_suffix}")

            # Суммируем по валютам
            if currency not in day_totals_by_currency:
                day_totals_by_currency[currency] = 0
            day_totals_by_currency[currency] += amount

        # Итог за день
        totals_list = []
        for curr, total in day_totals_by_currency.items():
            total_str = f"{total:,.0f}".replace(',', ' ')
            curr_symbol = get_currency_symbol(curr)
            totals_list.append(f"+{total_str} {curr_symbol}")
        result_parts.append(f"  💰 <b>{get_text('total_for_day', lang)}:</b> {', '.join(totals_list)}")

    # Если было ограничение
    if is_limited:
        result_parts.append(f"\n⚠️ <i>Показано первые {max_incomes} доходов</i>")

    return "\n".join(result_parts)
