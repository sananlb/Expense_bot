import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from expenses.models import Profile, Expense, Budget
from ..services.expense import get_expenses_summary
from ..utils import format_amount, get_month_name

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def send_weekly_report(self, user_id: int, profile: Profile):
        """Send weekly expense report for last 7 days"""
        try:
            today = date.today()
            week_start = today - timedelta(days=6)  # Последние 7 дней включая сегодня
            
            # Получаем сводку за последние 7 дней
            summary = await get_expenses_summary(
                telegram_id=user_id,
                start_date=week_start,
                end_date=today
            )
            
            # Формируем текст отчета
            text = f"📊 Недельный отчет ({week_start.strftime('%d.%m')} - {today.strftime('%d.%m')})\n\n"
            
            if summary['total'] == 0:
                text += "💰 За последние 7 дней расходов не было"
            else:
                # Общая сумма
                text += f"💰 Всего потрачено: {format_amount(summary['total'], summary['currency'], 'ru')}\n"
                text += f"📝 Количество трат: {summary.get('count', 0)}\n"
                
                if summary.get('count', 0) > 0:
                    avg = summary['total'] / summary.get('count', 1)
                    text += f"💵 Средний чек: {format_amount(avg, summary['currency'], 'ru')}\n\n"
                
                # По категориям
                if summary['by_category']:
                    text += "📊 Топ категорий:\n"
                    for cat in summary['by_category'][:5]:  # Топ-5 категорий
                        percentage = float(cat['total']) / float(summary['total']) * 100
                        text += f"{cat['icon']} {cat['name']}: {format_amount(cat['total'], summary['currency'], 'ru')} ({percentage:.1f}%)\n"
                
                # Потенциальный кешбэк
                if summary.get('potential_cashback', 0) > 0:
                    text += f"\n💳 Потенциальный кешбэк: {format_amount(summary['potential_cashback'], summary['currency'], 'ru')}"
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📈 Показать с начала месяца", callback_data="show_month_start")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard
            )
            
            logger.info(f"Weekly report sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending weekly report to user {user_id}: {e}")
    
    async def send_monthly_report(self, user_id: int, profile: Profile):
        """Send monthly expense report"""
        try:
            today = date.today()
            # Отчет за весь текущий месяц
            month_start = today.replace(day=1)
            
            # Получаем сводку за месяц
            summary = await get_expenses_summary(
                telegram_id=user_id,
                start_date=month_start,
                end_date=today
            )
            
            month_name = get_month_name(today.month, 'ru')
            
            # Формируем текст отчета
            text = f"📊 Ежемесячный отчет за {month_name} {today.year}\n\n"
            
            if summary['total'] == 0:
                text += f"💰 В {month_name} расходов не было"
            else:
                # Общая сумма
                text += f"💰 Всего потрачено: {format_amount(summary['total'], summary['currency'], 'ru')}\n"
                text += f"📝 Количество трат: {summary.get('count', 0)}\n"
                
                if summary.get('count', 0) > 0:
                    avg = summary['total'] / summary.get('count', 1)
                    text += f"💵 Средний чек: {format_amount(avg, summary['currency'], 'ru')}\n\n"
                
                # По категориям
                if summary['by_category']:
                    text += "📊 Распределение по категориям:\n"
                    for cat in summary['by_category'][:10]:  # Топ-10 категорий
                        percentage = float(cat['total']) / float(summary['total']) * 100
                        text += f"{cat['icon']} {cat['name']}: {format_amount(cat['total'], summary['currency'], 'ru')} ({percentage:.1f}%)\n"
                
                # Потенциальный кешбэк
                if summary.get('potential_cashback', 0) > 0:
                    text += f"\n💳 Потенциальный кешбэк за месяц: {format_amount(summary['potential_cashback'], summary['currency'], 'ru')}"
                
                # Сравнение с прошлым месяцем
                prev_month = today.month - 1 if today.month > 1 else 12
                prev_year = today.year if today.month > 1 else today.year - 1
                prev_month_start = date(prev_year, prev_month, 1)
                
                # Последний день прошлого месяца
                from calendar import monthrange
                prev_month_end = date(prev_year, prev_month, monthrange(prev_year, prev_month)[1])
                
                prev_summary = await get_expenses_summary(
                    telegram_id=user_id,
                    start_date=prev_month_start,
                    end_date=prev_month_end
                )
                
                if prev_summary['total'] > 0:
                    diff = summary['total'] - prev_summary['total']
                    diff_percent = (diff / prev_summary['total']) * 100 if prev_summary['total'] > 0 else 0
                    
                    text += "\n\n📈 Сравнение с прошлым месяцем:\n"
                    if diff > 0:
                        text += f"Потрачено больше на {format_amount(abs(diff), summary['currency'], 'ru')} (+{abs(diff_percent):.1f}%)"
                    else:
                        text += f"Потрачено меньше на {format_amount(abs(diff), summary['currency'], 'ru')} (-{abs(diff_percent):.1f}%)"
            
            # Создаем состояние для сохранения данных отчета
            storage_key = StorageKey(
                bot_id=self.bot.id,
                chat_id=user_id,
                user_id=user_id
            )
            state = FSMContext(
                storage=self.bot.fsm_storage,
                key=storage_key
            )
            await state.update_data(
                current_month=today.month,
                current_year=today.year
            )
            
            # Добавляем кнопки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="pdf_generate_current")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard
            )
            
            logger.info(f"Monthly report sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending monthly report to user {user_id}: {e}")
    
    async def send_budget_warning(self, user_id: int, budget: Budget, spent: Decimal, percent: float):
        """Send budget warning notification"""
        try:
            period_text = {
                'daily': 'день',
                'weekly': 'неделю', 
                'monthly': 'месяц'
            }.get(budget.period, budget.period)
            
            cat_text = f" в категории {budget.category.name}" if budget.category else ""
            
            text = f"""⚠️ <b>Предупреждение о бюджете</b>
            
Вы потратили {percent:.0f}% от бюджета на {period_text}{cat_text}.

💰 Потрачено: {format_amount(spent, 'RUB', 'ru')}
📊 Лимит: {format_amount(budget.amount, 'RUB', 'ru')}
💵 Осталось: {format_amount(budget.amount - spent, 'RUB', 'ru')}"""
            
            if percent >= 100:
                text += "\n\n❗ <b>Бюджет превышен!</b>"
            elif percent >= 90:
                text += "\n\n⚠️ <b>Осталось менее 10% бюджета</b>"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Мои расходы", callback_data="expenses_today")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            logger.info(f"Budget warning sent to user {user_id} ({percent:.0f}%)")
            
        except Exception as e:
            logger.error(f"Error sending budget warning to user {user_id}: {e}")