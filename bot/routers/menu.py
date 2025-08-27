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

from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils import get_text
from ..decorators import rate_limit

router = Router(name="menu")




@router.callback_query(lambda c: c.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать главное меню через callback"""
    await show_main_menu(callback, state)


async def show_main_menu(message: types.Message | types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Отображение главного меню согласно ТЗ"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Showing main menu")
    
    text = get_text('main_menu_title', lang)
    
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
        [InlineKeyboardButton(text=get_text('expenses_button', lang), callback_data="expenses_today")],
    ]
    
    # Кешбэк только для подписчиков
    if has_subscription:
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('cashback_button', lang), callback_data="cashback_menu")])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text=get_text('categories_button', lang), callback_data="categories_menu")],
        [InlineKeyboardButton(text=get_text('recurring_button', lang), callback_data="recurring_menu")],
        [InlineKeyboardButton(text=get_text('subscription_button', lang), callback_data="menu_subscription")],
    ])
    
    # Реферальная программа только для подписчиков
    if has_subscription:
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('referral_button', lang), callback_data="menu_referral")])
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text=get_text('settings_button', lang), callback_data="settings")],
        [InlineKeyboardButton(text=get_text('info_button', lang), callback_data="start")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "expenses_today")
async def show_today_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за сегодня"""
    # Импортируем функцию из reports
    from ..routers.reports import show_expenses_summary
    
    today = date.today()
    
    # Используем единую функцию show_expenses_summary
    await show_expenses_summary(
        callback.message,
        today,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
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


