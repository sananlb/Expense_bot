"""
Обработчик регулярных операций (доходы и расходы)
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import date
from decimal import Decimal
import asyncio
import logging
from expenses.models import RecurringPayment

logger = logging.getLogger(__name__)

from ..services.recurring import (
    get_user_recurring_payments, create_recurring_payment, 
    update_recurring_payment, delete_recurring_payment, 
    get_recurring_payment_by_id
)
from ..services.category import get_user_categories
from ..services.income import get_user_income_categories
from ..utils.message_utils import send_message_with_cleanup
from ..utils import get_text
from ..utils.category_helpers import get_category_display_name
from ..utils.validators import validate_amount, parse_description_amount
from ..utils.formatters import format_currency, format_date
from ..decorators import rate_limit

router = Router(name="recurring")


class RecurringForm(StatesGroup):
    """Состояния для добавления ежемесячного платежа"""
    waiting_for_description = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_day = State()
    waiting_for_edit_data = State()  # Новое состояние для редактирования
    # Состояния для редактирования отдельных полей
    editing_amount = State()
    editing_description = State()
    editing_day = State()


@router.message(Command("recurring"))
async def cmd_recurring(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Команда /recurring - управление ежемесячными платежами"""
    await show_recurring_menu(message, state, lang)


async def show_recurring_menu(message: types.Message | types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню ежемесячных платежей"""
    # Получаем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    # Получаем регулярные платежи пользователя
    payments = await get_user_recurring_payments(user_id)
    
    text = f"<b>{get_text('recurring_payments', lang)}</b>\n\n💡 {get_text('recurring_hint', lang)}"
    
    if payments:
        # Разделяем платежи по типам
        income_payments = [p for p in payments if p.operation_type == RecurringPayment.OPERATION_TYPE_INCOME]
        expense_payments = [p for p in payments if p.operation_type == RecurringPayment.OPERATION_TYPE_EXPENSE]
        
        # Сортируем каждую группу: активные сначала, приостановленные в конце
        def sort_by_status(payments_list):
            active = [p for p in payments_list if p.is_active]
            paused = [p for p in payments_list if not p.is_active]
            return active + paused
        
        # Отображаем доходы
        if income_payments:
            text += f"\n\n{get_text('recurring_income_section', lang)}"
            sorted_income = sort_by_status(income_payments)
            
            for payment in sorted_income:
                status = "✅" if payment.is_active else "⏸"
                text += f"\n\n{status} <b>{payment.description}</b>\n"
                text += f"{get_text('recurring_amount', lang)}: <i>+{format_currency(payment.amount, payment.currency or 'RUB')}</i>\n"
                text += f"{get_text('recurring_date', lang)}: <i>{get_text('day_of_month', lang).format(day=payment.day_of_month)}</i>\n"
                if payment.category:
                    category_name = get_category_display_name(payment.category, lang)
                    text += f"{get_text('recurring_category', lang)}: <i>{category_name}</i>"
        
        # Отображаем расходы
        if expense_payments:
            text += f"\n\n{get_text('recurring_expense_section', lang)}"
            sorted_expense = sort_by_status(expense_payments)
            
            for payment in sorted_expense:
                status = "✅" if payment.is_active else "⏸"
                text += f"\n\n{status} <b>{payment.description}</b>\n"
                text += f"{get_text('recurring_amount', lang)}: <i>{format_currency(payment.amount, payment.currency or 'RUB')}</i>\n"
                text += f"{get_text('recurring_date', lang)}: <i>{get_text('day_of_month', lang).format(day=payment.day_of_month)}</i>\n"
                if payment.category:
                    category_name = get_category_display_name(payment.category, lang)
                    text += f"{get_text('recurring_category', lang)}: <i>{category_name}</i>"
    else:
        text += f"\n\n{get_text('no_recurring_payments', lang)}"
    
    # Формируем кнопки в зависимости от наличия платежей
    keyboard_buttons = [
        [InlineKeyboardButton(text=get_text('add_recurring', lang), callback_data="add_recurring")]
    ]
    
    # Показываем кнопки редактировать и удалить только если есть платежи
    if payments:
        keyboard_buttons.append(
            [InlineKeyboardButton(text=get_text('edit_recurring', lang), callback_data="edit_recurring")]
        )
        keyboard_buttons.append(
            [InlineKeyboardButton(text=get_text('delete_recurring', lang), callback_data="delete_recurring")]
        )
    
    keyboard_buttons.append(
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "recurring_menu")
async def callback_recurring_menu(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню регулярных платежей через callback"""
    await show_recurring_menu(callback, state, lang)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_recurring")
async def add_recurring_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начало добавления регулярного платежа"""
    await callback.message.edit_text(
        f"<b>{get_text('add_recurring_payment', lang)}</b>\n\n{get_text('recurring_payment_hint', lang)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back', lang), callback_data="recurring_menu")]
        ]),
        parse_mode="HTML"
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await state.set_state(RecurringForm.waiting_for_description)
    await callback.answer()


@router.message(RecurringForm.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка данных для добавления платежа"""
    text = message.text.strip()
    user_id = message.from_user.id
    
    # Используем утилиту для парсинга с разрешением ввода только суммы
    try:
        parsed = parse_description_amount(text, allow_only_amount=True)
        description = parsed['description']
        amount = parsed['amount']
        is_income = parsed.get('is_income', False)
    except ValueError as e:
        logger.warning(f"Invalid recurring payment input from user {message.from_user.id}: {e}")
        await send_message_with_cleanup(message, state, "❌ Некорректный формат ввода. Укажите описание и сумму.")
        return
    
    await state.update_data(description=description, amount=amount, is_income=is_income)
    
    # Теперь сразу показываем выбор категории
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await show_category_selection(message, state, lang)


# Удалены обработчики для суммы - теперь сумма вводится вместе с названием


async def show_category_selection(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Показать выбор категории"""
    user_id = message.chat.id if hasattr(message, 'chat') else message.from_user.id
    
    # Получаем данные из состояния чтобы понять, это доход или расход
    data = await state.get_data()
    is_income = data.get('is_income', False)
    
    if is_income:
        # Для доходов используем категории доходов
        from ..services.income import get_user_income_categories
        categories = await get_user_income_categories(user_id)
    else:
        # Для расходов используем обычные категории
        categories = await get_user_categories(user_id)
    
    if not categories:
        await send_message_with_cleanup(message, state,
            get_text('no_categories_create_first', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=get_text('to_categories', lang), callback_data="categories_menu")]
            ])
        )
        await state.clear()
        return
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(categories), 2):
        category_name_1 = get_category_display_name(categories[i], lang)
        row = [InlineKeyboardButton(
            text=f"{category_name_1}", 
            callback_data=f"recurring_cat_{categories[i].id}"
        )]
        if i + 1 < len(categories):
            category_name_2 = get_category_display_name(categories[i + 1], lang)
            row.append(InlineKeyboardButton(
                text=f"{category_name_2}", 
                callback_data=f"recurring_cat_{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back', lang), callback_data="recurring_menu")])
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(
            get_text('select_payment_category', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        await send_message_with_cleanup(message, state,
            get_text('select_payment_category', lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    await state.set_state(RecurringForm.waiting_for_category)


@router.callback_query(lambda c: c.data.startswith("recurring_cat_"), RecurringForm.waiting_for_category)
async def process_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора категории"""
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=category_id)
    
    # Показываем выбор дня месяца
    keyboard_buttons = []
    # Показываем популярные дни
    popular_days = [1, 5, 10, 15, 20, 25, 30]
    
    for i in range(0, len(popular_days), 3):
        row = []
        for j in range(3):
            if i + j < len(popular_days):
                day = popular_days[i + j]
                row.append(InlineKeyboardButton(
                    text=get_text('day_number', lang).format(day=day), 
                    callback_data=f"recurring_day_{day}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back', lang), callback_data="back_to_category_selection")])
    
    await callback.message.edit_text(
        get_text('choose_payment_day', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(RecurringForm.waiting_for_day)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("recurring_day_"), RecurringForm.waiting_for_day)
async def process_day_button(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора дня кнопкой и сохранение платежа"""
    day = int(callback.data.split("_")[-1])
    data = await state.get_data()
    
    user_id = callback.from_user.id
    
    # Создаем регулярную операцию
    try:
        is_income = data.get('is_income', False)
        description = data['description']
        
        payment = await create_recurring_payment(
            user_id=user_id,
            category_id=data['category_id'],
            amount=data['amount'],
            description=description,
            day_of_month=day,
            is_income=is_income
        )
        
        await state.clear()
        
        # Удаляем старое сообщение с выбором даты
        try:
            await callback.message.delete()
        except:
            pass
        
        # Показываем меню регулярных платежей
        await show_recurring_menu(callback, state, lang)
        await callback.answer(get_text('recurring_payment_added', lang))
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


# Удален обработчик для ввода суммы - теперь сумма вводится вместе с названием


@router.message(RecurringForm.waiting_for_day)
async def process_day_text(message: types.Message, state: FSMContext):
    """Обработка ввода дня текстом"""
    data = await state.get_data()
    user_id = message.from_user.id
    
    try:
        day = int(message.text.strip())
        
        if day < 1 or day > 30:
            data = await state.get_data()
            lang = data.get('lang', 'ru')
            await send_message_with_cleanup(message, state, get_text('day_should_be_1_30', lang))
            return
        
        # Создаем регулярный платеж
        payment = await create_recurring_payment(
            user_id=user_id,
            category_id=data['category_id'],
            amount=data['amount'],
            description=data['description'],
            day_of_month=day
        )
        
        await state.clear()
        # Показываем меню регулярных платежей
        await show_recurring_menu(message, state)
        
    except ValueError:
        data = await state.get_data()
        lang = data.get('lang', 'ru')
        await send_message_with_cleanup(message, state, get_text('enter_day_1_30', lang))


@router.callback_query(lambda c: c.data == "edit_recurring")
async def edit_recurring_list(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать список платежей для редактирования"""
    user_id = callback.from_user.id
    payments = await get_user_recurring_payments(user_id)
    
    if not payments:
        await callback.answer(get_text('no_recurring_payments', lang), show_alert=True)
        return
    
    # Сортируем платежи: активные сначала, приостановленные в конце
    active_payments = [p for p in payments if p.is_active]
    paused_payments = [p for p in payments if not p.is_active]
    sorted_payments = active_payments + paused_payments
    
    keyboard_buttons = []
    for payment in sorted_payments:
        status = "✅" if payment.is_active else "⏸"
        text = f"{status} {payment.description} - {payment.amount:.0f} ₽"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=text, 
                callback_data=f"edit_recurring_{payment.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back', lang), callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        get_text('select_payment_to_edit', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_recurring_"))
async def edit_recurring_menu(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Меню редактирования платежа"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    status_text = get_text('payment_active', lang) if payment.is_active else get_text('payment_paused', lang)
    toggle_text = get_text('pause_payment', lang) if payment.is_active else get_text('resume_payment', lang)
    
    text = get_text('edit_payment_text', lang).format(
        description=payment.description,
        amount=format_currency(payment.amount, 'RUB'),
        category=get_category_display_name(payment.category, lang) if payment.category else ('Без категории' if lang == 'ru' else 'No Category'),
        day=payment.day_of_month,
        status=status_text
    )
    
    # Сохраняем данные платежа в состояние
    await state.update_data(
        editing_payment_id=payment_id,
        old_category_id=payment.category.id,
        old_day=payment.day_of_month
    )
    await state.set_state(RecurringForm.waiting_for_edit_data)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=get_text('edit_amount', lang), callback_data=f"edit_amount_{payment_id}"),
            InlineKeyboardButton(text=get_text('edit_description', lang), callback_data=f"edit_description_{payment_id}")
        ],
        [
            InlineKeyboardButton(text=get_text('edit_category', lang), callback_data=f"edit_category_{payment_id}"),
            InlineKeyboardButton(text=get_text('edit_day', lang), callback_data=f"edit_day_{payment_id}")
        ],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_recurring_{payment_id}")],
        [InlineKeyboardButton(text=get_text('back', lang), callback_data="recurring_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "back_to_category_selection")
async def back_to_category_selection(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Назад к выбору категории при добавлении нового платежа"""
    await show_category_selection(callback, state, lang)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("toggle_recurring_"))
async def toggle_recurring(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Включить/отключить регулярный платеж"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if payment:
        # Переключаем статус
        new_status = not payment.is_active
        await update_recurring_payment(user_id, payment_id, is_active=new_status)
        
        # Сразу показываем основное меню регулярных платежей
        await callback.answer(get_text('payment_status_changed', lang))
        await show_recurring_menu(callback, state, lang)
    else:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)


# Обработчики редактирования отдельных полей
@router.callback_query(lambda c: c.data.startswith("edit_amount_"))
async def edit_amount_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать редактирование суммы"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    await state.update_data(editing_payment_id=payment_id)
    await state.set_state(RecurringForm.editing_amount)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back', lang), callback_data=f"edit_recurring_{payment_id}")]
    ])
    
    current_amount = format_currency(payment.amount, payment.currency or 'RUB')
    text = f"{get_text('enter_new_amount', lang)}\n\nТекущая сумма: <i>{current_amount}</i>"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_description_"))
async def edit_description_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать редактирование названия"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    await state.update_data(editing_payment_id=payment_id)
    await state.set_state(RecurringForm.editing_description)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back', lang), callback_data=f"edit_recurring_{payment_id}")]
    ])
    
    text = f"{get_text('enter_new_description', lang)}\n\nТекущее название: <i>{payment.description}</i>"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_day_"))
async def edit_day_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать редактирование дня месяца"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    await state.update_data(editing_payment_id=payment_id)
    await state.set_state(RecurringForm.editing_day)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back', lang), callback_data=f"edit_recurring_{payment_id}")]
    ])
    
    text = f"{get_text('enter_new_day', lang)}\n\nТекущий день: <i>{payment.day_of_month} число месяца</i>"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_category_"))
async def edit_category_start(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать редактирование категории"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    await state.update_data(editing_payment_id=payment_id, edit_field='category')
    await state.set_state(RecurringForm.waiting_for_category)
    
    # Определяем тип операции и показываем соответствующие категории
    if payment.operation_type == RecurringPayment.OPERATION_TYPE_INCOME:
        categories = await get_user_income_categories(user_id)
        cat_display = get_category_display_name(payment.category, lang) if payment.category else ('Без категории' if lang == 'ru' else 'No Category')
        text = f"{get_text('choose_new_category', lang)}\n\n💰 Доход: <i>{cat_display}</i>"
    else:
        categories = await get_user_categories(user_id)
        cat_display = get_category_display_name(payment.category, lang) if payment.category else ('Без категории' if lang == 'ru' else 'No Category')
        text = f"{get_text('choose_new_category', lang)}\n\n💸 Расход: <i>{cat_display}</i>"
    
    # Формируем клавиатуру с категориями
    keyboard_buttons = []
    for i, category in enumerate(categories):
        if i % 2 == 0:
            keyboard_buttons.append([])
        keyboard_buttons[-1].append(
            InlineKeyboardButton(
                text=get_category_display_name(category, lang),
                callback_data=f"set_category_{payment_id}_{category.id}"
            )
        )
    
    # Кнопка отмены
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text('back', lang), callback_data=f"edit_recurring_{payment_id}")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("set_category_"))
async def set_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Установить новую категорию"""
    parts = callback.data.split("_")
    payment_id = int(parts[2])
    category_id = int(parts[3])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer(get_text('payment_not_found', lang), show_alert=True)
        return
    
    # Обновляем категорию в зависимости от типа операции
    if payment.operation_type == RecurringPayment.OPERATION_TYPE_INCOME:
        await update_recurring_payment(user_id, payment_id, income_category_id=category_id)
    else:
        await update_recurring_payment(user_id, payment_id, expense_category_id=category_id)
    
    await state.clear()
    await callback.answer()
    await show_recurring_menu(callback, state, lang)


# Обработчики редактирования отдельных полей
@router.message(RecurringForm.editing_amount)
async def process_edit_amount(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка новой суммы для редактирования"""
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    payment_id = data.get('editing_payment_id')
    
    if not payment_id:
        await send_message_with_cleanup(message, state, get_text('payment_not_found', lang))
        return
    
    try:
        amount = await validate_amount(text)
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Некорректная сумма. Введите положительное число.")
        return
    
    # Обновляем сумму
    await update_recurring_payment(user_id, payment_id, amount=amount)
    await state.clear()
    
    # Возвращаемся к основному меню
    await show_recurring_menu(message, state, lang)


@router.message(RecurringForm.editing_description)
async def process_edit_description(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка нового названия для редактирования"""
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    payment_id = data.get('editing_payment_id')
    
    if not payment_id:
        await send_message_with_cleanup(message, state, get_text('payment_not_found', lang))
        return
    
    if len(text) > 200:
        await send_message_with_cleanup(message, state, "❌ Название слишком длинное (максимум 200 символов).")
        return
    
    # Капитализируем первую букву
    if text:
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    
    # Обновляем название
    await update_recurring_payment(user_id, payment_id, description=text)
    await state.clear()
    
    # Возвращаемся к основному меню
    await show_recurring_menu(message, state, lang)


@router.message(RecurringForm.editing_day)
async def process_edit_day(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка нового дня месяца для редактирования"""
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    payment_id = data.get('editing_payment_id')
    
    if not payment_id:
        await send_message_with_cleanup(message, state, get_text('payment_not_found', lang))
        return
    
    try:
        day = int(text)
        if not (1 <= day <= 30):
            raise ValueError("Day out of range")
    except ValueError:
        await send_message_with_cleanup(message, state, get_text('enter_day_1_30', lang))
        return
    
    # Обновляем день
    await update_recurring_payment(user_id, payment_id, day_of_month=day)
    await state.clear()
    
    # Возвращаемся к основному меню
    await show_recurring_menu(message, state, lang)


@router.message(RecurringForm.waiting_for_edit_data)
async def process_edit_data(message: types.Message, state: FSMContext):
    """Обработка данных для редактирования платежа"""
    text = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Используем утилиту для парсинга с разрешением ввода только суммы
    try:
        parsed = parse_description_amount(text, allow_only_amount=True)
        description = parsed['description']
        amount = parsed['amount']
    except ValueError as e:
        logger.warning(f"Invalid recurring payment input from user {message.from_user.id}: {e}")
        await send_message_with_cleanup(message, state, "❌ Некорректный формат ввода. Укажите описание и сумму.")
        return
    
    # Удаляем старый платеж
    await delete_recurring_payment(user_id, data['editing_payment_id'])
    
    # Создаем новый платеж с обновленными данными
    try:
        payment = await create_recurring_payment(
            user_id=user_id,
            category_id=data['old_category_id'],
            amount=amount,
            description=description,
            day_of_month=data['old_day']
        )
        
        await state.clear()
        
        # Сразу показываем меню без сообщения
        await show_recurring_menu(message, state)
    except Exception as e:
        logger.error(f"Error updating recurring payment for user {message.from_user.id}: {e}")
        await send_message_with_cleanup(message, state, "❌ Ошибка при обновлении. Попробуйте позже.")
        await state.clear()


@router.callback_query(lambda c: c.data == "delete_recurring")
async def delete_recurring_list(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать список платежей для удаления"""
    user_id = callback.from_user.id
    payments = await get_user_recurring_payments(user_id)
    
    if not payments:
        await callback.answer(get_text('no_recurring_payments', lang), show_alert=True)
        return
    
    # Сортируем платежи: активные сначала, приостановленные в конце
    active_payments = [p for p in payments if p.is_active]
    paused_payments = [p for p in payments if not p.is_active]
    sorted_payments = active_payments + paused_payments
    
    keyboard_buttons = []
    for payment in sorted_payments:
        status = "✅" if payment.is_active else "⏸"
        text = f"{status} {payment.description} - {payment.amount:.0f} ₽"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=text, 
                callback_data=f"del_recurring_{payment.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_arrow', lang), callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        get_text('select_payment_to_delete', lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_recurring_"))
async def delete_recurring_confirm(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Удаление регулярного платежа"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    success = await delete_recurring_payment(user_id, payment_id)
    
    if success:
        await callback.answer(get_text('payment_deleted', lang))
        # Показываем меню регулярных платежей
        await show_recurring_menu(callback, state, lang)
    else:
        await callback.answer(get_text('payment_delete_failed', lang), show_alert=True)
