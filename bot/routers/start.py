"""
Обработчик команды /start и приветствия
"""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
import asyncio

from bot.utils import get_text
from bot.services.profile import get_or_create_profile
from bot.keyboards import main_menu_keyboard, back_close_keyboard
from bot.services.category import create_default_categories
from bot.utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from bot.utils.commands import update_user_commands

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка команды /start - показать информацию о боте"""
    user_id = message.from_user.id
    
    # Создаем или получаем профиль пользователя
    profile = await get_or_create_profile(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code
    )
    
    # Создаем базовые категории для нового пользователя
    created = await create_default_categories(user_id)
    
    # Обновляем команды бота для пользователя
    await update_user_commands(message.bot, user_id)
    
    # Информация о боте
    text = """💰 ExpenseBot - ваш помощник в учете расходов

Основные возможности:

💸 Добавление расходов:
Просто отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

💳 Кешбэки по банковским картам:
Отслеживайте выгодные предложения от банков
Настройте категории с максимальным кешбэком

📊 Отчеты о тратах:
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил сегодня"
Получайте красивые PDF отчеты с графиками"""
    
    # Кнопка закрыть
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    # Отправляем информацию
    await send_message_with_cleanup(message, state, text, reply_markup=inline_keyboard)




@router.callback_query(F.data == "menu")
async def callback_menu(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать главное меню по callback"""
    text = f"{get_text('main_menu', lang)}\n\n{get_text('choose_action', lang)}"
    
    await send_message_with_cleanup(
        callback, state, text,
        reply_markup=main_menu_keyboard(lang)
    )
    await callback.answer()






@router.callback_query(F.data == "start")
async def callback_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать информацию о боте через callback"""
    # Обновляем команды бота для пользователя
    await update_user_commands(callback.bot, callback.from_user.id)
    
    # Информация о боте
    text = """💰 ExpenseBot - ваш помощник в учете расходов

Основные возможности:

💸 Добавление расходов:
Просто отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

💳 Кешбэки по банковским картам:
Отслеживайте выгодные предложения от банков
Настройте категории с максимальным кешбэком

📊 Отчеты о тратах:
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил сегодня"
Получайте красивые PDF отчеты с графиками"""
    
    # Кнопка закрыть
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=inline_keyboard)
    except Exception:
        # Если не удалось отредактировать, отправляем новое
        await send_message_with_cleanup(callback, state, text, reply_markup=inline_keyboard)
    
    await callback.answer()


@router.callback_query(F.data == "close")
async def close_message(callback: types.CallbackQuery, state: FSMContext):
    """Закрытие сообщения"""
    await callback.message.delete()
    # Очищаем последнее сохраненное сообщение меню
    await state.update_data(last_menu_message_id=None)
    await callback.answer()