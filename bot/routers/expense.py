"""
Обработчик трат - главная функция бота
"""
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramNotFound, TelegramForbiddenError
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
import asyncio
import logging

from ..services.expense import add_expense
from ..services.cashback import calculate_potential_cashback, calculate_expense_cashback
from ..services.category import get_or_create_category, create_default_income_categories
from bot.utils.income_category_definitions import (
    get_income_category_display_name as get_income_category_display_for_key,
    normalize_income_category_key,
    strip_leading_emoji,
)
from ..services.subscription import check_subscription
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils import get_text, get_user_language
from ..utils.expense_parser import parse_expense_message
from ..utils.formatters import format_currency, format_expenses_summary, format_date
from ..utils.validators import validate_amount, parse_description_amount
from ..utils.expense_messages import format_expense_added_message
from ..utils.category_helpers import get_category_display_name
from ..decorators import require_subscription, rate_limit
from ..keyboards import expenses_summary_keyboard
from expenses.models import Profile
from django.db import DatabaseError

router = Router(name="expense")
logger = logging.getLogger(__name__)


def format_decimal_amount(amount: Decimal) -> str:
    """Formats Decimal/number with thousand separators and trims trailing zeros."""
    formatted = format(amount, ",f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


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
    today = date.today()
    
    # Перенаправляем на обработчик reports через callback
    from ..routers.reports import callback_expenses_today
    
    # Создаем фейковый callback query для переиспользования логики
    from aiogram.types import CallbackQuery
    
    # Просто вызываем show_expenses_summary напрямую
    from ..routers.reports import show_expenses_summary
    await show_expenses_summary(
        message,
        today,
        today,
        lang,
        state=state,
        edit=False
    )


@router.callback_query(lambda c: c.data == "expenses_month")
async def show_month_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за текущий месяц"""
    user_id = callback.from_user.id
    today = date.today()
    start_date = today.replace(day=1)
    
    # Используем show_expenses_summary из reports
    from ..routers.reports import show_expenses_summary
    await show_expenses_summary(
        callback.message,
        start_date,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    
    await callback.answer()


@router.callback_query(lambda c: c.data == "expenses_prev_month")
async def show_prev_month_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за предыдущий месяц"""
    user_id = callback.from_user.id
    
    # Получаем текущий период из состояния
    data = await state.get_data()
    current_month = data.get('current_month') or date.today().month
    current_year = data.get('current_year') or date.today().year
    
    # Вычисляем предыдущий месяц
    if current_month == 1:
        prev_month = 12
        prev_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_year = current_year
    
    # Определяем даты начала и конца месяца
    from calendar import monthrange
    start_date = date(prev_year, prev_month, 1)
    _, last_day = monthrange(prev_year, prev_month)
    end_date = date(prev_year, prev_month, last_day)
    
    # Используем show_expenses_summary из reports
    from ..routers.reports import show_expenses_summary
    await show_expenses_summary(
        callback.message,
        start_date,
        end_date,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    
    await callback.answer()
    return
    
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
        text = f"""📊 <b>{month_names[prev_month]} {prev_year}</b>

💸 <b>Потрачено за месяц:</b>
• 0 {get_text('rub', lang)}

{get_text('no_expenses_this_month', lang)}"""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 <b>{month_names[prev_month]} {prev_year}</b>

💸 <b>Потрачено за месяц:</b>
"""
        # Показываем все валюты
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"• {format_currency(amount, curr)}\n"

        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📁 <b>{get_text('by_categories', lang)}:</b>"
            # Добавляем топ-8 категорий
            other_amount = {}
            for i, cat in enumerate(summary['categories']):
                if i < 8 and cat['amount'] > 0:
                    from types import SimpleNamespace
                    cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                    translated_name = get_category_display_name(cat_obj, lang)
                    text += f"\n{cat['icon']} {translated_name}: {format_currency(cat['amount'], cat['currency'])}"
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
        start_date = date(prev_year, prev_month, 1)
        import calendar
        last_day = calendar.monthrange(prev_year, prev_month)[1]
        end_date = date(prev_year, prev_month, last_day)
        
        cashback = await calculate_potential_cashback(user_id, start_date, end_date)
        if cashback > 0:
            text += f"\n\n💳 <b>Потенциальный кешбэк:</b>\n• {format_currency(cashback, 'RUB')}"
    
    # Обновляем текущий период в состоянии
    await state.update_data(current_month=prev_month, current_year=prev_year)
    
    # Определяем название предыдущего и следующего месяцев для кнопок
    if prev_month == 1:
        prev_button_month = 12
        prev_button_year = prev_year - 1
    else:
        prev_button_month = prev_month - 1
        prev_button_year = prev_year
    
    if prev_month == 12:
        next_button_month = 1
        next_button_year = prev_year + 1
    else:
        next_button_month = prev_month + 1
        next_button_year = prev_year
    
    # Проверяем, не является ли следующий месяц будущим
    today = date.today()
    is_future = (next_button_year > today.year) or (next_button_year == today.year and next_button_month > today.month)
    
    # Кнопки навигации с PDF отчетом
    keyboard_buttons = [
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="pdf_generate_current")]
    ]
    
    # Добавляем кнопки навигации
    nav_buttons = []
    nav_buttons.append(InlineKeyboardButton(
        text=f"← {month_names[prev_button_month]}",
        callback_data="expenses_prev_month"
    ))
    
    if not is_future:
        nav_buttons.append(InlineKeyboardButton(
            text=f"{month_names[next_button_month]} →",
            callback_data="expenses_next_month"
        ))
    
    keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "expenses_next_month")
async def show_next_month_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать траты за следующий месяц"""
    user_id = callback.from_user.id
    
    # Получаем текущий период из состояния
    data = await state.get_data()
    current_month = data.get('current_month') or date.today().month
    current_year = data.get('current_year') or date.today().year
    
    # Вычисляем следующий месяц
    if current_month == 12:
        next_month = 1
        next_year = current_year + 1
    else:
        next_month = current_month + 1
        next_year = current_year
    
    # Определяем даты начала и конца месяца
    from calendar import monthrange
    start_date = date(next_year, next_month, 1)
    _, last_day = monthrange(next_year, next_month)
    end_date = date(next_year, next_month, last_day)
    
    # Используем show_expenses_summary из reports
    from ..routers.reports import show_expenses_summary
    await show_expenses_summary(
        callback.message,
        start_date,
        end_date,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    
    await callback.answer()
    return
    
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
        text = f"""📊 <b>{month_names[next_month]} {next_year}</b>

💸 <b>Потрачено за месяц:</b>
• 0 {get_text('rub', lang)}

{get_text('no_expenses_this_month', lang)}"""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 <b>{month_names[next_month]} {next_year}</b>

💸 <b>Потрачено за месяц:</b>
"""
        # Показываем все валюты
        currency_totals = summary.get('currency_totals', {})
        for curr, amount in sorted(currency_totals.items()):
            if amount > 0:
                text += f"• {format_currency(amount, curr)}\n"

        # Показываем категории для всех валют
        if summary.get('categories'):
            text += f"\n📁 <b>{get_text('by_categories', lang)}:</b>"
            # Добавляем топ-8 категорий
            other_amount = {}
            for i, cat in enumerate(summary['categories']):
                if i < 8 and cat['amount'] > 0:
                    from types import SimpleNamespace
                    cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                    translated_name = get_category_display_name(cat_obj, lang)
                    text += f"\n{cat['icon']} {translated_name}: {format_currency(cat['amount'], cat['currency'])}"
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
        start_date = date(next_year, next_month, 1)
        import calendar
        last_day = calendar.monthrange(next_year, next_month)[1]
        end_date = date(next_year, next_month, last_day)
        
        cashback = await calculate_potential_cashback(user_id, start_date, end_date)
        if cashback > 0:
            text += f"\n\n💳 <b>Потенциальный кешбэк:</b>\n• {format_currency(cashback, 'RUB')}"
    
    # Обновляем текущий период в состоянии
    await state.update_data(current_month=next_month, current_year=next_year)
    
    # Определяем название предыдущего и следующего месяцев для кнопок
    if next_month == 1:
        prev_button_month = 12
        prev_button_year = next_year - 1
    else:
        prev_button_month = next_month - 1
        prev_button_year = next_year
    
    if next_month == 12:
        next_button_month = 1
        next_button_year = next_year + 1
    else:
        next_button_month = next_month + 1
        next_button_year = next_year
    
    # Проверяем, не является ли следующий месяц будущим
    today = date.today()
    is_future = (next_button_year > today.year) or (next_button_year == today.year and next_button_month > today.month)
    
    # Кнопки навигации с PDF отчетом
    keyboard_buttons = [
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="pdf_generate_current")]
    ]
    
    # Добавляем кнопки навигации
    nav_buttons = []
    nav_buttons.append(InlineKeyboardButton(
        text=f"← {month_names[prev_button_month]}",
        callback_data="expenses_prev_month"
    ))
    
    if not is_future:
        nav_buttons.append(InlineKeyboardButton(
            text=f"{month_names[next_button_month]} →",
            callback_data="expenses_next_month"
        ))
    
    keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "expenses_today_view")
async def show_today_expenses(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться к сегодняшним тратам"""
    from bot.routers.reports import show_expenses_summary
    
    today = date.today()
    
    # Сбрасываем состояние месяца
    await state.update_data(current_month=None, current_year=None)
    
    # Показываем траты за сегодня
    await show_expenses_summary(
        callback.message,
        today,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "pdf_generate_current")
async def generate_pdf_report(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация PDF отчета за текущий выбранный месяц"""
    if not await check_subscription(callback.from_user.id):
        await callback.answer(get_text('subscription_required', lang), show_alert=True)
        return

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
            except (TelegramForbiddenError, TelegramBadRequest):
                break  # Пользователь заблокировал бота или некорректный chat_id
    
    # Запускаем задачу отправки индикатора
    action_task = asyncio.create_task(keep_sending_action())
    
    try:
        # Импортируем сервис генерации PDF
        from ..services.pdf_report import PDFReportService
        pdf_service = PDFReportService()
        
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=callback.from_user.id,
            year=year,
            month=month,
            lang=lang
        )
        
        if not pdf_bytes:
            await callback.message.answer(
                "❌ <b>Нет данных для отчета</b>\n\n"
                "За выбранный месяц не найдено расходов.",
                parse_mode="HTML"
            )
            return
        
        # Определяем режим (личный/семейный) для пометки в заголовке PDF
        from asgiref.sync import sync_to_async
        @sync_to_async
        def is_household(uid):
            from expenses.models import Profile, UserSettings
            try:
                profile = Profile.objects.get(telegram_id=uid)
                settings = profile.settings if hasattr(profile, 'settings') else UserSettings.objects.create(profile=profile)
                return bool(profile.household_id) and getattr(settings, 'view_scope', 'personal') == 'household'
            except Exception:
                return False
        household_mode = await is_household(callback.from_user.id)

        # Формируем имя файла
        if lang == 'en':
            months = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
            filename = f"Coins_Report_{months[month-1]}_{year}.pdf"
        else:
            months = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                      'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            filename = f"Отчет_Coins_{months[month-1]}_{year}.pdf"
        
        # Создаем файл для отправки
        from aiogram.types import BufferedInputFile
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)
        
        # Отправляем PDF
        if lang == 'en':
            mode = " – 🏠 Household" if household_mode else ""
            caption = (
                f"📊 <b>Report for {months[month-1]} {year}{mode}</b>\n\n"
                "The report contains:\n"
                "• Overall expense statistics\n"
                "• Distribution by categories\n"
                "• Daily spending dynamics\n"
                "• Cashback information\n\n"
                "💡 <i>Tip: Save the report to track expense dynamics</i>\n\n"
                "✨ Generated with Coins @showmecoinbot"
            )
        else:
            mode = " – 🏠 Семейный бюджет" if household_mode else ""
            caption = (
                f"📊 <b>Отчет за {months[month-1]} {year}{mode}</b>\n\n"
                "В отчете содержится:\n"
                "• Общая статистика расходов\n"
                "• Распределение по категориям\n"
                "• Динамика трат по дням\n"
                "• Информация о кешбеке\n\n"
                "💡 <i>Совет: сохраните отчет для отслеживания динамики расходов</i>\n\n"
                "✨ Сгенерировано в Coins ✨\n"
                "✨ @showmecoinbot ✨"
            )
        await callback.message.answer_document(
            document=pdf_file,
            caption=caption
        )
        
        # Удаляем предыдущее сообщение со сводкой
        try:
            await callback.message.delete()
        except (TelegramBadRequest, TelegramNotFound):
            pass  # Игнорируем ошибки если сообщение уже удалено
        
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        if lang == 'en':
            error_text = (
                "❌ <b>Error generating report</b>\n\n"
                "Please try again later or contact support."
            )
        else:
            error_text = (
                "❌ <b>Ошибка при генерации отчета</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку."
            )
        await callback.message.answer(
            error_text,
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
async def process_edit_amount(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка новой суммы"""
    import re
    from ..utils.expense_parser import detect_currency, CURRENCY_PATTERNS

    text = (message.text or "").strip()
    text_no_spaces = re.sub(r"\s+", "", text)

    # Получаем валюту пользователя для определения валюты по умолчанию
    from ..services.profile import get_or_create_profile
    profile = await get_or_create_profile(message.from_user.id)
    user_currency = (profile.currency or 'RUB').upper()

    inline_currency = None
    inline_amount = None
    currency_explicit = False

    # Формат вида "100usd"
    inline_trailing = re.fullmatch(r'([+-]?\d+(?:[.,]\d+)?)([a-z]{2,4})', text_no_spaces, flags=re.IGNORECASE)
    if inline_trailing:
        code_candidate = inline_trailing.group(2).upper()
        if code_candidate in CURRENCY_PATTERNS or code_candidate == user_currency:
            inline_currency = code_candidate
            inline_amount = inline_trailing.group(1)
            currency_explicit = True

    # Формат вида "usd100"
    if inline_currency is None:
        inline_leading = re.fullmatch(r'([a-z]{2,4})([+-]?\d+(?:[.,]\d+)?)', text_no_spaces, flags=re.IGNORECASE)
        if inline_leading:
            code_candidate = inline_leading.group(1).upper()
            if code_candidate in CURRENCY_PATTERNS or code_candidate == user_currency:
                inline_currency = code_candidate
                inline_amount = inline_leading.group(2)
                currency_explicit = True

    detected_currency = inline_currency or detect_currency(text, user_currency)
    currency = (detected_currency or user_currency).upper()

    if inline_amount is not None:
        cleaned_text = inline_amount
    else:
        cleaned_text = text
        for curr_patterns in CURRENCY_PATTERNS.values():
            for pattern in curr_patterns:
                new_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
                if new_text != cleaned_text:
                    currency_explicit = True
                    cleaned_text = new_text

        cleaned_no_spaces = re.sub(r"\s+", "", cleaned_text)
        tail_match = re.fullmatch(r'([+-]?\d+(?:[.,]\d+)?)([a-z]{2,4})', cleaned_no_spaces, flags=re.IGNORECASE)
        if tail_match:
            cleaned_text = tail_match.group(1)
            currency_explicit = True
        else:
            head_match = re.fullmatch(r'([a-z]{2,4})([+-]?\d+(?:[.,]\d+)?)', cleaned_no_spaces, flags=re.IGNORECASE)
            if head_match:
                cleaned_text = head_match.group(2)
                currency_explicit = True

        cleaned_text = cleaned_text.strip()

    try:
        amount = await validate_amount(cleaned_text)
    except ValueError as e:
        await message.answer(f"❌ {str(e)}")
        return

    data = await state.get_data()
    item_id = data.get('editing_expense_id')
    is_income = data.get('editing_type') == 'income'

    update_kwargs = {'amount': amount}
    if currency_explicit:
        update_kwargs['currency'] = currency

    # Обновляем операцию с новой валютой (если указана явно)
    if is_income:
        from ..services.income import update_income
        success = await update_income(message.from_user.id, item_id, **update_kwargs)
    else:
        from ..services.expense import update_expense
        success = await update_expense(message.from_user.id, item_id, **update_kwargs)

    if success:
        # Удаляем промежуточное сообщение с запросом ввода
        data = await state.get_data()
        prompt_message_id = data.get('editing_prompt_message_id')
        if prompt_message_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
            except Exception:
                pass  # Игнорируем ошибки удаления (сообщение могло быть уже удалено)

        # Показываем обновленную операцию
        await show_updated_expense(message, state, item_id, lang)
    else:
        error_msg = "❌ Не удалось обновить сумму дохода" if is_income else "❌ Не удалось обновить сумму"
        await message.answer(error_msg)


@router.message(EditExpenseForm.editing_description)
async def process_edit_description(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка нового описания"""
    description = message.text.strip()
    if not description:
        await message.answer("❌ Описание не может быть пустым")
        return
    
    # Капитализация только первой буквы, не меняя регистр остальных
    if description and len(description) > 0:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    data = await state.get_data()
    item_id = data.get('editing_expense_id')
    is_income = data.get('editing_type') == 'income'
    
    # Обновляем операцию
    if is_income:
        from ..services.income import update_income
        success = await update_income(message.from_user.id, item_id, description=description)
    else:
        from ..services.expense import update_expense
        success = await update_expense(message.from_user.id, item_id, description=description)
    
    if success:
        # Удаляем промежуточное сообщение с запросом ввода
        data = await state.get_data()
        prompt_message_id = data.get('editing_prompt_message_id')
        if prompt_message_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
            except Exception:
                pass  # Игнорируем ошибки удаления (сообщение могло быть уже удалено)

        # Показываем обновленную операцию
        await show_updated_expense(message, state, item_id, lang)
    else:
        error_msg = "❌ Не удалось обновить описание дохода" if is_income else "❌ Не удалось обновить описание"
        await message.answer(error_msg)



# Обработчик ввода суммы после уточнения - ДОЛЖЕН БЫТЬ ПЕРЕД основным обработчиком
@router.message(ExpenseForm.waiting_for_amount_clarification)
async def handle_amount_clarification(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Обработка суммы после уточнения описания траты"""
    from ..utils.expense_parser import parse_expense_message
    from ..services.expense import add_expense
    from ..services.category import get_or_create_category
    from ..services.cashback import calculate_expense_cashback
    from ..utils.expense_intent import is_show_expenses_request
    
    user_id = message.from_user.id
    text = message.text.strip()
    
    # УЛУЧШЕНИЕ: Используем единый модуль для проверки
    is_show_request, confidence = is_show_expenses_request(text)
    if is_show_request and confidence >= 0.7:
        # Это команда показа трат, выходим из состояния и обрабатываем команду
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
        from ..routers.chat import process_chat_message
        await process_chat_message(message, state, text, skip_typing=True)
        return
    
    # Получаем сохраненное описание
    data = await state.get_data()
    description = data.get('expense_description', '')
    
    if not description:
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
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
        await message.answer(get_text('could_not_recognize_amount', lang))
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
    expense_date = parsed_full.get('expense_date') if parsed_full else parsed_amount.get('expense_date')
    try:
        expense = await add_expense(
            user_id=user_id,
            category_id=category.id,
            amount=amount,
            description=final_description,
            currency=currency,
            expense_date=expense_date,  # Добавляем дату, если она была указана
            ai_categorized=parsed_full.get('ai_enhanced', False) if parsed_full else False,
            ai_confidence=parsed_full.get('confidence') if parsed_full else None
        )
    except ValueError as e:
        # Обработка ошибок валидации даты
        await message.answer(f"❌ {str(e)}", parse_mode="HTML")
        await state.clear()
        return
    
    # Форматируем сообщение с учетом валюты
    amount_text = format_currency(expense.amount, currency)
    
    # Проверяем подписку и рассчитываем кешбэк
    cashback_text = ""
    has_subscription = await check_subscription(user_id)
    # Получаем валюту пользователя из профиля
    user_currency = profile.currency if profile else 'RUB'
    # Кешбэк начисляется только для трат в валюте пользователя
    if has_subscription and currency == user_currency:
        current_month = datetime.now().month
        cashback = await calculate_expense_cashback(
            user_id=user_id,
            category_id=category.id,
            amount=expense.amount,
            month=current_month
        )
        if cashback > 0:
            cashback_text = f" (+{cashback:.0f} ₽)"
            # Сохраняем кешбек в базе данных
            expense.cashback_amount = Decimal(str(cashback))
            await expense.asave()
    
    # Удаляем сообщение с запросом суммы
    clarification_message_id = data.get('clarification_message_id')
    if clarification_message_id:
        try:
            await message.bot.delete_message(
                chat_id=user_id,
                message_id=clarification_message_id
            )
        except Exception as e:
            logger.debug(f"Could not delete clarification message: {e}")
    
    # Очищаем состояние
    from bot.utils.state_utils import clear_state_keep_cashback
    await clear_state_keep_cashback(state)
    
    # Формируем сообщение с информацией о потраченном за день
    message_text = await format_expense_added_message(
        expense=expense,
        category=category,
        cashback_text=cashback_text,
        lang=lang
    )

    # Отправляем подтверждение (сообщение о трате не должно исчезать)
    # send_message_with_cleanup сама удалит старое меню после отправки нового
    await send_message_with_cleanup(message, state,
        message_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_expense_{expense.id}")
            ]
        ]),
        parse_mode="HTML",
        keep_message=True  # Не удалять это сообщение при следующих действиях
    )


# Обработчик кнопки отмены ввода траты
@router.callback_query(lambda c: c.data == "cancel_expense_input")
async def cancel_expense_input(callback: types.CallbackQuery, state: FSMContext):
    """Отмена ввода траты и удаление сообщения"""
    # Получаем данные из состояния
    data = await state.get_data()
    clarification_message_id = data.get('clarification_message_id')
    
    # Очищаем состояние
    from bot.utils.state_utils import clear_state_keep_cashback
    await clear_state_keep_cashback(state)
    
    # Удаляем сообщение с запросом суммы
    try:
        if clarification_message_id:
            await callback.bot.delete_message(
                chat_id=callback.from_user.id,
                message_id=clarification_message_id
            )
    except Exception as e:
        logger.error(f"Error deleting clarification message: {e}")
    
    # Просто подтверждаем нажатие кнопки без текста
    await callback.answer()


# Обработчик текстовых сообщений
@router.message(F.text & ~F.text.startswith('/'))
@rate_limit(max_calls=30, period=60)  # 30 сообщений в минуту
async def handle_text_expense(message: types.Message, state: FSMContext, text: str = None, lang: str = 'ru', user_id: Optional[int] = None):
    """Обработка текстовых сообщений с тратами

    Args:
        user_id: Опциональный user_id для случаев когда message.from_user не соответствует реальному пользователю
                 (например, при вызове из callback где message.from_user - это бот)
    """
    # Импортируем необходимые функции в начале
    from ..services.category import get_or_create_category
    from ..services.expense import add_expense
    from ..services.cashback import calculate_expense_cashback
    from aiogram.fsm.context import FSMContext
    from ..routers.chat import process_chat_message
    import asyncio

    # Глобальная обработка кешбэка: запускается независимо от активного состояния FSM
    try:
        incoming_text = text if text is not None else (message.text or "")
        from ..services.cashback_free_text import looks_like_cashback_free_text, process_cashback_free_text
        if looks_like_cashback_free_text(incoming_text):
            ok, resp = await process_cashback_free_text(message.from_user.id, incoming_text)
            if ok:
                await send_message_with_cleanup(message, state, resp, parse_mode="HTML")
            else:
                hint = "\n\nФормат: <i>кешбек 5 процентов на категорию Кафе и рестораны Тинькофф</i>"
                await send_message_with_cleanup(message, state, resp + hint, parse_mode="HTML")
            return
    except Exception as e:
        logger.debug(f"Cashback free text detection error (early): {e}")
    
    # Проверяем, есть ли активное состояние (кроме нашего состояния ожидания суммы)
    current_state = await state.get_state()

    # Список состояний, при которых НЕ нужно обрабатывать траты
    skip_states = [
        # Household states
        "HouseholdStates:waiting_for_household_name",
        "HouseholdStates:waiting_for_rename",
        # Recurring states
        "RecurringForm:waiting_for_description",
        "RecurringForm:waiting_for_amount",
        "RecurringForm:waiting_for_category",
        "RecurringForm:waiting_for_day",
        "RecurringForm:waiting_for_edit_data",
        # Referral states (если есть)
        "ReferralStates:waiting_for_withdrawal_amount",
        # Category states
        "CategoryForm:waiting_for_name",
        "CategoryForm:waiting_for_icon",
        "CategoryForm:waiting_for_custom_icon",
        "CategoryForm:waiting_for_edit_choice",
        "CategoryForm:waiting_for_new_name",
        "CategoryForm:waiting_for_new_icon",
        # CategoryStates (второй класс для категорий)
        "CategoryStates:editing_name",
        # Edit expense states
        "EditExpenseForm:choosing_field",
        "EditExpenseForm:editing_amount",
        "EditExpenseForm:editing_description",
        "EditExpenseForm:editing_category",
        # Cashback states
        "CashbackForm:waiting_for_category",
        "CashbackForm:waiting_for_bank",
        "CashbackForm:waiting_for_percent",
        # Subscription states
        "PromoCodeStates:waiting_for_promo",
        # Settings states
        "SettingsStates:language",
        "SettingsStates:timezone",
        "SettingsStates:currency",
        # Top5 states (если есть)
        "Top5States:waiting_for_period",
        # Chat states
        "ChatStates:active_chat"
    ]

    # Если активно любое состояние редактирования или меню, которое должно быть закрыто при вводе траты
    states_to_clear_on_expense = [
        "EditExpenseForm:editing_category",
        "EditExpenseForm:choosing_field",
        "EditExpenseForm:editing_amount",
        "EditExpenseForm:editing_description",
        "PromoCodeStates:waiting_for_promo",
        "CategoryForm:waiting_for_name",
        "CategoryForm:waiting_for_icon",
        "CategoryStates:editing_name"
    ]

    if current_state and current_state in states_to_clear_on_expense:
        # Сначала получаем данные для удаления меню
        data = await state.get_data()
        last_menu_id = data.get('last_menu_message_id')

        # Сохраняем данные о кешбеке если есть
        cashback_menu_ids = data.get('cashback_menu_ids', [])
        persistent_cashback = data.get('persistent_cashback_menu', False)

        # Очищаем состояние
        await state.clear()

        # Восстанавливаем данные о кешбеке если нужно
        if persistent_cashback and cashback_menu_ids:
            await state.update_data(
                persistent_cashback_menu=True,
                cashback_menu_ids=cashback_menu_ids
            )

        # Пытаемся удалить последнее меню если это не меню кешбека
        if last_menu_id and last_menu_id not in cashback_menu_ids:
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=last_menu_id
                )
            except:
                pass

        logger.info(f"Cleared state {current_state} for user {message.from_user.id} on expense input")
        current_state = None  # Сбрасываем для продолжения обработки

    # Пропускаем обработку трат, если активно состояние другого роутера
    if current_state and current_state in skip_states:
        logger.info(f"Skipping expense handler due to active state: {current_state}")
        return

    # Если есть состояние из другого модуля (не ExpenseForm), очищаем его
    if current_state and current_state != "ExpenseForm:waiting_for_amount_clarification" and not current_state.startswith("ExpenseForm:"):
        logger.info(f"Auto-clearing foreign state '{current_state}' to process expense")
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
        # Продолжаем обработку траты

    # Используем переданный user_id или берём из message.from_user
    # (важно для callback'ов где message.from_user - это бот)
    if user_id is None and message.from_user:
        user_id = message.from_user.id

    if user_id is None:
        logger.error("Cannot determine user_id for expense processing")
        return

    # Проверяем принятие политики конфиденциальности
    from expenses.models import Profile
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        if not profile.accepted_privacy:
            logger.warning(f"User {user_id} tried to add expense without accepting privacy policy")
            # Отправляем сообщение с предложением принять политику
            from bot.constants import get_privacy_url_for
            privacy_url = get_privacy_url_for(lang)
            privacy_text = get_text('must_accept_privacy', lang) if lang == 'ru' else "You must accept the privacy policy to use the bot."
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=get_text('privacy_policy_header', lang),
                    url=privacy_url
                )
            ]])
            await message.answer(privacy_text, reply_markup=kb, parse_mode='HTML')
            return
    except Profile.DoesNotExist:
        logger.warning(f"Profile not found for user {user_id} when trying to add expense")
        # Профиль должен быть создан через /start, но если нет - отправляем к началу
        await message.answer(get_text('start_bot_first', lang) if get_text('start_bot_first', lang) else "Please start the bot with /start command first.")
        return
    
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
                except (TelegramForbiddenError, TelegramBadRequest):
                    break  # Пользователь заблокировал бота или некорректный chat_id
    
    # Запускаем задачу
    typing_task = asyncio.create_task(delayed_typing())
    
    # Функция для отмены индикатора печатания
    async def cancel_typing():
        nonlocal typing_cancelled
        typing_cancelled = True
        if typing_task and not typing_task.done():
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass
    
    # Если текст не передан явно, берем из сообщения
    if text is None:
        text = message.text
    
    # (перенесено вверх) Проверка на ввод кешбэка выполняется до проверки состояния

    # ВАЖНО: Сначала проверяем есть ли ключевые слова в тексте
    # Если есть - это точно трата, не нужно проверять намерения
    from expenses.models import CategoryKeyword
    from django.db.models import Q
    from ..utils.expense_intent import is_show_expenses_request
    import re

    # Извлекаем слова из текста (убираем числа и короткие слова)
    text_words = [w.lower() for w in re.findall(r'[а-яёa-z]+', text.lower()) if len(w) >= 3]

    has_keyword = False
    if text_words:
        # Проверяем есть ли какое-то из слов в сохраненных ключевых словах пользователя
        keyword_query = Q()
        for word in text_words:
            keyword_query |= Q(keyword__iexact=word)

        has_keyword = await CategoryKeyword.objects.filter(
            keyword_query,
            category__profile__telegram_id=user_id
        ).aexists()

        if has_keyword:
            logger.info(f"Found keyword in saved keywords for user {user_id}, treating as expense: '{text}'")

    # НОВОЕ: Проверка на запрос показа трат ДО вызова AI парсера (экономия токенов)
    # НО только если НЕ найдено ключевое слово
    if not has_keyword:
        is_show_request, confidence = is_show_expenses_request(text)
        if is_show_request and confidence >= 0.7:
            logger.info(f"Detected show expenses request: '{text}' (confidence: {confidence:.2f})")
            from ..routers.chat import process_chat_message
            # Сохраняем уже запущенный индикатор до отправки ответа
            await process_chat_message(message, state, text, skip_typing=True)
            # После ответа корректно останавливаем индикатор
            await cancel_typing()
            return
    
    # НОВОЕ: Проверка на бюджет перед проверкой дохода
    from ..utils.expense_parser import detect_budget_intent, detect_income_intent, parse_income_message
    data = await state.get_data()
    skip_budget_intent = data.get('skip_budget_intent', False)
    if skip_budget_intent:
        await state.update_data(skip_budget_intent=False)

    if not skip_budget_intent and detect_budget_intent(text) and not detect_income_intent(text):
        logger.info(f"Detected budget intent: '{text}'")

        # Извлекаем сумму из текста
        from ..utils.expense_parser import extract_amount_from_patterns
        amount, text_without_amount = extract_amount_from_patterns(text)

        if amount and amount > 0:
            # Отменяем индикатор печатания
            await cancel_typing()

            display_amount = format_decimal_amount(amount)
            # Конвертируем в строку без лишних нулей после точки
            amount_plain = str(amount)
            if '.' in amount_plain:
                amount_plain = amount_plain.rstrip('0').rstrip('.')

            # Формируем сообщение с предложением записать как доход
            if lang == 'en':
                budget_text = f"""💰 <b>Set budget or balance?</b>

It looks like you want to add <b>{display_amount}</b> to your balance.

Budget or balance is recorded as income with a "+" sign. Expenses will be deducted from income, and you will see the final balance in reports.

Record <b>+{display_amount}</b> as income?"""
                btn_yes = "✅ Yes, record as income"
                btn_no = "❌ No, it's an expense"
            else:
                budget_text = f"""💰 <b>Задать бюджет или баланс?</b>

Похоже, вы хотите добавить на баланс <b>{display_amount}</b>.

Бюджет или баланс записывается как доход со знаком "+". Расходы будут вычитаться из доходов, и вы увидите итоговый баланс в отчётах.

Записать <b>+{display_amount}</b> как доход?"""
                btn_yes = "✅ Да, записать как доход"
                btn_no = "❌ Нет, это трата"

            # Создаем кнопки подтверждения
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=btn_no, callback_data=f"budget_decline:{amount_plain}"),
                    InlineKeyboardButton(text=btn_yes, callback_data=f"budget_confirm:{amount_plain}")
                ]
            ])

            # Сохраняем оригинальный текст в состояние для обработки в callback
            # Конвертируем Decimal в str для JSON-сериализации в Redis
            await state.update_data(budget_original_text=text, budget_amount=str(amount))

            await message.answer(budget_text, reply_markup=keyboard, parse_mode="HTML")
            return
        else:
            # Если не удалось извлечь сумму, продолжаем обычную обработку
            logger.warning(f"Budget intent detected but no amount found: '{text}'")

    # НОВОЕ: Проверка на доход перед парсингом как расход
    if detect_income_intent(text):
        logger.info(f"Detected income intent: '{text}'")

        # Проверка подписки для функции учета доходов
        has_subscription = await check_subscription(user_id)
        if not has_subscription:
            # Отменяем индикатор печатания
            await cancel_typing()

            # Формируем сообщение о необходимости подписки
            subscription_msg = f"""❌ <b>Учет доходов — премиум функция</b>

💰 Функция учета доходов доступна только по подписке.

С подпиской вы получите:
• 📊 Полный учет доходов и расходов
• 🎤 Голосовой ввод трат
• 📄 PDF отчеты
• 👨‍👩‍👧‍👦 Семейный бюджет
• 💳 Кешбэк менеджер
• 📈 Расширенная аналитика

Оформите подписку, чтобы вести полноценный учет финансов!"""

            # Создаем кнопку для оформления подписки
            from ..keyboards.subscription import get_subscription_button
            keyboard = get_subscription_button()

            await message.answer(subscription_msg, reply_markup=keyboard, parse_mode="HTML")
            return

        # Обрабатываем как доход
        from expenses.models import Profile
        try:
            profile = await Profile.objects.aget(telegram_id=user_id)
        except Profile.DoesNotExist:
            profile = await Profile.objects.acreate(telegram_id=user_id)
            try:
                await create_default_income_categories(user_id)
            except Exception as e:
                logger.debug(f"Failed to create default income categories: {e}")

        # Парсим доход
        parsed_income = await parse_income_message(text, user_id=user_id, profile=profile, use_ai=True)
        
        if parsed_income:
            # Создаем доход
            from ..services.income import create_income
            from expenses.models import IncomeCategory
            
            # Получаем или создаем категорию дохода
            category = None
            category_key = parsed_income.get('category_key') or normalize_income_category_key(parsed_income.get('category'))
            candidate_names = set()

            if parsed_income.get('category'):
                candidate_names.add(parsed_income['category'])
                candidate_names.add(strip_leading_emoji(parsed_income['category']))

            if category_key:
                for lang_code_candidate in ('ru', 'en'):
                    display_name = get_income_category_display_for_key(category_key, lang_code_candidate)
                    candidate_names.add(display_name)
                    candidate_names.add(strip_leading_emoji(display_name))

            candidate_names = {name for name in candidate_names if name}

            if candidate_names:
                from django.db.models import Q
                query = Q()
                for name in candidate_names:
                    query |= Q(name__iexact=name) | Q(name_ru__iexact=name) | Q(name_en__iexact=name)

                try:
                    category = await IncomeCategory.objects.filter(
                        profile=profile,
                        is_active=True
                    ).filter(query).afirst()
                except (DatabaseError, AttributeError) as e:
                    logger.debug(f"Error matching income category by normalized name: {e}")
                    category = None

            if not category:
                try:
                    default_names = [
                        get_income_category_display_for_key('other', 'ru'),
                        get_income_category_display_for_key('other', 'en'),
                        '💰 Прочие доходы',
                    ]
                    category = await IncomeCategory.objects.filter(
                        profile=profile,
                        is_active=True
                    ).filter(name__in=default_names).afirst()
                except (DatabaseError, AttributeError) as e:
                    logger.debug(f"Error finding default income category: {e}")
                    category = None
            
            # Создаем доход
            try:
                income = await create_income(
                    user_id=user_id,
                    amount=parsed_income['amount'],
                    category_id=category.id if category else None,
                    description=parsed_income.get('description', get_text('income', lang)),
                    income_date=parsed_income.get('income_date'),
                    income_type=parsed_income.get('income_type', 'other'),
                    ai_categorized=parsed_income.get('ai_enhanced', False),
                    ai_confidence=parsed_income.get('confidence', 0.5),
                    currency=parsed_income.get('currency', 'RUB')
                )
            except ValueError as e:
                # Обработка ошибок валидации даты
                await message.answer(f"❌ {str(e)}", parse_mode="HTML")
                return
            
            if income:
                await cancel_typing()  # Отменяем индикатор печатания
                
                # Используем единую функцию форматирования
                from ..utils.expense_messages import format_income_added_message
                text_msg = await format_income_added_message(
                    income=income,
                    category=category,
                    similar_income=parsed_income.get('similar_income', False),
                    lang=lang
                )
                
                # Добавляем кнопки редактирования
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_income_{income.id}")
                    ]
                ])

                # Отправляем подтверждение (сообщение о доходе не должно исчезать)
                # send_message_with_cleanup сама удалит старое меню после отправки нового
                await send_message_with_cleanup(
                    message=message,
                    state=state,
                    text=text_msg,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    keep_message=True  # Не удалять это сообщение при следующих действиях
                )
                
                logger.info(f"Income created: {income.id} for user {user_id}")
                return
            else:
                # Если не удалось создать доход (ошибка в БД или другие проблемы)
                await cancel_typing()
                logger.error(f"Failed to create income for user {user_id}: create_income returned None")
                await message.answer(
                    "❌ Не удалось добавить доход. Попробуйте позже.",
                    parse_mode="HTML"
                )
                return
        else:
            # Если не удалось распарсить как доход, продолжаем как расход
            logger.warning(f"Failed to parse as income despite intent: '{text}'")
    
    # Парсим сообщение с AI поддержкой (как расход)
    from expenses.models import Profile
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    logger.info(f"Starting parse_expense_message for text: '{text}', user_id: {user_id}")
    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    # Убираем эмодзи из логов для Windows
    if parsed:
        safe_parsed = {k: v.encode('ascii', 'ignore').decode('ascii') if isinstance(v, str) else v 
                       for k, v in parsed.items()}
        logger.info(f"Parsing completed, result: {safe_parsed}")
    else:
        logger.info("Parsing completed, result: None")
    
    if not parsed:
        # Проверяем, не указана ли явно нулевая сумма (например "кофе 0")
        import re
        zero_amount_pattern = re.compile(r'\b0+(?:[.,]0+)?\s*(?:руб|р|rub|₽)?$', re.IGNORECASE)
        if zero_amount_pattern.search(text.strip()):
            await cancel_typing()
            error_msg = get_text('amount_must_be_positive', lang) if lang != 'ru' else "❌ Сумма должна быть больше нуля"
            await message.answer(error_msg, parse_mode="HTML")
            return

        # Повторная проверка с использованием единого модуля (на случай если AI парсер не сработал)
        # НО если мы нашли ключевое слово - не проверяем намерение снова
        if not has_keyword:
            is_show_request, show_confidence = is_show_expenses_request(text)
        else:
            is_show_request, show_confidence = False, 0.0
            logger.info(f"Skipping intent check because keyword was found for: '{text}'")

        if is_show_request and show_confidence >= 0.6:
            logger.info(f"Show expenses request detected after parsing failed: '{text}'")
            from ..routers.chat import process_chat_message
            # Сохраняем typing до отправки ответа
            await process_chat_message(message, state, text, skip_typing=True)
            await cancel_typing()
            return
        
        # Используем улучшенный классификатор для определения типа сообщения
        from ..utils.text_classifier import classify_message, get_expense_indicators
        
        message_type, confidence = classify_message(text)
        
        # Логируем для отладки
        if confidence > 0.5:
            indicators = get_expense_indicators(text)
            logger.info(f"Classified '{text}' as {message_type} (confidence: {confidence:.2f}), indicators: {indicators}")
        
        # Если классификатор определил это как чат - направляем в чат
        if message_type == 'chat':
            logger.info(f"Message classified as chat, redirecting: '{text}'")
            from ..routers.chat import process_chat_message
            # Сохраняем typing до отправки ответа
            await process_chat_message(message, state, text, skip_typing=True)
            await cancel_typing()
            return
        
        # Иначе это трата (message_type == 'record')
        might_be_expense = True
        logger.info(f"Message classified as expense record, searching for similar expenses: '{text}'")

        if might_be_expense and len(text) > 2:  # Минимальная длина для осмысленного описания
            # Сначала ищем похожие траты за последний год
            from ..services.expense import find_similar_expenses
            from datetime import datetime

            logger.info(f"Calling find_similar_expenses for: '{text}'")
            similar = await find_similar_expenses(user_id, text)
            logger.info(f"Found {len(similar) if similar else 0} similar expenses")
            
            # Также проверяем похожие доходы
            from ..services.income import get_last_income_by_description, create_income
            similar_income = await get_last_income_by_description(user_id, text)
            
            if similar or similar_income:
                # Определяем, что использовать - расход или доход
                if similar and not similar_income:
                    # Только похожие расходы
                    last_expense = similar[0]  # Берем самую частую/последнюю
                    amount = last_expense['amount']
                    currency = last_expense['currency']
                    category_name = last_expense['category']
                    
                    # Создаем или получаем категорию
                    category = await get_or_create_category(user_id, category_name)
                elif similar_income and not similar:
                    # Только похожий доход - создаем доход вместо расхода
                    amount = similar_income.amount
                    currency = similar_income.currency or 'RUB'
                    category = similar_income.category
                    
                    # Делаем первую букву заглавной
                    description_capitalized = text[0].upper() + text[1:] if text else text
                    
                    # Создаем доход
                    try:
                        income = await create_income(
                            user_id=user_id,
                            amount=amount,
                            category_id=category.id if category else None,
                            description=description_capitalized,
                            currency=currency
                        )
                    except ValueError as e:
                        # Обработка ошибок валидации даты
                        await message.answer(f"❌ {str(e)}", parse_mode="HTML")
                        return
                    
                    if income:
                        await cancel_typing()

                        # Используем единую функцию форматирования для дохода
                        from ..utils.expense_messages import format_income_added_message
                        text_msg = await format_income_added_message(
                            income=income,
                            category=category,
                            similar_income=True,
                            lang=lang
                        )

                        # Добавляем кнопки редактирования
                        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [
                                InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_income_{income.id}")
                            ]
                        ])

                        # Отправляем подтверждение
                        # send_message_with_cleanup сама удалит старое меню после отправки нового
                        await send_message_with_cleanup(
                            message=message,
                            state=state,
                            text=text_msg,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            keep_message=True
                        )
                    else:
                        # Если не удалось создать доход (ошибка в БД или другие проблемы)
                        await cancel_typing()
                        logger.error(f"Failed to create income for user {user_id}: create_income returned None")
                        await message.answer(
                            "❌ Не удалось добавить доход. Попробуйте позже.",
                            parse_mode="HTML"
                        )
                    return
                else:
                    # Есть и расходы и доходы - используем более свежую запись
                    from datetime import datetime
                    
                    # Получаем дату последнего расхода
                    expense_date = similar[0].get('date') if similar else None
                    # Дата последнего дохода
                    income_date = similar_income.income_date if similar_income else None
                    
                    # Сравниваем даты и выбираем более свежую
                    use_income = False
                    if expense_date and income_date:
                        use_income = income_date > expense_date
                    elif income_date and not expense_date:
                        use_income = True
                    
                    if use_income:
                        # Используем доход
                        amount = similar_income.amount
                        currency = similar_income.currency or 'RUB'
                        category = similar_income.category
                        
                        # Делаем первую букву заглавной
                        description_capitalized = text[0].upper() + text[1:] if text else text
                        
                        # Создаем доход
                        try:
                            income = await create_income(
                                user_id=user_id,
                                amount=amount,
                                category_id=category.id if category else None,
                                description=description_capitalized,
                                currency=currency
                            )
                        except ValueError as e:
                            # Обработка ошибок валидации даты
                            await message.answer(f"❌ {str(e)}", parse_mode="HTML")
                            return
                        
                        if income:
                            await cancel_typing()

                            # Используем единую функцию форматирования для дохода
                            from ..utils.expense_messages import format_income_added_message
                            text_msg = await format_income_added_message(
                                income=income,
                                category=category,
                                similar_income=True,
                                lang=lang
                            )

                            # Добавляем кнопки редактирования
                            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [
                                    InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_income_{income.id}")
                                ]
                            ])

                            # Отправляем подтверждение
                            # send_message_with_cleanup сама удалит старое меню после отправки нового
                            await send_message_with_cleanup(
                                message=message,
                                state=state,
                                text=text_msg,
                                reply_markup=keyboard,
                                parse_mode="HTML",
                                keep_message=True
                            )
                        else:
                            # Если не удалось создать доход (ошибка в БД или другие проблемы)
                            await cancel_typing()
                            logger.error(f"Failed to create income for user {user_id}: create_income returned None")
                            await message.answer(
                                "❌ Не удалось добавить доход. Попробуйте позже.",
                                parse_mode="HTML"
                            )
                        return
                    else:
                        # Используем расход
                        last_expense = similar[0]
                        amount = last_expense['amount']
                        currency = last_expense['currency']
                        category_name = last_expense['category']

                        # Создаем или получаем категорию
                        category = await get_or_create_category(user_id, category_name)

                # Делаем первую букву заглавной
                description_capitalized = text[0].upper() + text[1:] if text else text
                
                # Сохраняем трату
                try:
                    expense = await add_expense(
                        user_id=user_id,
                        category_id=category.id,
                        amount=amount,
                        description=description_capitalized,
                        currency=currency,
                        expense_date=parsed.get('expense_date') if parsed else None,  # Добавляем дату, если она была указана
                        ai_categorized=parsed.get('ai_enhanced', False) if parsed else False,
                        ai_confidence=parsed.get('confidence') if parsed else None
                    )
                except ValueError as e:
                    # Обработка ошибок валидации даты
                    await message.answer(f"❌ {str(e)}", parse_mode="HTML")
                    return
                
                # Форматируем сообщение с учетом валюты
                amount_text = format_currency(expense.amount, currency)
                
                # Проверяем подписку и рассчитываем кешбэк
                cashback_text = ""
                has_subscription = await check_subscription(user_id)
                # Получаем валюту пользователя из профиля
                user_currency = profile.currency if profile else 'RUB'
                # Кешбэк начисляется только для трат в валюте пользователя
                if has_subscription and currency == user_currency:
                    current_month = datetime.now().month
                    cashback = await calculate_expense_cashback(
                        user_id=user_id,
                        category_id=category.id,
                        amount=expense.amount,
                        month=current_month
                    )
                    if cashback > 0:
                        cashback_text = f" (+{cashback:.0f} ₽)"
                        # Сохраняем кешбек в базе данных
                        expense.cashback_amount = Decimal(str(cashback))
                        await expense.asave()
                
                # Формируем сообщение с информацией о потраченном за день
                message_text = await format_expense_added_message(
                    expense=expense,
                    category=category,
                    cashback_text=cashback_text,
                    similar_expense=True,
                    lang=lang
                )

                # Отправляем подтверждение (сообщение о трате не должно исчезать)
                await cancel_typing()
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                # send_message_with_cleanup сама удалит старое меню после отправки нового
                await send_message_with_cleanup(message, state,
                    message_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_expense_{expense.id}")
                        ]
                    ]),
                    parse_mode="HTML",
                    keep_message=True  # Не удалять это сообщение при следующих действиях
                )
            else:
                # Если похожих трат нет, используем обычный двухшаговый ввод
                logger.info(f"No similar expenses found, asking for amount: '{text}'")
                await state.update_data(expense_description=text)
                await state.set_state(ExpenseForm.waiting_for_amount_clarification)
                
                # Язык пользователя берём из middleware или используем русский по умолчанию
                stored_lang = None
                try:
                    stored_lang = await get_user_language(message.from_user.id)
                except Exception:
                    stored_lang = None
                user_lang = stored_lang or lang or getattr(message, 'user_language', 'ru') or 'ru'
                
                await cancel_typing()
                
                # Создаем inline клавиатуру с кнопкой отмены
                cancel_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=get_text('cancel', user_lang), callback_data="cancel_expense_input")]
                ])
                
                sent_message = await message.answer(
                    get_text('want_to_add_expense', user_lang).format(text=text),
                    reply_markup=cancel_keyboard
                )
                
                # Сохраняем ID сообщения для возможного удаления
                await state.update_data(clarification_message_id=sent_message.message_id)
            return
        
        # Не похоже на трату - обрабатываем как чат
        logger.info(f"Expense parser returned None for text: '{text}', processing as chat")
        # Сохраняем typing до отправки ответа в чат
        await process_chat_message(message, state, text, skip_typing=True)
        await cancel_typing()
        return
    
    # Проверяем, использовались ли данные из предыдущей траты
    reused_from_last = parsed.get('reused_from_last', False)
    
    # Проверяем/создаем категорию
    category = await get_or_create_category(user_id, parsed['category'])
    
    # Сохраняем в оригинальной валюте
    amount = parsed['amount']
    currency = parsed.get('currency', 'RUB')
    
    # Добавляем трату в оригинальной валюте
    try:
        expense = await add_expense(
            user_id=user_id,
            category_id=category.id,
            amount=amount,
            description=parsed['description'],
            currency=currency,
            expense_date=parsed.get('expense_date'),  # Добавляем дату, если она была указана
            ai_categorized=parsed.get('ai_enhanced', False),
            ai_confidence=parsed.get('confidence')
        )
    except ValueError as e:
        # Обработка ошибок валидации даты
        await message.answer(f"❌ {str(e)}", parse_mode="HTML")
        return

    # Проверяем что трата успешно создана
    if expense is None:
        logger.error(f"Failed to create expense for user {user_id}: add_expense returned None")
        await message.answer("❌ Не удалось сохранить трату. Попробуйте позже.", parse_mode="HTML")
        return

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
    # Получаем валюту пользователя из профиля
    user_currency = profile.currency if profile else 'RUB'
    # Кешбэк начисляется только для трат в валюте пользователя
    if has_subscription and currency == user_currency:
        current_month = datetime.now().month
        cashback = await calculate_expense_cashback(
            user_id=user_id,
            category_id=category.id,
            amount=expense.amount,
            month=current_month
        )
        if cashback > 0:
            cashback_text = f" (+{cashback:.0f} ₽)"
            # Сохраняем кешбек в базе данных
            expense.cashback_amount = Decimal(str(cashback))
            await expense.asave()
    
    # Формируем сообщение с информацией о потраченном за день
    message_text = await format_expense_added_message(
        expense=expense,
        category=category,
        cashback_text=cashback_text,
        confidence_text=confidence_text,
        reused_from_last=reused_from_last,
        lang=lang
    )
    
    await cancel_typing()

    # Отправляем сообщение о трате
    # send_message_with_cleanup сама удалит старое меню после отправки нового
    await send_message_with_cleanup(message, state,
        message_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_expense_{expense.id}")
            ]
        ]),
        parse_mode="HTML",
        keep_message=True  # Не удалять это сообщение при следующих действиях
    )

    # Гарантируем отмену задачи
    await cancel_typing()
    
    # # Восстанавливаем меню кешбека если оно было активно
    # from ..routers.cashback import restore_cashback_menu_if_needed
    # await restore_cashback_menu_if_needed(state, message.bot, message.chat.id)


# Обработчик голосовых сообщений
@router.message(F.voice)
@rate_limit(max_calls=10, period=60)  # 10 голосовых в минуту
async def handle_voice_expense(message: types.Message, state: FSMContext, lang: str = 'ru'):
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
    
    # Получаем язык пользователя из middleware/настроек
    stored_lang = None
    try:
        stored_lang = await get_user_language(message.from_user.id)
    except Exception:
        stored_lang = None

    user_language = stored_lang or lang or getattr(message, 'user_language', 'ru') or 'ru'
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

    logger.info(f"[VOICE_EXPENSE] User {message.from_user.id} | Voice recognized successfully | Processing text: {text[:100]}")

    # Вызываем обработчик текстовых сообщений напрямую с распознанным текстом
    # Как это сделано в nutrition_bot
    await handle_text_expense(message, state, text=text, lang=user_language)


# Обработчик фото (чеков)
@router.message(F.photo)
@rate_limit(max_calls=10, period=60)  # 10 фото в минуту
async def handle_photo_expense(message: types.Message, state: FSMContext):
    """Обработка фото чеков"""
    await send_message_with_cleanup(message, state, "📸 Обработка чеков будет добавлена в следующей версии.")


# Обработчик аудио-файлов (не голосовых сообщений)
@router.message(F.audio)
async def handle_audio_unsupported(message: types.Message, state: FSMContext):
    """
    Обработка аудио-файлов.
    Бот поддерживает только голосовые сообщения (voice), не аудио-файлы.
    """
    if not message.from_user:
        return
    user_id = message.from_user.id
    from bot.utils.language import get_user_language
    lang = await get_user_language(user_id)

    if lang == 'ru':
        text = (
            "🎵 Аудио-файлы не поддерживаются.\n\n"
            "Для записи трат используйте:\n"
            "• 🎤 Голосовое сообщение (зажмите микрофон)\n"
            "• ⌨️ Текстовое сообщение"
        )
    else:
        text = (
            "🎵 Audio files are not supported.\n\n"
            "To record expenses, use:\n"
            "• 🎤 Voice message (hold the microphone button)\n"
            "• ⌨️ Text message"
        )

    await send_message_with_cleanup(message, state, text)


# Обработчик видео-заметок (кружочков)
@router.message(F.video_note)
async def handle_video_note_unsupported(message: types.Message, state: FSMContext):
    """
    Обработка видео-заметок (кружочков).
    Бот поддерживает только голосовые сообщения (voice), не видео.
    """
    if not message.from_user:
        return
    user_id = message.from_user.id
    from bot.utils.language import get_user_language
    lang = await get_user_language(user_id)

    if lang == 'ru':
        text = (
            "🎥 Видео-заметки не поддерживаются.\n\n"
            "Для записи трат используйте:\n"
            "• 🎤 Голосовое сообщение (зажмите микрофон)\n"
            "• ⌨️ Текстовое сообщение"
        )
    else:
        text = (
            "🎥 Video notes are not supported.\n\n"
            "To record expenses, use:\n"
            "• 🎤 Voice message (hold the microphone button)\n"
            "• ⌨️ Text message"
        )

    await send_message_with_cleanup(message, state, text)


# Обработчик редактирования траты или дохода
def _parse_edit_target(callback_data: str) -> tuple[int | None, str | None]:
    """
    Извлекает ID и тип (income/expense) из callback_data вида
    edit_field_amount_expense_123 или edit_done_income_123.
    """
    parts = callback_data.split("_")
    if len(parts) < 3:
        return None, None
    try:
        item_id = int(parts[-1])
    except ValueError:
        return None, None
    item_type = parts[-2] if parts[-2] in {"income", "expense"} else None
    return item_id, item_type


@router.callback_query(lambda c: c.data.startswith(("edit_expense_", "edit_income_")))
async def edit_expense(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование траты или дохода"""
    # Определяем тип операции
    is_income = callback.data.startswith("edit_income_")
    item_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    # Получаем язык пользователя
    from bot.utils.language import get_user_language
    lang = await get_user_language(user_id)

    # Получаем информацию о трате или доходе
    if is_income:
        from expenses.models import Income
        try:
            expense = await Income.objects.select_related('category').aget(
                id=item_id,
                profile__telegram_id=user_id
            )
        except Income.DoesNotExist:
            await callback.answer(get_text('income_not_found', lang), show_alert=True)
            from bot.utils.state_utils import clear_state_keep_cashback
            await clear_state_keep_cashback(state)
            return
    else:
        from expenses.models import Expense
        try:
            expense = await Expense.objects.select_related('category').aget(
                id=item_id,
                profile__telegram_id=user_id
            )
        except Expense.DoesNotExist:
            await callback.answer(get_text('expense_not_found', lang), show_alert=True)
            from bot.utils.state_utils import clear_state_keep_cashback
            await clear_state_keep_cashback(state)
            return
    
    # Сохраняем ID и тип в состоянии
    await state.update_data(
        editing_expense_id=item_id,
        editing_type='income' if is_income else 'expense'
    )
    
    # Проверяем, есть ли кешбек (только для расходов)
    from bot.services.cashback import calculate_expense_cashback
    from datetime import datetime
    from expenses.models import Profile

    has_cashback = False
    if not is_income and not expense.cashback_excluded:  # Только для расходов
        # Получаем валюту пользователя
        try:
            profile = await Profile.objects.aget(telegram_id=user_id)
            user_currency = profile.currency if profile else 'RUB'
        except Profile.DoesNotExist:
            user_currency = 'RUB'

        # Кешбек начисляется только для трат в валюте пользователя
        expense_currency = expense.currency if hasattr(expense, 'currency') else 'RUB'
        if expense_currency == user_currency:
            current_month = datetime.now().month
            cashback = await calculate_expense_cashback(
                user_id=user_id,
                category_id=expense.category.id if expense.category else None,
                amount=float(expense.amount),
                month=current_month
            )
            has_cashback = cashback > 0
    
    # Показываем меню выбора поля для редактирования
    translated_category = get_category_display_name(expense.category, lang) if expense.category else (get_text('other_income', lang) if is_income else get_text('no_category', lang))
    
    # Получаем правильное поле для суммы и описания
    amount = expense.amount
    description = expense.description
    currency = expense.currency if hasattr(expense, 'currency') else '₽'
    
    edit_prefix = "income" if is_income else "expense"
    buttons = [
        [
            InlineKeyboardButton(
                text=f"💰 {get_text('sum', lang)}: {amount:.0f} {currency}",
                callback_data=f"edit_field_amount_{edit_prefix}_{item_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📝 {get_text('description', lang)}: {description}",
                callback_data=f"edit_field_description_{edit_prefix}_{item_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📁 {get_text('category', lang)}: {translated_category}",
                callback_data=f"edit_field_category_{edit_prefix}_{item_id}"
            )
        ],
    ]
    
    # Добавляем кнопку удаления кешбека только для расходов
    if not is_income and has_cashback and not expense.cashback_excluded:
        buttons.append([InlineKeyboardButton(text="💸 Убрать кешбек", callback_data=f"remove_cashback_{item_id}")])
    
    # Для удаления используем правильный префикс
    delete_callback = f"delete_income_{item_id}" if is_income else f"delete_expense_{item_id}"
    buttons.extend([
        [InlineKeyboardButton(text=get_text('delete_button', lang), callback_data=delete_callback)],
        [
            InlineKeyboardButton(
                text=f"✅ {get_text('edit_done', lang)}",
                callback_data=f"edit_done_{edit_prefix}_{item_id}"
            )
        ]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Меняем заголовок в зависимости от типа
    title = get_text('editing_income', lang) if is_income else get_text('editing_expense', lang)
    await callback.message.edit_text(
        f"✏️ <b>{title}</b>\n\n"
        f"{get_text('choose_field_to_edit', lang)}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(EditExpenseForm.choosing_field)
    await callback.answer()


# Обработчик удаления траты
@router.callback_query(lambda c: c.data.startswith("remove_cashback_"))
async def remove_cashback(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Удаление кешбека из траты"""
    expense_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    from expenses.models import Expense
    from bot.services.cashback import calculate_expense_cashback
    from datetime import datetime
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    try:
        # Получаем трату с profile для корректной работы format_expense_added_message
        expense = await Expense.objects.select_related('category', 'profile').aget(
            id=expense_id,
            profile__telegram_id=user_id
        )
        
        # Устанавливаем флаг исключения кешбека
        expense.cashback_excluded = True
        await expense.asave()
        
        # Без уведомления - сразу показываем обновленную трату
        # Используем единый формат сообщения
        from ..utils.expense_messages import format_expense_added_message
        
        # Кешбек не показываем, так как он исключен
        message_text = await format_expense_added_message(
            expense=expense,
            category=expense.category,
            cashback_text="",  # Пустой текст кешбека
            lang=lang
        )
        
        # Показываем обновленную трату с кнопкой редактирования
        await callback.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=f"edit_expense_{expense.id}")
                ]
            ]),
            parse_mode="HTML"
        )
        
        # Очищаем состояние редактирования
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
        
        # Отвечаем на callback без уведомления
        await callback.answer()
        
    except Expense.DoesNotExist:
        await callback.answer("❌ Трата не найдена", show_alert=True)
    except Exception as e:
        logger.error(f"Error removing cashback: {e}")
        await callback.answer("❌ Ошибка при удалении кешбека", show_alert=True)


@router.callback_query(lambda c: c.data.startswith(("delete_expense_", "delete_income_")))
async def delete_expense(callback: types.CallbackQuery, state: FSMContext):
    """Удаление траты или дохода"""
    # Определяем тип операции
    is_income = callback.data.startswith("delete_income_")
    item_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    # Получаем язык пользователя
    from bot.utils.language import get_user_language, get_text
    lang = await get_user_language(user_id)

    # Удаляем трату или доход
    if is_income:
        from ..services.income import delete_income
        success = await delete_income(user_id, item_id)
    else:
        from ..services.expense import delete_expense as delete_expense_service
        success = await delete_expense_service(user_id, item_id)

    if success:
        # Заменяем сообщение на уведомление об удалении (единообразное поведение для всех сообщений)
        deleted_msg_key = 'income_deleted_message' if is_income else 'expense_deleted_message'
        deleted_msg = get_text(deleted_msg_key, lang)
        try:
            await callback.message.edit_text(deleted_msg, reply_markup=None)
        except Exception as e:
            # Если не можем отредактировать, логируем для диагностики
            logger.warning(f"Could not edit message after delete: {e}")

        # Очищаем состояние после удаления
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)

        # Отправляем уведомление пользователю (popup сверху экрана)
        success_key = 'income_deleted_success' if is_income else 'expense_deleted_success'
        success_msg = get_text(success_key, lang)
        await callback.answer(success_msg)

        # # Восстанавливаем меню кешбека если оно было активно
        # from ..routers.cashback import restore_cashback_menu_if_needed
        # await restore_cashback_menu_if_needed(state, callback.bot, callback.message.chat.id)
    else:
        error_key = 'failed_delete_income' if is_income else 'failed_delete_expense'
        error_msg = get_text(error_key, lang)
        await callback.answer(error_msg, show_alert=True)


# Обработчики выбора поля для редактирования
@router.callback_query(lambda c: c.data.startswith("edit_field_amount"))
async def edit_field_amount(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование суммы"""
    expense_id, item_type = _parse_edit_target(callback.data)
    data = await state.get_data()

    if expense_id is None:
        expense_id = data.get('editing_expense_id')
    if item_type is None:
        item_type = data.get('editing_type')

    if expense_id is None:
        logger.warning(f"[edit_field_amount] Missing expense id for user {callback.from_user.id} (callback: {callback.data})")
        await callback.answer(
            "❌ Сессия редактирования истекла. Попробуйте начать заново.",
            show_alert=True
        )
        await state.clear()
        return

    await state.update_data(
        editing_expense_id=expense_id,
        editing_type=item_type or data.get('editing_type'),
        lang=lang,
    )

    edit_prefix = 'income' if (item_type or data.get('editing_type')) == 'income' else 'expense'

    await callback.message.edit_text(
        f"💰 <b>{get_text('editing_amount', lang)}</b>\n\n"
        f"{get_text('enter_new_amount', lang)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_back_{edit_prefix}_{expense_id}")]
        ])
    )
    # Сохраняем ID сообщения для последующего удаления
    await state.update_data(editing_prompt_message_id=callback.message.message_id)
    await state.set_state(EditExpenseForm.editing_amount)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_field_description"))
async def edit_field_description(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование описания"""
    expense_id, item_type = _parse_edit_target(callback.data)
    data = await state.get_data()

    if expense_id is None:
        expense_id = data.get('editing_expense_id')
    if item_type is None:
        item_type = data.get('editing_type')

    if expense_id is None:
        logger.warning(f"[edit_field_description] Missing expense id for user {callback.from_user.id} (callback: {callback.data})")
        await callback.answer(
            "❌ Сессия редактирования истекла. Попробуйте начать заново.",
            show_alert=True
        )
        await state.clear()
        return

    await state.update_data(
        editing_expense_id=expense_id,
        editing_type=item_type or data.get('editing_type'),
        lang=lang,
    )

    edit_prefix = 'income' if (item_type or data.get('editing_type')) == 'income' else 'expense'

    await callback.message.edit_text(
        f"📝 <b>{get_text('editing_description', lang)}</b>\n\n"
        f"{get_text('enter_new_description', lang)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_back_{edit_prefix}_{expense_id}")]
        ])
    )
    # Сохраняем ID сообщения для последующего удаления
    await state.update_data(editing_prompt_message_id=callback.message.message_id)
    await state.set_state(EditExpenseForm.editing_description)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_field_category"))
async def edit_field_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Редактирование категории"""
    user_id = callback.from_user.id
    expense_id, item_type = _parse_edit_target(callback.data)
    data = await state.get_data()
    is_income = (item_type or data.get('editing_type')) == 'income'
    edit_prefix = 'income' if is_income else 'expense'
    if expense_id is None:
        expense_id = data.get('editing_expense_id')

    if expense_id is None:
        logger.warning(f"[edit_field_category] Missing expense id for user {callback.from_user.id} (callback: {callback.data})")
        await callback.answer(
            "❌ Сессия редактирования истекла. Попробуйте начать заново.",
            show_alert=True
        )
        await state.clear()
        return

    await state.update_data(
        editing_expense_id=expense_id,
        editing_type=item_type or data.get('editing_type'),
        lang=lang,
    )
    
    # Получаем соответствующие категории
    if is_income:
        from ..services.income import get_user_income_categories
        categories = await get_user_income_categories(user_id)
        no_categories_msg = "У вас нет категорий доходов."
    else:
        from ..services.category import get_user_categories
        categories = await get_user_categories(user_id)
        no_categories_msg = "У вас нет категорий. Создайте их через /categories"
    
    if not categories:
        await callback.answer(no_categories_msg, show_alert=True)
        return
    
    keyboard_buttons = []
    # Группируем категории по 2 в строке
    for i in range(0, len(categories), 2):
        translated_name = get_category_display_name(categories[i], lang)
        row = [InlineKeyboardButton(
            text=f"{translated_name}", 
            callback_data=f"expense_cat_{categories[i].id}"
        )]
        if i + 1 < len(categories):
            translated_name_2 = get_category_display_name(categories[i + 1], lang)
            row.append(InlineKeyboardButton(
                text=f"{translated_name_2}", 
                callback_data=f"expense_cat_{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_cancel_{edit_prefix}_{expense_id}")])
    
    await callback.message.edit_text(
        f"📁 <b>Выберите новую категорию</b>:\n\n"
        f"<i>Бот запомнит ваш выбор для похожих трат</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )
    await state.set_state(EditExpenseForm.editing_category)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cancel"))
async def edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования категории"""
    data = await state.get_data()
    expense_id, item_type = _parse_edit_target(callback.data)

    if expense_id is None:
        expense_id = data.get('editing_expense_id')
    if item_type is None:
        item_type = data.get('editing_type')

    if expense_id:
        # Возвращаемся к меню редактирования траты/дохода
        lang = data.get('lang', 'ru')
        await show_edit_menu_callback(callback, state, expense_id, lang, item_type=item_type)
    else:
        # Если это было управление категориями, просто удаляем сообщение
        await callback.message.delete()
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_back_"))
async def edit_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к меню редактирования траты"""
    expense_id, item_type = _parse_edit_target(callback.data)

    if expense_id is None:
        await callback.answer("❌ Ошибка: ID траты не найден")
        return

    data = await state.get_data()
    lang = data.get('lang', 'ru')
    await show_edit_menu_callback(callback, state, expense_id, lang, item_type=item_type)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_done"))
async def edit_done(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Завершение редактирования"""
    data = await state.get_data()
    item_id, item_type = _parse_edit_target(callback.data)

    if item_id is None:
        item_id = data.get('editing_expense_id')
    if item_type is None:
        item_type = data.get('editing_type')

    if item_id is None:
        logger.warning(f"[edit_done] Missing expense id for user {callback.from_user.id} (callback: {callback.data})")
        await callback.answer(
            "❌ Сессия редактирования истекла. Попробуйте начать заново.",
            show_alert=True
        )
        await state.clear()
        return

    is_income = item_type == 'income'

    await state.update_data(
        editing_expense_id=item_id,
        editing_type=item_type or data.get('editing_type'),
        lang=lang,
    )
    
    # Получаем обновленный объект
    try:
        if is_income:
            from expenses.models import Income
            expense = await Income.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=callback.from_user.id
            )
        else:
            from expenses.models import Expense
            expense = await Expense.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=callback.from_user.id
            )
        
        # Рассчитываем кешбек только для расходов
        cashback_text = ""
        if not is_income:
            has_subscription = await check_subscription(callback.from_user.id)
            if has_subscription and expense.category and not expense.cashback_excluded:
                # Получаем валюту пользователя из профиля
                user_currency = expense.profile.currency if expense.profile else 'RUB'
                # Кешбек начисляется только для трат в валюте пользователя
                expense_currency = expense.currency if hasattr(expense, 'currency') else 'RUB'
                if expense_currency == user_currency:
                    current_month = datetime.now().month
                    cashback = await calculate_expense_cashback(
                        user_id=callback.from_user.id,
                        category_id=expense.category.id,
                        amount=expense.amount,
                        month=current_month
                    )
                    if cashback > 0:
                        cashback_text = f" (+{cashback:.0f} ₽)"
                        # Сохраняем кешбек в базе данных
                        expense.cashback_amount = Decimal(str(cashback))
                        await expense.asave()
        
        # Формируем сообщение
        if is_income:
            # Для доходов используем единый формат
            from ..utils.expense_messages import format_income_added_message
            message_text = await format_income_added_message(
                income=expense,
                category=expense.category,
                lang=lang
            )
            edit_callback = f"edit_income_{expense.id}"
        else:
            # Для расходов используем существующий формат
            from ..utils.expense_messages import format_expense_added_message
            message_text = await format_expense_added_message(
                expense=expense,
                category=expense.category,
                cashback_text=cashback_text,
                lang=lang
            )
            edit_callback = f"edit_expense_{expense.id}"
        
        # Редактируем сообщение с кнопками редактирования
        await callback.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=edit_callback)
                ]
            ]),
            parse_mode="HTML"
        )
    except Exception:
        error_msg = "❌ Ошибка при получении данных дохода" if is_income else "❌ Ошибка при получении данных траты"
        await callback.message.edit_text(error_msg)
    
    from bot.utils.state_utils import clear_state_keep_cashback
    await clear_state_keep_cashback(state)
    await callback.answer()






@router.callback_query(lambda c: c.data.startswith("expense_cat_"), EditExpenseForm.editing_category)
async def process_edit_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора новой категории"""
    category_id = int(callback.data.split("_")[-1])
    
    data = await state.get_data()
    item_id = data.get('editing_expense_id')
    is_income = data.get('editing_type') == 'income'
    
    # Получаем информацию об операции для обучения (только для расходов)
    if is_income:
        from expenses.models import Income
        try:
            expense = await Income.objects.aget(id=item_id)
            old_category_id = expense.category_id
            description = expense.description
        except Income.DoesNotExist:
            await callback.answer("❌ Доход не найден", show_alert=True)
            from bot.utils.state_utils import clear_state_keep_cashback
            await clear_state_keep_cashback(state)
            return
    else:
        from expenses.models import Expense
        try:
            expense = await Expense.objects.aget(id=item_id)
            old_category_id = expense.category_id
            description = expense.description
        except Expense.DoesNotExist:
            await callback.answer("❌ Трата не найдена", show_alert=True)
            from bot.utils.state_utils import clear_state_keep_cashback
            await clear_state_keep_cashback(state)
            return
    
    # Обновляем операцию
    if is_income:
        from ..services.income import update_income
        success = await update_income(callback.from_user.id, item_id, category_id=category_id)
    else:
        from ..services.expense import update_expense
        success = await update_expense(callback.from_user.id, item_id, category_id=category_id)
    
    if success:
        # Обучение ключевым словам теперь происходит через Celery задачу
        # Вызов update_keywords_weights.delay() находится в update_expense()

        # Показываем обновленную операцию
        await show_updated_expense_callback(callback, state, item_id, lang)
    else:
        error_msg = "❌ Не удалось обновить категорию дохода" if is_income else "❌ Не удалось обновить категорию"
        await callback.answer(error_msg, show_alert=True)


async def show_edit_menu(message: types.Message, state: FSMContext, expense_id: int, lang: str = 'ru'):
    """Показать меню редактирования после изменения"""
    from expenses.models import Expense
    
    try:
        expense = await Expense.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=message.from_user.id
        )
        
        translated_category = get_category_display_name(expense.category, lang)
        data = await state.get_data()
        edit_prefix = 'income' if data.get('editing_type') == 'income' else 'expense'
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Сумма: {expense.amount:.0f} ₽", callback_data=f"edit_field_amount_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text=f"📝 Описание: {expense.description}", callback_data=f"edit_field_description_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text=f"📁 Категория: {translated_category}", callback_data=f"edit_field_category_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"edit_done_{edit_prefix}_{expense.id}")]
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
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)


async def show_edit_menu_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    expense_id: int,
    lang: str = 'ru',
    item_type: str | None = None
):
    """Показать меню редактирования для callback"""
    from expenses.models import Expense, Income
    
    try:
        data = await state.get_data()
        is_income = (item_type or data.get('editing_type')) == 'income'
        model = Income if is_income else Expense
        expense = await model.objects.select_related('category').aget(
            id=expense_id,
            profile__telegram_id=callback.from_user.id
        )
        
        translated_category = get_category_display_name(expense.category, lang)
        edit_prefix = 'income' if is_income else 'expense'
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Сумма: {expense.amount:.0f} ₽", callback_data=f"edit_field_amount_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text=f"📝 Описание: {expense.description}", callback_data=f"edit_field_description_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text=f"📁 Категория: {translated_category}", callback_data=f"edit_field_category_{edit_prefix}_{expense.id}")],
            [InlineKeyboardButton(text="✅ Готово", callback_data=f"edit_done_{edit_prefix}_{expense.id}")]
        ])
        
        await callback.message.edit_text(
            "✏️ <b>Редактирование траты</b>\n\n"
            "Выберите поле для изменения:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(EditExpenseForm.choosing_field)
        await callback.answer()
    except (Expense.DoesNotExist, Income.DoesNotExist):
        await callback.answer("❌ Трата не найдена", show_alert=True)
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)


async def show_updated_expense(message: types.Message, state: FSMContext, item_id: int, lang: str = 'ru'):
    """Показать обновленную операцию (доход или расход)"""
    data = await state.get_data()
    is_income = data.get('editing_type') == 'income'
    
    try:
        if is_income:
            from expenses.models import Income
            expense = await Income.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=message.from_user.id
            )
        else:
            from expenses.models import Expense
            expense = await Expense.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=message.from_user.id
            )
        
        # Формируем сообщение
        if is_income:
            # Для доходов используем единый формат
            from ..utils.expense_messages import format_income_added_message
            message_text = await format_income_added_message(
                income=expense,
                category=expense.category,
                lang=lang
            )
            edit_callback = f"edit_income_{expense.id}"
        else:
            # Для расходов
            cashback_text = ""
            has_subscription = await check_subscription(message.from_user.id)
            if has_subscription and expense.category:
                # Получаем валюту пользователя из профиля
                user_currency = expense.profile.currency if expense.profile else 'RUB'
                # Кешбек начисляется только для трат в валюте пользователя
                expense_currency = expense.currency if hasattr(expense, 'currency') else 'RUB'
                if expense_currency == user_currency:
                    current_month = datetime.now().month
                    cashback = await calculate_expense_cashback(
                        user_id=message.from_user.id,
                        category_id=expense.category.id,
                        amount=expense.amount,
                        month=current_month
                    )
                    if cashback > 0:
                        cashback_text = f" (+{cashback:.0f} ₽)"
                        # Сохраняем кешбек в базе данных
                        expense.cashback_amount = Decimal(str(cashback))
                        await expense.asave()
            
            message_text = await format_expense_added_message(
                expense=expense,
                category=expense.category,
                cashback_text=cashback_text,
                lang=lang
            )
            edit_callback = f"edit_expense_{expense.id}"
        
        await send_message_with_cleanup(message, state,
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=edit_callback)
                ]
            ]),
            parse_mode="HTML",
            keep_message=True  # Не удалять это сообщение при следующих действиях
        )
        
        # Очищаем состояние
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
    except (Expense.DoesNotExist, Income.DoesNotExist):
        error_msg = "❌ Доход не найден" if is_income else "❌ Трата не найдена"
        await message.answer(error_msg)
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)


async def show_updated_expense_callback(callback: types.CallbackQuery, state: FSMContext, item_id: int, lang: str = 'ru'):
    """Показать обновленную операцию для callback"""
    data = await state.get_data()
    is_income = data.get('editing_type') == 'income'
    
    try:
        if is_income:
            from expenses.models import Income
            expense = await Income.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=callback.from_user.id
            )
        else:
            from expenses.models import Expense
            expense = await Expense.objects.select_related('category', 'profile').aget(
                id=item_id,
                profile__telegram_id=callback.from_user.id
            )
        
        # Формируем сообщение
        if is_income:
            # Для доходов используем единый формат
            from ..utils.expense_messages import format_income_added_message
            message_text = await format_income_added_message(
                income=expense,
                category=expense.category,
                lang=lang
            )
            edit_callback = f"edit_income_{expense.id}"
        else:
            # Для расходов
            cashback_text = ""
            has_subscription = await check_subscription(callback.from_user.id)
            if has_subscription and expense.category and not expense.cashback_excluded:
                # Получаем валюту пользователя из профиля
                user_currency = expense.profile.currency if expense.profile else 'RUB'
                # Кешбек начисляется только для трат в валюте пользователя
                expense_currency = expense.currency if hasattr(expense, 'currency') else 'RUB'
                if expense_currency == user_currency:
                    current_month = datetime.now().month
                    cashback = await calculate_expense_cashback(
                        user_id=callback.from_user.id,
                        category_id=expense.category.id,
                        amount=expense.amount,
                        month=current_month
                    )
                    if cashback > 0:
                        cashback_text = f" (+{cashback:.0f} ₽)"
                        # Сохраняем кешбек в базе данных
                        expense.cashback_amount = Decimal(str(cashback))
                        await expense.asave()
            
            message_text = await format_expense_added_message(
                expense=expense,
                category=expense.category,
                cashback_text=cashback_text,
                lang=lang
            )
            edit_callback = f"edit_expense_{expense.id}"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=get_text('edit_button', lang), callback_data=edit_callback)
                ]
            ]),
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)
        await callback.answer()
    except (Expense.DoesNotExist, Income.DoesNotExist):
        error_msg = "❌ Доход не найден" if is_income else "❌ Трата не найдена"
        await callback.answer(error_msg, show_alert=True)
        from bot.utils.state_utils import clear_state_keep_cashback
        await clear_state_keep_cashback(state)


# Обработчик подтверждения записи бюджета как дохода
@router.callback_query(lambda c: c.data.startswith("budget_confirm:"))
async def budget_confirm_callback(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Подтверждение записи бюджета как дохода"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Извлекаем сумму из callback data
    amount_str = callback.data.split(":")[1]
    try:
        amount = Decimal(amount_str)
    except (InvalidOperation, ValueError):
        error_msg = "⚠️ Некорректная сумма" if lang == 'ru' else "⚠️ Invalid amount"
        await callback.answer(error_msg, show_alert=True)
        return

    # Получаем оригинальный текст из состояния
    data = await state.get_data()
    original_text = data.get('budget_original_text', '') or (callback.message.text or '')

    # Формируем текст для записи как доход: добавляем знак +
    # Используем amount_str без разделителей тысяч для парсера
    income_text = f"+{amount_str}"

    # Добавляем описание если было в оригинальном тексте
    # (убираем ключевые слова бюджета)
    from ..utils.expense_parser import BUDGET_KEYWORDS
    description_words = []
    for word in original_text.split():
        word_lower = word.lower()
        is_budget_keyword = False
        for lang_keywords in BUDGET_KEYWORDS.values():
            if word_lower in lang_keywords:
                is_budget_keyword = True
                break
        # Также пропускаем числа
        if not is_budget_keyword and not word.replace('.', '').replace(',', '').isdigit():
            description_words.append(word)

    if description_words:
        income_text += " " + " ".join(description_words)
    else:
        # Если описания нет, добавляем "Бюджет" или "Budget"
        income_text += " " + ("Бюджет" if lang == 'ru' else "Budget")

    # Удаляем сообщение с подтверждением
    try:
        await callback.message.delete()
    except:
        pass

    # Сбрасываем флаг намерения бюджета, чтобы не попасть снова в воронку
    await state.update_data(skip_budget_intent=True, budget_original_text=None, budget_amount=None)

    # Обрабатываем как доход через существующую логику
    # Используем callback.message который имеет связь с bot, но передаём правильный user_id
    await handle_text_expense(callback.message, state, text=income_text, lang=lang, user_id=user_id)

    await callback.answer()


# Обработчик отклонения записи бюджета (записать как трату)
@router.callback_query(lambda c: c.data.startswith("budget_decline:"))
async def budget_decline_callback(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Отклонение записи бюджета - обрабатываем как обычную трату"""
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # Получаем оригинальный текст из состояния
    data = await state.get_data()
    original_text = data.get('budget_original_text', '') or (callback.message.text or '')

    # Удаляем сообщение с подтверждением
    try:
        await callback.message.delete()
    except:
        pass

    # Ставим флаг пропуска бюджетной воронки и очищаем сохранённые данные
    await state.update_data(skip_budget_intent=True, budget_original_text=None, budget_amount=None)

    # Обрабатываем как обычную трату через основной пайплайн
    # Используем callback.message который имеет связь с bot, но передаём правильный user_id
    await handle_text_expense(callback.message, state, text=original_text, lang=lang, user_id=user_id)
    await callback.answer()
