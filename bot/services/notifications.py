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
        
    async def send_monthly_report(self, user_id: int, profile: Profile):
        """Send monthly expense report"""
        try:
            from ..services.pdf_report import PDFReportService
            from aiogram.types import BufferedInputFile
            
            today = date.today()
            # Отчет за весь текущий месяц
            month_start = today.replace(day=1)
            
            # Генерируем PDF отчет
            pdf_service = PDFReportService()
            pdf_bytes = await pdf_service.generate_monthly_report(
                user_id=user_id,
                year=today.year,
                month=today.month
            )
            
            month_name = get_month_name(today.month, 'ru')
            
            if pdf_bytes:
                # Отправляем PDF файл
                pdf_file = BufferedInputFile(
                    pdf_bytes,
                    filename=f"monthly_report_{today.year}_{today.month:02d}.pdf"
                )
                
                await self.bot.send_document(
                    chat_id=user_id,
                    document=pdf_file,
                    caption=f"📊 Ежемесячный отчет за {month_name} {today.year}"
                )
                
                logger.info(f"Monthly PDF report sent to user {user_id}")
            # Если расходов не было - ничего не отправляем
            
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