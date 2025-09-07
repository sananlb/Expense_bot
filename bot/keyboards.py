"""
Клавиатуры для бота
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.utils import get_text


def main_menu_keyboard(lang: str = 'ru', cashback_enabled: bool = True) -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('expenses_today', lang), callback_data="expenses_today")
    
    # Показываем кнопку кешбэка только если он включен
    if cashback_enabled:
        keyboard.button(text=get_text('cashback_menu', lang), callback_data="cashback_menu")
    
    keyboard.button(text=get_text('categories_menu', lang), callback_data="categories_menu")
    keyboard.button(text=get_text('recurring_menu', lang), callback_data="recurring_menu")
    keyboard.button(text=get_text('settings_menu', lang), callback_data="settings")
    keyboard.button(text=get_text('info', lang), callback_data="start")
    
    # Адаптивная сетка в зависимости от количества кнопок
    if cashback_enabled:
        keyboard.adjust(2, 2, 2)  # 6 кнопок: 2-2-2
    else:
        keyboard.adjust(2, 2, 1)  # 5 кнопок: 2-2-1
    
    return keyboard.as_markup()


def back_close_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Кнопка Закрыть"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(1)
    return keyboard.as_markup()


def settings_keyboard(lang: str = 'ru', cashback_enabled: bool = True) -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('change_language', lang), callback_data="change_language")
    keyboard.button(text=get_text('change_timezone', lang), callback_data="change_timezone")
    keyboard.button(text=get_text('change_currency', lang), callback_data="change_currency")
    
    # Кнопка переключения кешбэка
    status = get_text('disable_cashback' if cashback_enabled else 'enable_cashback', lang)
    cashback_text = get_text('toggle_cashback', lang).format(status=status)
    keyboard.button(text=cashback_text, callback_data="toggle_cashback")
    
    # Кнопка навигации
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(1, 1, 1, 1, 1)
    return keyboard.as_markup()


def get_language_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Выбор языка"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text="🇷🇺 Русский", callback_data="lang_ru")
    keyboard.button(text="🇬🇧 English", callback_data="lang_en")
    
    # Кнопки навигации
    keyboard.button(text=get_text('back_arrow', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(2, 1, 1)
    return keyboard.as_markup()


def get_timezone_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Выбор часового пояса по зонам UTC"""
    keyboard = InlineKeyboardBuilder()
    
    # Отрицательные смещения (UTC-12 до UTC-1)
    for offset in range(12, 0, -1):
        keyboard.button(
            text=f"UTC-{offset}", 
            callback_data=f"tz_-{offset}"
        )
    
    # UTC
    keyboard.button(text="UTC+0", callback_data="tz_0")
    
    # Положительные смещения (UTC+1 до UTC+14)
    for offset in range(1, 15):
        keyboard.button(
            text=f"UTC+{offset}", 
            callback_data=f"tz_+{offset}"
        )
    
    # Кнопки навигации
    keyboard.button(text=get_text('back_arrow', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    # Группируем кнопки по 3 в ряд, последние по одной для навигации
    keyboard.adjust(*[3] * 9, 1, 1)
    return keyboard.as_markup()


def get_currency_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Выбор валюты"""
    keyboard = InlineKeyboardBuilder()
    
    currencies = [
        # Основные валюты
        ("RUB ₽", "curr_rub"),
        ("USD $", "curr_usd"),
        ("EUR €", "curr_eur"),
        # Латинская Америка
        ("ARS $", "curr_ars"),   # Аргентинское песо
        ("COP $", "curr_cop"),   # Колумбийское песо
        ("PEN S/", "curr_pen"),  # Перуанский соль
        ("CLP $", "curr_clp"),   # Чилийское песо
        ("MXN $", "curr_mxn"),   # Мексиканское песо
        ("BRL R$", "curr_brl"),  # Бразильский реал
        # СНГ
        ("KZT ₸", "curr_kzt"),   # Казахстан
        ("UAH ₴", "curr_uah"),   # Украина
        ("BYN Br", "curr_byn"),  # Беларусь
        ("UZS", "curr_uzs"),     # Узбекистан
        ("AMD ֏", "curr_amd"),   # Армения
        ("AZN ₼", "curr_azn"),   # Азербайджан
        ("KGS", "curr_kgs"),     # Киргизия
        ("TJS", "curr_tjs"),     # Таджикистан
        ("TMT", "curr_tmt"),     # Туркменистан
        ("MDL", "curr_mdl"),     # Молдова
        ("GEL ₾", "curr_gel"),   # Грузия
        # Другие популярные валюты
        ("INR ₹", "curr_inr"),   # Индия
        ("CNY ¥", "curr_cny"),   # Китайский юань
        ("TRY ₺", "curr_try"),   # Турецкая лира
        ("GBP £", "curr_gbp"),   # Британский фунт
        ("CHF", "curr_chf"),     # Швейцарский франк
    ]
    
    for text, callback_data in currencies:
        keyboard.button(text=text, callback_data=callback_data)
    
    # Кнопки навигации
    keyboard.button(text=get_text('back_arrow', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    # Группируем по 3 кнопки в ряд (теперь у нас 25 валют + 2 навигационные кнопки)
    keyboard.adjust(*[3] * 8, 1, 1, 1)  # 8 рядов по 3 валюты + 1 валюта + кнопки навигации по одной в ряд
    return keyboard.as_markup()


def expenses_summary_keyboard(lang: str = 'ru', period: str = 'today', show_pdf: bool = True, current_month: int = None, current_year: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для сводки расходов"""
    from datetime import date
    from bot.utils import get_month_name
    
    keyboard = InlineKeyboardBuilder()
    today = date.today()
    
    # Кнопка дневника трат - добавляем только для периода 'today'
    if period == 'today':
        keyboard.button(text=get_text('diary_button', lang), callback_data="show_diary")
        keyboard.button(text=get_text('month_start_button', lang), callback_data="show_month_start")
        
        # Добавляем кнопку предыдущего месяца для удобства навигации
        from bot.utils import get_month_name
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_month_name = get_month_name(prev_month, lang).capitalize()
        keyboard.button(text=f"← {prev_month_name}", callback_data="expenses_prev_month")
        
        # Кнопка Топ-5
        keyboard.button(text=get_text('top5_button', lang), callback_data="top5_menu")
    elif period == 'month' and show_pdf:
        # Для месячных отчетов показываем кнопку PDF
        keyboard.button(text=get_text('generate_pdf', lang), callback_data="pdf_generate_current")
        
        # Кнопки навигации по месяцам
        if current_month and current_year:
            # Определяем предыдущий месяц
            if current_month == 1:
                prev_month = 12
                prev_year = current_year - 1
            else:
                prev_month = current_month - 1
                prev_year = current_year
                
            # Определяем следующий месяц
            if current_month == 12:
                next_month = 1
                next_year = current_year + 1
            else:
                next_month = current_month + 1
                next_year = current_year
            
            # Проверяем, не является ли следующий месяц будущим
            is_future = (next_year > today.year) or (next_year == today.year and next_month > today.month)
            
            # Кнопка предыдущего месяца
            prev_month_name = get_month_name(prev_month, lang).capitalize()
            keyboard.button(text=f"← {prev_month_name}", callback_data="expenses_prev_month")
            
            # Кнопка "Сегодня" - показываем только для текущего месяца
            is_current_month = (current_month == today.month and current_year == today.year)
            if is_current_month:
                keyboard.button(text=get_text('today_arrow', lang), callback_data="expenses_today_view")
            
            # Кнопка следующего месяца (если не будущий)
            if not is_future:
                next_month_name = get_month_name(next_month, lang).capitalize()
                keyboard.button(text=f"{next_month_name} →", callback_data="expenses_next_month")
        else:
            keyboard.button(text=get_text('prev_month_arrow', lang), callback_data="expenses_prev_month")
    
    # Кнопка закрытия
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    if period == 'today':
        keyboard.adjust(1, 1, 1, 1, 1)  # 5 кнопок: дневник, с начала месяца, предыдущий месяц, Топ-5, закрыть
    elif period == 'month' and show_pdf:
        if current_month and current_year:
            # Проверяем количество кнопок навигации
            is_future = (current_year > today.year) or (current_year == today.year and current_month >= today.month)
            
            # Подсчитываем количество кнопок навигации
            nav_buttons = 1  # Всегда есть кнопка предыдущего месяца
            
            # Добавляем кнопку "Сегодня" только для текущего месяца
            is_current_month_check = (current_month == today.month and current_year == today.year)
            if is_current_month_check:
                nav_buttons += 1
                
            if not is_future:
                nav_buttons += 1  # Добавляем кнопку следующего месяца
            
            if nav_buttons == 1:
                keyboard.adjust(1, 1, 1)  # PDF, одна кнопка навигации, закрыть
            elif nav_buttons == 2:
                keyboard.adjust(1, 2, 1)  # PDF, две кнопки навигации, закрыть
            else:
                keyboard.adjust(1, 3, 1)  # PDF, три кнопки навигации, закрыть
        else:
            keyboard.adjust(1, 1, 1)  # PDF, предыдущий месяц, закрыть
    elif period == 'month':  # Месячный отчет без PDF
        if current_month and current_year:
            # Проверяем количество кнопок навигации
            is_future = (current_year > today.year) or (current_year == today.year and current_month >= today.month)
            
            # Подсчитываем количество кнопок навигации
            nav_buttons = 1  # Всегда есть кнопка предыдущего месяца
            
            # Добавляем кнопку "Сегодня" только для текущего месяца
            is_current_month_check = (current_month == today.month and current_year == today.year)
            if is_current_month_check:
                nav_buttons += 1
                
            if not is_future:
                nav_buttons += 1  # Добавляем кнопку следующего месяца
            
            if nav_buttons == 1:
                keyboard.adjust(1, 1)  # Одна кнопка навигации, закрыть
            elif nav_buttons == 2:
                keyboard.adjust(2, 1)  # Две кнопки навигации, закрыть
            else:
                keyboard.adjust(3, 1)  # Три кнопки навигации, закрыть
        else:
            keyboard.adjust(1, 1)  # Предыдущий месяц, закрыть
    else:
        keyboard.adjust(1)  # Только закрытие
    
    return keyboard.as_markup()


def categories_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Меню категорий"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('add_category', lang), callback_data="add_category")
    keyboard.button(text=get_text('delete_category', lang), callback_data="delete_category")
    
    # Кнопка закрытия
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(2, 1)
    return keyboard.as_markup()


def cashback_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Меню кешбэков"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('add_cashback', lang), callback_data="add_cashback")
    keyboard.button(text=get_text('remove_cashback', lang), callback_data="remove_cashback")
    keyboard.button(text=get_text('remove_all_cashback', lang), callback_data="remove_all_cashback")
    
    # Кнопка закрытия
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(2, 1, 1)
    return keyboard.as_markup()


def yes_no_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура Да/Нет"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('yes', lang), callback_data="yes")
    keyboard.button(text=get_text('no', lang), callback_data="no")
    
    keyboard.adjust(2)
    return keyboard.as_markup()


def expense_actions_keyboard(expense_id: int, lang: str = 'ru') -> InlineKeyboardMarkup:
    """Действия с расходом"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('change_category', lang), callback_data=f"change_category:{expense_id}")
    keyboard.button(text=get_text('delete', lang), callback_data=f"delete_expense:{expense_id}")
    
    keyboard.adjust(2)
    return keyboard.as_markup()


def month_selection_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Выбор месяца"""
    keyboard = InlineKeyboardBuilder()
    
    # Месяцы
    months = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]
    
    for i, month in enumerate(months, 1):
        keyboard.button(text=get_text(month, lang), callback_data=f"month_{i}")
    
    # Кнопки навигации
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(3, 3, 3, 3, 1)
    return keyboard.as_markup()
