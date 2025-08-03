import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from profiles.models import Profile
from expenses.models import Expense, Budget
from ..services.expense import get_today_summary, get_month_summary
from ..services.reports import generate_monthly_report

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def send_daily_report(self, user_id: int, profile: Profile):
        """Send daily expense report"""
        try:
            today = date.today()
            summary = await get_today_summary(user_id)
            
            if not summary or summary['total'] == 0:
                # No expenses today, skip notification
                return
            
            # Format daily report
            text = f"""📊 Ежедневный отчет за {today.strftime('%d.%m.%Y')}

💰 Потрачено сегодня: {summary['total']:,.0f} ₽
📝 Количество трат: {summary['count']}

📊 По категориям:"""
            
            # Add top categories
            for cat in summary['categories'][:5]:
                percent = (cat['amount'] / summary['total']) * 100
                text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽ ({percent:.1f}%)"
            
            # Check budgets
            budget_warnings = await self._check_budgets(profile, summary['total'])
            if budget_warnings:
                text += "\n\n⚠️ Предупреждения по бюджетам:"
                for warning in budget_warnings:
                    text += f"\n• {warning}"
            
            # Add buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Показать за месяц", callback_data="expenses_month")],
                [InlineKeyboardButton(text="➕ Добавить расход", callback_data="add_expense")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard
            )
            
            logger.info(f"Daily report sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending daily report to user {user_id}: {e}")
    
    async def send_weekly_report(self, user_id: int, profile: Profile):
        """Send weekly expense report"""
        try:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            
            # Get weekly expenses
            expenses = await Expense.objects.filter(
                profile=profile,
                date__gte=week_start,
                date__lte=today
            ).select_related('category').aall()
            
            if not expenses:
                return
            
            total = sum(e.amount for e in expenses)
            
            # Group by category
            categories = {}
            for expense in expenses:
                # Название категории уже содержит эмодзи
                cat_name = expense.category.name if expense.category else "💰 Прочие расходы"
                categories[cat_name] = categories.get(cat_name, 0) + expense.amount
            
            # Sort categories by amount
            sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)
            
            # Format weekly report
            text = f"""📊 Недельный отчет ({week_start.strftime('%d.%m')} - {today.strftime('%d.%m')})

💰 Потрачено за неделю: {total:,.0f} ₽
📝 Количество трат: {len(expenses)}
💵 Средний чек: {total/len(expenses):,.0f} ₽

📊 Топ категорий:"""
            
            for cat, amount in sorted_cats[:5]:
                percent = (amount / total) * 100
                text += f"\n{cat}: {amount:,.0f} ₽ ({percent:.1f}%)"
            
            # Compare with previous week
            prev_week_start = week_start - timedelta(days=7)
            prev_week_end = week_start - timedelta(days=1)
            
            prev_expenses = await Expense.objects.filter(
                profile=profile,
                date__gte=prev_week_start,
                date__lte=prev_week_end
            ).aall()
            
            if prev_expenses:
                prev_total = sum(e.amount for e in prev_expenses)
                diff = total - prev_total
                diff_percent = (diff / prev_total) * 100 if prev_total > 0 else 0
                
                if diff > 0:
                    text += f"\n\n📈 По сравнению с прошлой неделей: +{diff:,.0f} ₽ (+{diff_percent:.1f}%)"
                else:
                    text += f"\n\n📉 По сравнению с прошлой неделей: {diff:,.0f} ₽ ({diff_percent:.1f}%)"
            
            # Add buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📄 Скачать отчет PDF", callback_data="generate_pdf_week")]
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
            month_start = today.replace(day=1)
            
            # Get month summary
            summary = await get_month_summary(user_id, today.month, today.year)
            
            if not summary or summary['total'] == 0:
                return
            
            # Format monthly report
            month_names = {
                1: "январь", 2: "февраль", 3: "март", 4: "апрель",
                5: "май", 6: "июнь", 7: "июль", 8: "август",
                9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
            }
            
            text = f"""📊 Месячный отчет за {month_names[today.month]} {today.year}

💰 Потрачено за месяц: {summary['total']:,.0f} ₽
📝 Количество трат: {summary['count']}
💵 Средний чек: {summary['total']/summary['count']:,.0f} ₽

📊 Топ категорий:"""
            
            for cat in summary['categories'][:5]:
                percent = (cat['amount'] / summary['total']) * 100
                text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽ ({percent:.1f}%)"
            
            # Budget status
            budgets = await Budget.objects.filter(
                profile=profile,
                is_active=True
            ).aall()
            
            if budgets:
                text += "\n\n💳 Статус бюджетов:"
                for budget in budgets:
                    spent = await self._get_budget_spent(budget, month_start, today)
                    percent = (spent / budget.amount) * 100 if budget.amount > 0 else 0
                    
                    if percent >= 100:
                        status = "❌ Превышен"
                    elif percent >= 80:
                        status = "⚠️ Близок к лимиту"
                    else:
                        status = "✅ В пределах"
                    
                    text += f"\n• {budget.name}: {spent:,.0f}/{budget.amount:,.0f} ₽ ({percent:.0f}%) {status}"
            
            # Generate PDF report
            pdf_path = await generate_monthly_report(user_id, today.month, today.year)
            
            # Add buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics_month")],
                [InlineKeyboardButton(text="💳 Управление бюджетами", callback_data="manage_budgets")]
            ])
            
            # Send message with PDF
            await self.bot.send_document(
                chat_id=user_id,
                document=open(pdf_path, 'rb'),
                caption=text,
                reply_markup=keyboard
            )
            
            logger.info(f"Monthly report sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending monthly report to user {user_id}: {e}")
    
    async def send_budget_warning(self, user_id: int, budget: Budget, spent: Decimal, percent: float):
        """Send budget warning notification"""
        try:
            text = f"""⚠️ Предупреждение по бюджету!

💳 Бюджет: {budget.name}
💰 Потрачено: {spent:,.0f} ₽ из {budget.amount:,.0f} ₽
📊 Использовано: {percent:.0f}%

"""
            
            if percent >= 100:
                text += "❌ Бюджет превышен! Рекомендуем сократить расходы в этой категории."
            elif percent >= 90:
                text += "⚠️ Осталось менее 10% бюджета. Будьте внимательны с тратами."
            else:
                text += "⚠️ Использовано более 80% бюджета. Контролируйте расходы."
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Подробнее", callback_data=f"budget_details_{budget.id}")],
                [InlineKeyboardButton(text="✏️ Изменить лимит", callback_data=f"edit_budget_{budget.id}")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard
            )
            
            logger.info(f"Budget warning sent to user {user_id} for budget {budget.name}")
            
        except Exception as e:
            logger.error(f"Error sending budget warning: {e}")
    
    async def _check_budgets(self, profile: Profile, daily_spent: Decimal) -> List[str]:
        """Check budget limits and return warnings"""
        warnings = []
        
        try:
            budgets = await Budget.objects.filter(
                profile=profile,
                is_active=True
            ).aall()
            
            today = date.today()
            
            for budget in budgets:
                if budget.period == 'daily':
                    spent = daily_spent
                    period_text = "день"
                elif budget.period == 'weekly':
                    week_start = today - timedelta(days=today.weekday())
                    spent = await self._get_budget_spent(budget, week_start, today)
                    period_text = "неделю"
                elif budget.period == 'monthly':
                    month_start = today.replace(day=1)
                    spent = await self._get_budget_spent(budget, month_start, today)
                    period_text = "месяц"
                else:
                    continue
                
                percent = (spent / budget.amount) * 100 if budget.amount > 0 else 0
                
                if percent >= 100:
                    warnings.append(f"{budget.name}: превышен лимит за {period_text} ({spent:,.0f}/{budget.amount:,.0f} ₽)")
                elif percent >= 80:
                    warnings.append(f"{budget.name}: использовано {percent:.0f}% за {period_text}")
                
                # Send separate warning notification for critical budgets
                if percent >= 80 and not budget.notified_80_percent:
                    await self.send_budget_warning(profile.telegram_id, budget, spent, percent)
                    budget.notified_80_percent = True
                    await budget.asave()
                
        except Exception as e:
            logger.error(f"Error checking budgets: {e}")
        
        return warnings
    
    async def _get_budget_spent(self, budget: Budget, start_date: date, end_date: date) -> Decimal:
        """Calculate spent amount for budget period"""
        filters = {
            'profile': budget.profile,
            'date__gte': start_date,
            'date__lte': end_date
        }
        
        if budget.category:
            filters['category'] = budget.category
        
        expenses = await Expense.objects.filter(**filters).aall()
        return sum(e.amount for e in expenses)


async def schedule_notifications(bot: Bot):
    """Schedule automatic notifications"""
    service = NotificationService(bot)
    
    # This would be called by Celery beat or similar scheduler
    # For now, just define the structure
    
    async def send_daily_reports():
        """Send daily reports to all users with this preference"""
        profiles = await Profile.objects.filter(
            settings__notifications__daily_report=True
        ).aall()
        
        for profile in profiles:
            await service.send_daily_report(profile.telegram_id, profile)
    
    async def send_weekly_reports():
        """Send weekly reports on Sundays"""
        if datetime.now().weekday() == 6:  # Sunday
            profiles = await Profile.objects.filter(
                settings__notifications__weekly_report=True
            ).aall()
            
            for profile in profiles:
                await service.send_weekly_report(profile.telegram_id, profile)
    
    async def send_monthly_reports():
        """Send monthly reports on the 1st"""
        if datetime.now().day == 1:
            profiles = await Profile.objects.filter(
                settings__notifications__monthly_report=True
            ).aall()
            
            for profile in profiles:
                await service.send_monthly_report(profile.telegram_id, profile)
    
    return {
        'daily': send_daily_reports,
        'weekly': send_weekly_reports,
        'monthly': send_monthly_reports
    }