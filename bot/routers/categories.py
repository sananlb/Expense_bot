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
from ..utils.message_utils import send_message_with_cleanup, safe_delete_message
from ..utils import get_text, get_user_language
from ..utils.category_helpers import get_category_display_name
from ..utils.category_ui import build_icon_keyboard
from ..utils.emoji_utils import EMOJI_PREFIX_RE, strip_leading_emoji
from ..utils.input_sanitizer import InputSanitizer
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


# ===== Helpers to unify create/edit flows across expense and income categories =====
def _compose_category_name(icon: str, name: str) -> str:
    base = (name or '').strip()
    if not icon:
        return base
    icon = icon.strip()
    if not base:
        return icon
    # Capitalize first letter of the textual part for consistency
    return f"{icon} {base.capitalize()}"


async def _show_expense_edit_list(message_or_cb: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = message_or_cb.from_user.id if isinstance(message_or_cb, types.CallbackQuery) else message_or_cb.from_user.id
    lang = await get_user_language(user_id)
    categories = await get_user_categories(user_id)

    # Exclude "Other expenses"
    editable = []
    for cat in categories:
        is_other = False
        if getattr(cat, 'name_ru', None) and 'прочие расходы' in cat.name_ru.lower():
            is_other = True
        if getattr(cat, 'name_en', None) and 'other expenses' in cat.name_en.lower():
            is_other = True
        if not is_other:
            editable.append(cat)

    if not editable:
        if isinstance(message_or_cb, types.CallbackQuery):
            await message_or_cb.answer(get_text('no_categories_to_edit', lang), show_alert=True)
        return

    keyboard_buttons = []
    for i in range(0, len(editable), 2):
        name1 = get_category_display_name(editable[i], lang)
        row = [InlineKeyboardButton(text=name1, callback_data=f"edit_cat_{editable[i].id}")]
        if i + 1 < len(editable):
            name2 = get_category_display_name(editable[i + 1], lang)
            row.append(InlineKeyboardButton(text=name2, callback_data=f"edit_cat_{editable[i + 1].id}"))
        keyboard_buttons.append(row)
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])

    text = get_text('choose_category_to_edit', lang)
    await send_message_with_cleanup(message_or_cb, state, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))


async def _show_income_edit_list(message_or_cb: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = message_or_cb.from_user.id if isinstance(message_or_cb, types.CallbackQuery) else message_or_cb.from_user.id
    lang = await get_user_language(user_id)
    from bot.services.income import get_user_income_categories
    categories = await get_user_income_categories(user_id)

    if not categories:
        if isinstance(message_or_cb, types.CallbackQuery):
            await message_or_cb.answer(get_text('no_income_categories_to_edit', lang), show_alert=True)
        return

    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([InlineKeyboardButton(text=get_category_display_name(cat, lang), callback_data=f"edit_income_cat_{cat.id}")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="income_categories_menu")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])

    text = get_text('choose_income_category_to_edit', lang)
    await send_message_with_cleanup(message_or_cb, state, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons))


async def _finalize_after_change(message_or_cb: types.Message | types.CallbackQuery, state: FSMContext, operation: str, cat_type: str):
    # По требованию: после любой операции (create/edit) возвращаемся
    # в исходное меню категорий соответствующего типа, а не в список редактирования
    if cat_type == 'income':
        await show_income_categories_menu(message_or_cb, state)
    else:
        await show_expense_categories_menu(message_or_cb, state)


async def _apply_icon_and_finalize(event: types.CallbackQuery | types.Message, state: FSMContext, icon: str):
    data = await state.get_data()
    operation = data.get('operation')  # 'create' | 'edit'
    cat_type = data.get('cat_type')    # 'expense' | 'income'
    name = data.get('name')
    user_id = event.from_user.id if isinstance(event, (types.Message, types.CallbackQuery)) else None

    if not cat_type:
        # Fallback to expense if not set (backward compatibility)
        cat_type = 'expense'

    # Отвечаем на callback чтобы убрать "часики" на кнопке
    if isinstance(event, types.CallbackQuery):
        try:
            await event.answer()
        except Exception:
            pass

    try:
        if cat_type == 'income':
            if operation == 'edit':
                from bot.services.income import update_income_category
                category_id = data.get('category_id') or data.get('editing_income_category_id')
                full_name = _compose_category_name(icon, name)
                await update_income_category(user_id, category_id, new_name=full_name)
            else:
                from bot.services.income import create_income_category
                await create_income_category(user_id, name.capitalize(), icon)
        else:
            if operation == 'edit':
                category_id = data.get('category_id') or data.get('editing_category_id')
                full_name = _compose_category_name(icon, name)
                from bot.services.category import update_category_name
                await update_category_name(user_id, category_id, full_name)
            else:
                await create_category(user_id, name.capitalize(), icon)
    except ValueError as e:
        # Бизнес-ошибка (дубликат, пустое название, лимит) — показываем пользователю
        # event.answer() уже вызван выше (строка 142), повторный show_alert не сработает
        await send_message_with_cleanup(event, state, f"❌ {str(e)}")
        return
    finally:
        # Показываем новое меню ПЕРЕД очисткой state, чтобы send_message_with_cleanup
        # могла удалить старое меню выбора иконок из last_menu_message_id
        await _finalize_after_change(event, state, operation or 'create', cat_type)

        # Очищаем только поля связанные с категориями, но сохраняем last_menu_message_id
        data = await state.get_data()
        await state.set_data({
            'last_menu_message_id': data.get('last_menu_message_id'),
            'cashback_menu_ids': data.get('cashback_menu_ids', [])
        })


@router.message(Command("categories"))
async def cmd_categories(message: types.Message, state: FSMContext):
    """Команда /categories - управление категориями"""
    # Сохраняем ID старого меню для удаления ПОСЛЕ показа нового
    data = await state.get_data()
    old_menu_id = data.get('last_menu_message_id')
    cashback_menu_ids = data.get('cashback_menu_ids', [])

    # По умолчанию показываем категории трат СНАЧАЛА, передаем state для сохранения ID меню
    await show_expense_categories_menu(message, state)

    # Удаляем предыдущее меню ПОСЛЕ показа нового (ТОЛЬКО если это НЕ меню кешбека)
    if old_menu_id and old_menu_id not in cashback_menu_ids:
        await safe_delete_message(
            bot=message.bot,
            chat_id=message.chat.id,
            message_id=old_menu_id
        )


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
        [InlineKeyboardButton(text=get_text('expense_categories_button', lang), callback_data="expense_categories_menu")],
        [InlineKeyboardButton(text=get_text('income_categories_button', lang), callback_data="income_categories_menu")],
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
    
    text = f"<b>{get_text('expense_categories_title', lang)}</b>\n\n"
    
    # Показываем все категории пользователя
    if categories:
        # Категории уже отсортированы в get_user_categories
        for i, cat in enumerate(categories):
            # Переводим название категории если нужно
            translated_name = get_category_display_name(cat, lang)
            text += f"{translated_name}\n"
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
            [InlineKeyboardButton(text=get_text('income_categories_button', lang), callback_data="income_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    else:
        # Без подписки можно только просматривать
        text += "\n\n" + get_text('categories_subscription_note', lang)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('get_subscription', lang), callback_data="menu_subscription")],
            [InlineKeyboardButton(text=get_text('income_categories_button', lang), callback_data="income_categories_menu")],
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
    
    text = f"<b>{get_text('income_categories_title', lang)}</b>\n\n"
    
    # Показываем все категории доходов
    if income_categories:
        for i, cat in enumerate(income_categories):
            translated_name = get_category_display_name(cat, lang)
            text += f"{translated_name}\n"
            # Добавляем отступ между категориями
            if i < len(income_categories) - 1:
                text += "\n"
    else:
        text += get_text('no_income_categories_yet', lang)
    
    # Формируем клавиатуру в зависимости от подписки
    if has_subscription:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_button', lang), callback_data="add_income_category")],
            [InlineKeyboardButton(text=get_text('edit_button', lang), callback_data="edit_income_categories")],
            [InlineKeyboardButton(text=get_text('delete_button', lang), callback_data="delete_income_categories")],
            [InlineKeyboardButton(text=get_text('expense_categories_button', lang), callback_data="expense_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    else:
        # Без подписки можно только просматривать
        text += "\n\n" + get_text('income_categories_subscription_note', lang)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('get_subscription', lang), callback_data="menu_subscription")],
            [InlineKeyboardButton(text=get_text('expense_categories_button', lang), callback_data="expense_categories_menu")],
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
    
    await safe_delete_message(message=callback.message)
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
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    if not await check_subscription(callback.from_user.id):
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return
    
    lang = await get_user_language(callback.from_user.id)
    # Сбрасываем предыдущее состояние, чтобы не потянуть старые editing_* значения
    await state.clear()
    await callback.message.edit_text(
        get_text('adding_category', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    )
    # Обновляем контекст состояния (единый контракт)
    await state.update_data(
        last_menu_message_id=callback.message.message_id,
        operation='create',
        cat_type='expense'
    )
    await state.set_state(CategoryForm.waiting_for_name)
    await callback.answer()


@router.message(CategoryForm.waiting_for_name)
async def process_category_name(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка названия категории (текст или голос)"""
    # Обработка голосовых сообщений
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.", reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        name = voice_text
    elif message.text:
        # Игнорируем команды - они обработаются в middleware
        if message.text.startswith('/'):
            return
        name = message.text.strip()
    else:
        await message.answer("❌ Пожалуйста, введите название категории текстом или голосом.")
        return

    # Дополнительная проверка что мы все еще в правильном состоянии
    current_state = await state.get_state()
    if current_state != CategoryForm.waiting_for_name.state:
        return

    # Получаем язык пользователя
    lang = await get_user_language(message.from_user.id)
    
    raw_name = name.strip()
    if len(raw_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        await send_message_with_cleanup(
            message,
            state,
            f"❌ Название слишком длинное. Максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов."
        )
        return

    name = InputSanitizer.sanitize_category_name(raw_name).strip()
    if not name:
        await send_message_with_cleanup(message, state, "❌ Название категории не может быть пустым.")
        return
    
    # Проверяем, есть ли уже эмодзи в начале названия (включая композитные с ZWJ)
    has_emoji = bool(EMOJI_PREFIX_RE.match(name))
    
    # Удаляем сообщение пользователя
    await safe_delete_message(message=message)

    if has_emoji:
        # Если эмодзи уже есть, сразу создаем категорию
        user_id = message.from_user.id
        try:
            # Капитализируем первую букву после эмодзи
            parts = name.split(maxsplit=1)
            if len(parts) == 2:
                name = parts[0] + ' ' + parts[1].capitalize()
            await state.update_data(name=name, operation='create', cat_type='expense')
            await _apply_icon_and_finalize(message, state, '')
        except ValueError as e:
            await send_message_with_cleanup(message, state, f"❌ {str(e)}")
            await state.clear()
    else:
        # Если эмодзи нет, сразу показываем выбор иконок
        name = name.capitalize()
        await state.update_data(name=name, operation='create', cat_type='expense')
        kb = build_icon_keyboard(back_callback="cancel_category_creation", lang=lang)
        await send_message_with_cleanup(
            message, state,
            get_text('choose_icon_for_category', lang).format(name=name),
            reply_markup=kb
        )
        await state.set_state(CategoryForm.waiting_for_icon)




@router.callback_query(lambda c: c.data == "custom_icon")
async def custom_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Запрос пользовательского эмодзи"""
    data = await state.get_data()
    operation = data.get('operation') or 'create'
    cat_type = data.get('cat_type', 'expense')
    category_id = data.get('category_id') or data.get('editing_category_id')

    # Определяем корректную кнопку "Назад"
    if operation == 'edit':
        back_cb = f"edit_income_cat_{category_id}" if cat_type == 'income' else f"edit_cat_{category_id}"
    else:
        back_cb = "income_categories_menu" if cat_type == 'income' else "expense_categories_menu"

    lang = await get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        "✏️ Отправьте свой эмодзи для категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data=back_cb)],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    )
    await state.set_state(CategoryForm.waiting_for_custom_icon)
    await callback.answer()


@router.message(CategoryForm.waiting_for_custom_icon)
async def process_custom_icon(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка пользовательского эмодзи (текст или голос)"""
    # Обработка голосовых - для эмодзи голос не подходит
    if message.voice:
        await message.answer("❌ Для иконки нужно отправить эмодзи текстом, голос не подходит.")
        return

    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте эмодзи.")
        return

    # Игнорируем команды - они обработаются в middleware
    if message.text.startswith('/'):
        return

    # Дополнительная проверка что мы все еще в правильном состоянии
    current_state = await state.get_state()
    if current_state != CategoryForm.waiting_for_custom_icon.state:
        return

    custom_icon = message.text.strip()

    # Проверяем что введены ТОЛЬКО эмодзи (используем централизованный паттерн с ZWJ/VS-16)
    match = EMOJI_PREFIX_RE.match(custom_icon)
    # Должен быть match И он должен покрывать всю строку (нет текста после эмодзи)
    if not match or match.group().strip() != custom_icon or len(custom_icon) > 24:
        await send_message_with_cleanup(message, state, "❌ Пожалуйста, отправьте один или несколько эмодзи без текста.")
        return

    # Удаляем сообщение пользователя
    await safe_delete_message(message=message)

    # Применяем иконку через общий обработчик
    await _apply_icon_and_finalize(message, state, custom_icon)


@router.callback_query(lambda c: c.data == "no_icon")
async def no_icon_selected(callback: types.CallbackQuery, state: FSMContext):
    """Создать категорию без иконки"""
    await _apply_icon_and_finalize(callback, state, '')




@router.callback_query(lambda c: c.data.startswith("set_icon_"))
async def set_category_icon(callback: types.CallbackQuery, state: FSMContext):
    """Установить выбранную иконку"""
    icon = callback.data.replace("set_icon_", "")
    await _apply_icon_and_finalize(callback, state, icon)


@router.callback_query(lambda c: c.data == "edit_categories")
async def edit_categories_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список категорий для редактирования"""
    # Очищаем состояние при возврате к списку категорий для редактирования
    await state.clear()
    
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    editable_categories = []
    for cat in categories:
        # Проверяем оба языковых поля
        is_other = False
        if cat.name_ru and 'прочие расходы' in cat.name_ru.lower():
            is_other = True
        if cat.name_en and 'other expenses' in cat.name_en.lower():
            is_other = True
        if not is_other:
            editable_categories.append(cat)
    
    if not editable_categories:
        await callback.answer(get_text('no_categories_to_edit', lang), show_alert=True)
        return

    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(editable_categories), 2):
        # Переводим название категории
        translated_name = get_category_display_name(editable_categories[i], lang)
        row = [InlineKeyboardButton(
            text=translated_name,
            callback_data=f"edit_cat_{editable_categories[i].id}"
        )]
        if i + 1 < len(editable_categories):
            translated_name_2 = get_category_display_name(editable_categories[i + 1], lang)
            row.append(InlineKeyboardButton(
                text=translated_name_2,
                callback_data=f"edit_cat_{editable_categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])

    await callback.message.edit_text(
        get_text('choose_category_to_edit', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data == "delete_categories")
async def delete_categories_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список категорий для удаления"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription
    if not await check_subscription(callback.from_user.id):
        lang = await get_user_language(callback.from_user.id)
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return
    
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    categories = await get_user_categories(user_id)
    
    # Фильтруем категории - исключаем "Прочие расходы"
    deletable_categories = []
    for cat in categories:
        # Проверяем оба языковых поля
        is_other = False
        if cat.name_ru and 'прочие расходы' in cat.name_ru.lower():
            is_other = True
        if cat.name_en and 'other expenses' in cat.name_en.lower():
            is_other = True
        if not is_other:
            deletable_categories.append(cat)
    
    if not deletable_categories:
        await callback.answer(get_text('no_categories_to_delete', lang), show_alert=True)
        return
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(deletable_categories), 2):
        # Переводим название категории
        translated_name = get_category_display_name(deletable_categories[i].name, lang)
        row = [InlineKeyboardButton(
            text=translated_name, 
            callback_data=f"del_cat_{deletable_categories[i].id}"
        )]
        if i + 1 < len(deletable_categories):
            translated_name_2 = get_category_display_name(deletable_categories[i + 1], lang)
            row.append(InlineKeyboardButton(
                text=translated_name_2,
                callback_data=f"del_cat_{deletable_categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])

    await callback.message.edit_text(
        get_text('choose_category_to_delete', lang),
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


@router.callback_query(lambda c: c.data.startswith("edit_cat_") and not c.data.startswith("edit_cat_name_") and not c.data.startswith("edit_cat_icon_"))
async def edit_category(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование категории"""
    import logging
    from aiogram.exceptions import TelegramBadRequest
    logger = logging.getLogger(__name__)
    logger.info(f"edit_category called with data: {callback.data}")

    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)

    if category:
        # Сохраняем ID категории в состоянии для последующего редактирования
        lang = await get_user_language(callback.from_user.id)
        category_display = get_category_display_name(category, lang)
        await state.update_data(editing_category_id=cat_id, old_category_name=category_display, operation='edit', cat_type='expense', category_id=cat_id)

        # Показываем меню выбора что редактировать
        try:
            await callback.message.edit_text(
                get_text('editing_category_header', lang).format(name=category_display),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_text('edit_name_button', lang), callback_data=f"edit_cat_name_{cat_id}")],
                    [InlineKeyboardButton(text=get_text('edit_icon_button', lang), callback_data=f"edit_cat_icon_{cat_id}")],
                    [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="edit_categories")],
                    [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
                ]),
                parse_mode='HTML'
            )
        except TelegramBadRequest:
            # Если сообщение уже такое же, просто подтверждаем callback
            pass
    else:
        await callback.answer("❌ Категория не найдена", show_alert=True)

    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cat_name_"))
async def edit_category_name_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования названия категории"""
    from aiogram.exceptions import TelegramBadRequest

    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)

    if category:
        await state.update_data(editing_category_id=cat_id)
        await state.set_state(CategoryStates.editing_name)

        try:
            await callback.message.edit_text(
                get_text('enter_new_category_name', lang).format(name=category.name),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data=f"edit_cat_{cat_id}")],
                    [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
                ])
            )
        except TelegramBadRequest:
            # Если сообщение уже такое же, просто подтверждаем callback
            pass
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cat_icon_"))
async def edit_category_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало редактирования иконки категории"""
    import re
    from aiogram.exceptions import TelegramBadRequest

    cat_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Получаем информацию о категории
    category = await get_category_by_id(user_id, cat_id)

    if category:
        # Извлекаем чистое название без эмодзи (включая композитные с ZWJ)
        name_without_emoji = strip_leading_emoji(category.name)

        await state.update_data(
            editing_category_id=cat_id,
            category_id=cat_id,
            name=name_without_emoji,
            operation='edit',
            cat_type='expense'
        )

        # Показываем выбор иконок (единый набор)
        kb = build_icon_keyboard(back_callback=f"edit_cat_{cat_id}", lang=lang)
        try:
            await callback.message.edit_text(
                get_text('choose_icon_for_category', lang).format(name=name_without_emoji),
                reply_markup=kb
            )
        except TelegramBadRequest:
            # Если сообщение уже такое же, просто подтверждаем callback
            pass
        await state.set_state(CategoryForm.waiting_for_icon)
    await callback.answer()


@router.message(CategoryStates.editing_name)
async def process_edit_category_name(
    message: types.Message,
    state: FSMContext,
    voice_text: str | None = None,
    voice_no_subscription: bool = False,
    voice_transcribe_failed: bool = False
):
    """Обработка нового названия категории (текст или голос)"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"process_edit_category_name called for user {message.from_user.id}")

    lang = await get_user_language(message.from_user.id)

    # Обработка голосового ввода
    if message.voice:
        if voice_no_subscription:
            await message.answer(get_text('voice_premium_only', lang))
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer(get_text('voice_recognition_failed', lang))
            return
        new_name = voice_text.strip()
    elif message.text:
        # Игнорируем команды - они обработаются в middleware
        if message.text.startswith('/'):
            return
        new_name = message.text.strip()
    else:
        # Неподдерживаемый тип сообщения
        return
    raw_new_name = new_name.strip()
    if len(raw_new_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        await message.answer(
            f"❌ Название слишком длинное. Максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов."
        )
        return

    new_name = InputSanitizer.sanitize_category_name(raw_new_name).strip()
    if not new_name:
        await message.answer("❌ Название категории не может быть пустым.")
        return

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
    
    # Проверяем, есть ли эмодзи в текущем названии категории (включая композитные с ZWJ)
    current_emoji_match = EMOJI_PREFIX_RE.match(current_category.name)
    current_emoji = current_emoji_match.group(0).strip() if current_emoji_match else None

    # Проверяем, есть ли эмодзи в новом названии
    new_emoji_match = EMOJI_PREFIX_RE.match(new_name)
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
    # Используем сервис, который корректно обновляет иконку и мультиязычные поля
    from bot.services.category import update_category_name as _update_category_name
    try:
        await _update_category_name(user_id, cat_id, final_name)
        logger.info(f"Category {cat_id} updated successfully with name: {final_name}")

        # Удаляем сообщение пользователя
        await safe_delete_message(message=message)

        # Очищаем состояние
        await state.clear()

        # Показываем меню категорий трат (не общее меню)
        await show_expense_categories_menu(message, state)
    except ValueError as e:
        lang = await get_user_language(message.from_user.id)
        await message.answer(
            f"❌ {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="expense_categories_menu")],
                [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
            ])
        )
        await state.clear()


@router.callback_query(lambda c: c.data == "cancel_category")
async def cancel_category(callback: types.CallbackQuery, state: FSMContext):
    """Отмена операции с категорией"""
    await callback.answer()
    await safe_delete_message(message=callback.message)
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
    # Сбрасываем предыдущее состояние, чтобы не потянуть старые editing_* значения
    await state.clear()
    await callback.message.edit_text(
        get_text('adding_income_category', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="income_categories_menu")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
    )
    await state.update_data(last_menu_message_id=callback.message.message_id, operation='create', cat_type='income')
    await state.set_state(IncomeCategoryForm.waiting_for_name)
    await callback.answer()


@router.message(IncomeCategoryForm.waiting_for_name)
async def process_income_category_name(
    message: types.Message,
    state: FSMContext,
    voice_text: str | None = None,
    voice_no_subscription: bool = False,
    voice_transcribe_failed: bool = False
):
    """Обработка названия категории доходов (текст или голос)"""
    lang = await get_user_language(message.from_user.id)

    # Обработка голосового ввода
    if message.voice:
        if voice_no_subscription:
            await message.answer(get_text('voice_premium_only', lang))
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer(get_text('voice_recognition_failed', lang))
            return
        name = voice_text.strip()
    elif message.text:
        # Игнорируем команды - они обработаются в middleware
        if message.text.startswith('/'):
            return
        name = message.text.strip()
    else:
        # Неподдерживаемый тип сообщения
        return

    # Дополнительная проверка что мы все еще в правильном состоянии
    current_state = await state.get_state()
    if current_state != IncomeCategoryForm.waiting_for_name.state:
        return
    
    raw_name = name.strip()
    if len(raw_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        await send_message_with_cleanup(
            message,
            state,
            f"❌ Название слишком длинное. Максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов."
        )
        return

    name = InputSanitizer.sanitize_category_name(raw_name).strip()
    if not name:
        await send_message_with_cleanup(message, state, "❌ Название категории не может быть пустым.")
        return
    
    # Проверяем, есть ли уже эмодзи в начале названия (включая композитные с ZWJ)
    has_emoji = bool(EMOJI_PREFIX_RE.match(name))

    # Удаляем сообщение пользователя
    await safe_delete_message(message=message)

    if has_emoji:
        # Если эмодзи уже есть, сразу создаем категорию
        user_id = message.from_user.id
        try:
            # Капитализируем первую букву после эмодзи
            parts = name.split(maxsplit=1)
            if len(parts) == 2:
                name = parts[0] + ' ' + parts[1].capitalize()
            # Сохраняем единый контекст и показываем выбор иконок не требуется (эмодзи уже есть)
            await state.update_data(name=name, operation='create', cat_type='income')
            await _apply_icon_and_finalize(message, state, '')
        except ValueError as e:
            await send_message_with_cleanup(message, state, f"❌ {str(e)}")
            await state.clear()
    else:
        # Если эмодзи нет, показываем выбор иконок
        # Капитализируем название
        name = name.capitalize()
        await state.update_data(name=name, operation='create', cat_type='income')

        lang = await get_user_language(message.from_user.id)
        kb = build_icon_keyboard(back_callback="cancel_income_category_creation", lang=lang)
        await send_message_with_cleanup(
            message, state,
            get_text('choose_icon_for_income_category', lang).format(name=name),
            reply_markup=kb
        )
        await state.set_state(IncomeCategoryForm.waiting_for_icon)


@router.callback_query(lambda c: c.data.startswith("set_income_icon_"), IncomeCategoryForm.waiting_for_icon)
async def set_income_category_icon(callback: types.CallbackQuery, state: FSMContext):
    """Redirect legacy income icon callback to unified handler"""
    icon = callback.data.replace("set_income_icon_", "")
    data = await state.get_data()
    await state.update_data(
        name=data.get('name'),
        operation=data.get('operation') or ('edit' if (data.get('category_id') or data.get('editing_income_category_id')) else 'create'),
        cat_type='income',
        category_id=data.get('category_id') or data.get('editing_income_category_id')
    )
    await _apply_icon_and_finalize(callback, state, icon)


@router.callback_query(lambda c: c.data == "no_income_icon", IncomeCategoryForm.waiting_for_icon)
async def no_income_icon(callback: types.CallbackQuery, state: FSMContext):
    """Redirect legacy income no-icon callback to unified handler"""
    data = await state.get_data()
    await state.update_data(
        name=data.get('name'),
        operation=data.get('operation') or ('edit' if (data.get('category_id') or data.get('editing_income_category_id')) else 'create'),
        cat_type='income',
        category_id=data.get('category_id') or data.get('editing_income_category_id')
    )
    await _apply_icon_and_finalize(callback, state, '')


@router.callback_query(lambda c: c.data == "custom_income_icon")
async def custom_income_icon_start(callback: types.CallbackQuery, state: FSMContext):
    """Redirect legacy income custom icon to unified one"""
    data = await state.get_data()
    await state.update_data(
        name=data.get('name'),
        operation=data.get('operation') or ('edit' if (data.get('category_id') or data.get('editing_income_category_id')) else 'create'),
        cat_type='income',
        category_id=data.get('category_id') or data.get('editing_income_category_id')
    )
    return await custom_icon_start(callback, state)


@router.message(IncomeCategoryForm.waiting_for_custom_icon)
async def process_custom_income_icon(message: types.Message, state: FSMContext):
    """Обработка пользовательского эмодзи для категории доходов (только текст)"""
    # Голосовой ввод не подходит для эмодзи - игнорируем голосовые сообщения
    if message.voice:
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text('send_emoji_not_voice', lang, default="❌ Пожалуйста, отправьте эмодзи текстом, не голосом"))
        return

    # Проверяем что есть текст
    if not message.text:
        return

    # Игнорируем команды - они обработаются в middleware
    if message.text.startswith('/'):
        return

    # Дополнительная проверка что мы все еще в правильном состоянии
    current_state = await state.get_state()
    if current_state != IncomeCategoryForm.waiting_for_custom_icon.state:
        return

    custom_icon = message.text.strip()

    # Проверяем что введены ТОЛЬКО эмодзи (используем централизованный паттерн с ZWJ/VS-16)
    match = EMOJI_PREFIX_RE.match(custom_icon)
    # Должен быть match И он должен покрывать всю строку (нет текста после эмодзи)
    if not match or match.group().strip() != custom_icon or len(custom_icon) > 24:
        await send_message_with_cleanup(message, state, "❌ Пожалуйста, отправьте один или несколько эмодзи без текста")
        return
    
    data = await state.get_data()
    name = data.get('name')

    if not name:
        await send_message_with_cleanup(message, state, "❌ Ошибка: название категории не найдено")
        await state.clear()
        return

    # Удаляем сообщение пользователя
    await safe_delete_message(message=message)

    await state.update_data(name=name, operation='create', cat_type='income')
    await _apply_icon_and_finalize(message, state, custom_icon)


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
        await callback.answer(get_text('no_income_categories_to_delete', lang), show_alert=True)
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
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('close', lang), callback_data="close")
    ])

    await callback.message.edit_text(
        get_text('choose_income_category_to_delete', lang),
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
        await callback.answer(get_text('no_income_categories_to_edit', lang), show_alert=True)
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
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('close', lang), callback_data="close")
    ])

    await callback.message.edit_text(
        get_text('choose_income_category_to_edit', lang),
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
        lang = await get_user_language(user_id)
        category_display_name = get_category_display_name(category, lang)
        await state.update_data(editing_income_category_id=category_id, category_id=category_id, old_income_category_name=category_display_name)
        
        # Показываем меню выбора что редактировать
        await callback.message.edit_text(
            get_text('editing_income_category_header', lang).format(name=category_display_name),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text('edit_name_button', lang), callback_data=f"edit_income_name_{category_id}")],
                [InlineKeyboardButton(text=get_text('edit_icon_button', lang), callback_data=f"edit_income_icon_{category_id}")],
                [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="edit_income_categories")],
                [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
            ]),
            parse_mode='HTML'
        )
    else:
        await callback.answer(get_text('error_category_not_found', lang), show_alert=True)
    
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
        await state.update_data(editing_income_category_id=category_id, category_id=category_id)
        await state.set_state(IncomeCategoryForm.waiting_for_new_name)

        await callback.message.edit_text(
            get_text('enter_new_income_category_name', lang).format(name=category.name),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data=f"edit_income_cat_{category_id}")],
                [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
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
        # Извлекаем чистое название без эмодзи (включая композитные с ZWJ)
        name_without_emoji = strip_leading_emoji(category.name)
        
        await state.update_data(
            editing_income_category_id=category_id,
            category_id=category_id,
            income_category_name=name_without_emoji,
            name=name_without_emoji,
            operation='edit',
            cat_type='income'
        )
        
        # Показываем выбор иконок (единый набор)
        kb = build_icon_keyboard(back_callback=f"edit_income_cat_{category_id}", lang=lang)
        await callback.message.edit_text(
            get_text('choose_icon_for_income_category', lang).format(name=name_without_emoji),
            reply_markup=kb
        )
        await state.set_state(IncomeCategoryForm.waiting_for_icon)
    await callback.answer()


@router.message(IncomeCategoryForm.waiting_for_new_name)
async def process_new_income_category_name(
    message: types.Message,
    state: FSMContext,
    voice_text: str | None = None,
    voice_no_subscription: bool = False,
    voice_transcribe_failed: bool = False
):
    """Обработка нового названия категории доходов (текст или голос)"""
    lang = await get_user_language(message.from_user.id)

    # Обработка голосового ввода
    if message.voice:
        if voice_no_subscription:
            await message.answer(get_text('voice_premium_only', lang))
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer(get_text('voice_recognition_failed', lang))
            return
        new_name = voice_text.strip()
    elif message.text:
        # Игнорируем команды
        if message.text.startswith('/'):
            return
        new_name = message.text.strip()
    else:
        # Неподдерживаемый тип сообщения
        return

    raw_new_name = new_name.strip()
    if len(raw_new_name) > InputSanitizer.MAX_CATEGORY_LENGTH:
        await send_message_with_cleanup(
            message,
            state,
            f"❌ Название слишком длинное. Максимум {InputSanitizer.MAX_CATEGORY_LENGTH} символов."
        )
        return

    new_name = InputSanitizer.sanitize_category_name(raw_new_name).strip()
    if not new_name:
        await send_message_with_cleanup(message, state, "❌ Название категории не может быть пустым.")
        return
    
    data = await state.get_data()
    category_id = data.get('category_id') or data.get('editing_income_category_id')
    
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
    
    # Проверяем, есть ли эмодзи в текущем названии категории (включая композитные с ZWJ)
    current_emoji_match = EMOJI_PREFIX_RE.match(current_category.name)
    current_emoji = current_emoji_match.group(0).strip() if current_emoji_match else None

    # Проверяем, есть ли эмодзи в новом названии
    new_emoji_match = EMOJI_PREFIX_RE.match(new_name)
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

    # Удаляем сообщение пользователя
    await safe_delete_message(message=message)

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
