"""
Обработчик категорий расходов
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
from typing import List

from ..services.category import (
    get_user_categories, create_category, update_category, 
    delete_category, get_icon_for_category, get_category_by_id
)
from ..services.expense import get_month_summary
from ..utils.message_utils import send_message_with_cleanup
from datetime import date

router = Router(name="categories")


class CategoryForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_icon = State()
    waiting_for_edit_choice = State()
    waiting_for_new_name = State()
    waiting_for_new_icon = State()


@router.message(Command("categories"))
async def cmd_categories(message: types.Message, state: FSMContext):
    """Команда /categories - управление категориями"""
    # Удаляем предыдущее меню
    data = await state.get_data()
    old_menu_id = data.get('last_menu_message_id')
    if old_menu_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_menu_id)
        except:
            pass
        await state.update_data(last_menu_message_id=None)
    
    await show_categories_menu(message, state)


async def show_categories_menu(message: types.Message | types.CallbackQuery, state: FSMContext = None):
    """Показать меню категорий"""
    # Определяем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
        
    categories = await get_user_categories(user_id)
    
    text = "📁 Управление категориями\n\nВаши категории:"
    
    # Показываем все категории пользователя
    if categories:
        text += "\n"
        for cat in categories:
            text += f"\n{cat.icon} {cat.name}"
    else:
        text += "\n\nУ вас пока нет категорий."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_category")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_categories")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="delete_categories")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    # Используем send_message_with_cleanup для правильной работы с меню
    if state:
        sent_msg = await send_message_with_cleanup(message, state, text, reply_markup=keyboard)
    else:
        # Если state не передан, отправляем обычным способом
        if isinstance(message, types.CallbackQuery):
            sent_msg = await message.bot.send_message(
                chat_id=message.from_user.id,
                text=text,
                reply_markup=keyboard
            )
        else:
            sent_msg = await message.answer(text, reply_markup=keyboard)
    
    # Сохраняем ID меню если передан state
    if state:
        await state.update_data(last_menu_message_id=sent_msg.message_id)


@router.callback_query(lambda c: c.data == "categories_menu")
async def callback_categories_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню категорий через callback"""
    await callback.message.delete()
    await show_categories_menu(callback.message, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_category")
async def add_category_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления категории"""
    await callback.message.edit_text(
        "➕ Добавление новой категории\n\n"
        "Введите название категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️", callback_data="cancel_category")]
        ])
    )
    await state.set_state(CategoryForm.waiting_for_name)
    await callback.answer()


@router.message(CategoryForm.waiting_for_name)
async def process_category_name(message: types.Message, state: FSMContext):
    """Обработка названия категории"""
    name = message.text.strip()
    
    if len(name) > 50:
        await send_message_with_cleanup(message, state, "❌ Название слишком длинное. Максимум 50 символов.")
        return
    
    # Сохраняем название и предлагаем иконку
    await state.update_data(name=name)
    
    # Автоматически подбираем иконку
    suggested_icon = get_icon_for_category(name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Использовать эту", callback_data=f"use_icon_{suggested_icon}")],
        [InlineKeyboardButton(text="🎨 Выбрать другую", callback_data="choose_icon")],
        [InlineKeyboardButton(text="◀️", callback_data="cancel_category")]
    ])
    
    await send_message_with_cleanup(
        message, state,
        f"Для категории «{name}» предлагаю иконку: {suggested_icon}\n\n"
        "Хотите использовать её или выбрать другую?",
        reply_markup=keyboard
    )
    await state.set_state(CategoryForm.waiting_for_icon)


@router.callback_query(lambda c: c.data.startswith("use_icon_"))
async def use_suggested_icon(callback: types.CallbackQuery, state: FSMContext):
    """Использовать предложенную иконку"""
    icon = callback.data.replace("use_icon_", "")
    data = await state.get_data()
    name = data.get('name')
    
    user_id = callback.from_user.id
    category = await create_category(user_id, name, icon)
    
    await state.clear()
    
    # Показываем сообщение об успешном добавлении и сразу меню категорий
    await callback.message.edit_text(f"✅ Категория «{name}» {icon} успешно добавлена!")
    await callback.answer()
    
    # Небольшая задержка для лучшего UX
    await asyncio.sleep(1)
    
    # Показываем меню категорий
    await show_categories_menu(callback, state)


@router.callback_query(lambda c: c.data == "choose_icon")
async def choose_icon(callback: types.CallbackQuery):
    """Выбор иконки из списка"""
    icons = [
        ['💰', '💵', '💳', '💸', '🏦'],
        ['🛒', '🍽️', '☕', '🍕', '🥘'],
        ['🚗', '🚕', '🚌', '✈️', '⛽'],
        ['🏠', '💡', '🔧', '🛠️', '🏡'],
        ['👕', '👟', '👜', '💄', '💍'],
        ['💊', '🏥', '💉', '🩺', '🏋️'],
        ['📱', '💻', '🎮', '📷', '🎧'],
        ['🎭', '🎬', '🎪', '🎨', '🎯'],
        ['📚', '✏️', '🎓', '📖', '🖊️'],
        ['🎁', '🎉', '🎂', '💐', '🎈']
    ]
    
    keyboard_buttons = []
    for row in icons:
        buttons_row = [InlineKeyboardButton(text=icon, callback_data=f"set_icon_{icon}") for icon in row]
        keyboard_buttons.append(buttons_row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️", callback_data="cancel_category")])
    
    await callback.message.edit_text(
        "🎨 Выберите иконку для категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("set_icon_"))
async def set_category_icon(callback: types.CallbackQuery, state: FSMContext):
    """Установить выбранную иконку"""
    icon = callback.data.replace("set_icon_", "")
    data = await state.get_data()
    name = data.get('name')
    
    user_id = callback.from_user.id
    category = await create_category(user_id, name, icon)
    
    await state.clear()
    
    # Показываем сообщение об успешном добавлении
    await callback.message.edit_text(f"✅ Категория «{name}» {icon} успешно добавлена!")
    await callback.answer()
    
    # Небольшая задержка для лучшего UX
    await asyncio.sleep(1)
    
    # Показываем меню категорий
    await show_categories_menu(callback, state)


@router.callback_query(lambda c: c.data == "edit_categories")
async def edit_categories_list(callback: types.CallbackQuery):
    """Показать список категорий для редактирования"""
    user_id = callback.from_user.id
    categories = await get_user_categories(user_id)
    
    # Все категории можно редактировать
    if not categories:
        await callback.answer("У вас нет категорий для редактирования", show_alert=True)
        return
    
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.icon} {cat.name}", 
                callback_data=f"edit_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️", callback_data="categories_menu")])
    
    await callback.message.edit_text(
        "✏️ Выберите категорию для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "delete_categories")
async def delete_categories_list(callback: types.CallbackQuery):
    """Показать список категорий для удаления"""
    user_id = callback.from_user.id
    categories = await get_user_categories(user_id)
    
    # Можно удалять все категории
    if not categories:
        await callback.answer("У вас нет категорий", show_alert=True)
        return
    
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.icon} {cat.name}", 
                callback_data=f"del_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️", callback_data="categories_menu")])
    
    await callback.message.edit_text(
        "🗑 Выберите категорию для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_cat_"))
async def delete_category_direct(callback: types.CallbackQuery, state: FSMContext):
    """Удаление категории без подтверждения"""
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Получаем информацию о категории для уведомления
    category = await get_category_by_id(user_id, cat_id)
    
    if category:
        success = await delete_category(user_id, cat_id)
        
        if success:
            # Показываем сообщение об успешном удалении
            await callback.message.edit_text(f"✅ Категория «{category.name}» {category.icon} удалена")
            await callback.answer()
            
            # Небольшая задержка для лучшего UX
            await asyncio.sleep(1)
            
            # Возвращаем в меню категорий
            await show_categories_menu(callback, state)
        else:
            await callback.answer("❌ Не удалось удалить категорию", show_alert=True)
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)




@router.callback_query(lambda c: c.data == "cancel_category")
async def cancel_category(callback: types.CallbackQuery, state: FSMContext):
    """Отмена операции с категорией"""
    await state.clear()
    await callback.message.delete()
    await show_categories_menu(callback.message, state)
    await callback.answer()