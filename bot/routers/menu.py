"""
Главное меню бота согласно ТЗ
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from datetime import datetime, date
from decimal import Decimal
import asyncio

from ..services.expense import get_today_summary, get_month_summary
from ..services.cashback import calculate_potential_cashback
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils.formatters import format_currency, format_expenses_summary
from ..decorators import rate_limit

router = Router(name="menu")




@router.callback_query(lambda c: c.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать главное меню через callback"""
    await show_main_menu(callback, state)


async def show_main_menu(message: types.Message | types.CallbackQuery, state: FSMContext):
    """Отображение главного меню согласно ТЗ"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Showing main menu")
    
    text = """💰 Главное меню

Выберите действие:"""
    
    # Проверяем подписку для отображения кешбэка
    from bot.services.subscription import check_subscription
    
    # Определяем user_id в зависимости от типа
    if isinstance(message, types.Message):
        user_id = message.from_user.id
    elif isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
        
    has_subscription = await check_subscription(user_id)
    
    # Формируем кнопки меню
    keyboard_buttons = [
        [InlineKeyboardButton(text="📊 Расходы", callback_data="expenses_today")],
    ]
    
    # Кешбэк только для подписчиков
    if has_subscription:
        keyboard_buttons.append([InlineKeyboardButton(text="💳 Кешбэк", callback_data="cashback_menu")])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")],
        [InlineKeyboardButton(text="🔄 Регулярные платежи", callback_data="recurring_menu")],
        [InlineKeyboardButton(text="⭐ Подписка", callback_data="menu_subscription")],
    ])
    
    # Реферальная программа только для подписчиков
    if has_subscription:
        keyboard_buttons.append([InlineKeyboardButton(text="🎁 Реферальная программа", callback_data="menu_referral")])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu")],
        [InlineKeyboardButton(text="📖 Информация", callback_data="start")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "expenses_today")
async def show_today_expenses(callback: types.CallbackQuery, state: FSMContext):
    """Показать траты за сегодня"""
    user_id = callback.from_user.id
    today = date.today()
    
    # Получаем сводку за сегодня
    summary = await get_today_summary(user_id)
    
    if not summary or (not summary.get('currency_totals') or all(v == 0 for v in summary.get('currency_totals', {}).values())):
        text = f"""📊 {today.strftime('%d %B')}

💸 **Потрачено сегодня:**
• 0 ₽

Сегодня трат пока нет."""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 {today.strftime('%d %B')}

💸 **Потрачено сегодня:**
"""
        # Показываем все валюты
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"• {format_currency(amount, curr)}\n"
        
        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📁 По категориям:\n"
            for cat in summary['categories']:
                if cat['amount'] > 0:
                    text += f"\n{cat['icon']} {cat['name']}: {format_currency(cat['amount'], cat['currency'])}"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, today, today)
        if cashback > 0:
            text += f"\n\n💳 **Потенциальный кешбэк:**\n• {format_currency(cashback, 'RUB')}"
        else:
            text += f"\n\n💳 **Потенциальный кешбэк:**\n• 0 ₽"
    
    # Получаем сводку за месяц для проверки наличия трат
    month_summary = await get_month_summary(user_id, today.month, today.year)
    
    # Кнопки навигации
    keyboard_buttons = []
    
    # Показываем кнопку "с начала месяца" только если есть траты за месяц
    if month_summary and month_summary.get('total', 0) > 0:
        keyboard_buttons.append([InlineKeyboardButton(text="📅 Показать с начала месяца", callback_data="expenses_month")])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        # Если не удалось отредактировать, отправляем новое
        await send_message_with_cleanup(callback, state, text, reply_markup=keyboard)
    await callback.answer()




@router.callback_query(lambda c: c.data == "start")
async def show_start(callback: types.CallbackQuery, state: FSMContext):
    """Показать стартовое сообщение (callback на кнопку Инфо)"""
    from ..routers.start import get_start_message, get_start_keyboard
    
    text = get_start_message()
    keyboard = get_start_keyboard()
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        # Если не удалось отредактировать, отправляем новое
        await send_message_with_cleanup(callback, state, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu_main")
async def callback_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать главное меню через callback (возврат из подменю)"""
    await show_main_menu(callback, state)
    await callback.answer()


