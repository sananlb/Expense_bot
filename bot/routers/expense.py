"""
Обработчик трат - главная функция бота
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import CancelHandler
from datetime import date
import asyncio
import logging

from ..services.expense import get_today_summary, add_expense
from ..services.cashback import calculate_potential_cashback
from ..services.category import get_or_create_category
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils import get_text
from ..utils.expense_parser import parse_expense_message
from ..utils.formatters import format_currency, format_expenses_summary, format_date
from ..utils.validators import validate_amount, parse_description_amount
from ..decorators import require_subscription, rate_limit
from expenses.models import Profile

router = Router(name="expense")
logger = logging.getLogger(__name__)


class ExpenseForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()


class EditExpenseForm(StatesGroup):
    choosing_field = State()
    editing_amount = State()
    editing_description = State()
    editing_category = State()


@router.message(Command("expenses"))
async def cmd_expenses(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Команда /expenses - показать траты за сегодня"""
    user_id = message.from_user.id
    today = date.today()
    
    # Получаем сводку за сегодня
    summary = await get_today_summary(user_id)
    
    # Получаем название месяца
    month_name = get_text(today.strftime('%B').lower(), lang)
    
    # Заголовок с датой
    header = f"📊 {get_text('summary_for', lang)} {get_text('today', lang).lower()}, {today.strftime('%d')} {month_name}\n\n"
    
    if not summary or summary['total'] == 0:
        text = header + f"💰 {get_text('total', lang)}: {format_currency(0, summary.get('currency', 'RUB'))}\n\n{get_text('no_expenses_today', lang)}."
    else:
        # Используем утилиту форматирования
        text = header + format_expenses_summary(summary, lang)
        
        # Если есть траты в других валютах, показываем их
        if not summary.get('single_currency', True):
            text += f"\n\n💱 {get_text('other_currencies', lang)}:"
            for curr, amount in summary.get('currency_totals', {}).items():
                if curr != summary.get('currency', 'RUB') and amount > 0:
                    text += f"\n{format_currency(amount, curr)}"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, today, today)
        text += f"\n\n💳 {get_text('potential_cashback', lang)}: {format_currency(cashback, 'RUB')}"
    
    # Кнопки навигации
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('show_month_start', lang), callback_data="expenses_month")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "expenses_month")
async def show_month_expenses(callback: types.CallbackQuery, lang: str = 'ru'):
    """Показать траты за текущий месяц"""
    user_id = callback.from_user.id
    today = date.today()
    start_date = today.replace(day=1)
    
    # Импортируем здесь чтобы избежать циклических импортов
    from ..services.expense import get_month_summary
    
    # Получаем сводку за месяц
    summary = await get_month_summary(user_id, today.month, today.year)
    
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
    
    if not summary or summary['total'] == 0:
        text = f"""📊 {get_text('summary_for', lang)} {month_names[today.month]} {today.year}

💰 {get_text('total_spent_month', lang)}: 0 {get_text('rub', lang)}

{get_text('no_expenses_this_month', lang)}"""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 {get_text('summary_for', lang)} {month_names[today.month]} {today.year}

💰 {get_text('total_spent_month', lang)}: {summary['total']:,.0f} {get_text('rub', lang)}

📊 {get_text('by_categories', lang)}:"""
        
        # Добавляем топ-5 категорий
        for i, cat in enumerate(summary['categories'][:5]):
            percent = (cat['amount'] / summary['total']) * 100
            text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽ ({percent:.1f}%)"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, start_date, today)
        text += f"\n\n💳 Потенциальный кешбэк: {cashback:,.0f} ₽"
    
    # Кнопки навигации с PDF отчетом
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="generate_pdf")],
        [
            InlineKeyboardButton(text="⬅️", callback_data="expenses_today"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# Обработчики ввода новых значений
@router.message(EditExpenseForm.editing_amount)
async def process_edit_amount(message: types.Message, state: FSMContext):
    """Обработка новой суммы"""
    try:
        amount = await validate_amount(message.text)
    except ValueError as e:
        await message.answer(f"❌ {str(e)}")
        return
    
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    # Обновляем трату
    from ..services.expense import update_expense
    success = await update_expense(message.from_user.id, expense_id, amount=amount)
    
    if success:
        # Показываем обновленную трату
        await show_updated_expense(message, state, expense_id)
    else:
        await message.answer("❌ Не удалось обновить сумму")


@router.message(EditExpenseForm.editing_description)
async def process_edit_description(message: types.Message, state: FSMContext):
    """Обработка нового описания"""
    description = message.text.strip()
    if not description:
        await message.answer("❌ Описание не может быть пустым")
        return
    
    # Капитализация первой буквы
    description = description[0].upper() + description[1:] if description else description
    
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    # Обновляем трату
    from ..services.expense import update_expense
    success = await update_expense(message.from_user.id, expense_id, description=description)
    
    if success:
        # Показываем обновленную трату
        await show_updated_expense(message, state, expense_id)
    else:
        await message.answer("❌ Не удалось обновить описание")



# Обработчик текстовых сообщений
@router.message(F.text & ~F.text.startswith('/'))
@rate_limit(max_calls=30, period=60)  # 30 сообщений в минуту
async def handle_text_expense(message: types.Message, state: FSMContext, text: str = None):
    """Обработка текстовых сообщений с тратами"""
    # Проверяем, есть ли активное состояние
    current_state = await state.get_state()
    if current_state:
        # Если есть активное состояние, не обрабатываем как трату
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Skipping expense handler due to active state: {current_state}")
        return
    
    user_id = message.from_user.id
    
    # Если текст не передан явно, берем из сообщения
    if text is None:
        text = message.text
    
    # Парсим сообщение с AI поддержкой
    from expenses.models import Profile
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    
    if not parsed:
        # Не удалось распознать трату - пропускаем обработку
        # Сообщение будет обработано chat_router'ом
        logger.info(f"Expense parser returned None for text: '{text}', passing to chat router")
        raise CancelHandler()  # Явно отменяем обработку для передачи следующему роутеру
    
    # Проверяем/создаем категорию
    category = await get_or_create_category(user_id, parsed['category'])
    
    # Сохраняем в оригинальной валюте
    amount = parsed['amount']
    currency = parsed.get('currency', 'RUB')
    
    # Добавляем трату в оригинальной валюте
    expense = await add_expense(
        user_id=user_id,
        category_id=category.id,
        amount=amount,
        description=parsed['description'],
        currency=currency
    )
    
    # Формируем ответ
    confidence_text = ""
    if parsed.get('ai_enhanced') and parsed.get('confidence'):
        confidence_text = f"\n🤖 AI уверенность: {parsed['confidence']*100:.0f}%"
    
    # Форматируем сообщение с учетом валюты
    amount_text = format_currency(expense.amount, currency)
    
    await send_message_with_cleanup(message, state,
        f"✅ Трата добавлена!\n\n"
        f"💰 Сумма: {amount_text}\n"
        f"📁 Категория: {category.icon} {category.name}\n"
        f"📝 Описание: {expense.description}"
        f"{confidence_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
            ]
        ])
    )


# Обработчик голосовых сообщений
@router.message(F.voice)
@rate_limit(max_calls=10, period=60)  # 10 голосовых в минуту
async def handle_voice_expense(message: types.Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
    
    has_subscription = await check_subscription(message.from_user.id)
    if not has_subscription:
        await message.answer(
            subscription_required_message() + "\n\n⚠️ Голосовой ввод доступен только с подпиской.",
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        return
    
    # Получаем язык пользователя из middleware
    user_language = getattr(message, 'user_language', 'ru')
    bot = message.bot
    
    try:
        # Пробуем использовать простой встроенный распознаватель
        from bot.services.voice_recognition import process_voice_for_expense
        
        # Распознаем голосовое сообщение с учетом языка
        text = await process_voice_for_expense(message, bot, user_language)
        
    except ImportError:
        # Если библиотеки не установлены, используем старый метод
        from bot.services.voice_processing import process_voice_expense
        
        # Распознаем голосовое сообщение
        text = await process_voice_expense(message, bot, user_language)
    
    if not text:
        return
    
    # Вызываем обработчик текстовых сообщений напрямую с распознанным текстом
    # Как это сделано в nutrition_bot
    await handle_text_expense(message, state, text=text)


# Обработчик фото (чеков)
@router.message(F.photo)
@rate_limit(max_calls=10, period=60)  # 10 фото в минуту
async def handle_photo_expense(message: types.Message, state: FSMContext):
    """Обработка фото чеков"""
    await send_message_with_cleanup(message, state, "📸 Обработка чеков будет добавлена в следующей версии.")


# Обработчик редактирования траты
@router.callback_query(lambda c: c.data.startswith("edit_expense_"))
async def edit_expense(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование траты"""
    expense_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    # Получаем информацию о трате
    from ..services.expense import get_last_expense
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=user_id
        )
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)
        return
    
    # Сохраняем ID траты в состоянии
    await state.update_data(editing_expense_id=expense_id)
    
    # Показываем меню выбора поля для редактирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Сумма: {expense.amount:.0f} ₽", callback_data="edit_field_amount")],
        [InlineKeyboardButton(text=f"📝 Описание: {expense.description}", callback_data="edit_field_description")],
        [InlineKeyboardButton(text=f"📁 Категория: {expense.category.name}", callback_data="edit_field_category")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="edit_done")]
    ])
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование траты</b>\n\n"
        "Выберите поле для изменения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(EditExpenseForm.choosing_field)
    await callback.answer()


# Обработчик удаления траты
@router.callback_query(lambda c: c.data.startswith("delete_expense_"))
async def delete_expense(callback: types.CallbackQuery):
    """Удаление траты"""
    expense_id = int(callback.data.split("_")[-1])
    from ..services.expense import delete_expense as delete_expense_service
    
    user_id = callback.from_user.id
    
    # Удаляем трату
    success = await delete_expense_service(user_id, expense_id)
    
    if success:
        await callback.message.delete()
    else:
        await callback.answer("❌ Не удалось удалить трату", show_alert=True)


# Обработчики выбора поля для редактирования
@router.callback_query(lambda c: c.data == "edit_field_amount", EditExpenseForm.choosing_field)
async def edit_field_amount(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование суммы"""
    await callback.message.edit_text(
        "💰 <b>Изменение суммы</b>\n\n"
        "Введите новую сумму:",
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_amount)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_field_description", EditExpenseForm.choosing_field)
async def edit_field_description(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование описания"""
    await callback.message.edit_text(
        "📝 <b>Изменение описания</b>\n\n"
        "Введите новое описание:",
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_description)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_field_category", EditExpenseForm.choosing_field)
async def edit_field_category(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование категории"""
    user_id = callback.from_user.id
    from ..services.category import get_user_categories
    
    categories = await get_user_categories(user_id)
    
    keyboard_buttons = []
    for cat in categories:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{cat.name}", 
                callback_data=f"expense_cat_{cat.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")])
    
    await callback.message.edit_text(
        "📁 <b>Выберите новую категорию</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_category)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_done", EditExpenseForm.choosing_field)
async def edit_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования"""
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    # Получаем обновленную трату
    from expenses.models import Expense
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        await callback.message.edit_text(
            f"✅ <b>Трата обновлена!</b>\n\n"
            f"💰 Сумма: {expense.amount:.0f} ₽\n"
            f"📁 Категория: {expense.category.name}\n"
            f"📝 Описание: {expense.description}",
            parse_mode="HTML"
        )
    except Expense.DoesNotExist:
        await callback.message.edit_text("❌ Ошибка при получении данных траты")
    
    await state.clear()
    await callback.answer()






@router.callback_query(lambda c: c.data.startswith("expense_cat_"), EditExpenseForm.editing_category)
async def process_edit_category(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора новой категории"""
    category_id = int(callback.data.split("_")[-1])
    
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    # Получаем информацию о трате для обучения
    from expenses.models import Expense
    try:
        expense = await Expense.objects.aget(id=expense_id)
        old_category_id = expense.category_id
        description = expense.description
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)
        return
    
    # Обновляем трату
    from ..services.expense import update_expense
    success = await update_expense(callback.from_user.id, expense_id, category_id=category_id)
    
    if success:
        # Если категория изменилась, запускаем обучение
        if old_category_id != category_id:
            from ..services.category import learn_from_category_change
            import asyncio
            # Запускаем в фоне, не ждём завершения
            asyncio.create_task(
                learn_from_category_change(
                    callback.from_user.id, 
                    expense_id, 
                    category_id, 
                    description
                )
            )
        
        # Показываем обновленную трату
        await show_updated_expense_callback(callback, state, expense_id)
    else:
        await callback.answer("❌ Не удалось обновить категорию", show_alert=True)


# Вспомогательная функция для показа меню редактирования
async def show_edit_menu(message: types.Message, state: FSMContext, expense_id: int):
    """Показать меню редактирования после изменения"""
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=message.from_user.id
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Сумма: {expense.amount:.0f} ₽", callback_data="edit_field_amount")],
            [InlineKeyboardButton(text=f"📝 Описание: {expense.description}", callback_data="edit_field_description")],
            [InlineKeyboardButton(text=f"📁 Категория: {expense.category.name}", callback_data="edit_field_category")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="edit_done")]
        ])
        
        await send_message_with_cleanup(message, state,
            "✏️ <b>Редактирование траты</b>\n\n"
            "Выберите поле для изменения:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(EditExpenseForm.choosing_field)
    except Expense.DoesNotExist:
        await message.answer("❌ Трата не найдена")


async def show_edit_menu_callback(callback: types.CallbackQuery, state: FSMContext, expense_id: int):
    """Показать меню редактирования для callback"""
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Сумма: {expense.amount:.0f} ₽", callback_data="edit_field_amount")],
            [InlineKeyboardButton(text=f"📝 Описание: {expense.description}", callback_data="edit_field_description")],
            [InlineKeyboardButton(text=f"📁 Категория: {expense.category.name}", callback_data="edit_field_category")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="edit_done")]
        ])
        
        await callback.message.edit_text(
            "✏️ <b>Редактирование траты</b>\n\n"
            "Выберите поле для изменения:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(EditExpenseForm.choosing_field)
        await callback.answer()
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)


async def show_updated_expense(message: types.Message, state: FSMContext, expense_id: int):
    """Показать обновленную трату"""
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=message.from_user.id
        )
        
        # Форматируем сообщение
        currency = expense.currency or 'RUB'
        if currency == 'RUB':
            amount_text = f"{expense.amount:.0f} ₽"
        else:
            amount_text = f"{expense.amount:.2f} {currency}"
        
        await send_message_with_cleanup(message, state,
            f"✅ Трата обновлена!\n\n"
            f"💰 Сумма: {amount_text}\n"
            f"📁 Категория: {expense.category.icon} {expense.category.name}\n"
            f"📝 Описание: {expense.description}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                    InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                ]
            ])
        )
        
        # Очищаем состояние
        await state.clear()
    except Expense.DoesNotExist:
        await message.answer("❌ Трата не найдена")
        await state.clear()


async def show_updated_expense_callback(callback: types.CallbackQuery, state: FSMContext, expense_id: int):
    """Показать обновленную трату для callback"""
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        # Форматируем сообщение
        currency = expense.currency or 'RUB'
        if currency == 'RUB':
            amount_text = f"{expense.amount:.0f} ₽"
        else:
            amount_text = f"{expense.amount:.2f} {currency}"
        
        await callback.message.edit_text(
            f"✅ Трата обновлена!\n\n"
            f"💰 Сумма: {amount_text}\n"
            f"📁 Категория: {expense.category.icon} {expense.category.name}\n"
            f"📝 Описание: {expense.description}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                    InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                ]
            ])
        )
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)
        await state.clear()