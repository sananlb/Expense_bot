"""
Обработчик регулярных платежей
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import date
from decimal import Decimal
import asyncio

from ..services.recurring import (
    get_user_recurring_payments, create_recurring_payment, 
    update_recurring_payment, delete_recurring_payment, 
    get_recurring_payment_by_id
)
from ..services.category import get_user_categories
from ..utils.message_utils import send_message_with_cleanup
from ..utils import get_text
from ..utils.validators import validate_amount, parse_description_amount
from ..utils.formatters import format_currency, format_date
from ..decorators import rate_limit

router = Router(name="recurring")


class RecurringForm(StatesGroup):
    """Состояния для добавления регулярного платежа"""
    waiting_for_description = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_day = State()
    waiting_for_edit_data = State()  # Новое состояние для редактирования


@router.message(Command("recurring"))
async def cmd_recurring(message: types.Message, state: FSMContext):
    """Команда /recurring - управление регулярными платежами"""
    await show_recurring_menu(message, state)


async def show_recurring_menu(message: types.Message | types.CallbackQuery, state: FSMContext):
    """Показать меню регулярных платежей"""
    # Получаем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    
    # Получаем регулярные платежи пользователя
    payments = await get_user_recurring_payments(user_id)
    
    text = "🔄 <b>Регулярные платежи</b>"
    
    if payments:
        # Сортируем платежи: активные сначала, приостановленные в конце
        active_payments = [p for p in payments if p.is_active]
        paused_payments = [p for p in payments if not p.is_active]
        sorted_payments = active_payments + paused_payments
        
        for payment in sorted_payments:
            status = "✅" if payment.is_active else "⏸"
            text += f"\n\n{status} <b>{payment.description}</b>\n"
            text += f"Сумма: <i>{format_currency(payment.amount, 'RUB')}</i>\n"
            text += f"Дата: <i>{payment.day_of_month} число месяца</i>\n"
            text += f"Категория: <i>{payment.category.name}</i>"
    else:
        text += "\n\nУ вас пока нет регулярных платежей."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_recurring")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_recurring")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="delete_recurring")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "recurring_menu")
async def callback_recurring_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню регулярных платежей через callback"""
    await show_recurring_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_recurring")
async def add_recurring_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления регулярного платежа"""
    await callback.message.edit_text(
        "➕ <b>Добавление регулярного платежа</b>\n\n"
        "✅ Отправьте название и сумму в формате:\n"
        "<i>Название Сумма</i>\n\n"
        "Например: <i>Квартира 50000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recurring_menu")]
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
    
    # Используем утилиту для парсинга
    try:
        parsed = parse_description_amount(text)
        description = parsed['description']
        amount = parsed['amount']
    except ValueError as e:
        await send_message_with_cleanup(message, state, f"❌ {str(e)}")
        return
    
    await state.update_data(description=description, amount=amount)
    
    # Теперь сразу показываем выбор категории
    await show_category_selection(message, state)


# Удалены обработчики для суммы - теперь сумма вводится вместе с названием


async def show_category_selection(message: types.Message, state: FSMContext):
    """Показать выбор категории"""
    user_id = message.chat.id if hasattr(message, 'chat') else message.from_user.id
    categories = await get_user_categories(user_id)
    
    if not categories:
        await send_message_with_cleanup(message, state,
            "❌ У вас нет категорий. Сначала создайте категории.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📁 К категориям", callback_data="categories_menu")]
            ])
        )
        await state.clear()
        return
    
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.name}", 
                callback_data=f"recurring_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(
            "📁 Выберите категорию для платежа:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        await send_message_with_cleanup(message, state,
            "📁 Выберите категорию для платежа:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    
    await state.set_state(RecurringForm.waiting_for_category)


@router.callback_query(lambda c: c.data.startswith("recurring_cat_"), RecurringForm.waiting_for_category)
async def process_category(callback: types.CallbackQuery, state: FSMContext):
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
                    text=f"{day} число", 
                    callback_data=f"recurring_day_{day}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        "📅 В какой день месяца записывать платеж?\n\n"
        "Выберите из списка или введите число от 1 до 30:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(RecurringForm.waiting_for_day)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("recurring_day_"), RecurringForm.waiting_for_day)
async def process_day_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора дня кнопкой и сохранение платежа"""
    day = int(callback.data.split("_")[-1])
    data = await state.get_data()
    
    user_id = callback.from_user.id
    
    # Создаем регулярный платеж
    try:
        payment = await create_recurring_payment(
            user_id=user_id,
            category_id=data['category_id'],
            amount=data['amount'],
            description=data['description'],
            day_of_month=day
        )
        
        await state.clear()
        # Показываем меню регулярных платежей
        await show_recurring_menu(callback, state)
        await callback.answer()
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
            await send_message_with_cleanup(message, state, "❌ День должен быть от 1 до 30")
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
        await send_message_with_cleanup(message, state, "❌ Введите число от 1 до 30")


@router.callback_query(lambda c: c.data == "edit_recurring")
async def edit_recurring_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список платежей для редактирования"""
    user_id = callback.from_user.id
    payments = await get_user_recurring_payments(user_id)
    
    if not payments:
        await callback.answer("У вас нет регулярных платежей", show_alert=True)
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
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        "✏️ Выберите платеж для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_recurring_"))
async def edit_recurring_menu(callback: types.CallbackQuery, state: FSMContext):
    """Меню редактирования платежа"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if not payment:
        await callback.answer("Платеж не найден", show_alert=True)
        return
    
    status_text = "Активен ✅" if payment.is_active else "Приостановлен ⏸"
    toggle_text = "⏸ Приостановить" if payment.is_active else "▶️ Возобновить"
    
    text = f"""✏️ <b>Редактирование платежа</b>

Регулярный платеж: <i>{payment.description}</i>
Сумма: <i>{format_currency(payment.amount, 'RUB')}</i>
Категория: <i>{payment.category.name}</i>
Дата: <i>{payment.day_of_month} число месяца</i>
Статус: <i>{status_text}</i>

✅ Чтобы изменить название и сумму, отправьте сообщение в формате:
<i>Название Сумма</i>
Например: <i>Квартира 50000</i>"""
    
    # Сохраняем данные платежа в состояние
    await state.update_data(
        editing_payment_id=payment_id,
        old_category_id=payment.category.id,
        old_day=payment.day_of_month
    )
    await state.set_state(RecurringForm.waiting_for_edit_data)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_recurring_{payment_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="recurring_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("toggle_recurring_"))
async def toggle_recurring(callback: types.CallbackQuery, state: FSMContext):
    """Включить/отключить регулярный платеж"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    payment = await get_recurring_payment_by_id(user_id, payment_id)
    if payment:
        # Переключаем статус
        new_status = not payment.is_active
        await update_recurring_payment(user_id, payment_id, is_active=new_status)
        
        # Сразу показываем основное меню регулярных платежей
        await callback.answer("✅ Статус платежа изменен")
        await show_recurring_menu(callback, state)
    else:
        await callback.answer("Платеж не найден", show_alert=True)


@router.message(RecurringForm.waiting_for_edit_data)
async def process_edit_data(message: types.Message, state: FSMContext):
    """Обработка данных для редактирования платежа"""
    text = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Используем утилиту для парсинга
    try:
        parsed = parse_description_amount(text)
        description = parsed['description']
        amount = parsed['amount']
    except ValueError as e:
        await send_message_with_cleanup(message, state, f"❌ {str(e)}")
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
        
        await send_message_with_cleanup(message, state, "✅ Регулярный платеж успешно обновлен!")
        await state.clear()
        
        # Ждем немного и показываем меню
        await asyncio.sleep(1)
        await show_recurring_menu(message, state)
    except Exception as e:
        await send_message_with_cleanup(message, state, f"❌ Ошибка при обновлении: {str(e)}")
        await state.clear()


@router.callback_query(lambda c: c.data == "delete_recurring")
async def delete_recurring_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список платежей для удаления"""
    user_id = callback.from_user.id
    payments = await get_user_recurring_payments(user_id)
    
    if not payments:
        await callback.answer("У вас нет регулярных платежей", show_alert=True)
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
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        "🗑 Выберите платеж для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_recurring_"))
async def delete_recurring_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Удаление регулярного платежа"""
    payment_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    success = await delete_recurring_payment(user_id, payment_id)
    
    if success:
        await callback.answer("✅ Платеж удален")
        # Показываем меню регулярных платежей
        await show_recurring_menu(callback, state)
    else:
        await callback.answer("❌ Не удалось удалить платеж", show_alert=True)