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

router = Router(name="recurring")


class RecurringForm(StatesGroup):
    """Состояния для добавления регулярного платежа"""
    waiting_for_description = State()
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_day = State()


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
    
    text = "🔄 <b>Регулярные платежи</b>\n\nВаши регулярные платежи:"
    
    if payments:
        text += "\n"
        for payment in payments:
            status = "✅" if payment.is_active else "⏸"
            text += f"\n\n{status} {payment.description}\n"
            text += f"💰 {payment.amount:,.0f} ₽ - {payment.category.name}\n"
            text += f"📅 Каждое {payment.day_of_month} число месяца"
    else:
        text += "\n\nУ вас пока нет регулярных платежей."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_recurring")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_recurring")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="delete_recurring")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "recurring_menu")
async def callback_recurring_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню регулярных платежей через callback"""
    await callback.message.delete()
    await show_recurring_menu(callback.message, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "add_recurring")
async def add_recurring_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления регулярного платежа"""
    await callback.message.edit_text(
        "➕ Добавление регулярного платежа\n\n"
        "Введите описание платежа (например: Квартира, Интернет):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")]
        ])
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await state.set_state(RecurringForm.waiting_for_description)
    await callback.answer()


@router.message(RecurringForm.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания платежа"""
    description = message.text.strip()
    
    if len(description) > 200:
        await send_message_with_cleanup(message, state, "❌ Описание слишком длинное. Максимум 200 символов.")
        return
    
    await state.update_data(description=description)
    
    # Кнопки с популярными суммами
    keyboard_buttons = []
    amounts = ["1000", "2000", "5000", "10000", "20000", "50000"]
    
    # Две кнопки в ряд
    for i in range(0, len(amounts), 2):
        row = []
        for j in range(2):
            if i + j < len(amounts):
                row.append(InlineKeyboardButton(
                    text=f"{int(amounts[i + j]):,} ₽".replace(",", " "), 
                    callback_data=f"recurring_amount_{amounts[i + j]}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    await send_message_with_cleanup(message, state,
        "💰 Укажите сумму платежа:\n\n"
        "Выберите из списка или введите свою:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(RecurringForm.waiting_for_amount)


@router.callback_query(lambda c: c.data.startswith("recurring_amount_"), RecurringForm.waiting_for_amount)
async def process_amount_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора суммы кнопкой"""
    amount = float(callback.data.split("_")[-1])
    await state.update_data(amount=amount)
    
    # Показываем выбор категории
    await show_category_selection(callback.message, state)
    await callback.answer()


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
        await message.edit_text(
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
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


@router.message(RecurringForm.waiting_for_amount)
async def process_amount_text(message: types.Message, state: FSMContext):
    """Обработка ввода суммы текстом"""
    try:
        amount_text = message.text.strip().replace(' ', '').replace(',', '.')
        amount = float(amount_text)
        
        if amount <= 0:
            await send_message_with_cleanup(message, state, "❌ Сумма должна быть больше 0")
            return
        
        await state.update_data(amount=amount)
        await show_category_selection(message, state)
        
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Введите корректную сумму")


@router.message(RecurringForm.waiting_for_day)
async def process_day_text(message: types.Message, state: FSMContext):
    """Обработка ввода дня текстом"""
    try:
        day = int(message.text.strip())
        
        if day < 1 or day > 30:
            await send_message_with_cleanup(message, state, "❌ День должен быть от 1 до 30")
            return
        
        data = await state.get_data()
        user_id = message.from_user.id
        
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
    
    keyboard_buttons = []
    for payment in payments:
        status = "✅" if payment.is_active else "⏸"
        text = f"{status} {payment.description} - {payment.amount:,.0f} ₽"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=text, 
                callback_data=f"toggle_recurring_{payment.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recurring_menu")])
    
    await callback.message.edit_text(
        "✏️ Нажмите на платеж для включения/отключения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
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
        
        # Обновляем список
        await edit_recurring_list(callback, state)
    else:
        await callback.answer("Платеж не найден", show_alert=True)


@router.callback_query(lambda c: c.data == "delete_recurring")
async def delete_recurring_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список платежей для удаления"""
    user_id = callback.from_user.id
    payments = await get_user_recurring_payments(user_id)
    
    if not payments:
        await callback.answer("У вас нет регулярных платежей", show_alert=True)
        return
    
    keyboard_buttons = []
    for payment in payments:
        text = f"{payment.description} - {payment.amount:,.0f} ₽"
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