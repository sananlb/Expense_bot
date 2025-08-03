from celery import shared_task
from datetime import datetime, date
import asyncio
import logging

from django.conf import settings
from aiogram import Bot

logger = logging.getLogger(__name__)


@shared_task
def send_daily_reports():
    """Send daily expense reports to all users"""
    try:
        from profiles.models import Profile
        from bot.services.notifications import NotificationService
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Get users with daily reports enabled
        profiles = Profile.objects.filter(
            settings__notifications__daily_report=True
        ).select_related('user')
        
        logger.info(f"Sending daily reports to {profiles.count()} users")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_daily_report(profile.telegram_id, profile)
                )
            except Exception as e:
                logger.error(f"Error sending daily report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_daily_reports task: {e}")


@shared_task
def send_weekly_reports():
    """Send weekly expense reports (on Sundays)"""
    try:
        # Only run on Sundays
        if datetime.now().weekday() != 6:
            return
        
        from profiles.models import Profile
        from bot.services.notifications import NotificationService
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Get users with weekly reports enabled
        profiles = Profile.objects.filter(
            settings__notifications__weekly_report=True
        ).select_related('user')
        
        logger.info(f"Sending weekly reports to {profiles.count()} users")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_weekly_report(profile.telegram_id, profile)
                )
            except Exception as e:
                logger.error(f"Error sending weekly report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_weekly_reports task: {e}")


@shared_task
def send_monthly_reports():
    """Send monthly expense reports (on the 1st)"""
    try:
        # Only run on the 1st day of month
        if datetime.now().day != 1:
            return
        
        from profiles.models import Profile
        from bot.services.notifications import NotificationService
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Get users with monthly reports enabled
        profiles = Profile.objects.filter(
            settings__notifications__monthly_report=True
        ).select_related('user')
        
        logger.info(f"Sending monthly reports to {profiles.count()} users")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_monthly_report(profile.telegram_id, profile)
                )
            except Exception as e:
                logger.error(f"Error sending monthly report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_monthly_reports task: {e}")


@shared_task
def check_budget_limits():
    """Check budget limits and send warnings"""
    try:
        from profiles.models import Profile
        from expenses.models import Budget, Expense
        from bot.services.notifications import NotificationService
        from decimal import Decimal
        
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        service = NotificationService(bot)
        
        # Get all active budgets
        budgets = Budget.objects.filter(
            is_active=True
        ).select_related('profile', 'category')
        
        today = date.today()
        
        for budget in budgets:
            try:
                # Calculate spent amount based on period
                if budget.period == 'daily':
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date=today
                    )
                elif budget.period == 'weekly':
                    from datetime import timedelta
                    week_start = today - timedelta(days=today.weekday())
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date__gte=week_start,
                        date__lte=today
                    )
                elif budget.period == 'monthly':
                    month_start = today.replace(day=1)
                    expenses = Expense.objects.filter(
                        profile=budget.profile,
                        date__gte=month_start,
                        date__lte=today
                    )
                else:
                    continue
                
                # Filter by category if specified
                if budget.category:
                    expenses = expenses.filter(category=budget.category)
                
                # Calculate total spent
                spent = sum(e.amount for e in expenses)
                percent = (spent / budget.amount) * 100 if budget.amount > 0 else 0
                
                # Send warnings at 80%, 90%, and 100%
                if percent >= 80:
                    # Check if we should send notification
                    should_notify = False
                    
                    if percent >= 100 and not budget.notified_exceeded:
                        should_notify = True
                        budget.notified_exceeded = True
                    elif 90 <= percent < 100 and not budget.notified_90_percent:
                        should_notify = True
                        budget.notified_90_percent = True
                    elif 80 <= percent < 90 and not budget.notified_80_percent:
                        should_notify = True
                        budget.notified_80_percent = True
                    
                    if should_notify:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        loop.run_until_complete(
                            service.send_budget_warning(
                                budget.profile.telegram_id,
                                budget,
                                spent,
                                percent
                            )
                        )
                        
                        loop.close()
                        budget.save()
                
                # Reset notifications for new period
                elif percent < 80:
                    if budget.notified_80_percent or budget.notified_90_percent or budget.notified_exceeded:
                        budget.notified_80_percent = False
                        budget.notified_90_percent = False
                        budget.notified_exceeded = False
                        budget.save()
                
            except Exception as e:
                logger.error(f"Error checking budget {budget.id}: {e}")
        
    except Exception as e:
        logger.error(f"Error in check_budget_limits task: {e}")


@shared_task
def cleanup_old_expenses():
    """Clean up expenses older than retention period"""
    try:
        from expenses.models import Expense
        from datetime import timedelta
        
        # Keep expenses for 2 years by default
        retention_days = getattr(settings, 'EXPENSE_RETENTION_DAYS', 730)
        cutoff_date = date.today() - timedelta(days=retention_days)
        
        # Delete old expenses
        deleted_count, _ = Expense.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Deleted {deleted_count} expenses older than {cutoff_date}")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_expenses task: {e}")