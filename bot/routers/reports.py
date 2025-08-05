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
from bot.services.expense import get_expenses_summary, get_expenses_by_period
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button

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
async def callback_expenses_today(callback: CallbackQuery, lang: str = 'ru'):
    """Показать расходы за сегодня"""
    today = date.today()
    
    await show_expenses_summary(
        callback.message,
        today,
        today,
        lang,
        edit=True,
        original_message=callback.message
    )
    await callback.answer()


@router.callback_query(F.data == "show_month_start")
async def callback_show_month_start(callback: CallbackQuery, lang: str = 'ru'):
    """Показать расходы с начала месяца"""
    today = date.today()
    start_date = today.replace(day=1)
    
    await show_expenses_summary(
        callback.message,
        start_date,
        today,
        lang,
        edit=True,
        original_message=callback.message
    )
    await callback.answer()




async def show_expenses_summary(
    message: Message,
    start_date: date,
    end_date: date,
    lang: str,
    edit: bool = False,
    original_message: Message = None
):
    """Показать сводку расходов за период"""
    try:
        # Получаем данные
        summary = await get_expenses_summary(
            telegram_id=message.from_user.id if not edit else original_message.from_user.id,
            start_date=start_date,
            end_date=end_date
        )
        
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
                    percentage = float(cat['total']) / float(summary['total']) * 100
                    text += f"{cat['icon']} {cat['name']}: {format_amount(cat['total'], summary['currency'], lang)} ({percentage:.1f}%)\n"
                
            # Потенциальный кешбэк
            if summary['potential_cashback'] > 0:
                text += f"\n💳 {get_text('potential_cashback', lang)}: {format_amount(summary['potential_cashback'], summary['currency'], lang)}"
        
        # Определяем период для клавиатуры
        period = 'today' if start_date == end_date == date.today() else 'month'
        
        # Сохраняем даты в состоянии для генерации PDF
        from aiogram.fsm.storage.base import StorageKey
        storage_key = StorageKey(
            bot_id=message.bot.id,
            chat_id=message.chat.id if not edit else original_message.chat.id,
            user_id=message.from_user.id if not edit else original_message.from_user.id
        )
        state = FSMContext(
            storage=message.bot.fsm_storage,
            key=storage_key
        )
        await state.update_data(
            report_start_date=start_date,
            report_end_date=end_date
        )
        
        # Отправляем или редактируем сообщение
        if edit and original_message:
            await original_message.edit_text(
                text,
                reply_markup=expenses_summary_keyboard(lang, period)
            )
        else:
            await send_message_with_cleanup(
                message, state, text,
                reply_markup=expenses_summary_keyboard(lang, period)
            )
            
    except Exception as e:
        logger.error(f"Error showing expenses summary: {e}")
        error_text = get_text('error_occurred', lang)
        if edit and original_message:
            await original_message.edit_text(error_text)
        else:
            await send_message_with_cleanup(message, state, error_text)


@router.message(Command("report"))
async def cmd_report(message: Message, lang: str = 'ru'):
    """Команда /report - выбор периода для отчета"""
    keyboard = month_selection_keyboard(lang)
    
    await send_message_with_cleanup(
        message, state,
        get_text('choose_month', lang),
        reply_markup=keyboard
    )


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