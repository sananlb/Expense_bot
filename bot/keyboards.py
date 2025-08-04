"""
Клавиатуры для бота
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.utils import get_text


def main_menu_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('expenses_today', lang), callback_data="expenses_today")
    keyboard.button(text=get_text('cashback_menu', lang), callback_data="cashback_menu")
    keyboard.button(text=get_text('categories_menu', lang), callback_data="categories_menu")
    keyboard.button(text="🔄 Регулярные платежи", callback_data="recurring_menu")
    keyboard.button(text=get_text('settings_menu', lang), callback_data="settings")
    keyboard.button(text=get_text('info', lang), callback_data="start")
    
    keyboard.adjust(2, 2, 2)
    return keyboard.as_markup()


def back_close_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Кнопки Назад и Закрыть"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('back', lang), callback_data="back")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(2)
    return keyboard.as_markup()


def settings_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.button(text=get_text('change_language', lang), callback_data="change_language")
    keyboard.button(text=get_text('change_timezone', lang), callback_data="change_timezone")
    keyboard.button(text=get_text('change_currency', lang), callback_data="change_currency")
    keyboard.button(text=get_text('configure_reports', lang), callback_data="configure_reports")
    
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
    keyboard.button(text=get_text('back', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(2, 2)
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
    keyboard.button(text=get_text('back', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    # Группируем кнопки по 3 в ряд, последние 2 для навигации
    keyboard.adjust(*[3] * 9, 2)
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
    keyboard.button(text=get_text('back', lang), callback_data="settings")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    # Группируем по 3 кнопки в ряд (теперь у нас 25 валют + 2 навигационные кнопки)
    keyboard.adjust(*[3] * 8, 1, 2)  # 8 рядов по 3 валюты + 1 валюта + 2 навигационные кнопки
    return keyboard.as_markup()


def expenses_summary_keyboard(lang: str = 'ru', period: str = 'today') -> InlineKeyboardMarkup:
    """Клавиатура для сводки расходов"""
    keyboard = InlineKeyboardBuilder()
    
    if period == 'today':
        keyboard.button(text=get_text('show_month_start', lang), callback_data="show_month_start")
    else:
        keyboard.button(text=get_text('generate_pdf', lang), callback_data="generate_pdf")
    
    # Кнопка закрытия
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(1, 1)
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
    keyboard.button(text=get_text('back', lang), callback_data="cashback")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    keyboard.adjust(3, 3, 3, 3, 2)
    return keyboard.as_markup()