"""
Обработчик категорий расходов
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
import asyncio
from typing import List

from ..services.category import (
    get_user_categories, create_category, update_category, 
    delete_category, get_icon_for_category, get_category_by_id,
    add_category_keyword, remove_category_keyword, get_category_keywords
)
from ..utils.message_utils import send_message_with_cleanup
from ..utils import get_text, get_user_language, translate_category_name
from datetime import date

router = Router(name="categories")


class CategoryForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_icon = State()
    waiting_for_custom_icon = State()
    waiting_for_edit_choice = State()
    waiting_for_new_name = State()
    waiting_for_new_icon = State()


class IncomeCategoryForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_icon = State()
    waiting_for_custom_icon = State()
    waiting_for_edit_choice = State()
    waiting_for_new_name = State()
    waiting_for_new_icon = State()
    waiting_for_delete_choice = State()


class CategoryStates(StatesGroup):
    editing_name = State()


@router.message(Command("categories"))
async def cmd_categories(message: types.Message, state: FSMContext):
    """Команда /categories - управление категориями"""
    # Удаляем предыдущее меню ТОЛЬКО если это НЕ меню кешбека
    data = await state.get_data()
    old_menu_id = data.get('last_menu_message_id')
    cashback_menu_ids = data.get('cashback_menu_ids', [])
    
    # Проверяем, не является ли это меню кешбека
    if old_menu_id and old_menu_id not in cashback_menu_ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old_menu_id)
            await state.update_data(last_menu_message_id=None)
        except (TelegramBadRequest, TelegramNotFound):
            pass  # Сообщение уже удалено
    
    # По умолчанию показываем категории трат  
    await show_expense_categories_menu(message, state)


async def show_categories_menu(message: types.Message | types.CallbackQuery, state: FSMContext = None):
    """Показать главное меню категорий с выбором типа"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Определяем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    logger.info(f"show_categories_menu called for user_id: {user_id}")
    
    # Получаем язык пользователя
    lang = await get_user_language(user_id)
    
    # Новое меню выбора типа категорий
    text = "📁 <b>Категории</b>\n\nВыберите тип категорий:"
    
    # Кнопки выбора типа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Категории трат", callback_data="expense_categories_menu")],
        [InlineKeyboardButton(text="💰 Категории доходов", callback_data="income_categories_menu")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    # Отправляем сообщение
    
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


async def show_expense_categories_menu(message: types.Message | types.CallbackQuery, state: FSMContext = None):
    """Показать меню категорий трат"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Определяем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    logger.info(f"show_expense_categories_menu called for user_id: {user_id}")
    
    # Получаем язык пользователя
    lang = await get_user_language(user_id)
    
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    has_subscription = await check_subscription(user_id)
        
    categories = await get_user_categories(user_id)
    logger.info(f"Found {len(categories)} expense categories for user {user_id}")
    
    text = "📁 <b>Категории трат</b>\n\n"
    
    # Показываем все категории пользователя
    if categories:
        # Категории уже отсортированы в get_user_categories
        for i, cat in enumerate(categories):
            # Переводим название категории если нужно
            translated_name = translate_category_name(cat.name, lang)
            text += f"• {translated_name}\n"
            # Добавляем отступ между категориями
            if i < len(categories) - 1:
                text += "\n"
    else:
        text += get_text('no_categories_yet', lang)
    
    # Формируем клавиатуру в зависимости от подписки
    if has_subscription:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_button', lang), callback_data="add_category")],
            [InlineKeyboardButton(text=get_text('edit_button', lang), callback_data="edit_categories")],
            [InlineKeyboardButton(text=get_text('delete_button', lang), callback_data="delete_categories")],
            [InlineKeyboardButton(text="💰 Категории доходов", callback_data="income_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    else:
        # Без подписки можно только просматривать
        text += "\n\n" + get_text('categories_subscription_note', lang)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('get_subscription', lang), callback_data="menu_subscription")],
            [InlineKeyboardButton(text="💰 Категории доходов", callback_data="income_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    
    # Отправляем сообщение
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


async def show_income_categories_menu(message: types.Message | types.CallbackQuery, state: FSMContext = None):
    """Показать меню категорий доходов"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Определяем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    logger.info(f"show_income_categories_menu called for user_id: {user_id}")
    
    # Получаем язык пользователя
    lang = await get_user_language(user_id)
    
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    has_subscription = await check_subscription(user_id)
    
    # Получаем категории доходов
    from bot.services.income import get_user_income_categories
    income_categories = await get_user_income_categories(user_id)
    logger.info(f"Found {len(income_categories)} income categories for user {user_id}")
    
    text = "📁 <b>Категории доходов</b>\n\n"
    
    # Показываем все категории доходов
    if income_categories:
        for i, cat in enumerate(income_categories):
            translated_name = translate_category_name(cat.name, lang)
            text += f"• {translated_name}\n"
            # Добавляем отступ между категориями
            if i < len(income_categories) - 1:
                text += "\n"
    else:
        text += get_text('no_income_categories_yet', lang) if lang == 'en' else "У вас пока нет категорий доходов."
    
    # Формируем клавиатуру в зависимости от подписки
    if has_subscription:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_button', lang), callback_data="add_income_category")],
            [InlineKeyboardButton(text=get_text('edit_button', lang), callback_data="edit_income_categories")],
            [InlineKeyboardButton(text=get_text('delete_button', lang), callback_data="delete_income_categories")],
            [InlineKeyboardButton(text="💸 Категории трат", callback_data="expense_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    else:
        # Без подписки можно только просматривать
        text += "\n\n" + (get_text('income_categories_subscription_note', lang) if lang == 'en' else "💎 Для управления категориями доходов необходима подписка")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('get_subscription', lang), callback_data="menu_subscription")],
            [InlineKeyboardButton(text="💸 Категории трат", callback_data="expense_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    
    # Отправляем сообщение
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
    """Показать главное меню категорий через callback"""
    # Проверяем, находимся ли мы в состоянии редактирования траты
    current_state = await state.get_state()
    
    # Очищаем состояние только если НЕ редактируем трату
    if current_state and not current_state.startswith("EditExpenseForm"):
        await state.clear()
    
    await callback.message.delete()
    # Показываем сразу категории трат вместо меню выбора
    await show_expense_categories_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "expense_categories_menu")
async def callback_expense_categories_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню категорий трат"""
    # Убираем удаление - send_message_with_cleanup сама отредактирует сообщение
    await show_expense_categories_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "income_categories_menu")
async def callback_income_categories_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню категорий доходов"""
    # Убираем удаление - send_message_with_cleanup сама отредактирует сообщение
    await show_income_categories_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_category")
async def add_category_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления категории"""
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        get_text('adding_category', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('cancel', lang), callback_data="categories_menu")]
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
            # Сразу показываем меню категорий трат
            await show_expense_categories_menu(message, state)
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
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свой эмодзи", callback_data="custom_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_category_creation")])
        
        await send_message_with_cleanup(
            message, state,
            f"🎨 Выберите иконку для категории «{name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(CategoryForm.waiting_for_icon)




@router.callback_query(lambda c: c.data == "custom_icon")
async def custom_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Запрос пользовательского эмодзи"""
    await callback.message.edit_text(
        "✏️ Отправьте свой эмодзи для категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="categories_menu")]
        ])
    )
    await state.set_state(CategoryForm.waiting_for_custom_icon)
    await callback.answer()


@router.message(CategoryForm.waiting_for_custom_icon)
async def process_custom_icon(message: types.Message, state: FSMContext):
    """Обработка пользовательского эмодзи"""
    import re
    
    custom_icon = message.text.strip()
    
    # Проверяем, что введен один эмодзи
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+$'
    if not re.match(emoji_pattern, custom_icon) or len(custom_icon) > 2:
        await send_message_with_cleanup(message, state, "❌ Пожалуйста, отправьте только один эмодзи.")
        return
    
    data = await state.get_data()
    name = data.get('name')
    user_id = message.from_user.id
    
    # Проверяем, редактируем ли мы категорию
    editing_category_id = data.get('editing_category_id')
    if editing_category_id:
        # Обновляем существующую категорию
        full_name = f"{custom_icon} {name}" if custom_icon else name
        category = await update_category(user_id, editing_category_id, name=full_name)
    else:
        category = await create_category(user_id, name, custom_icon)
    
    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass  # Сообщение уже удалено
    
    # Очищаем состояние
    await state.clear()
    
    # Показываем меню категорий трат
    await show_expense_categories_menu(message, state)


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
    
    # Показываем меню категорий трат (не общее меню)
    await show_expense_categories_menu(callback, state)
    
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
    
    # Показываем меню категорий трат (не общее меню)
    await show_expense_categories_menu(callback, state)
    
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_categories")
async def edit_categories_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список категорий для редактирования"""
    # Очищаем состояние при возврате к списку категорий для редактирования
    await state.clear()
    
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    editable_categories = [cat for cat in categories if 'прочие расходы' not in cat.name.lower()]
    
    if not editable_categories:
        await callback.answer("У вас нет категорий для редактирования", show_alert=True)
        return
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(editable_categories), 2):
        # Переводим название категории
        translated_name = translate_category_name(editable_categories[i].name, lang)
        row = [InlineKeyboardButton(
            text=translated_name, 
            callback_data=f"edit_cat_{editable_categories[i].id}"
        )]
        if i + 1 < len(editable_categories):
            translated_name_2 = translate_category_name(editable_categories[i + 1].name, lang)
            row.append(InlineKeyboardButton(
                text=translated_name_2, 
                callback_data=f"edit_cat_{editable_categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")])
    
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
    lang = await get_user_language(user_id)
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    deletable_categories = [cat for cat in categories if 'прочие расходы' not in cat.name.lower()]
    
    if not deletable_categories:
        await callback.answer("У вас нет категорий для удаления", show_alert=True)
        return
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(deletable_categories), 2):
        # Переводим название категории
        translated_name = translate_category_name(deletable_categories[i].name, lang)
        row = [InlineKeyboardButton(
            text=translated_name, 
            callback_data=f"del_cat_{deletable_categories[i].id}"
        )]
        if i + 1 < len(deletable_categories):
            translated_name_2 = translate_category_name(deletable_categories[i + 1].name, lang)
            row.append(InlineKeyboardButton(
                text=translated_name_2, 
                callback_data=f"del_cat_{deletable_categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")])
    
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
            # Сразу показываем меню категорий трат
            await show_expense_categories_menu(callback, state)
        else:
            await callback.answer("❌ Не удалось удалить категорию", show_alert=True)
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)



# Обработчик skip_edit_name удален - теперь используется новый процесс редактирования


@router.callback_query(lambda c: c.data.startswith("edit_cat_"))
async def edit_category(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование категории"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"edit_category called with data: {callback.data}")
    
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)
    
    if category:
        # Сохраняем ID категории в состоянии для последующего редактирования
        await state.update_data(editing_category_id=cat_id, old_category_name=category.name)
        
        # Показываем меню выбора что редактировать
        await callback.message.edit_text(
            f"✏️ Редактирование категории «{category.name}»\n\n"
            "Что вы хотите изменить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Название", callback_data=f"edit_cat_name_{cat_id}")],
                [InlineKeyboardButton(text="🎨 Иконку", callback_data=f"edit_cat_icon_{cat_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_categories")]
            ])
        )
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)
    
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cat_name_"))
async def edit_category_name_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования названия категории"""
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)
    
    if category:
        await state.update_data(editing_category_id=cat_id)
        await state.set_state(CategoryStates.editing_name)
        
        await callback.message.edit_text(
            f"📝 Введите новое название для категории «{category.name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_cat_{cat_id}")]
            ])
        )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cat_icon_"))
async def edit_category_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования иконки категории"""
    import re
    
    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)
    
    if category:
        # Извлекаем чистое название без эмодзи
        emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+\s*'
        name_without_emoji = re.sub(emoji_pattern, '', category.name)
        
        await state.update_data(
            editing_category_id=cat_id,
            name=name_without_emoji
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
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свой эмодзи", callback_data="custom_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_cat_{cat_id}")])
        
        await callback.message.edit_text(
            f"🎨 Выберите новую иконку для категории «{name_without_emoji}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(CategoryForm.waiting_for_icon)
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
    
    # Получаем текущую категорию для извлечения иконки
    current_category = await get_category_by_id(user_id, cat_id)
    if not current_category:
        await message.answer("❌ Категория не найдена")
        await state.clear()
        return
    
    # Проверяем, есть ли эмодзи в текущем названии категории
    import re
    emoji_pattern = r'^([\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+)\s*'
    current_emoji_match = re.match(emoji_pattern, current_category.name)
    current_emoji = current_emoji_match.group(1) if current_emoji_match else None
    
    # Проверяем, есть ли эмодзи в новом названии
    new_emoji_match = re.match(emoji_pattern, new_name)
    has_new_emoji = bool(new_emoji_match)
    
    if has_new_emoji:
        # Если в новом названии есть эмодзи, используем его как есть
        final_name = new_name.strip()
    elif current_emoji:
        # Если в новом названии нет эмодзи, но есть в старом - сохраняем старую иконку
        final_name = f"{current_emoji} {new_name.strip()}"
    else:
        # Если нет эмодзи ни в старом, ни в новом - оставляем без иконки
        final_name = new_name.strip()
    
    # Всегда обновляем категорию с финальным названием
    new_category = await update_category(user_id, cat_id, name=final_name)
    
    if new_category:
        logger.info(f"Category {cat_id} updated successfully with name: {final_name}")
        
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except (TelegramBadRequest, TelegramNotFound):
            pass  # Сообщение уже удалено
        
        # Очищаем состояние
        await state.clear()
        
        # Показываем меню категорий трат (не общее меню)
        await show_expense_categories_menu(message, state)
    else:
        await message.answer(
            "❌ Не удалось обновить категорию.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="categories_menu")]
            ])
        )


@router.callback_query(lambda c: c.data == "cancel_category")
async def cancel_category(callback: types.CallbackQuery, state: FSMContext):
    """Отмена операции с категорией"""
    await callback.answer()
    await callback.message.delete()
    # Передаем callback вместо callback.message после удаления
    await show_expense_categories_menu(callback, state)


@router.callback_query(lambda c: c.data == "cancel_category_creation")
async def cancel_category_creation(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания категории"""
    await state.clear()
    # Не удаляем сообщение - send_message_with_cleanup отредактирует его
    await show_expense_categories_menu(callback, state)
    await callback.answer()


# ========== ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИЙ ДОХОДОВ ==========

@router.callback_query(lambda c: c.data == "add_income_category")
async def add_income_category_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления категории доходов"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    if not await check_subscription(callback.from_user.id):
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return
    
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        "📝 Введите название категории доходов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="income_categories_menu")]
        ])
    )
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await state.set_state(IncomeCategoryForm.waiting_for_name)
    await callback.answer()


@router.message(IncomeCategoryForm.waiting_for_name)
async def process_income_category_name(message: types.Message, state: FSMContext):
    """Обработка названия категории доходов"""
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
            from bot.services.income import create_income_category
            category = await create_income_category(user_id, name, '')
            await state.clear()
            await show_income_categories_menu(message, state)
        except ValueError as e:
            await send_message_with_cleanup(message, state, f"❌ {str(e)}")
            await state.clear()
    else:
        # Если эмодзи нет, показываем выбор иконок
        await state.update_data(income_category_name=name)
        
        # Иконки для категорий доходов
        icons = [
            ['💰', '💵', '💸', '💴', '💶'],
            ['💷', '💳', '🏦', '💹', '📈'],
            ['💼', '💻', '🏢', '🏭', '👔'],
            ['🎯', '🎁', '🎉', '🏆', '💎'],
            ['🚀', '✨', '⭐', '🌟', '💫'],
            ['📱', '🎮', '🎬', '🎭', '🎨'],
            ['🏠', '🚗', '✈️', '🛍️', '🍔'],
            ['📚', '🎓', '🏥', '⚽', '🎸']
        ]
        
        keyboard_buttons = []
        for row in icons:
            buttons_row = [InlineKeyboardButton(text=icon, callback_data=f"set_income_icon_{icon}") for icon in row]
            keyboard_buttons.append(buttons_row)
        
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_income_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свой эмодзи", callback_data="custom_income_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_income_category_creation")])
        
        await send_message_with_cleanup(
            message, state,
            f"🎨 Выберите иконку для категории доходов «{name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(IncomeCategoryForm.waiting_for_icon)


@router.callback_query(lambda c: c.data.startswith("set_income_icon_"), IncomeCategoryForm.waiting_for_icon)
async def set_income_category_icon(callback: types.CallbackQuery, state: FSMContext):
    """Установка иконки категории доходов"""
    icon = callback.data.replace("set_income_icon_", "")
    data = await state.get_data()
    name = data.get('income_category_name')
    editing_category_id = data.get('editing_income_category_id')
    
    if not name:
        await callback.answer("❌ Ошибка: название категории не найдено", show_alert=True)
        await state.clear()
        return
    
    try:
        if editing_category_id:
            # Обновляем существующую категорию
            from bot.services.income import update_income_category
            full_name = f"{icon} {name}" if icon else name
            category = await update_income_category(callback.from_user.id, editing_category_id, new_name=full_name)
            message = "✅ Категория доходов обновлена"
        else:
            # Создаем новую категорию
            from bot.services.income import create_income_category
            category = await create_income_category(callback.from_user.id, name, icon)
            message = "✅ Категория доходов добавлена"
        
        await state.clear()
        # Не удаляем сообщение - send_message_with_cleanup отредактирует его
        await show_income_categories_menu(callback, state)
        await callback.answer(message)
    except ValueError as e:
        await callback.answer(f"❌ {str(e)}", show_alert=True)
        await state.clear()


@router.callback_query(lambda c: c.data == "no_income_icon", IncomeCategoryForm.waiting_for_icon)
async def no_income_icon(callback: types.CallbackQuery, state: FSMContext):
    """Создание категории доходов без иконки или обновление существующей"""
    data = await state.get_data()
    name = data.get('income_category_name')
    editing_category_id = data.get('editing_income_category_id')
    
    if not name:
        await callback.answer("❌ Ошибка: название категории не найдено", show_alert=True)
        await state.clear()
        return
    
    try:
        if editing_category_id:
            # Обновляем существующую категорию
            from bot.services.income import update_income_category
            category = await update_income_category(callback.from_user.id, editing_category_id, new_name=name)
            message = "✅ Категория доходов обновлена"
        else:
            # Создаем новую категорию
            from bot.services.income import create_income_category
            category = await create_income_category(callback.from_user.id, name, '')
            message = "✅ Категория доходов добавлена"
        
        await state.clear()
        # Не удаляем сообщение - send_message_with_cleanup отредактирует его
        await show_income_categories_menu(callback, state)
        await callback.answer(message)
    except ValueError as e:
        await callback.answer(f"❌ {str(e)}", show_alert=True)
        await state.clear()


@router.callback_query(lambda c: c.data == "custom_income_icon")
async def custom_income_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Запрос пользовательского эмодзи для категории доходов"""
    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        "✏️ Отправьте свой эмодзи для категории доходов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="income_categories_menu")]
        ])
    )
    await state.set_state(IncomeCategoryForm.waiting_for_custom_icon)
    await callback.answer()


@router.message(IncomeCategoryForm.waiting_for_custom_icon)
async def process_custom_income_icon(message: types.Message, state: FSMContext):
    """Обработка пользовательского эмодзи для категории доходов"""
    import re
    
    custom_icon = message.text.strip()
    
    # Проверяем, что введен один эмодзи
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+$'
    if not re.match(emoji_pattern, custom_icon) or len(custom_icon) > 2:
        await send_message_with_cleanup(message, state, "❌ Пожалуйста, отправьте только один эмодзи")
        return
    
    data = await state.get_data()
    name = data.get('income_category_name')
    
    if not name:
        await send_message_with_cleanup(message, state, "❌ Ошибка: название категории не найдено")
        await state.clear()
        return
    
    try:
        from bot.services.income import create_income_category
        category = await create_income_category(message.from_user.id, name, custom_icon)
        await state.clear()
        await show_income_categories_menu(message, state)
    except ValueError as e:
        await send_message_with_cleanup(message, state, f"❌ {str(e)}")
        await state.clear()


@router.callback_query(lambda c: c.data == "delete_income_categories")
async def delete_income_categories_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало удаления категорий доходов"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    if not await check_subscription(callback.from_user.id):
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return
    
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем категории доходов
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)
    
    if not categories:
        await callback.answer("У вас нет категорий доходов для удаления", show_alert=True)
        return
    
    # Создаем клавиатуру с категориями
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=cat.name,
                callback_data=f"del_income_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="income_categories_menu")
    ])
    
    await callback.message.edit_text(
        "🗑 Выберите категорию доходов для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await state.set_state(IncomeCategoryForm.waiting_for_delete_choice)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_income_cat_"))
async def delete_income_category(callback: types.CallbackQuery, state: FSMContext):
    """Удаление выбранной категории доходов"""
    category_id = int(callback.data.replace("del_income_cat_", ""))
    user_id = callback.from_user.id
    
    try:
        from bot.services.income import delete_income_category
        await delete_income_category(user_id, category_id)
        await state.clear()
        # Не удаляем сообщение - просто показываем обновленное меню
        # send_message_with_cleanup автоматически отредактирует текущее сообщение
        await show_income_categories_menu(callback, state)
        await callback.answer("✅ Категория доходов удалена")
    except ValueError as e:
        await callback.answer(f"❌ {str(e)}", show_alert=True)


@router.callback_query(lambda c: c.data == "edit_income_categories")
async def edit_income_categories_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования категорий доходов"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    if not await check_subscription(callback.from_user.id):
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return
    
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем категории доходов
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)
    
    if not categories:
        await callback.answer("У вас нет категорий доходов для редактирования", show_alert=True)
        return
    
    # Создаем клавиатуру с категориями
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=cat.name,
                callback_data=f"edit_income_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="income_categories_menu")
    ])
    
    await callback.message.edit_text(
        "✏️ Выберите категорию доходов для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await state.set_state(IncomeCategoryForm.waiting_for_edit_choice)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_income_cat_"))
async def edit_income_category(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование выбранной категории доходов"""
    category_id = int(callback.data.replace("edit_income_cat_", ""))
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)
    category = next((cat for cat in categories if cat.id == category_id), None)
    
    if category:
        await state.update_data(editing_income_category_id=category_id, old_income_category_name=category.name)
        
        # Показываем меню выбора что редактировать
        await callback.message.edit_text(
            f"✏️ Редактирование категории доходов «{category.name}»\n\n"
            "Что вы хотите изменить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Название", callback_data=f"edit_income_name_{category_id}")],
                [InlineKeyboardButton(text="🎨 Иконку", callback_data=f"edit_income_icon_{category_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_income_categories")]
            ])
        )
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)
    
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_income_name_"))
async def edit_income_category_name_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования названия категории доходов"""
    category_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)
    category = next((cat for cat in categories if cat.id == category_id), None)
    
    if category:
        await state.update_data(editing_income_category_id=category_id)
        await state.set_state(IncomeCategoryForm.waiting_for_new_name)
        
        await callback.message.edit_text(
            f"📝 Введите новое название для категории доходов «{category.name}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_income_cat_{category_id}")]
            ])
        )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_income_icon_"))
async def edit_income_category_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования иконки категории доходов"""
    import re
    
    category_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    # Получаем информацию о категории
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)
    category = next((cat for cat in categories if cat.id == category_id), None)
    
    if category:
        # Извлекаем чистое название без эмодзи
        emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+\s*'
        name_without_emoji = re.sub(emoji_pattern, '', category.name)
        
        await state.update_data(
            editing_income_category_id=category_id,
            income_category_name=name_without_emoji
        )
        
        # Показываем выбор иконок для доходов
        icons = [
            ['💰', '💵', '💸', '💴', '💶'],
            ['💷', '💳', '🏦', '💹', '📈'],
            ['💼', '💻', '🏢', '🏭', '👔'],
            ['🎯', '🎁', '🎉', '🏆', '💎'],
            ['🚀', '✨', '⭐', '🌟', '💫'],
            ['📱', '🎮', '🎬', '🎭', '🎨'],
            ['🏠', '🚗', '✈️', '🛍️', '🍔'],
            ['📚', '🎓', '🏥', '⚽', '🎸']
        ]
        
        keyboard_buttons = []
        for row in icons:
            buttons_row = [InlineKeyboardButton(text=icon, callback_data=f"set_income_icon_{icon}") for icon in row]
            keyboard_buttons.append(buttons_row)
        
        keyboard_buttons.append([InlineKeyboardButton(text="➡️ Без иконки", callback_data="no_income_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Ввести свой эмодзи", callback_data="custom_income_icon")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_income_cat_{category_id}")])
        
        await callback.message.edit_text(
            f"🎨 Выберите новую иконку для категории доходов «{name_without_emoji}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
        await state.set_state(IncomeCategoryForm.waiting_for_icon)
    await callback.answer()


@router.message(IncomeCategoryForm.waiting_for_new_name)
async def process_new_income_category_name(message: types.Message, state: FSMContext):
    """Обработка нового названия категории доходов"""
    new_name = message.text.strip()
    
    if len(new_name) > 50:
        await send_message_with_cleanup(message, state, "❌ Название слишком длинное. Максимум 50 символов.")
        return
    
    data = await state.get_data()
    category_id = data.get('editing_income_category_id')
    
    if not category_id:
        await send_message_with_cleanup(message, state, "❌ Ошибка: категория не найдена")
        await state.clear()
        return
    
    # Получаем текущую категорию для извлечения иконки
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(message.from_user.id)
    current_category = next((cat for cat in categories if cat.id == category_id), None)
    
    if not current_category:
        await send_message_with_cleanup(message, state, "❌ Категория не найдена")
        await state.clear()
        return
    
    # Проверяем, есть ли эмодзи в текущем названии категории
    import re
    emoji_pattern = r'^([\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+)\s*'
    current_emoji_match = re.match(emoji_pattern, current_category.name)
    current_emoji = current_emoji_match.group(1) if current_emoji_match else None
    
    # Проверяем, есть ли эмодзи в новом названии
    new_emoji_match = re.match(emoji_pattern, new_name)
    has_new_emoji = bool(new_emoji_match)
    
    if has_new_emoji:
        # Если в новом названии есть эмодзи, используем его как есть
        final_name = new_name.strip()
    elif current_emoji:
        # Если в новом названии нет эмодзи, но есть в старом - сохраняем старую иконку
        final_name = f"{current_emoji} {new_name.strip()}"
    else:
        # Если нет эмодзи ни в старом, ни в новом - оставляем без иконки
        final_name = new_name.strip()
    
    try:
        from bot.services.income import update_income_category
        # Обновляем категорию с финальным названием
        await update_income_category(message.from_user.id, category_id, final_name)
        
        await state.clear()
        await show_income_categories_menu(message, state)
    except ValueError as e:
        await send_message_with_cleanup(message, state, f"❌ {str(e)}")
        await state.clear()


@router.callback_query(lambda c: c.data == "cancel_income_category_creation", IncomeCategoryForm.waiting_for_icon)
async def cancel_income_category_creation(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания категории доходов из состояния выбора иконки"""
    await state.clear()
    # Не удаляем сообщение - send_message_with_cleanup отредактирует его
    await show_income_categories_menu(callback, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_income_category_creation", IncomeCategoryForm.waiting_for_custom_icon)
async def cancel_income_category_creation_custom(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания категории доходов из состояния ввода кастомной иконки"""
    await state.clear()
    # Не удаляем сообщение - send_message_with_cleanup отредактирует его
    await show_income_categories_menu(callback, state)
    await callback.answer()

# Fallback обработчики для случаев когда состояние уже сброшено
@router.callback_query(lambda c: c.data == "cancel_income_category_creation")
async def cancel_income_category_creation_fallback(callback: types.CallbackQuery, state: FSMContext):
    """Fallback для отмены создания категории доходов когда состояние уже сброшено"""
    # Просто отвечаем без действий, так как состояние уже сброшено
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_income_icon_"))
async def set_income_icon_fallback(callback: types.CallbackQuery, state: FSMContext):
    """Fallback для установки иконки когда состояние уже сброшено"""
    await callback.answer()

@router.callback_query(lambda c: c.data == "no_income_icon")
async def no_income_icon_fallback(callback: types.CallbackQuery, state: FSMContext):
    """Fallback для выбора без иконки когда состояние уже сброшено"""
    await callback.answer()