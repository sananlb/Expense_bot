"""
Router for expense reports and analytics
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, date, timedelta
from calendar import monthrange
import logging

from bot.keyboards import expenses_summary_keyboard, month_selection_keyboard, back_close_keyboard
from bot.utils import get_text, format_amount, get_month_name
from bot.services.expense import get_expenses_summary, get_expenses_by_period, get_last_expenses
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

router = Router(name="reports")


@router.message(Command("summary"))
async def cmd_summary(message: Message, lang: str = 'ru'):
    """Команда /summary - показать сводку за месяц"""
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today
    
    await show_expenses_summary(message, start_date, end_date, lang)


@router.callback_query(F.data == "expenses_today")
async def callback_expenses_today(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать расходы за сегодня"""
    today = date.today()
    
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


@router.callback_query(F.data == "show_month_start")
async def callback_show_month_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать расходы с начала месяца"""
    today = date.today()
    start_date = today.replace(day=1)
    
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




async def show_expenses_summary(
    message: Message,
    start_date: date,
    end_date: date,
    lang: str,
    state: FSMContext = None,
    edit: bool = False,
    original_message: Message = None,
    callback: CallbackQuery = None
):
    """Показать сводку расходов за период"""
    try:
        # Получаем данные - при edit берем user_id из callback
        if callback:
            user_id = callback.from_user.id
        elif not edit:
            user_id = message.from_user.id
        else:
            # Fallback - не должно происходить
            logger.error("No callback provided for edit mode!")
            user_id = message.chat.id
        
        logger.info(f"Getting expenses summary for user {user_id}, period: {start_date} to {end_date}")
        
        summary = await get_expenses_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(f"Summary result: total={summary.get('total', 0)}, count={summary.get('count', 0)}, categories={len(summary.get('by_category', []))}")
        
        # Формируем текст
        if start_date == end_date:
            if start_date == date.today():
                period_text = get_text('today', lang)
            else:
                period_text = start_date.strftime('%d.%m.%Y')
        else:
            month_name = get_month_name(start_date.month, lang)
            if start_date.month == end_date.month and start_date.year == end_date.year:
                period_text = f"{month_name} {start_date.year}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        
        text = f"📊 {get_text('summary', lang)} {period_text}\n\n"
        
        if summary['total'] == 0:
            text += get_text('no_expenses_period', lang)
        else:
            # Общая сумма
            text += f"💰 {get_text('total', lang)}: {format_amount(summary['total'], summary['currency'], lang)}\n\n"
            
            # По категориям
            if summary['by_category']:
                text += f"📊 {get_text('by_categories', lang)}:\n"
                for cat in summary['by_category'][:10]:  # Максимум 10 категорий
                    icon_text = f"{cat['icon']} " if cat.get('icon') else ""
                    text += f"{icon_text}{cat['name']}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                
            # Потенциальный кешбэк
            if summary['potential_cashback'] > 0:
                text += f"\n💳 {get_text('potential_cashback', lang)}: {format_amount(summary['potential_cashback'], summary['currency'], lang)}"
        
        # Добавляем подсказку внизу курсивом
        text += "\n\n<i>Показать отчет за другой период?</i>"
        
        # Определяем период для клавиатуры
        today = date.today()
        is_today = start_date == end_date == today
        is_current_month = (start_date.day == 1 and 
                           start_date.month == today.month and 
                           start_date.year == today.year and
                           end_date >= today)
        
        if is_today:
            period = 'today'
            show_pdf = False
        elif is_current_month or (start_date.day == 1 and end_date.month == start_date.month):
            period = 'month'
            show_pdf = True
        else:
            period = 'custom'
            show_pdf = True
        
        # Логирование для отладки
        logger.info(f"Period determination: start_date={start_date}, end_date={end_date}, today={today}, is_today={is_today}, period={period}")
        
        # Сохраняем даты в состоянии для генерации PDF
        if state:
            await state.update_data(
                report_start_date=start_date.isoformat(),
                report_end_date=end_date.isoformat(),
                current_month=start_date.month if start_date.day == 1 else None,
                current_year=start_date.year if start_date.day == 1 else None
            )
        
        # Отправляем или редактируем сообщение
        if edit and original_message:
            await original_message.edit_text(
                text,
                reply_markup=expenses_summary_keyboard(lang, period, show_pdf)
            )
        else:
            await send_message_with_cleanup(
                message, state, text,
                reply_markup=expenses_summary_keyboard(lang, period, show_pdf)
            )
            
    except Exception as e:
        logger.error(f"Error showing expenses summary: {e}")
        error_text = get_text('error_occurred', lang)
        if edit and original_message:
            await original_message.edit_text(error_text)
        else:
            await message.answer(error_text)


@router.message(Command("report"))
async def cmd_report(message: Message, lang: str = 'ru'):
    """Команда /report - выбор периода для отчета"""
    keyboard = month_selection_keyboard(lang)
    
    await send_message_with_cleanup(
        message, state,
        get_text('choose_month', lang),
        reply_markup=keyboard
    )


@router.callback_query(F.data == "show_diary")
async def callback_show_diary(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать дневник трат (последние 2 дня, максимум 20 записей)"""
    try:
        from datetime import datetime, timedelta
        from expenses.models import Expense
        from asgiref.sync import sync_to_async
        
        user_id = callback.from_user.id
        
        # Определяем период - последние 2 дня
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=2)
        
        # Получаем траты за последние 2 дня, но не более 20
        @sync_to_async
        def get_recent_expenses():
            return list(Expense.objects.filter(
                profile__telegram_id=user_id,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('expense_date', 'created_at')[:20])
        
        expenses = await get_recent_expenses()
        
        if not expenses:
            text = "📋 <b>Дневник трат</b>\n\n<i>Трат не найдено</i>"
        else:
            text = "📋 <b>Дневник трат</b>\n\n"
            
            total_amount = {}  # Для подсчета общей суммы по валютам
            current_date = None
            
            for expense in expenses:
                # Группируем по датам
                if expense.expense_date != current_date:
                    current_date = expense.expense_date
                    # Форматируем дату
                    if current_date == end_date:
                        date_str = "Сегодня"
                    elif current_date == end_date - timedelta(days=1):
                        date_str = "Вчера"
                    elif current_date == end_date - timedelta(days=2):
                        date_str = "Позавчера"
                    else:
                        date_str = current_date.strftime('%d.%m.%Y')
                    text += f"\n<b>📅 {date_str}</b>\n"
                
                # Форматируем время, описание и сумму в одну строку
                time_str = expense.created_at.strftime('%H:%M')
                description = expense.description or "Без описания"
                # Обрезаем длинное описание
                if len(description) > 30:
                    description = description[:27] + "..."
                
                # Форматируем сумму с валютой
                currency = expense.currency or 'RUB'
                amount = float(expense.amount)
                
                # Добавляем к общей сумме
                if currency not in total_amount:
                    total_amount[currency] = 0
                total_amount[currency] += amount
                
                amount_str = f"{amount:,.0f}".replace(',', ' ')
                if currency == 'RUB':
                    amount_str += ' ₽'
                elif currency == 'USD':
                    amount_str += ' $'
                elif currency == 'EUR':
                    amount_str += ' €'
                else:
                    amount_str += f' {currency}'
                
                text += f"  {time_str} — {description} {amount_str}\n"
            
            # Добавляем итоговую сумму
            if total_amount:
                text += "\n<b>💰 Итого:</b>\n"
                for currency, total in total_amount.items():
                    total_str = f"{total:,.0f}".replace(',', ' ')
                    currency_symbol = {'RUB': '₽', 'USD': '$', 'EUR': '€'}.get(currency, currency)
                    text += f"• {total_str} {currency_symbol}\n"
        
        # Добавляем кнопку "Назад"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="expenses_today")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing expense diary: {e}")
        await callback.answer("Произошла ошибка при загрузке дневника", show_alert=True)



@router.callback_query(F.data == "back_to_summary")
async def callback_back_to_summary(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться к последнему отчету"""
    data = await state.get_data()
    start_date = data.get('report_start_date')
    end_date = data.get('report_end_date')
    
    if start_date and end_date:
        # Преобразуем строки обратно в date объекты
        from datetime import date as date_type
        if isinstance(start_date, str):
            start_date = date_type.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date_type.fromisoformat(end_date)
            
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
    else:
        # Если нет сохраненных дат, показываем отчет за текущий месяц
        today = date.today()
        start_date = today.replace(day=1)
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


@router.callback_query(F.data.startswith("month_"))
async def callback_select_month(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора месяца для отчета"""
    month = int(callback.data.split('_')[1])
    year = date.today().year
    
    # Если выбранный месяц больше текущего, берем прошлый год
    if month > date.today().month:
        year -= 1
        
    # Определяем даты
    start_date = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = date(year, month, last_day)
    
    # Показываем сводку
    await show_expenses_summary(
        callback.message,
        start_date,
        end_date,
        lang,
        edit=True,
        original_message=callback.message
    )
    await callback.answer()