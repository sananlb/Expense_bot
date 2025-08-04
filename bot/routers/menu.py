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

router = Router(name="menu")




@router.callback_query(lambda c: c.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать главное меню через callback"""
    await show_main_menu(callback, state)


async def show_main_menu(message: types.Message | types.CallbackQuery, state: FSMContext):
    """Отображение главного меню согласно ТЗ"""
    text = """💰 Главное меню

Выберите действие:"""
    
    # Кнопки главного меню по ТЗ
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Расходы", callback_data="expenses_today")],
        [InlineKeyboardButton(text="💳 Кешбэк", callback_data="cashback_menu")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="categories_menu")],
        [InlineKeyboardButton(text="🔄 Регулярные платежи", callback_data="recurring_menu")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings_menu")],
        [InlineKeyboardButton(text="📖 Информация", callback_data="start")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "expenses_today")
async def show_today_expenses(callback: types.CallbackQuery, state: FSMContext):
    """Показать траты за сегодня"""
    user_id = callback.from_user.id
    today = date.today()
    
    # Получаем сводку за сегодня
    summary = await get_today_summary(user_id)
    
    if not summary or summary['total'] == 0:
        text = f"""📊 Сводка за сегодня, {today.strftime('%d %B')}

💰 Всего: 0 ₽

Сегодня трат пока нет."""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 Сводка за сегодня, {today.strftime('%d %B')}

💰 Всего: {summary['total']:,.0f} ₽

📊 По категориям:"""
        
        # Добавляем категории
        for cat in summary['categories']:
            percent = (cat['amount'] / summary['total']) * 100
            text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽ ({percent:.1f}%)"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, today, today)
        text += f"\n\n💳 Потенциальный кешбэк: {cashback:,.0f} ₽"
    
    # Получаем сводку за месяц для проверки наличия трат
    month_summary = await get_month_summary(user_id, today.month, today.year)
    
    # Кнопки навигации
    keyboard_buttons = []
    
    # Показываем кнопку "с начала месяца" только если есть траты за месяц
    if month_summary and month_summary.get('total', 0) > 0:
        keyboard_buttons.append([InlineKeyboardButton(text="📅 Показать с начала месяца", callback_data="expenses_month")])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️", callback_data="menu"),
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


