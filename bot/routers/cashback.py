"""
Обработчик кешбэков
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import date, datetime
from decimal import Decimal
from typing import List
import asyncio

from ..services.cashback import (
    get_user_cashbacks, add_cashback, update_cashback, 
    delete_cashback, get_cashback_by_id, format_cashback_note
)
from ..services.category import get_user_categories
from expenses.models import Cashback
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect, safe_delete_message
from ..utils import get_text, get_user_language
from ..utils.category_helpers import get_category_display_name
from ..utils.formatters import format_currency
from ..utils.expense_parser import convert_words_to_numbers
from ..utils.logging_safe import log_safe_id
import logging

logger = logging.getLogger(__name__)
router = Router(name="cashback")




from ..services.cashback_free_text import _normalize_bank_name as _normalize_bank_alias

async def _canonicalize_bank_for_user(user_id: int, raw_name: str) -> str:
    """Приводим название банка к канону по словарю алиасов, без подмены на старые варианты."""
    return _normalize_bank_alias(raw_name or "").strip()

async def send_cashback_menu_direct(bot, chat_id: int, state: FSMContext, month: int = None):
    """Отправить меню кешбека напрямую без message объекта"""
    from datetime import date
    target_month = month or date.today().month
    current_date = date.today()
    
    # Получаем язык пользователя из базы данных
    lang = await get_user_language(chat_id)
    
    # Сохраняем информацию о том, что меню кешбека активно
    await state.update_data(
        persistent_cashback_menu=True,
        cashback_menu_month=target_month,
        cashback_menu_message_id=None  # Будет установлен после отправки
    )
    
    # Получаем кешбэки пользователя
    cashbacks = await get_user_cashbacks(chat_id, target_month)
    
    # Формируем текст
    # Названия месяцев
    month_names = {
        1: get_text('january', lang).capitalize(),
        2: get_text('february', lang).capitalize(),
        3: get_text('march', lang).capitalize(),
        4: get_text('april', lang).capitalize(),
        5: get_text('may', lang).capitalize(),
        6: get_text('june', lang).capitalize(),
        7: get_text('july', lang).capitalize(),
        8: get_text('august', lang).capitalize(),
        9: get_text('september', lang).capitalize(),
        10: get_text('october', lang).capitalize(),
        11: get_text('november', lang).capitalize(),
        12: get_text('december', lang).capitalize()
    }
    
    if not cashbacks:
        text = f"💳 {get_text('cashbacks', lang)} {month_names[target_month]}\n\n"
        text += f"{get_text('no_cashback_info', lang)}\n\n"
        text += get_text('add_cashback_hint', lang)
    else:
        # Используем format_cashback_note для форматирования
        text = format_cashback_note(cashbacks, target_month, lang)
    
    # Формируем клавиатуру
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    if not cashbacks:
        # Если кешбеков нет, показываем только кнопки добавить и закрыть
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    else:
        # Если кешбэк есть, показываем все кнопки управления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add"),
                InlineKeyboardButton(text=get_text('edit', lang), callback_data="cashback_edit")
            ],
            [
                InlineKeyboardButton(text=get_text('remove_cashback', lang), callback_data="cashback_remove"),
                InlineKeyboardButton(text=get_text('remove_all_cashback', lang), callback_data="cashback_remove_all")
            ],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    
    # Отправляем меню
    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Получаем текущие данные состояния
    data = await state.get_data()
    cashback_menu_ids = data.get('cashback_menu_ids', [])
    
    # Добавляем новый ID в список меню кешбека
    if sent_message.message_id not in cashback_menu_ids:
        cashback_menu_ids.append(sent_message.message_id)
    
    # Сохраняем обновленный список ID и флаги
    await state.update_data(
        persistent_cashback_menu=True,
        cashback_menu_month=target_month,
        cashback_menu_ids=cashback_menu_ids,
        cashback_menu_message_id=sent_message.message_id,
        last_menu_message_id=sent_message.message_id
    )


async def restore_cashback_menu_if_needed(state: FSMContext, bot, chat_id: int):
    """Восстановить меню кешбека если оно было активно"""
    data = await state.get_data()
    if data.get('persistent_cashback_menu'):
        # Получаем сохраненный месяц
        month = data.get('cashback_menu_month')
        # Вызываем функцию отправки меню напрямую с bot объектом
        await send_cashback_menu_direct(bot, chat_id, state, month=month)


class CashbackForm(StatesGroup):
    """Состояния для добавления кешбэка"""
    waiting_for_category = State()
    waiting_for_bank = State()
    waiting_for_percent = State()  # Только процент вводится текстом
    
    # Состояния для редактирования
    choosing_cashback_to_edit = State()
    editing_bank = State()
    editing_percent = State()


@router.message(Command("cashback"))
async def cmd_cashback(message: types.Message, state: FSMContext):
    """Команда /cashback - управление кешбэками"""
    lang = await get_user_language(message.from_user.id)
    await show_cashback_menu(message, state, lang)


async def show_cashback_menu(message: types.Message | types.CallbackQuery, state: FSMContext, lang: str = 'ru', month: int = None):
    """Показать меню кешбэков"""
    # Получаем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    current_date = date.today()
    target_month = month or current_date.month
    
    # Сохраняем информацию о том, что меню кешбека активно
    await state.update_data(
        persistent_cashback_menu=True,
        cashback_menu_month=target_month,
        cashback_menu_message_id=None  # Будет установлен после отправки
    )
    
    # Получаем кешбэки пользователя
    cashbacks = await get_user_cashbacks(user_id, target_month)
    
    # Получаем язык пользователя из базы данных
    if lang == 'ru':  # Если язык не передан, получаем из базы
        lang = await get_user_language(user_id)
    
    # Названия месяцев
    month_names = {
        1: get_text('january', lang).capitalize(),
        2: get_text('february', lang).capitalize(),
        3: get_text('march', lang).capitalize(),
        4: get_text('april', lang).capitalize(),
        5: get_text('may', lang).capitalize(),
        6: get_text('june', lang).capitalize(),
        7: get_text('july', lang).capitalize(),
        8: get_text('august', lang).capitalize(),
        9: get_text('september', lang).capitalize(),
        10: get_text('october', lang).capitalize(),
        11: get_text('november', lang).capitalize(),
        12: get_text('december', lang).capitalize()
    }
    
    if not cashbacks:
        text = f"💳 {get_text('cashbacks', lang)} {month_names[target_month]}\n\n"
        text += f"{get_text('no_cashback_info', lang)}\n\n"
        text += get_text('add_cashback_hint', lang)
        
        # Если кешбеков нет, показываем только кнопки добавить и закрыть
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    else:
        text = format_cashback_note(cashbacks, target_month, lang)
        
        # Если кешбэк есть, показываем все кнопки управления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add"),
                InlineKeyboardButton(text=get_text('edit', lang), callback_data="cashback_edit")
            ],
            [
                InlineKeyboardButton(text=get_text('remove_cashback', lang), callback_data="cashback_remove"),
                InlineKeyboardButton(text=get_text('remove_all_cashback', lang), callback_data="cashback_remove_all")
            ],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    
    # Отправляем меню кешбека особым способом
    if isinstance(message, (types.Message, types.CallbackQuery)):
        # Безопасно получаем bot объект
        if isinstance(message, types.Message):
            bot = message.bot if message.bot else None
            chat_id = message.chat.id if hasattr(message, 'chat') else None
        elif isinstance(message, types.CallbackQuery):
            bot = message.bot if hasattr(message, 'bot') else None
            chat_id = message.message.chat.id if hasattr(message.message, 'chat') else None
        
        if not bot or not chat_id:
            logger.error(
                "Bot or chat_id is None: bot_present=%s, chat=%s",
                bool(bot),
                log_safe_id(chat_id, "chat"),
            )
            return
        
        # НЕ удаляем старое меню кешбека - оно должно оставаться на экране
        # Пользователь может иметь несколько меню кешбека одновременно
        
        # Если это CallbackQuery, редактируем существующее сообщение
        if isinstance(message, types.CallbackQuery):
            try:
                await message.message.edit_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                sent_message = message.message
            except Exception as e:
                # Если не удалось отредактировать, отправляем новое
                logger.warning("Failed to edit cashback message: %s", e)
                sent_message = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Для обычного сообщения отправляем новое
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        # Получаем текущие данные состояния
        data = await state.get_data()
        cashback_menu_ids = data.get('cashback_menu_ids', [])
        current_last_menu = data.get('last_menu_message_id')
        
        # Добавляем новый ID в список меню кешбека
        if sent_message.message_id not in cashback_menu_ids:
            cashback_menu_ids.append(sent_message.message_id)
        
        # Сохраняем обновленный список ID и флаги
        update_data = {
            'cashback_menu_ids': cashback_menu_ids,  # Список всех ID меню кешбека
            'cashback_menu_message_id': sent_message.message_id,  # Последний ID для совместимости
            'persistent_cashback_menu': True,
            'cashback_menu_month': target_month
        }
        
        # НЕ перезаписываем last_menu_message_id если там уже есть ID другого (не кешбек) меню
        # Это позволит правильно удалять обычные меню при навигации
        if not current_last_menu or current_last_menu in cashback_menu_ids:
            update_data['last_menu_message_id'] = sent_message.message_id
            
        await state.update_data(**update_data)


@router.callback_query(lambda c: c.data == "cashback_menu")
async def callback_cashback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню кешбэков через callback"""
    from bot.utils.state_utils import clear_state_keep_cashback

    # Очищаем состояние FSM при возврате в главное меню кешбека (но сохраняем флаги)
    await clear_state_keep_cashback(state)

    # Проверяем, включен ли кешбэк
    from bot.services.profile import get_user_settings
    user_settings = await get_user_settings(callback.from_user.id)

    lang = await get_user_language(callback.from_user.id)

    if not user_settings.cashback_enabled:
        await callback.answer(get_text('cashback_disabled_message', lang), show_alert=True)
        return

    # Проверяем подписку
    from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button

    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.edit_text(
            subscription_required_message() + "\n\n" + get_text('cashback_management_subscription', lang),
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await show_cashback_menu(callback, state, lang)
    await callback.answer()


@router.callback_query(lambda c: c.data == "close_cashback_menu")
async def close_cashback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Закрыть меню кешбека"""
    from bot.utils.state_utils import clear_state_keep_cashback

    message_id = callback.message.message_id

    # Получаем список ID меню кешбека
    data = await state.get_data()
    cashback_menu_ids = data.get('cashback_menu_ids', [])

    # Удаляем текущий ID из списка
    if message_id in cashback_menu_ids:
        cashback_menu_ids.remove(message_id)

    # Удаляем само сообщение
    await safe_delete_message(message=callback.message)

    # Если это было последнее меню кешбека, очищаем все флаги И состояние FSM
    if not cashback_menu_ids:
        await state.clear()  # Полная очистка при закрытии последнего меню
    else:
        # Если остались другие меню кешбека, очищаем состояние FSM но сохраняем флаги кешбека
        await clear_state_keep_cashback(state)

    await callback.answer()


@router.callback_query(lambda c: c.data == "cashback_add")
async def add_cashback_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления кешбэка"""
    user_id = callback.from_user.id
    
    # Получаем язык из базы данных
    lang = await get_user_language(user_id)
    
    categories = await get_user_categories(user_id)
    
    if not categories:
        await callback.answer(get_text('create_categories_first', lang), show_alert=True)
        return
    
    # Показываем список категорий
    keyboard_buttons = []
    
    # Добавляем опцию "Все категории"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text=get_text('all_categories', lang), 
            callback_data="cashback_cat_all"
        )
    ])
    
    # Группируем категории по 2 в строке
    for i in range(0, len(categories), 2):
        # get_category_display_name уже возвращает строку с эмодзи, поэтому НЕ добавляем icon повторно
        category_name = get_category_display_name(categories[i], lang)
        row = [InlineKeyboardButton(
            text=category_name,
            callback_data=f"cashback_cat_{categories[i].id}"
        )]
        if i + 1 < len(categories):
            category_name_2 = get_category_display_name(categories[i + 1], lang)
            row.append(InlineKeyboardButton(
                text=category_name_2,
                callback_data=f"cashback_cat_{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_menu")])
    
    text = f"{get_text('adding_cashback', lang)}\n\n{get_text('choose_category', lang)}"
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    except Exception:
        await send_message_with_cleanup(callback, state, 
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    await state.set_state(CashbackForm.waiting_for_category)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cashback_cat_"), CashbackForm.waiting_for_category)
async def process_cashback_category(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора категории"""
    lang = await get_user_language(callback.from_user.id)
    
    if callback.data == "cashback_cat_all":
        # Если выбраны все категории, сохраняем None
        await state.update_data(category_id=None)
    else:
        category_id = int(callback.data.split("_")[-1])
        await state.update_data(category_id=category_id)
    
    # Показываем варианты выбора банка только для RU; для других языков просим ввести вручную
    if (lang or '').lower().startswith('ru'):
        banks = [
            "Т-Банк", "Альфа-Банк", "ВТБ", "Сбер",
            "Райффайзенбанк", "Яндекс", "Озон"
        ]
        keyboard_buttons = []
        for i in range(0, len(banks), 2):
            row = [InlineKeyboardButton(text=banks[i], callback_data=f"cashback_bank_{banks[i]}")]
            if i + 1 < len(banks):
                row.append(InlineKeyboardButton(text=banks[i + 1], callback_data=f"cashback_bank_{banks[i + 1]}"))
            keyboard_buttons.append(row)
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_add")])
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")])
        await callback.message.edit_text(
            get_text('choose_bank_or_enter', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        # Только кнопки Назад/Отмена, просим ввести банк текстом
        keyboard_buttons = [
            [InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_add")],
            [InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")]
        ]
        await callback.message.edit_text(
            get_text('enter_bank_name', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    await state.set_state(CashbackForm.waiting_for_bank)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cashback_bank_"), CashbackForm.waiting_for_bank)
async def process_cashback_bank(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора банка"""
    lang = await get_user_language(callback.from_user.id)
    bank = callback.data.replace("cashback_bank_", "")
    bank_canon = await _canonicalize_bank_for_user(callback.from_user.id, bank)
    await state.update_data(bank_name=bank_canon)

    # Запрашиваем процент и описание
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_add")],
        [InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")]
    ])

    await callback.message.edit_text(
        f"💳 <b>{get_text('cashback_bank', lang)}:</b> {bank}\n\n"
        f"💰 {get_text('cashback_enter_percent', lang)}:\n\n"
        f"<b>{get_text('cashback_examples', lang)}:</b>\n"
        "• 5\n"
        f"• {get_text('cashback_example_1', lang)}\n"
        f"• {get_text('cashback_example_2', lang)}\n"
        f"• {get_text('cashback_example_3', lang)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await state.set_state(CashbackForm.waiting_for_percent)
    await callback.answer()


@router.message(CashbackForm.waiting_for_bank)
async def process_bank_text(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка ввода названия банка (текст или голос)"""
    lang = await get_user_language(message.from_user.id)

    # Обработка голосовых сообщений
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.", reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        bank_name = voice_text
    elif message.text:
        bank_name = message.text.strip()
    else:
        await message.answer("❌ Пожалуйста, введите название банка текстом или голосом.")
        return

    if len(bank_name) > 100:
        await message.answer(get_text('cashback_bank_too_long', lang))
        return

    bank_name = await _canonicalize_bank_for_user(message.from_user.id, bank_name)
    await state.update_data(bank_name=bank_name)

    # Запрашиваем процент и описание
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_add")],
        [InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")]
    ])

    await message.answer(
        f"💳 <b>{get_text('cashback_bank', lang)}:</b> {bank_name}\n\n"
        f"💰 {get_text('cashback_enter_percent', lang)}:\n\n"
        f"<b>{get_text('cashback_examples', lang)}:</b>\n"
        "• 5\n"
        f"• {get_text('cashback_example_1', lang)}\n"
        f"• {get_text('cashback_example_2', lang)}\n"
        f"• {get_text('cashback_example_3', lang)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await state.set_state(CashbackForm.waiting_for_percent)


@router.message(CashbackForm.waiting_for_percent)
async def process_percent_text(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка ввода описания и процента кешбэка (текст или голос)"""
    import re

    # Получаем язык пользователя
    lang = await get_user_language(message.from_user.id)

    # Обработка голосовых сообщений
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.", reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        text = voice_text
    elif message.text:
        text = message.text.strip()
    else:
        await message.answer("❌ Пожалуйста, введите процент текстом или голосом.")
        return

    # Конвертируем слова-числа в цифры (five -> 5, два -> 2)
    text = convert_words_to_numbers(text)

    # Паттерн для извлечения процента - ищем число в любом месте строки
    # Если только число - это процент без описания
    # Если есть текст и число - текст это описание, число это процент

    # Сначала проверяем, это только число (процент)?
    only_percent_pattern = r'^(\d+(?:[.,]\d+)?)\s*%?$'
    match = re.match(only_percent_pattern, text)

    if match:
        # Только процент, без описания
        percent_str = match.group(1).replace(',', '.')
        description = ''
    else:
        # Ищем число в конце строки (описание + процент)
        percent_at_end = r'^(.*?)\s+(\d+(?:[.,]\d+)?)\s*%?$'
        match = re.match(percent_at_end, text)

        if match:
            description = match.group(1).strip()
            percent_str = match.group(2).replace(',', '.')
        else:
            await message.answer(get_text('incorrect_format_percent', lang))
            return

    try:
        percent = float(percent_str)
    except ValueError:
        await message.answer(get_text('cashback_invalid_percent', lang))
        return

    # Проверяем разумность процента (модель ограничивает <=99)
    if percent > 99:
        await message.answer(get_text('cashback_percent_too_high', lang))
        return

    if percent <= 0:
        await message.answer(get_text('cashback_percent_zero', lang))
        return

    # Получаем данные из состояния
    data = await state.get_data()
    user_id = message.from_user.id
    current_month = date.today().month
    bank_name = await _canonicalize_bank_for_user(user_id, data.get('bank_name', ''))

    # Сразу сохраняем кешбэк с описанием
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data.get('category_id'),
            bank_name=bank_name,
            cashback_percent=percent,
            month=current_month,
            limit_amount=None,  # Без лимита
            description=description  # Используем введенное описание
        )

        await state.clear()

        # Сразу показываем меню кешбэков без подтверждения
        await show_cashback_menu(message, state)

    except Exception as e:
        logger.error("Error saving cashback for %s: %s", log_safe_id(message.from_user.id, "user"), e)
        await message.answer(get_text('cashback_save_error', lang))
        await state.clear()


# Обработчики редактирования кешбека

@router.callback_query(lambda c: c.data == "cashback_edit")
async def edit_cashback_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список кешбеков для редактирования"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    current_month = date.today().month

    cashbacks = await get_user_cashbacks(user_id, current_month)

    if not cashbacks:
        await callback.answer(get_text('cashback_no_to_edit', lang), show_alert=True)
        return

    keyboard_buttons = []
    for cb in cashbacks:
        if cb.category:
            category_name = get_category_display_name(cb.category, lang)
            text = f"{category_name} - {cb.bank_name} {cb.cashback_percent}%"
        else:
            text = f"{get_text('all_categories', lang)} - {cb.bank_name} {cb.cashback_percent}%"

        # Добавляем описание, если есть
        if cb.description:
            text += f" ({cb.description})"

        keyboard_buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"edit_cb_{cb.id}")
        ])

    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_menu")])

    await callback.message.edit_text(
        get_text('cashback_choose_to_edit', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )

    await state.set_state(CashbackForm.choosing_cashback_to_edit)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cb_"), CashbackForm.choosing_cashback_to_edit)
async def edit_cashback_selected(callback: types.CallbackQuery, state: FSMContext):
    """Кешбэк выбран для редактирования - показываем выбор банка"""
    lang = await get_user_language(callback.from_user.id)
    cashback_id = int(callback.data.split("_")[-1])

    # Получаем информацию о кешбэке
    cashback = await get_cashback_by_id(callback.from_user.id, cashback_id)

    if not cashback:
        await callback.answer(get_text('cashback_not_found', lang), show_alert=True)
        return

    # Сохраняем данные кешбэка в состоянии
    await state.update_data(
        editing_cashback_id=cashback_id,
        current_bank=cashback.bank_name,
        current_percent=float(cashback.cashback_percent),  # Преобразуем Decimal в float для JSON
        current_description=cashback.description or '',
        current_category_id=cashback.category_id
    )

    # Показываем список банков с кнопкой "Пропустить"
    keyboard_buttons = []

    # Для русского языка показываем российские банки
    if lang == 'ru':
        banks = [
            "Т-Банк", "Альфа-Банк", "ВТБ", "Сбер",
            "Райффайзенбанк", "Яндекс", "Озон"
        ]

        for i in range(0, len(banks), 2):
            row = [InlineKeyboardButton(text=banks[i], callback_data=f"edit_bank_{banks[i]}")]
            if i + 1 < len(banks):
                row.append(InlineKeyboardButton(text=banks[i + 1], callback_data=f"edit_bank_{banks[i + 1]}"))
            keyboard_buttons.append(row)

    text = f"💳 <b>{get_text('cashback_edit_title', lang)}</b>\n\n"
    text += f"{get_text('cashback_current_bank', lang)}: {cashback.bank_name}\n\n"
    text += get_text('cashback_enter_new_bank', lang)

    keyboard_buttons.append([InlineKeyboardButton(text=get_text('skip', lang), callback_data="skip_edit_bank")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="cashback_edit")])
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )

    await state.set_state(CashbackForm.editing_bank)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_bank_"), CashbackForm.editing_bank)
async def process_edit_bank(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора нового банка"""
    lang = await get_user_language(callback.from_user.id)
    bank = callback.data.replace("edit_bank_", "")
    bank_canon = await _canonicalize_bank_for_user(callback.from_user.id, bank)
    await state.update_data(new_bank=bank_canon)
    await show_edit_percent_prompt(callback, state, lang)
    await callback.answer()


@router.callback_query(lambda c: c.data == "skip_edit_bank", CashbackForm.editing_bank)
async def skip_edit_bank(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить изменение банка"""
    lang = await get_user_language(callback.from_user.id)
    data = await state.get_data()
    await state.update_data(new_bank=data['current_bank'])  # Оставляем текущий банк
    await show_edit_percent_prompt(callback, state, lang)
    await callback.answer()


@router.message(CashbackForm.editing_bank)
async def process_edit_bank_text(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка ввода названия банка при редактировании (текст или голос)"""
    lang = await get_user_language(message.from_user.id)

    # Обработка голосовых сообщений
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.", reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        bank_name = voice_text
    elif message.text:
        bank_name = message.text.strip()
    else:
        await message.answer("❌ Пожалуйста, введите название банка текстом или голосом.")
        return

    if len(bank_name) > 100:
        await message.answer(get_text('cashback_bank_too_long', lang))
        return

    bank_name = await _canonicalize_bank_for_user(message.from_user.id, bank_name)
    await state.update_data(new_bank=bank_name)
    await show_edit_percent_prompt(message, state, lang)


async def show_edit_percent_prompt(message_or_callback, state: FSMContext, lang: str = 'ru'):
    """Показать запрос на ввод описания и процента при редактировании"""
    data = await state.get_data()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back_button', lang), callback_data="back_to_edit_list")],
        [InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu")]
    ])

    text = f"💳 <b>{get_text('cashback_edit_title', lang)}</b>\n\n"
    text += f"{get_text('cashback_bank', lang)}: {data.get('new_bank', data['current_bank'])}\n"
    text += f"{get_text('cashback_current_percent', lang)}: {data['current_percent']}%\n"
    if data['current_description']:
        text += f"{get_text('cashback_current_description', lang)}: {data['current_description']}\n"
    text += f"\n💰 {get_text('cashback_enter_new_percent', lang)}:\n\n"
    text += f"<b>{get_text('cashback_examples', lang)}:</b>\n"
    text += "• 5\n"
    text += f"• {get_text('cashback_example_1', lang)}\n"
    text += f"• {get_text('cashback_example_2', lang)}"

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    await state.set_state(CashbackForm.editing_percent)


@router.callback_query(lambda c: c.data == "back_to_edit_list", CashbackForm.editing_percent)
async def back_to_edit_list(callback: types.CallbackQuery, state: FSMContext):
    """Вернуться к списку кешбеков для редактирования"""
    await edit_cashback_list(callback, state)
    await callback.answer()


@router.message(CashbackForm.editing_percent)
async def process_edit_percent(message: types.Message, state: FSMContext, voice_text: str | None = None, voice_no_subscription: bool = False, voice_transcribe_failed: bool = False):
    """Обработка ввода нового описания и процента (текст или голос)"""
    import re

    lang = await get_user_language(message.from_user.id)

    # Обработка голосовых сообщений
    if message.voice:
        if voice_no_subscription:
            from bot.services.subscription import subscription_required_message, get_subscription_button
            await message.answer(subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.", reply_markup=get_subscription_button(), parse_mode="HTML")
            return
        if voice_transcribe_failed or not voice_text:
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте ещё раз или введите текстом.")
            return
        text = voice_text
    elif message.text:
        text = message.text.strip()
    else:
        await message.answer("❌ Пожалуйста, введите процент текстом или голосом.")
        return

    # Конвертируем слова-числа в цифры (five -> 5, два -> 2)
    text = convert_words_to_numbers(text)

    # Используем тот же парсинг, что и при добавлении
    only_percent_pattern = r'^(\d+(?:[.,]\d+)?)\s*%?$'
    match = re.match(only_percent_pattern, text)

    if match:
        # Только процент, без описания
        percent_str = match.group(1).replace(',', '.')
        description = ''
    else:
        # Ищем число в конце строки (описание + процент)
        percent_at_end = r'^(.*?)\s+(\d+(?:[.,]\d+)?)\s*%?$'
        match = re.match(percent_at_end, text)

        if match:
            description = match.group(1).strip()
            percent_str = match.group(2).replace(',', '.')
        else:
            await message.answer(get_text('incorrect_format_percent', lang))
            return

    try:
        percent = float(percent_str)
    except ValueError:
        await message.answer(get_text('cashback_invalid_percent', lang))
        return

    # Проверяем разумность процента (модель ограничивает <=99)
    if percent > 99:
        await message.answer(get_text('cashback_percent_too_high', lang))
        return

    if percent <= 0:
        await message.answer(get_text('cashback_percent_zero', lang))
        return

    # Получаем данные из состояния
    data = await state.get_data()
    user_id = message.from_user.id

    # Обновляем кешбэк
    try:
        # Нормализуем банк на случай изменения
        new_bank = await _canonicalize_bank_for_user(user_id, data.get('new_bank', data['current_bank']))
        cashback = await update_cashback(
            user_id=user_id,
            cashback_id=data['editing_cashback_id'],
            bank_name=new_bank,
            cashback_percent=percent,
            description=description
        )

        await state.clear()

        # Сразу показываем меню кешбэков без подтверждения
        await show_cashback_menu(message, state)

    except Exception as e:
        logger.error("Error saving cashback for %s: %s", log_safe_id(message.from_user.id, "user"), e)
        await message.answer(get_text('cashback_save_error', lang))
        await state.clear()








# Регистрация обработчиков для кнопок удаления - в самом конце файла
@router.callback_query(F.data == "cashback_remove")
async def handle_cashback_remove(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки удаления"""
    logger.info("handle_cashback_remove called for %s", log_safe_id(callback.from_user.id, "user"))
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    current_month = date.today().month

    cashbacks = await get_user_cashbacks(user_id, current_month)
    logger.info(
        "Found %s cashbacks for %s",
        len(cashbacks) if cashbacks else 0,
        log_safe_id(user_id, "user"),
    )

    if not cashbacks:
        await callback.answer(get_text('cashback_no_to_remove', lang), show_alert=True)
        return

    keyboard_buttons = []
    for cb in cashbacks:
        if cb.category:
            category_name = get_category_display_name(cb.category, lang)
            text = f"{category_name} - {cb.bank_name} {cb.cashback_percent}%"
        else:
            text = f"{get_text('all_categories', lang)} - {cb.bank_name} {cb.cashback_percent}%"
        keyboard_buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"remove_cb_{cb.id}")
        ])

    await callback.message.edit_text(
        get_text('cashback_choose_to_remove', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data == "cashback_remove_all")
async def handle_cashback_remove_all(callback: types.CallbackQuery):
    """Обработчик кнопки удаления всех"""
    logger.info("handle_cashback_remove_all called for %s", log_safe_id(callback.from_user.id, "user"))
    lang = await get_user_language(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu"),
            InlineKeyboardButton(text=get_text('yes_delete_all', lang), callback_data="confirm_remove_all")
        ]
    ])
    
    await callback.message.edit_text(
        get_text('confirm_delete_all_cashbacks', lang),
        reply_markup=keyboard
    )
    await callback.answer()

# Обработчик выбора конкретного кешбэка для удаления
@router.callback_query(lambda c: c.data.startswith("remove_cb_"))
async def handle_confirm_remove_cashback(callback: types.CallbackQuery):
    """Подтверждение удаления кешбэка"""
    lang = await get_user_language(callback.from_user.id)
    cashback_id = int(callback.data.split("_")[-1])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text('cancel', lang), callback_data="cashback_menu"),
            InlineKeyboardButton(text=get_text('yes_delete', lang), callback_data=f"confirm_remove_cb_{cashback_id}")
        ]
    ])
    
    await callback.message.edit_text(
        get_text('confirm_delete_cashback', lang),
        reply_markup=keyboard
    )
    await callback.answer()

# Обработчик подтверждения удаления конкретного кешбэка
@router.callback_query(lambda c: c.data.startswith("confirm_remove_cb_"))
async def handle_remove_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление кешбэка подтверждено"""
    cashback_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    
    success = await delete_cashback(user_id, cashback_id)
    
    if success:
        # Показываем меню кешбэков, редактируя текущее сообщение
        await show_cashback_menu(callback, state, lang)
        await callback.answer(get_text('cashback_deleted', lang) if 'cashback_deleted' in get_text.__globals__ else "✅ Кешбэк удален")
    else:
        await callback.answer(get_text('cashback_delete_failed', lang), show_alert=True)

# Обработчик подтверждения удаления всех кешбэков
@router.callback_query(lambda c: c.data == "confirm_remove_all")
async def handle_remove_all_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление всех кешбэков подтверждено"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)
    current_month = date.today().month
    
    # Получаем все кешбэки пользователя
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if cashbacks:
        # Удаляем все кешбэки
        deleted_count = 0
        for cashback in cashbacks:
            success = await delete_cashback(user_id, cashback.id)
            if success:
                deleted_count += 1
        
        # Показываем меню кешбэков, редактируя текущее сообщение
        await show_cashback_menu(callback, state, lang)
        await callback.answer(f"✅ Удалено кешбэков: {deleted_count}")
    else:
        await callback.answer(get_text('no_cashbacks_to_delete', lang), show_alert=True)
