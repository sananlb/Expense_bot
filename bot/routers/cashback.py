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
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils import get_text

router = Router(name="cashback")


class CashbackForm(StatesGroup):
    """Состояния для добавления кешбэка"""
    waiting_for_category = State()
    waiting_for_bank = State()
    waiting_for_description = State()
    waiting_for_percent = State()
    waiting_for_limit = State()
    waiting_for_month = State()


@router.message(Command("cashback"))
async def cmd_cashback(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Команда /cashback - управление кешбэками"""
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
    
    # Получаем кешбэки пользователя
    cashbacks = await get_user_cashbacks(user_id, target_month)
    
    # Получаем язык пользователя
    if state:
        state_data = await state.get_data()
        lang = state_data.get('lang', 'ru')
    else:
        lang = 'ru'
    
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
        text = format_cashback_note(cashbacks, target_month)
    
    # Кнопки управления (без кнопки "Назад" по требованию)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add"),
            InlineKeyboardButton(text=get_text('remove_cashback', lang), callback_data="cashback_remove")
        ],
        [InlineKeyboardButton(text=get_text('remove_all_cashback', lang), callback_data="cashback_remove_all")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "cashback_menu")
async def callback_cashback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню кешбэков через callback"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
    
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.edit_text(
            subscription_required_message() + "\n\n💳 Управление кешбэками доступно только с подпиской.",
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await show_cashback_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "cashback_add")
async def add_cashback_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления кешбэка"""
    user_id = callback.from_user.id
    
    # Получаем язык из состояния
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    
    categories = await get_user_categories(user_id)
    
    if not categories:
        await callback.answer("Сначала создайте категории расходов", show_alert=True)
        return
    
    # Показываем список категорий
    keyboard_buttons = []
    
    # Добавляем опцию "Все категории"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="🌐 Все категории", 
            callback_data="cashback_cat_all"
        )
    ])
    
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.icon} {cat.name}", 
                callback_data=f"cashback_cat_{cat.id}"
            )
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
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
async def process_cashback_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора категории"""
    if callback.data == "cashback_cat_all":
        # Если выбраны все категории, сохраняем None
        await state.update_data(category_id=None)
    else:
        category_id = int(callback.data.split("_")[-1])
        await state.update_data(category_id=category_id)
    
    # Если язык английский, не показываем список банков
    if lang == 'en':
        keyboard_buttons = [[InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]]
        
        await callback.message.edit_text(
            get_text('enter_bank_name', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        # Популярные банки для русскоязычных пользователей
        banks = [
            "Т-Банк", "Альфа", "ВТБ", "Сбер", 
            "Райффайзен", "Яндекс", "Озон"
        ]
        
        keyboard_buttons = []
        for bank in banks:
            keyboard_buttons.append([
                InlineKeyboardButton(text=bank, callback_data=f"cashback_bank_{bank}")
            ])
        
        # Убрали кнопку "Назад" по требованию пользователя
        
        await callback.message.edit_text(
            get_text('choose_bank', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    # Банк можно ввести текстом, состояние уже установлено
    await state.set_state(CashbackForm.waiting_for_bank)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cashback_bank_"), CashbackForm.waiting_for_bank)
async def process_cashback_bank(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора банка"""
    bank = callback.data.replace("cashback_bank_", "")
    
    await state.update_data(bank_name=bank)
    await ask_for_description(callback.message, state)
    await state.set_state(CashbackForm.waiting_for_description)
    
    await callback.answer()


async def ask_for_description(message: types.Message, state: FSMContext):
    """Запрос описания кешбэка"""
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    text = "📝 Введите описание кешбэка\n\n"
    text += "Например: только в Пятёрочке, только онлайн, кроме алкоголя\n\n"
    text += "Или нажмите 'Пропустить' если описание не требуется"
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def ask_for_percent(message: types.Message, state: FSMContext):
    """Запрос процента кешбэка"""
    # Кнопки с популярными процентами
    keyboard_buttons = []
    percents = ["1%", "2%", "3%", "5%", "7%", "10%", "15%"]
    
    # Две кнопки в ряд
    for i in range(0, len(percents), 2):
        row = []
        for j in range(2):
            if i + j < len(percents):
                row.append(InlineKeyboardButton(
                    text=percents[i + j], 
                    callback_data=f"cashback_percent_{percents[i + j].replace('%', '')}"
                ))
        keyboard_buttons.append(row)
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await message.edit_text(
        "💰 Укажите процент кешбэка:\n\n"
        "Выберите из списка или введите свой:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


@router.callback_query(lambda c: c.data.startswith("cashback_percent_"), CashbackForm.waiting_for_percent)
async def process_cashback_percent_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора процента кнопкой и сохранение кешбэка"""
    percent = callback.data.split("_")[-1]
    await state.update_data(cashback_percent=float(percent))
    
    # Сохраняем кешбэк без лимита и месяца (по умолчанию с текущего момента)
    data = await state.get_data()
    user_id = callback.from_user.id
    current_month = date.today().month
    
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=float(percent),
            month=current_month,
            limit_amount=None,  # Без лимита
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


async def ask_for_limit(message: types.Message, state: FSMContext):
    """Запрос лимита кешбэка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без лимита", callback_data="cashback_no_limit")],
        [InlineKeyboardButton(text="1000 ₽", callback_data="cashback_limit_1000")],
        [InlineKeyboardButton(text="2000 ₽", callback_data="cashback_limit_2000")],
        [InlineKeyboardButton(text="3000 ₽", callback_data="cashback_limit_3000")],
        [InlineKeyboardButton(text="5000 ₽", callback_data="cashback_limit_5000")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    await message.edit_text(
        "💸 Есть ли лимит кешбэка в месяц?\n\n"
        "Выберите из списка или введите свою сумму:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("cashback_limit_") or c.data == "cashback_no_limit", CashbackForm.waiting_for_limit)
async def process_cashback_limit_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора лимита кнопкой"""
    if callback.data == "cashback_no_limit":
        limit = None
    else:
        limit = float(callback.data.split("_")[-1])
    
    await state.update_data(limit_amount=limit)
    
    # Спрашиваем про месяц
    await ask_for_month(callback.message, state)
    await state.set_state(CashbackForm.waiting_for_month)
    await callback.answer()


async def ask_for_month(message: types.Message, state: FSMContext):
    """Запрос месяца для кешбэка"""
    current_month = date.today().month
    
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    keyboard_buttons = []
    # Показываем текущий и следующие 3 месяца
    for i in range(4):
        month = ((current_month - 1 + i) % 12) + 1
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=month_names[month], 
                callback_data=f"cashback_month_{month}"
            )
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await message.edit_text(
        "📅 На какой месяц действует кешбэк?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


@router.callback_query(lambda c: c.data.startswith("cashback_month_"), CashbackForm.waiting_for_month)
async def process_cashback_month(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора месяца и сохранение кешбэка"""
    month = int(callback.data.split("_")[-1])
    data = await state.get_data()
    
    user_id = callback.from_user.id
    
    # Сохраняем кешбэк
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=data['cashback_percent'],
            month=month,
            limit_amount=data.get('limit_amount'),
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


@router.callback_query(lambda c: c.data == "cashback_remove")
async def remove_cashback_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список кешбэков для удаления"""
    user_id = callback.from_user.id
    current_month = date.today().month
    
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if not cashbacks:
        await callback.answer("У вас нет кешбэков для удаления", show_alert=True)
        return
    
    keyboard_buttons = []
    for cb in cashbacks:
        if cb.category:
            text = f"{cb.category.name} - {cb.bank_name} {cb.cashback_percent}%"
        else:
            text = f"🌐 Все категории - {cb.bank_name} {cb.cashback_percent}%"
        keyboard_buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"remove_cb_{cb.id}")
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "➖ Выберите кешбэк для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("remove_cb_"))
async def confirm_remove_cashback(callback: types.CallbackQuery):
    """Подтверждение удаления кешбэка"""
    cashback_id = int(callback.data.split("_")[-1])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_remove_cb_{cashback_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот кешбэк?",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("confirm_remove_cb_"))
async def remove_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление кешбэка подтверждено"""
    cashback_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    success = await delete_cashback(user_id, cashback_id)
    
    if success:
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    else:
        await callback.answer("❌ Не удалось удалить кешбэк", show_alert=True)


@router.callback_query(lambda c: c.data == "cashback_other_month")
async def select_other_month(callback: types.CallbackQuery):
    """Выбор другого месяца для просмотра кешбэков"""
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    keyboard_buttons = []
    # Показываем все 12 месяцев
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            if i + j < 12:
                month = i + j + 1
                row.append(InlineKeyboardButton(
                    text=month_names[month][:3],  # Сокращенное название
                    callback_data=f"view_cb_month_{month}"
                ))
        keyboard_buttons.append(row)
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "📅 Выберите месяц:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("view_cb_month_"))
async def view_cashback_month(callback: types.CallbackQuery):
    """Просмотр кешбэков за выбранный месяц"""
    month = int(callback.data.split("_")[-1])
    await callback.message.delete()
    await show_cashback_menu(callback.message, month)
    await callback.answer()


@router.callback_query(lambda c: c.data == "cashback_remove_all")
async def confirm_remove_all_cashback(callback: types.CallbackQuery):
    """Подтверждение удаления всех кешбэков"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu"),
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data="confirm_remove_all")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить ВСЕ кешбэки?\n\n"
        "Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "confirm_remove_all")
async def remove_all_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление всех кешбэков подтверждено"""
    user_id = callback.from_user.id
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
        
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    else:
        await callback.answer("Нет кешбэков для удаления", show_alert=True)
    
    await callback.answer()


# Обработчики ввода текста для форм
@router.message(CashbackForm.waiting_for_bank)
async def process_bank_text(message: types.Message, state: FSMContext):
    """Обработка ввода названия банка"""
    bank_name = message.text.strip()
    
    if len(bank_name) > 100:
        await send_message_with_cleanup(message, state, "❌ Название банка слишком длинное. Максимум 100 символов.")
        return
    
    await state.update_data(bank_name=bank_name)
    await ask_for_description(message, state)
    await state.set_state(CashbackForm.waiting_for_description)
    keyboard_buttons = []
    percents = ["1%", "2%", "3%", "5%", "7%", "10%", "15%"]
    
    # Две кнопки в ряд
    for i in range(0, len(percents), 2):
        row = []
        for j in range(2):
            if i + j < len(percents):
                row.append(InlineKeyboardButton(
                    text=percents[i + j], 
                    callback_data=f"cashback_percent_{percents[i + j].replace('%', '')}"
                ))
        keyboard_buttons.append(row)
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await send_message_with_cleanup(message, state,
        "💰 Укажите процент кешбэка:\n\n"
        "Выберите из списка или введите свой:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(CashbackForm.waiting_for_percent)


@router.callback_query(lambda c: c.data == "skip_description", CashbackForm.waiting_for_description)
async def skip_description(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить ввод описания"""
    await state.update_data(description='')
    await ask_for_percent(callback.message, state)
    await state.set_state(CashbackForm.waiting_for_percent)
    await callback.answer()


@router.message(CashbackForm.waiting_for_description)
async def process_description_text(message: types.Message, state: FSMContext):
    """Обработка ввода описания"""
    description = message.text.strip()
    
    if len(description) > 200:
        await send_message_with_cleanup(message, state, "❌ Описание слишком длинное. Максимум 200 символов.")
        return
    
    await state.update_data(description=description)
    await ask_for_percent(message, state)
    await state.set_state(CashbackForm.waiting_for_percent)


@router.message(CashbackForm.waiting_for_percent)
async def process_percent_text(message: types.Message, state: FSMContext):
    """Обработка ввода процента и сохранение кешбэка"""
    try:
        # Убираем символ % если есть
        percent_text = message.text.strip().replace('%', '').replace(',', '.')
        percent = float(percent_text)
        
        if percent <= 0 or percent > 100:
            await send_message_with_cleanup(message, state, "❌ Процент должен быть от 0 до 100")
            return
        
        # Сохраняем кешбэк без лимита и месяца
        data = await state.get_data()
        user_id = message.from_user.id
        current_month = date.today().month
        
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=percent,
            month=current_month,
            limit_amount=None,
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(message, state)
        
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Введите корректный процент (например: 5 или 5.5)")


@router.message(CashbackForm.waiting_for_limit)
async def process_limit_text(message: types.Message, state: FSMContext):
    """Обработка ввода лимита"""
    try:
        limit_text = message.text.strip().replace(' ', '').replace(',', '.')
        limit = float(limit_text)
        
        if limit <= 0:
            await send_message_with_cleanup(message, state, "❌ Лимит должен быть больше 0")
            return
        
        await state.update_data(limit_amount=limit)
        await ask_for_month(message, state)
        await state.set_state(CashbackForm.waiting_for_month)
        
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Введите корректную сумму (например: 1000 или 1000.50)")