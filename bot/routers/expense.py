"""
Обработчик трат - главная функция бота
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# from aiogram.exceptions import CancelHandler  # Not available in aiogram 3.x
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
from ..utils.expense_messages import format_expense_added_message
from ..decorators import require_subscription, rate_limit
from expenses.models import Profile

router = Router(name="expense")
logger = logging.getLogger(__name__)


class ExpenseForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()
    waiting_for_amount_clarification = State()  # Новое состояние для уточнения суммы


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
    header = f"📊 <b>{get_text('summary_for', lang)} {get_text('today', lang).lower()}, {today.strftime('%d')} {month_name}</b>\n\n"
    
    if not summary or (not summary.get('currency_totals') or all(v == 0 for v in summary.get('currency_totals', {}).values())):
        text = header + f"💰 {get_text('total', lang)}: {format_currency(0, summary.get('currency', 'RUB'))}\n\n{get_text('no_expenses_today', lang)}."
    else:
        # Показываем все валюты в разделе "Всего"
        text = header + f"💰 {get_text('total', lang)}:\n"
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"{format_currency(amount, curr)}\n"
        
        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📊 <b>{get_text('by_categories', lang)}:</b>"
            # Добавляем топ-8 категорий
            other_amount = {}
            for i, cat in enumerate(summary['categories']):
                if i < 8 and cat['amount'] > 0:
                    text += f"\n{cat.get('icon', '💰')} {cat['name']}: {format_currency(cat['amount'], cat['currency'])}"
                elif i >= 8 and cat['amount'] > 0:
                    # Суммируем остальные категории по валютам
                    curr = cat['currency']
                    if curr not in other_amount:
                        other_amount[curr] = 0
                    other_amount[curr] += cat['amount']
            
            # Добавляем "Остальные расходы" если есть
            if other_amount:
                for curr, amount in other_amount.items():
                    text += f"\n📊 Остальные расходы: {format_currency(amount, curr)}"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, today, today)
        text += f"\n\n💳 {get_text('potential_cashback', lang)}: {format_currency(cashback, 'RUB')}"
    
    # Добавляем подсказку внизу курсивом
    text += "\n\n<i>Показать отчет за другой период?</i>"
    
    # Кнопки навигации
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 С начала месяца", callback_data="expenses_month")],
        [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data == "expenses_month")
async def show_month_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
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
    
    if not summary or (not summary.get('currency_totals') or all(v == 0 for v in summary.get('currency_totals', {}).values())):
        text = f"""📊 <b>{get_text('summary_for', lang)} {month_names[today.month]} {today.year}</b>

💰 {get_text('total_spent_month', lang)}: 0 {get_text('rub', lang)}

{get_text('no_expenses_this_month', lang)}"""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 <b>{get_text('summary_for', lang)} {month_names[today.month]} {today.year}</b>

💰 {get_text('total_spent_month', lang)}:
"""
        # Показываем все валюты
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"{format_currency(amount, curr)}\n"

        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📊 <b>{get_text('by_categories', lang)}:</b>"
            # Добавляем топ-8 категорий
            other_amount = {}
            for i, cat in enumerate(summary['categories']):
                if i < 8 and cat['amount'] > 0:
                    # Для процентов используем сумму в валюте категории
                    currency_total = summary.get('currency_totals', {}).get(cat['currency'], 0)
                    percent = (float(cat['amount']) / float(currency_total)) * 100 if currency_total > 0 else 0
                    text += f"\n{cat['icon']} {cat['name']}: {format_currency(cat['amount'], cat['currency'])} ({percent:.1f}%)"
                elif i >= 8 and cat['amount'] > 0:
                    # Суммируем остальные категории по валютам
                    curr = cat['currency']
                    if curr not in other_amount:
                        other_amount[curr] = 0
                    other_amount[curr] += cat['amount']
            
            # Добавляем "Остальные расходы" если есть
            if other_amount:
                for curr, amount in other_amount.items():
                    currency_total = summary.get('currency_totals', {}).get(curr, 0)
                    percent = (float(amount) / float(currency_total)) * 100 if currency_total > 0 else 0
                    text += f"\n📊 Остальные расходы: {format_currency(amount, curr)} ({percent:.1f}%)"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, start_date, today)
        text += f"\n\n💳 Потенциальный кешбэк: {format_currency(cashback, 'RUB')}"
    
    # Добавляем подсказку внизу курсивом
    text += "\n\n<i>Показать отчет за другой период?</i>"
    
    # Сохраняем текущий период в состоянии
    await state.update_data(current_month=today.month, current_year=today.year)
    
    # Кнопки навигации с PDF отчетом
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="pdf_generate_current")],
        [InlineKeyboardButton(text="← Предыдущий месяц", callback_data="expenses_prev_month")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "expenses_prev_month")
async def show_prev_month_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за предыдущий месяц"""
    user_id = callback.from_user.id
    
    # Получаем текущий период из состояния
    data = await state.get_data()
    current_month = data.get('current_month', date.today().month)
    current_year = data.get('current_year', date.today().year)
    
    # Вычисляем предыдущий месяц
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    # Импортируем здесь чтобы избежать циклических импортов
    from ..services.expense import get_month_summary
    
    # Получаем сводку за месяц
    summary = await get_month_summary(user_id, prev_month, prev_year)
    
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
    
    if not summary or (not summary.get('currency_totals') or all(v == 0 for v in summary.get('currency_totals', {}).values())):
        text = f"""📊 <b>{get_text('summary_for', lang)} {month_names[prev_month]} {prev_year}</b>

💰 {get_text('total_spent_month', lang)}: 0 {get_text('rub', lang)}

{get_text('no_expenses_this_month', lang)}"""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 <b>{get_text('summary_for', lang)} {month_names[prev_month]} {prev_year}</b>

💰 {get_text('total_spent_month', lang)}:
"""
        # Показываем все валюты
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"{format_currency(amount, curr)}\n"

        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📊 <b>{get_text('by_categories', lang)}:</b>"
            # Добавляем топ-8 категорий
            other_amount = {}
            for i, cat in enumerate(summary['categories']):
                if i < 8 and cat['amount'] > 0:
                    # Для процентов используем сумму в валюте категории
                    currency_total = summary.get('currency_totals', {}).get(cat['currency'], 0)
                    percent = (float(cat['amount']) / float(currency_total)) * 100 if currency_total > 0 else 0
                    text += f"\n{cat['icon']} {cat['name']}: {format_currency(cat['amount'], cat['currency'])} ({percent:.1f}%)"
                elif i >= 8 and cat['amount'] > 0:
                    # Суммируем остальные категории по валютам
                    curr = cat['currency']
                    if curr not in other_amount:
                        other_amount[curr] = 0
                    other_amount[curr] += cat['amount']
            
            # Добавляем "Остальные расходы" если есть
            if other_amount:
                for curr, amount in other_amount.items():
                    currency_total = summary.get('currency_totals', {}).get(curr, 0)
                    percent = (float(amount) / float(currency_total)) * 100 if currency_total > 0 else 0
                    text += f"\n📊 Остальные расходы: {format_currency(amount, curr)} ({percent:.1f}%)"
        
        # Добавляем потенциальный кешбэк
        start_date = date(prev_year, prev_month, 1)
        import calendar
        last_day = calendar.monthrange(prev_year, prev_month)[1]
        end_date = date(prev_year, prev_month, last_day)
        
        cashback = await calculate_potential_cashback(user_id, start_date, end_date)
        text += f"\n\n💳 Потенциальный кешбэк: {format_currency(cashback, 'RUB')}"
    
    # Добавляем подсказку внизу курсивом
    text += "\n\n<i>Показать отчет за другой период?</i>"
    
    # Обновляем текущий период в состоянии
    await state.update_data(current_month=prev_month, current_year=prev_year)
    
    # Кнопки навигации с PDF отчетом
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="pdf_generate_current")],
        [InlineKeyboardButton(text="← Предыдущий месяц", callback_data="expenses_prev_month")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "pdf_generate_current")
async def generate_pdf_report(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация PDF отчета за текущий выбранный месяц"""
    await callback.answer()
    
    # Получаем текущий период из состояния
    data = await state.get_data()
    month = data.get('current_month', date.today().month)
    year = data.get('current_year', date.today().year)
    
    import asyncio
    
    # Создаем задачу для периодической отправки индикатора "отправляет файл"
    async def keep_sending_action():
        for _ in range(15):  # Отправляем 15 раз (каждые 1 сек = 15 секунд)
            try:
                await callback.bot.send_chat_action(callback.message.chat.id, "upload_document")
                await asyncio.sleep(1)
            except:
                break
    
    # Запускаем задачу отправки индикатора
    action_task = asyncio.create_task(keep_sending_action())
    
    try:
        # Импортируем сервис генерации PDF
        from ..services.pdf_report import PDFReportService
        pdf_service = PDFReportService()
        
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=callback.from_user.id,
            year=year,
            month=month
        )
        
        if not pdf_bytes:
            await callback.message.answer(
                "❌ <b>Нет данных для отчета</b>\n\n"
                "За выбранный месяц не найдено расходов.",
                parse_mode="HTML"
            )
            return
        
        # Формируем имя файла
        months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        filename = f"Отчет_Coins_{months[month-1]}_{year}.pdf"
        
        # Создаем файл для отправки
        from aiogram.types import BufferedInputFile
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)
        
        # Отправляем PDF
        await callback.message.answer_document(
            document=pdf_file,
            caption=(
                f"📊 <b>Отчет за {months[month-1]} {year}</b>\n\n"
                "В отчете содержится:\n"
                "• Общая статистика расходов\n"
                "• Распределение по категориям\n"
                "• Динамика трат по дням\n"
                "• Информация о кешбеке\n\n"
                "💡 <i>Совет: сохраните отчет для отслеживания динамики расходов</i>"
            )
        )
        
        # Удаляем предыдущее сообщение со сводкой
        try:
            await callback.message.delete()
        except:
            pass  # Игнорируем ошибки если сообщение уже удалено
        
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await callback.message.answer(
            "❌ <b>Ошибка при генерации отчета</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML"
        )
    finally:
        # Останавливаем задачу отправки индикатора
        action_task.cancel()
        try:
            await action_task
        except asyncio.CancelledError:
            pass


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



# Обработчик ввода суммы после уточнения - ДОЛЖЕН БЫТЬ ПЕРЕД основным обработчиком
@router.message(ExpenseForm.waiting_for_amount_clarification)
async def handle_amount_clarification(message: types.Message, state: FSMContext):
    """Обработка суммы после уточнения описания траты"""
    from ..utils.expense_parser import parse_expense_message
    from ..services.expense import add_expense
    from ..services.category import get_or_create_category
    from ..services.cashback import calculate_expense_cashback
    from ..services.subscription import check_subscription
    from datetime import datetime
    
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Получаем сохраненное описание
    data = await state.get_data()
    description = data.get('expense_description', '')
    
    if not description:
        await state.clear()
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
        return
    
    # Получаем профиль пользователя
    from expenses.models import Profile
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    # Парсим сумму из сообщения пользователя
    parsed_amount = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
    
    if not parsed_amount or not parsed_amount.get('amount'):
        await message.answer(
            "❌ Не удалось распознать сумму.\n"
            "Пожалуйста, введите число (например: 750 или 10.50):"
        )
        return
    
    # Объединяем описание и сумму для полного парсинга с AI
    full_text = f"{description} {text}"
    parsed_full = await parse_expense_message(full_text, user_id=user_id, profile=profile, use_ai=True)
    
    # Если полный парсинг успешен, используем его результат
    if parsed_full:
        amount = parsed_full['amount']
        currency = parsed_full.get('currency', 'RUB')
        category_name = parsed_full.get('category', 'Прочие расходы')
        final_description = parsed_full.get('description', description)
    else:
        # Fallback: используем отдельно распарсенные данные
        amount = parsed_amount['amount']
        currency = parsed_amount.get('currency', 'RUB')
        category_name = 'Прочие расходы'
        final_description = description
    
    # Создаем или получаем категорию
    category = await get_or_create_category(user_id, category_name)
    
    # Сохраняем трату
    expense = await add_expense(
        user_id=user_id,
        category_id=category.id,
        amount=amount,
        description=final_description,
        currency=currency
    )
    
    # Форматируем сообщение с учетом валюты
    amount_text = format_currency(expense.amount, currency)
    
    # Проверяем подписку и рассчитываем кешбэк
    cashback_text = ""
    has_subscription = await check_subscription(user_id)
    if has_subscription:
        current_month = datetime.now().month
        cashback = await calculate_expense_cashback(
            user_id=user_id,
            category_id=category.id,
            amount=expense.amount,
            month=current_month
        )
        if cashback > 0:
            cashback_text = f" (+{cashback:.0f} ₽)"
    
    # Очищаем состояние
    await state.clear()
    
    # Формируем сообщение с информацией о потраченном за день
    message_text = await format_expense_added_message(
        expense=expense,
        category=category,
        cashback_text=cashback_text
    )
    
    # Отправляем подтверждение (сообщение о трате не должно исчезать)
    await send_message_with_cleanup(message, state,
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
            ]
        ]),
        parse_mode="HTML",
        keep_message=True  # Не удалять это сообщение при следующих действиях
    )


# Обработчик текстовых сообщений
@router.message(F.text & ~F.text.startswith('/'))
@rate_limit(max_calls=30, period=60)  # 30 сообщений в минуту
async def handle_text_expense(message: types.Message, state: FSMContext, text: str = None):
    """Обработка текстовых сообщений с тратами"""
    # Импортируем необходимые функции в начале
    from ..services.category import get_or_create_category
    from ..services.expense import add_expense
    from ..services.cashback import calculate_expense_cashback
    from ..services.subscription import check_subscription
    from aiogram.fsm.context import FSMContext
    from ..routers.chat import process_chat_message
    import asyncio
    
    # Проверяем, есть ли активное состояние (кроме нашего состояния ожидания суммы, 
    # которое теперь обрабатывается отдельным обработчиком выше)
    current_state = await state.get_state()
    if current_state:
        # Пропускаем, если есть активное состояние
        logger.info(f"Skipping expense handler due to active state: {current_state}")
        return
    
    user_id = message.from_user.id
    
    # Создаем задачу для отправки индикатора "печатает..." с задержкой 2 секунды
    typing_task = None
    typing_cancelled = False
    
    async def delayed_typing():
        nonlocal typing_cancelled
        await asyncio.sleep(2.0)  # Задержка 2 секунды
        if typing_cancelled:
            return
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        # Планируем повторную отправку через 4 секунды
        while not typing_cancelled:
            await asyncio.sleep(4.0)
            if not typing_cancelled:
                try:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
                except:
                    break
    
    # Запускаем задачу
    typing_task = asyncio.create_task(delayed_typing())
    
    # Функция для отмены индикатора печатания
    def cancel_typing():
        nonlocal typing_cancelled
        typing_cancelled = True
        if typing_task and not typing_task.done():
            typing_task.cancel()
    
    # Если текст не передан явно, берем из сообщения
    if text is None:
        text = message.text
    
    # Парсим сообщение с AI поддержкой
    from expenses.models import Profile
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    logger.info(f"Starting parse_expense_message for text: '{text}', user_id: {user_id}")
    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    logger.info(f"Parsing completed, result: {parsed!r}")
    
    if not parsed:
        # Используем улучшенный классификатор для определения типа сообщения
        from ..utils.text_classifier import classify_message, get_expense_indicators
        
        message_type, confidence = classify_message(text)
        
        # Логируем для отладки
        if confidence > 0.5:
            indicators = get_expense_indicators(text)
            logger.info(f"Classified '{text}' as {message_type} (confidence: {confidence:.2f}), indicators: {indicators}")
        
        # Если классификатор уверен, что это трата
        might_be_expense = (message_type == 'record' and confidence >= 0.6)
        
        if might_be_expense and len(text) > 2:  # Минимальная длина для осмысленного описания
            # Сначала ищем похожие траты за последний год
            from ..services.expense import find_similar_expenses
            from datetime import datetime
            
            similar = await find_similar_expenses(user_id, text)
            
            if similar:
                # Если есть похожие траты, автоматически используем последнюю сумму
                last_expense = similar[0]  # Берем самую частую/последнюю
                amount = last_expense['amount']
                currency = last_expense['currency']
                category_name = last_expense['category']
                
                # Создаем или получаем категорию
                category = await get_or_create_category(user_id, category_name)
                
                # Сохраняем трату
                expense = await add_expense(
                    user_id=user_id,
                    category_id=category.id,
                    amount=amount,
                    description=text,
                    currency=currency
                )
                
                # Форматируем сообщение с учетом валюты
                amount_text = format_currency(expense.amount, currency)
                
                # Проверяем подписку и рассчитываем кешбэк
                cashback_text = ""
                has_subscription = await check_subscription(user_id)
                if has_subscription:
                    current_month = datetime.now().month
                    cashback = await calculate_expense_cashback(
                        user_id=user_id,
                        category_id=category.id,
                        amount=expense.amount,
                        month=current_month
                    )
                    if cashback > 0:
                        cashback_text = f" (+{cashback:.0f} ₽)"
                
                # Формируем сообщение с информацией о потраченном за день
                message_text = await format_expense_added_message(
                    expense=expense,
                    category=category,
                    cashback_text=cashback_text,
                    similar_expense=True
                )
                
                # Отправляем подтверждение (сообщение о трате не должно исчезать)
                cancel_typing()
                await send_message_with_cleanup(message, state,
                    message_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                            InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                        ]
                    ]),
                    parse_mode="HTML",
                    keep_message=True  # Не удалять это сообщение при следующих действиях
                )
            else:
                # Если похожих трат нет, используем обычный двухшаговый ввод
                await state.update_data(expense_description=text)
                await state.set_state(ExpenseForm.waiting_for_amount_clarification)
                
                # Язык пользователя берём из middleware или используем русский по умолчанию
                lang = 'ru'
                
                cancel_typing()
                await message.answer(
                    f"💰 Вы хотите внести трату \"{text}\"?\n\n"
                    f"Укажите сумму траты:",
                    reply_markup=types.ReplyKeyboardRemove()
                )
            return
        
        # Не похоже на трату - обрабатываем как чат
        logger.info(f"Expense parser returned None for text: '{text}', processing as chat")
        cancel_typing()
        await process_chat_message(message, state, text)
        return
    
    # Проверяем, использовались ли данные из предыдущей траты
    reused_from_last = parsed.get('reused_from_last', False)
    
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
    
    # Формируем ответ (убираем вывод AI уверенности)
    confidence_text = ""
    # if parsed.get('ai_enhanced') and parsed.get('confidence'):
    #     confidence_text = f"\n🤖 AI уверенность: {parsed['confidence']*100:.0f}%"
    
    # Форматируем сообщение с учетом валюты
    amount_text = format_currency(expense.amount, currency)
    
    # Проверяем подписку и рассчитываем кешбэк
    from datetime import datetime
    
    cashback_text = ""
    has_subscription = await check_subscription(user_id)
    if has_subscription:
        current_month = datetime.now().month
        cashback = await calculate_expense_cashback(
            user_id=user_id,
            category_id=category.id,
            amount=expense.amount,
            month=current_month
        )
        if cashback > 0:
            cashback_text = f" (+{cashback:.0f} ₽)"
    
    # Формируем сообщение с информацией о потраченном за день
    message_text = await format_expense_added_message(
        expense=expense,
        category=category,
        cashback_text=cashback_text,
        confidence_text=confidence_text,
        reused_from_last=reused_from_last
    )
    
    cancel_typing()
    await send_message_with_cleanup(message, state,
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
            ]
        ]),
        parse_mode="HTML",
        keep_message=True  # Не удалять это сообщение при следующих действиях
    )
    
    # Гарантируем отмену задачи
    cancel_typing()


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
async def edit_expense(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
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
        await callback.answer(get_text('expense_not_found', lang), show_alert=True)
        return
    
    # Сохраняем ID траты в состоянии
    await state.update_data(editing_expense_id=expense_id)
    
    # Показываем меню выбора поля для редактирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 {get_text('sum', lang)}: {expense.amount:.0f} ₽", callback_data="edit_field_amount")],
        [InlineKeyboardButton(text=f"📝 {get_text('description', lang)}: {expense.description}", callback_data="edit_field_description")],
        [InlineKeyboardButton(text=f"📁 {get_text('category', lang)}: {expense.category.name}", callback_data="edit_field_category")],
        [InlineKeyboardButton(text=f"✅ {get_text('edit_done', lang)}", callback_data="edit_done")]
    ])
    
    await callback.message.edit_text(
        f"✏️ <b>{get_text('editing_expense', lang)}</b>\n\n"
        f"{get_text('choose_field_to_edit', lang)}",
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
async def edit_field_amount(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование суммы"""
    await callback.message.edit_text(
        f"💰 <b>{get_text('editing_amount', lang)}</b>\n\n"
        f"{get_text('enter_new_amount', lang)}",
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_amount)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_field_description", EditExpenseForm.choosing_field)
async def edit_field_description(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование описания"""
    await callback.message.edit_text(
        f"📝 <b>{get_text('editing_description', lang)}</b>\n\n"
        f"{get_text('enter_new_description', lang)}",
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_description)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_field_category", EditExpenseForm.choosing_field)
async def edit_field_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование категории"""
    user_id = callback.from_user.id
    from ..services.category import get_user_categories
    
    categories = await get_user_categories(user_id)
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(
            text=f"{categories[i].name}", 
            callback_data=f"expense_cat_{categories[i].id}"
        )]
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(
                text=f"{categories[i + 1].name}", 
                callback_data=f"expense_cat_{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text=get_text('cancel', lang), callback_data="edit_cancel")])
    
    await callback.message.edit_text(
        f"📁 <b>{get_text('choose_new_category', lang)}</b>:\n\n"
        f"<i>{get_text('learning_message', lang)}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_category)
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_cancel")
async def edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования категории"""
    # Возвращаемся к меню редактирования траты
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    if expense_id:
        await show_edit_menu_callback(callback, state, expense_id)
    else:
        await callback.message.delete()
        await state.clear()
    await callback.answer()


@router.callback_query(lambda c: c.data == "edit_done", EditExpenseForm.choosing_field)
async def edit_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования"""
    data = await state.get_data()
    expense_id = data.get('editing_expense_id')
    
    # Получаем обновленную трату
    from expenses.models import Expense
    try:
        expense = await Expense.objects.select_related('category', 'profile').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        # Используем единый формат сообщения
        from ..utils.expense_messages import format_expense_added_message
        message_text = await format_expense_added_message(
            expense=expense,
            category=expense.category
        )
        
        # Редактируем сообщение с кнопками редактирования
        await callback.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                    InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                ]
            ]),
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
        expense = await Expense.objects.select_related('category', 'profile').aget(
            id=expense_id,
            profile__telegram_id=message.from_user.id
        )
        
        # Формируем сообщение с информацией о потраченном за день
        message_text = await format_expense_added_message(
            expense=expense,
            category=expense.category
        )
        
        await send_message_with_cleanup(message, state,
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                    InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                ]
            ]),
            parse_mode="HTML"
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
        expense = await Expense.objects.select_related('category', 'profile').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        # Формируем сообщение с информацией о потраченном за день
        message_text = await format_expense_added_message(
            expense=expense,
            category=expense.category
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                    InlineKeyboardButton(text="🗑 Не сохранять", callback_data=f"delete_expense_{expense.id}")
                ]
            ]),
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)
        await state.clear()