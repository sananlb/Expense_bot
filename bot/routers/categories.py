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
    delete_category, get_icon_for_category, get_category_by_id,
    add_category_keyword, remove_category_keyword, get_category_keywords
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


class CategoryStates(StatesGroup):
    editing_name = State()


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
    import logging
    logger = logging.getLogger(__name__)
    
    # Определяем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    logger.info(f"show_categories_menu called for user_id: {user_id}")
    
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    has_subscription = await check_subscription(user_id)
        
    categories = await get_user_categories(user_id)
    logger.info(f"Found {len(categories)} categories for user {user_id}")
    
    text = "📁 <b>Управление категориями</b>\n\nВаши категории:"
    
    # Показываем все категории пользователя
    if categories:
        text += "\n"
        # Категории уже отсортированы в get_user_categories
        for cat in categories:
            text += f"\n\n• {cat.name}"
    else:
        text += "\n\nУ вас пока нет категорий."
    
    # Формируем клавиатуру в зависимости от подписки
    if has_subscription:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="add_category")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_categories")],
            [InlineKeyboardButton(text="➖ Удалить", callback_data="delete_categories")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
        ])
    else:
        # Без подписки можно только просматривать
        text += "\n\n⚠️ <i>Редактирование категорий доступно только с подпиской</i>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="menu_subscription")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
        ])
    
    # Используем send_message_with_cleanup для правильной работы с меню
    if state:
        sent_msg = await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")
    else:
        # Если state не передан, отправляем обычным способом
        if isinstance(message, types.CallbackQuery):
            sent_msg = await message.bot.send_message(
                chat_id=message.from_user.id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
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
            [InlineKeyboardButton(text="❌ Отмена", callback_data="categories_menu")]
        ])
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await state.set_state(CategoryForm.waiting_for_name)
    await callback.answer()


@router.message(CategoryForm.waiting_for_name)
async def process_category_name(message: types.Message, state: FSMContext):
    """Обработка названия категории"""
    name = message.text.strip()
    
    if len(name) > 50:
        await send_message_with_cleanup(message, state, "❌ Название слишком длинное. Максимум 50 символов.")
        return
    
    # Проверяем, есть ли уже эмодзи в начале названия
    import re
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
    has_emoji = bool(re.match(emoji_pattern, name))
    
    if has_emoji:
        # Если эмодзи уже есть, сразу создаем категорию
        user_id = message.from_user.id
        try:
            category = await create_category(user_id, name, '')
            await state.clear()
            # Сразу показываем меню категорий
            await show_categories_menu(message, state)
        except ValueError as e:
            await send_message_with_cleanup(message, state, f"❌ {str(e)}")
            await state.clear()
    else:
        # Если эмодзи нет, сразу показываем выбор иконок
        await state.update_data(name=name)
        
        icons = [
            ['💰', '💵', '💳', '💸', '🏦'],
            ['🛒', '🍽️', '☕', '🍕', '👪'],
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
        
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_icon")])
        # Убрали кнопку "Назад" по требованию пользователя
        
        await send_message_with_cleanup(
            message, state,
            f"🎨 Выберите иконку для категории «{name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(CategoryForm.waiting_for_icon)




@router.callback_query(lambda c: c.data == "no_icon")
async def no_icon_selected(callback: types.CallbackQuery, state: FSMContext):
    """Создать категорию без иконки"""
    data = await state.get_data()
    name = data.get('name')
    
    user_id = callback.from_user.id
    
    # Проверяем, редактируем ли мы категорию
    editing_category_id = data.get('editing_category_id')
    if editing_category_id:
        # Обновляем существующую категорию вместо удаления
        # Для категории "без иконки" name уже содержит полное название
        category = await update_category(user_id, editing_category_id, name=name)
    else:
        category = await create_category(user_id, name, '')
    
    # Удаляем сообщение с выбором иконок
    try:
        await callback.message.delete()
    except Exception:
        # Игнорируем ошибку, если сообщение уже удалено
        pass
    
    # Очищаем состояние
    await state.clear()
    
    # Показываем меню категорий
    await show_categories_menu(callback, state)
    
    await callback.answer()




@router.callback_query(lambda c: c.data.startswith("set_icon_"))
async def set_category_icon(callback: types.CallbackQuery, state: FSMContext):
    """Установить выбранную иконку"""
    icon = callback.data.replace("set_icon_", "")
    data = await state.get_data()
    name = data.get('name')
    
    user_id = callback.from_user.id
    
    # Проверяем, редактируем ли мы категорию
    editing_category_id = data.get('editing_category_id')
    if editing_category_id:
        # Обновляем существующую категорию вместо удаления
        # Объединяем иконку и название
        full_name = f"{icon} {name}" if icon else name
        category = await update_category(user_id, editing_category_id, name=full_name)
    else:
        category = await create_category(user_id, name, icon)
    
    # Удаляем сообщение с выбором иконок
    try:
        await callback.message.delete()
    except Exception:
        # Игнорируем ошибку, если сообщение уже удалено
        pass
    
    # Очищаем состояние
    await state.clear()
    
    # Показываем меню категорий
    await show_categories_menu(callback, state)
    
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_categories")
async def edit_categories_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список категорий для редактирования"""
    user_id = callback.from_user.id
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    editable_categories = [cat for cat in categories if 'прочие расходы' not in cat.name.lower()]
    
    if not editable_categories:
        await callback.answer("У вас нет категорий для редактирования", show_alert=True)
        return
    
    keyboard_buttons = []
    for cat in editable_categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.name}", 
                callback_data=f"edit_cat_{cat.id}"
            )
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "✏️ Выберите категорию для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data == "delete_categories")
async def delete_categories_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список категорий для удаления"""
    user_id = callback.from_user.id
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    deletable_categories = [cat for cat in categories if 'прочие расходы' not in cat.name.lower()]
    
    if not deletable_categories:
        await callback.answer("У вас нет категорий для удаления", show_alert=True)
        return
    
    keyboard_buttons = []
    for cat in deletable_categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.name}", 
                callback_data=f"del_cat_{cat.id}"
            )
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "🗑 Выберите категорию для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
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
            await callback.answer()
            # Сразу показываем меню категорий
            await show_categories_menu(callback, state)
        else:
            await callback.answer("❌ Не удалось удалить категорию", show_alert=True)
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)



@router.callback_query(lambda c: c.data.startswith("skip_edit_name_"))
async def skip_edit_name(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить изменение названия и перейти к выбору иконки"""
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)
    
    if not category:
        await callback.answer("❌ Категория не найдена", show_alert=True)
        return
    
    # Проверяем, есть ли уже эмодзи в начале названия
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
    has_emoji = bool(re.match(emoji_pattern, category.name))
    
    if has_emoji:
        # Если эмодзи уже есть, просто возвращаемся к меню категорий
        await state.clear()
        await show_categories_menu(callback, state)
        await callback.answer("Название категории оставлено без изменений")
    else:
        # Если эмодзи нет, извлекаем чистое название без эмодзи
        name_without_emoji = re.sub(emoji_pattern + r'\s*', '', category.name)
        
        # Сохраняем данные для выбора иконки
        await state.update_data(
            editing_category_id=cat_id,
            name=name_without_emoji  # Сохраняем название без эмодзи
        )
        
        # Показываем выбор иконок
        icons = [
            ['💰', '💵', '💳', '💸', '🏦'],
            ['🛒', '🍽️', '☕', '🍕', '👪'],
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
        
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️", callback_data="edit_categories")])
        
        await callback.message.edit_text(
            f"🎨 Выберите новую иконку для категории «{name_without_emoji}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(CategoryForm.waiting_for_icon)
        await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cat_"))
async def edit_category(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование категории"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"edit_category called with data: {callback.data}")
    
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)
    
    if category:
        # Сохраняем ID категории в состоянии для последующего редактирования
        await state.update_data(editing_category_id=cat_id, old_category_name=category.name)
        await state.set_state(CategoryStates.editing_name)
        logger.info(f"State set to CategoryStates.editing_name for user {user_id}")
        
        await callback.message.edit_text(
            f"✏️ Редактирование категории «{category.name}»\n\n"
            "Введите новое название категории или нажмите «Пропустить», чтобы оставить текущее:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"skip_edit_name_{cat_id}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_categories")]
            ])
        )
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)
    
    await callback.answer()


@router.message(CategoryStates.editing_name)
async def process_edit_category_name(message: types.Message, state: FSMContext):
    """Обработка нового названия категории"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"process_edit_category_name called for user {message.from_user.id}")
    
    new_name = message.text.strip()
    user_id = message.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    cat_id = data.get('editing_category_id')
    old_name = data.get('old_category_name')
    
    if not cat_id:
        await message.answer("❌ Ошибка: не найдена редактируемая категория")
        await state.clear()
        return
    
    # Проверяем, есть ли уже эмодзи в начале названия
    import re
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
    has_emoji = bool(re.match(emoji_pattern, new_name))
    
    if has_emoji:
        # Если эмодзи уже есть, сразу обновляем категорию
        new_category = await update_category(user_id, cat_id, name=new_name.strip())
        
        if new_category:
            logger.info(f"Category {cat_id} updated successfully with name: {new_name.strip()}")
            
            # Удаляем сообщение пользователя
            try:
                await message.delete()
            except:
                pass
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем меню категорий
            await show_categories_menu(message, state)
        else:
            await message.answer(
                "❌ Не удалось обновить категорию.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="categories_menu")]
                ])
            )
    else:
        # Если эмодзи нет, показываем выбор иконок
        await state.update_data(name=new_name)
        # editing_category_id уже сохранен в состоянии
        
        icons = [
            ['💰', '💵', '💳', '💸', '🏦'],
            ['🛒', '🍽️', '☕', '🍕', '👪'],
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
        
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️", callback_data="edit_categories")])
        
        await send_message_with_cleanup(
            message, state,
            f"🎨 Выберите иконку для категории «{new_name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(CategoryForm.waiting_for_icon)


@router.callback_query(lambda c: c.data == "cancel_category")
async def cancel_category(callback: types.CallbackQuery, state: FSMContext):
    """Отмена операции с категорией"""
    await callback.answer()
    await callback.message.delete()
    # Передаем callback вместо callback.message после удаления
    await show_categories_menu(callback, state)