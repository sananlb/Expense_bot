"""
Router for budget management
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from decimal import Decimal, InvalidOperation
import logging

from bot.keyboards import back_close_keyboard, yes_no_keyboard
from bot.utils import get_text, format_amount
from bot.services.budget import create_budget, get_user_budgets, check_budget_status, delete_budget, check_all_budgets
from bot.services.category import get_user_categories
from bot.utils.message_utils import send_message_with_cleanup
from bot.utils.category_helpers import get_category_display_name

logger = logging.getLogger(__name__)

router = Router(name="budget")


class BudgetStates(StatesGroup):
    select_category = State()
    enter_amount = State()
    confirm_delete = State()


@router.message(Command("budget"))
async def cmd_budget(message: Message, state: FSMContext, lang: str = 'ru'):
    """Показать меню бюджета"""
    await state.clear()
    
    try:
        # Получаем статус всех бюджетов
        budgets = await check_all_budgets(message.from_user.id)
        
        if not budgets:
            text = f"{get_text('budget', lang)}\n\n{get_text('no_budgets', lang)}"
        else:
            text = f"{get_text('budget', lang)}\n\n"
            
            for budget in budgets:
                if budget['has_budget']:
                    icon = budget['category_icon']
                    name = budget['category_name']
                    amount = format_amount(budget['budget_amount'], lang=lang)
                    spent = format_amount(budget['spent'], lang=lang)
                    percentage = budget['percentage']
                    
                    status = "✅" if not budget['exceeded'] else "❌"
                    
                    text += f"{icon} {name}: {spent} / {amount} ({percentage:.0f}%) {status}\n"
        
        # Клавиатура
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text=get_text('add_budget', lang), callback_data="add_budget")
        keyboard.button(text=get_text('delete_budget', lang), callback_data="delete_budget")
        keyboard.button(text=get_text('close', lang), callback_data="close")
        keyboard.adjust(2, 1)
        
        await send_message_with_cleanup(message, state, text, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Error showing budget: {e}")
        await send_message_with_cleanup(message, state, get_text('error_occurred', lang))


@router.callback_query(F.data == "add_budget")
async def add_budget_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать добавление бюджета"""
    await state.set_state(BudgetStates.select_category)
    
    # Получаем категории пользователя
    categories = await get_user_categories(callback.from_user.id)
    
    if not categories:
        await callback.answer(get_text('no_categories', lang), show_alert=True)
        return
        
    # Формируем клавиатуру с категориями
    keyboard = InlineKeyboardBuilder()
    
    for category in categories:
        # Используем язык пользователя для отображения категории
        display_name = get_category_display_name(category, lang)
        keyboard.button(
            text=display_name,
            callback_data=f"budget_cat_{category.id}"
        )
    
    keyboard.button(text=get_text('back', lang), callback_data="budget_menu")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    
    # Настраиваем расположение кнопок
    buttons_count = len(categories)
    if buttons_count <= 6:
        keyboard.adjust(2, 2, 2, 2)
    else:
        keyboard.adjust(3, 3, 3, 3, 3, 3, 2)
    
    await callback.message.edit_text(
        get_text('choose_category_for_budget', lang),
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(BudgetStates.select_category, F.data.startswith("budget_cat_"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать выбор категории"""
    category_id = int(callback.data.split('_')[2])
    
    # Сохраняем выбранную категорию
    await state.update_data(category_id=category_id)
    await state.set_state(BudgetStates.enter_amount)
    
    await callback.message.edit_text(
        get_text('enter_budget_amount', lang),
        reply_markup=back_close_keyboard(lang)
    )


@router.message(BudgetStates.enter_amount)
async def process_budget_amount(message: Message, state: FSMContext, lang: str = 'ru'):
    """Обработать ввод суммы бюджета"""
    try:
        # Пытаемся извлечь число из текста
        text = message.text.replace(',', '.').strip()
        amount = Decimal(text)
        
        if amount <= 0:
            await send_message_with_cleanup(message, state, get_text('invalid_amount', lang))
            return
            
        # Получаем данные из состояния
        data = await state.get_data()
        category_id = data.get('category_id')
        
        # Создаем бюджет
        budget = await create_budget(
            telegram_id=message.from_user.id,
            category_id=category_id,
            amount=amount,
            period_type='monthly'  # По умолчанию месячный бюджет
        )
        
        if budget:
            await send_message_with_cleanup(message, state, get_text('budget_set', lang))
        else:
            await send_message_with_cleanup(message, state, get_text('error_occurred', lang))
            
        await state.clear()
        
    except (ValueError, InvalidOperation):
        await send_message_with_cleanup(message, state, get_text('invalid_amount', lang))


@router.callback_query(F.data == "delete_budget")
async def delete_budget_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Начать удаление бюджета"""
    # Получаем бюджеты пользователя
    budgets = await get_user_budgets(callback.from_user.id)
    
    if not budgets:
        await callback.answer(get_text('no_budgets', lang), show_alert=True)
        return
        
    # Формируем клавиатуру с бюджетами
    keyboard = InlineKeyboardBuilder()
    
    for budget in budgets:
        # Используем язык пользователя для отображения категории
        category_display = get_category_display_name(budget.category, lang)
        text = f"{category_display}: {format_amount(budget.amount, lang=lang)}"
        keyboard.button(
            text=text,
            callback_data=f"del_budget_{budget.id}"
        )
    
    keyboard.button(text=get_text('back', lang), callback_data="budget_menu")
    keyboard.button(text=get_text('close', lang), callback_data="close")
    keyboard.adjust(1, 1, 1, 2)
    
    await callback.message.edit_text(
        get_text('choose_budget_to_delete', lang),
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("del_budget_"))
async def confirm_budget_deletion(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Подтверждение удаления бюджета"""
    budget_id = int(callback.data.split('_')[2])
    
    await state.update_data(budget_id=budget_id)
    await state.set_state(BudgetStates.confirm_delete)
    
    await callback.message.edit_text(
        get_text('confirm_delete_budget', lang),
        reply_markup=yes_no_keyboard(lang)
    )


@router.callback_query(BudgetStates.confirm_delete, F.data.in_(["yes", "no"]))
async def process_budget_deletion(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработать подтверждение удаления"""
    if callback.data == "yes":
        data = await state.get_data()
        budget_id = data.get('budget_id')
        
        success = await delete_budget(callback.from_user.id, budget_id)
        
        if success:
            await callback.answer(get_text('budget_removed', lang))
        else:
            await callback.answer(get_text('error_occurred', lang))
    else:
        await callback.answer(get_text('cancelled', lang))
        
    await state.clear()
    # Возвращаемся в меню бюджета
    await callback.message.delete()
    await cmd_budget(callback.message, state, lang)


@router.callback_query(F.data == "budget_menu")
async def back_to_budget_menu(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться в меню бюджета"""
    await state.clear()
    await callback.message.delete()
    await cmd_budget(callback.message, state, lang)