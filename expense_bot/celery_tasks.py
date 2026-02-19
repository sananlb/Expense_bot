from celery import shared_task
from datetime import datetime, date, timedelta, time
import asyncio
import logging
import re
import os
from typing import List

from django.conf import settings
from django.db.models import Count, Sum, Avg, Case, When, FloatField, Q
from django.utils import timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound

logger = logging.getLogger(__name__)

def _shutdown_event_loop(loop: asyncio.AbstractEventLoop, *, bot: Bot = None, label: str = "") -> None:
    """
    Deterministically shutdown a manually-created asyncio event loop.

    Celery tasks here run async code via run_until_complete(). Some libraries (e.g. aiohttp/aiogram)
    may schedule additional cleanup work that needs at least one extra loop iteration (or pending tasks
    completion) before loop.close(), otherwise you can get "Unclosed client session/connector".
    """
    if loop is None:
        return

    if getattr(loop, "is_closed", lambda: False)():
        return

    ctx = f" in {label}" if label else ""

    try:
        # Ensure this loop is the current one for any cleanup relying on get_event_loop().
        try:
            asyncio.set_event_loop(loop)
        except Exception:
            pass

        if bot is not None:
            try:
                loop.run_until_complete(bot.close())
            except Exception as e:
                logger.error(f"Failed to close bot session{ctx}: {e}", exc_info=True)

            # Extra safety: explicitly close underlying aiohttp session if exposed.
            try:
                session = getattr(bot, "session", None)
                if session is not None:
                    is_closed = getattr(session, "closed", False)
                    if not is_closed:
                        loop.run_until_complete(session.close())
            except Exception as e:
                logger.error(f"Failed to close bot aiohttp session{ctx}: {e}", exc_info=True)

        # Close all AI services (httpx clients) before closing the loop
        # This prevents "Task exception was never retrieved" / "Event loop is closed" errors
        try:
            from bot.services.ai_selector import AISelector
            loop.run_until_complete(AISelector.close_all_services(clear_cache=True))
        except Exception as e:
            logger.debug(f"Failed to close AI services{ctx}: {e}")

        # Give the loop a chance to process callbacks scheduled by close().
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass

        # Drain pending tasks deterministically: wait briefly, then cancel leftovers.
        try:
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if pending:
                _, still_pending = loop.run_until_complete(asyncio.wait(pending, timeout=1.0))
                if still_pending:
                    for task in still_pending:
                        task.cancel()
                    # Try to await cancellations, but don't hang forever if a task ignores them.
                    try:
                        loop.run_until_complete(
                            asyncio.wait_for(
                                asyncio.gather(*still_pending, return_exceptions=True),
                                timeout=1.0,
                            )
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"{len(still_pending)} task(s) still pending after cancellation{ctx}; closing loop anyway"
                        )
        except Exception as e:
            logger.error(f"Failed to drain pending tasks{ctx}: {e}", exc_info=True)

        try:
            loop.run_until_complete(asyncio.wait_for(loop.shutdown_asyncgens(), timeout=1.0))
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while shutting down async generators{ctx}; closing loop anyway")
        except Exception as e:
            logger.error(f"Failed to shutdown async generators{ctx}: {e}", exc_info=True)

        shutdown_default_executor = getattr(loop, "shutdown_default_executor", None)
        if shutdown_default_executor is not None:
            try:
                loop.run_until_complete(asyncio.wait_for(shutdown_default_executor(), timeout=1.0))
            except asyncio.TimeoutError:
                logger.warning(f"Timeout while shutting down default executor{ctx}; closing loop anyway")
            except Exception as e:
                logger.error(f"Failed to shutdown default executor{ctx}: {e}", exc_info=True)

    finally:
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

        try:
            loop.close()
        except Exception as e:
            logger.error(f"Failed to close event loop{ctx}: {e}", exc_info=True)



@shared_task
def send_monthly_reports():
    """Send monthly expense reports to all users on the 1st day of month at 12:00 for previous month"""
    bot = None
    loop = None

    try:
        from expenses.models import Profile, Expense
        from bot.services.notifications import NotificationService
        from calendar import monthrange
        # Use main bot token for user-facing notifications
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)
        service = NotificationService(bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Use timezone-aware datetime to match CELERY_TIMEZONE (Europe/Moscow)
        now = timezone.now()  # Returns timezone-aware datetime in Europe/Moscow
        today = now.date()

        logger.info(f"Starting monthly reports task for {today}")

        # Calculate previous month period
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year

        # Get first and last day of previous month
        month_start = today.replace(year=prev_year, month=prev_month, day=1)
        last_day_of_prev_month = monthrange(prev_year, prev_month)[1]
        month_end = today.replace(year=prev_year, month=prev_month, day=last_day_of_prev_month)

        # Get all active profiles who have expenses in previous month
        # Monthly reports are sent to ALL users with expenses (not just subscribers)
        profiles_with_expenses = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lte=month_end
        ).values_list('profile_id', flat=True).distinct()

        # Get all profiles with expenses (no subscription filter)
        profiles = Profile.objects.filter(
            id__in=profiles_with_expenses
        ).distinct()

        logger.info(f"Sending monthly reports to {profiles.count()} users with expenses")

        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_monthly_report_notification(
                        profile.telegram_id,
                        profile,
                        prev_year,
                        prev_month,
                        attempt=1,
                    )
                )
            except Exception as e:
                error_msg = str(e)
                if is_retryable_error(error_msg):
                    logger.warning(
                        f"[MONTHLY_REPORT] user={profile.telegram_id} status=retry_scheduled "
                        f"attempt=1 delay=300s period={prev_year}-{prev_month:02d} error={error_msg}"
                    )
                    retry_send_monthly_report.apply_async(
                        args=[profile.telegram_id, prev_year, prev_month, 2],
                        countdown=300
                    )
                else:
                    logger.error(
                        f"[MONTHLY_REPORT] user={profile.telegram_id} status=failed_permanent "
                        f"period={prev_year}-{prev_month:02d} error={error_msg}"
                    )

    except Exception as e:
        logger.error(f"Error in send_monthly_reports task: {e}")

    finally:
        _shutdown_event_loop(loop, bot=bot, label="send_monthly_reports")


# Константы для retry логики отправки месячных отчетов
RETRYABLE_ERRORS = [
    'internal server error',  # 500
    'bad gateway',            # 502
    'service unavailable',    # 503
    'gateway timeout',        # 504
    'timeout', 'timed out',
    'connection reset',
    'retry after',
    'flood control',
]

NON_RETRYABLE_ERRORS = [
    'forbidden',              # 403 - бот заблокирован
    'chat not found',         # 400 - чат недоступен
    'user is deactivated',    # пользователь удален
    'bot was blocked',
    'have no rights',
    'need administrator',
]

# Backoff: 5 мин, 30 мин, 1 час
RETRY_DELAYS = [300, 1800, 3600]


def is_retryable_error(error_msg: str) -> bool:
    """Check if error is temporary and worth retrying"""
    error_lower = error_msg.lower()

    # First check if it's a non-retryable error
    for pattern in NON_RETRYABLE_ERRORS:
        if pattern in error_lower:
            return False

    # Then check if it matches retryable patterns
    for pattern in RETRYABLE_ERRORS:
        if pattern in error_lower:
            return True

    # Unknown errors - don't retry by default
    return False


@shared_task
def retry_send_monthly_report(user_id: int, year: int, month: int, attempt: int = 1):
    """
    Retry sending monthly report notification.
    Called when initial send fails with a temporary error.

    Backoff schedule: 5 min → 30 min → 1 hour
    """
    from django.core.cache import cache
    from expenses.models import Profile
    from bot.services.notifications import NotificationService

    bot = None
    loop = None

    # Idempotency check - don't send duplicates
    sent_key = f"monthly_report_sent:{user_id}:{year}:{month}"
    if cache.get(sent_key):
        logger.info(f"[MONTHLY_REPORT] user={user_id} status=already_sent period={year}-{month:02d}")
        return

    try:
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)
        service = NotificationService(bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        profile = Profile.objects.get(telegram_id=user_id)

        sent = loop.run_until_complete(
            service.send_monthly_report_notification(
                profile.telegram_id,
                profile,
                year,
                month,
                attempt=attempt,
            )
        )
        if not sent:
            logger.info(
                f"[MONTHLY_REPORT] user={user_id} status=skipped "
                f"attempt={attempt} period={year}-{month:02d}"
            )

    except Profile.DoesNotExist:
        logger.error(f"[MONTHLY_REPORT] user={user_id} status=failed error=profile_not_found")

    except Exception as e:
        error_msg = str(e)

        if is_retryable_error(error_msg):
            if attempt < 4:  # Max 4 attempts total (1 initial + 3 retries)
                delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"[MONTHLY_REPORT] user={user_id} status=retry_scheduled "
                    f"attempt={attempt} next_attempt={attempt + 1} delay={delay}s error={error_msg}"
                )
                # Schedule next retry
                retry_send_monthly_report.apply_async(
                    args=[user_id, year, month, attempt + 1],
                    countdown=delay
                )
            else:
                # All retries exhausted
                logger.error(
                    f"[MONTHLY_REPORT] user={user_id} status=failed "
                    f"attempts={attempt} period={year}-{month:02d} error={error_msg}"
                )
                # Alert admin
                try:
                    from bot.services.admin_notifier import send_admin_alert
                    loop.run_until_complete(
                        send_admin_alert(
                            f"❌ Monthly report FAILED after {attempt} attempts\n"
                            f"User: {user_id}\n"
                            f"Period: {year}-{month:02d}\n"
                            f"Error: {error_msg}",
                            disable_notification=True
                        )
                    )
                except Exception as alert_err:
                    logger.error(f"Failed to send admin alert: {alert_err}")
        else:
            # Non-retryable error (user blocked bot, etc.)
            logger.error(
                f"[MONTHLY_REPORT] user={user_id} status=failed_permanent "
                f"period={year}-{month:02d} error={error_msg}"
            )

    finally:
        _shutdown_event_loop(loop, bot=bot, label="retry_send_monthly_report")


@shared_task
def generate_monthly_insights():
    """Generate AI insights for all active subscribers on the 1st day of month at 11:00 for previous month"""
    loop = None
    try:
        from expenses.models import Profile, Expense
        from bot.services.monthly_insights import MonthlyInsightsService
        from calendar import monthrange

        # Use timezone-aware datetime to match CELERY_TIMEZONE (Europe/Moscow)
        now = timezone.now()
        today = now.date()

        logger.info(f"Starting monthly insights generation for {today}")

        # Calculate previous month period
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year

        # Get first and last day of previous month
        month_start = today.replace(year=prev_year, month=prev_month, day=1)
        last_day_of_prev_month = monthrange(prev_year, prev_month)[1]
        month_end = today.replace(year=prev_year, month=prev_month, day=last_day_of_prev_month)

        # Get profiles with expenses in previous month
        # Monthly insights are generated for ALL users with expenses (not just subscribers)
        profiles_with_expenses = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lte=month_end
        ).values_list('profile_id', flat=True).distinct()

        # Get all profiles with expenses (no subscription filter)
        profiles = Profile.objects.filter(
            id__in=profiles_with_expenses
        ).distinct()

        logger.info(f"Generating AI insights for {profiles.count()} users with expenses")

        # Initialize service
        service = MonthlyInsightsService()

        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        success_count = 0
        fail_count = 0

        insights_provider = os.getenv('AI_PROVIDER_INSIGHTS') or os.getenv('AI_PROVIDER_DEFAULT') or 'deepseek'
        insights_provider = insights_provider.lower()
        valid_providers = {'google', 'openai', 'deepseek', 'qwen', 'openrouter'}
        if insights_provider not in valid_providers:
            logger.warning(f"Unknown AI provider for insights: {insights_provider}, falling back to deepseek")
            insights_provider = 'deepseek'

        for profile in profiles:
            try:
                insight = loop.run_until_complete(
                    service.generate_insight(
                        profile=profile,
                        year=prev_year,
                        month=prev_month,
                        provider=insights_provider,
                        force_regenerate=False
                    )
                )

                if insight:
                    success_count += 1
                    logger.info(f"Generated insight for user {profile.telegram_id} for {prev_month}/{prev_year}")
                else:
                    logger.info(f"Skipped insight for user {profile.telegram_id} (insufficient data or no subscription)")

            except Exception as e:
                fail_count += 1
                logger.error(f"Error generating insight for user {profile.telegram_id}: {e}")

        logger.info(f"Insights generation completed: {success_count} successful, {fail_count} failed")

    except Exception as e:
        logger.error(f"Error in generate_monthly_insights task: {e}")

    finally:
        _shutdown_event_loop(loop, label="generate_monthly_insights")


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


@shared_task
def send_daily_admin_report():
    """Расширенный ежедневный отчет администратору с метриками мониторинга"""
    try:
        from expenses.models import (
            Profile, Expense, ExpenseCategory, Subscription, Income,
            UserAnalytics, AIServiceMetrics, SystemHealthCheck, 
            AffiliateCommission, RecurringPayment
        )
        from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2
        from django.utils import timezone
        from django.db.models import Q, Avg, Max, Min
        from datetime import timedelta
        import json

        def esc(v) -> str:
            return escape_markdown_v2(str(v))

        yesterday = timezone.localdate() - timedelta(days=1)
        today = timezone.localdate()
        week_ago = yesterday - timedelta(days=7)
        yesterday_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
        yesterday_end = timezone.make_aware(datetime.combine(yesterday, datetime.max.time()))

        # ===============================
        # БАЗОВАЯ СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ
        # ===============================
        total_users = Profile.objects.count()
        active_users = Expense.objects.filter(
            expense_date=yesterday
        ).values('profile').distinct().count()

        new_users = Profile.objects.filter(
            created_at__date=yesterday
        ).count()

        # WAU (Weekly Active Users) - пользователи с активностью за неделю
        weekly_active_users = Expense.objects.filter(
            expense_date__gte=week_ago,
            expense_date__lte=yesterday
        ).values('profile').distinct().count()

        # Retention: пользователи, зарегистрированные неделю назад и активные вчера
        week_ago_users = Profile.objects.filter(created_at__date=week_ago).values_list('id', flat=True)
        retained_users = Expense.objects.filter(
            profile_id__in=week_ago_users,
            expense_date=yesterday
        ).values('profile').distinct().count()
        retention_rate = (retained_users / len(week_ago_users) * 100) if week_ago_users else 0

        # ===============================
        # РАСШИРЕННАЯ СТАТИСТИКА РАСХОДОВ И ДОХОДОВ
        # ===============================
        expenses_stats = Expense.objects.filter(
            expense_date=yesterday
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            avg=Avg('amount'),
            max_expense=Max('amount'),
            ai_categorized=Count('id', filter=Q(ai_categorized=True))
        )

        # Статистика по доходам
        incomes_stats = Income.objects.filter(
            income_date=yesterday
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            avg=Avg('amount')
        )

        # AI категоризация эффективность
        ai_accuracy_rate = 0
        if expenses_stats['count'] and expenses_stats['count'] > 0:
            ai_accuracy_rate = (expenses_stats['ai_categorized'] / expenses_stats['count']) * 100

        # ===============================
        # ПОДПИСКИ И ФИНАНСЫ
        # ===============================
        new_subscriptions = Subscription.objects.filter(
            created_at__date=yesterday,
            payment_method__in=['stars', 'referral', 'promo']
        ).values('type').annotate(
            count=Count('id')
        ).order_by('type')

        # Подсчет подписок по типам
        subs_month = 0
        subs_six_months = 0
        subscription_revenue = 0
        
        for sub in new_subscriptions:
            if sub['type'] == 'month':
                subs_month = sub['count']
                subscription_revenue += sub['count'] * 150  # 150 звезд за месячную
            elif sub['type'] == 'six_months':
                subs_six_months = sub['count']
                subscription_revenue += sub['count'] * 750  # 750 звезд за полугодовую

        active_subscriptions = Subscription.objects.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).count()

        # Подписки истекающие в ближайшие 3 дня
        expiring_soon = Subscription.objects.filter(
            is_active=True,
            end_date__lte=timezone.now() + timedelta(days=3),
            end_date__gt=timezone.now()
        ).count()

        # ===============================
        # РЕФЕРАЛЬНАЯ ПРОГРАММА
        # ===============================
        affiliate_stats = AffiliateCommission.objects.filter(
            created_at__date=yesterday
        ).aggregate(
            new_commissions=Count('id'),
            total_commission_amount=Sum('commission_amount'),
            paid_commissions=Count('id', filter=Q(status='paid')),
            hold_commissions=Count('id', filter=Q(status='hold'))
        )

        # ===============================
        # AI СЕРВИСЫ МОНИТОРИНГ
        # ===============================
        ai_metrics = AIServiceMetrics.objects.filter(
            timestamp__gte=yesterday_start,
            timestamp__lte=yesterday_end
        ).aggregate(
            total_requests=Count('id'),
            successful_requests=Count('id', filter=Q(success=True)),
            avg_response_time=Avg('response_time'),
            max_response_time=Max('response_time'),
            total_tokens=Sum('tokens_used'),
            total_cost=Sum('estimated_cost')
        )

        ai_success_rate = 0
        if ai_metrics['total_requests']:
            ai_success_rate = (ai_metrics['successful_requests'] / ai_metrics['total_requests']) * 100

        # Статистика по сервисам
        openai_stats = AIServiceMetrics.objects.filter(
            timestamp__gte=yesterday_start,
            timestamp__lte=yesterday_end,
            service='openai'
        ).aggregate(
            requests=Count('id'),
            avg_time=Avg('response_time'),
            success_rate=Avg(Case(
                When(success=True, then=1.0),
                When(success=False, then=0.0),
                output_field=FloatField()
            ))
        )

        google_stats = AIServiceMetrics.objects.filter(
            timestamp__gte=yesterday_start,
            timestamp__lte=yesterday_end,
            service='google'
        ).aggregate(
            requests=Count('id'),
            avg_time=Avg('response_time'),
            success_rate=Avg(Case(
                When(success=True, then=1.0),
                When(success=False, then=0.0),
                output_field=FloatField()
            ))
        )

        deepseek_stats = AIServiceMetrics.objects.filter(
            timestamp__gte=yesterday_start,
            timestamp__lte=yesterday_end,
            service='deepseek'
        ).aggregate(
            requests=Count('id'),
            avg_time=Avg('response_time'),
            success_rate=Avg(Case(
                When(success=True, then=1.0),
                When(success=False, then=0.0),
                output_field=FloatField()
            ))
        )

        qwen_stats = AIServiceMetrics.objects.filter(
            timestamp__gte=yesterday_start,
            timestamp__lte=yesterday_end,
            service='qwen'
        ).aggregate(
            requests=Count('id'),
            avg_time=Avg('response_time'),
            success_rate=Avg(Case(
                When(success=True, then=1.0),
                When(success=False, then=0.0),
                output_field=FloatField()
            ))
        )

        # ===============================
        # СИСТЕМА И ПРОИЗВОДИТЕЛЬНОСТЬ
        # ===============================
        # Последняя проверка здоровья системы
        latest_health_check = SystemHealthCheck.objects.filter(
            timestamp__gte=yesterday_start
        ).order_by('-timestamp').first()

        system_status = "❓ Нет данных"
        if latest_health_check:
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '🚨'
            }
            system_status = f"{status_emoji.get(latest_health_check.overall_status, '❓')} {latest_health_check.overall_status.title()}"

        # ===============================
        # ПОЛЬЗОВАТЕЛЬСКАЯ АНАЛИТИКА
        # ===============================
        user_analytics = UserAnalytics.objects.filter(
            date=yesterday
        ).aggregate(
            total_messages=Sum('messages_sent'),
            total_voice_messages=Sum('voice_messages'),
            total_photos=Sum('photos_sent'),
            total_expenses_added=Sum('expenses_added'),
            total_incomes_added=Sum('incomes_added'),
            total_errors=Sum('errors_encountered'),
            total_pdf_reports=Sum('pdf_reports_generated'),
            total_cashback_calculated=Sum('cashback_calculated'),
            active_users_analytics=Count('profile', distinct=True)
        )

        # ===============================
        # РЕГУЛЯРНЫЕ ПЛАТЕЖИ
        # ===============================
        recurring_payments_processed = RecurringPayment.objects.filter(
            last_processed=yesterday
        ).count()

        # ===============================
        # ФОРМИРОВАНИЕ ОТЧЕТА
        # ===============================
        count_formatted = f"{(expenses_stats['count'] or 0):,}"
        total_formatted = f"{(expenses_stats['total'] or 0):,.0f}"
        
        # Форматируем дату с экранированием точек
        date_formatted = yesterday.strftime('%d.%m.%Y').replace('.', '\\.')
        
        # Формируем отчет
        report = (
            f"📊 \*Расширенный отчет ExpenseBot\*\n"
            f"📅 За {date_formatted}\n\n"
            
            f"👥 \*Пользователи:\*\n"
            f"  • Всего: {esc(f'{total_users:,}')}\n"
            f"  • Активных вчера: {esc(active_users)}\n"
            f"  • Активных за неделю: {esc(weekly_active_users)}\n"
            f"  • Новых регистраций: {esc(new_users)}\n"
            f"  • Retention \\(7d\\): {esc(f'{retention_rate:.1f}%')}\n\n"
            
            f"⭐ \*Подписки:\*\n"
            f"  • Активных всего: {esc(active_subscriptions)}\n"
            f"  • Истекают в 3 дня: {esc(expiring_soon)}\n"
            f"  • Куплено вчера \\(1 мес\\.\\): {esc(subs_month)}\n"
            f"  • Куплено вчера \\(6 мес\\.\\): {esc(subs_six_months)}\n"
        )
        
        if subscription_revenue > 0:
            report += f"  • Доход с подписок: {esc(subscription_revenue)} ⭐\n"

        # Реферальная программа
        if affiliate_stats['new_commissions']:
            report += (
                f"\n💼 \*Реферальная программа:\*\n"
                f"  • Новых комиссий: {esc(affiliate_stats['new_commissions'])}\n"
                f"  • Сумма комиссий: {esc(affiliate_stats['total_commission_amount'] or 0)} ⭐\n"
                f"  • На холде: {esc(affiliate_stats['hold_commissions'])}\n"
            )

        # AI сервисы
        if ai_metrics['total_requests']:
            avg_resp_time = ai_metrics.get('avg_response_time', 0) or 0
            total_tokens = ai_metrics.get('total_tokens', 0) or 0
            report += (
                f"\n🤖 \*AI сервисы:\*\n"
                f"  • Всего запросов: {esc(ai_metrics['total_requests'])}\n"
                f"  • Успешность: {esc(f'{ai_success_rate:.1f}%')}\n"
                f"  • Среднее время: {esc(f'{avg_resp_time:.2f}')}с\n"
                f"  • Использовано токенов: {esc(f'{total_tokens:,}')}\n"
            )
            
            if ai_metrics.get('total_cost'):
                total_cost = ai_metrics.get('total_cost', 0) or 0
                report += f"  • Приблизительная стоимость: ${esc(f'{total_cost:.3f}')}\n"
                
            if openai_stats['requests'] or google_stats['requests'] or deepseek_stats['requests'] or qwen_stats['requests']:
                openai_success = (openai_stats.get('success_rate') or 0) * 100
                google_success = (google_stats.get('success_rate') or 0) * 100
                deepseek_success = (deepseek_stats.get('success_rate') or 0) * 100
                qwen_success = (qwen_stats.get('success_rate') or 0) * 100
                
                if openai_stats['requests']:
                    report += (
                        f"  • OpenAI: {esc(openai_stats['requests'])} зап\\., "
                        f"{esc(f'{openai_success:.0f}')}% успех\n"
                    )
                if google_stats['requests']:
                    report += (
                        f"  • Google: {esc(google_stats['requests'])} зап\\., "
                        f"{esc(f'{google_success:.0f}')}% успех\n"
                    )
                if deepseek_stats['requests']:
                    report += (
                        f"  • DeepSeek: {esc(deepseek_stats['requests'])} зап\\., "
                        f"{esc(f'{deepseek_success:.0f}')}% успех\n"
                    )
                if qwen_stats['requests']:
                    report += (
                        f"  • Qwen: {esc(qwen_stats['requests'])} зап\\., "
                        f"{esc(f'{qwen_success:.0f}')}% успех\n"
                    )

        # Аналитика активности
        if user_analytics['active_users_analytics']:
            report += (
                f"\n📈 \*Активность пользователей:\*\n"
                f"  • Сообщений: {esc(user_analytics['total_messages'] or 0)}\n"
                f"  • Голосовых: {esc(user_analytics['total_voice_messages'] or 0)}\n"
                f"  • Фото: {esc(user_analytics['total_photos'] or 0)}\n"
                f"  • AI категоризация: {esc(f'{ai_accuracy_rate:.1f}%')}\n"
            )
            
            if user_analytics['total_pdf_reports']:
                report += f"  • PDF отчетов: {esc(user_analytics['total_pdf_reports'])}\n"
            
            if user_analytics['total_cashback_calculated']:
                cashback_calc = user_analytics['total_cashback_calculated']
                report += f"  • Кешбэк рассчитан: {esc(f'{cashback_calc:.0f}')} ₽\n"

        # Регулярные платежи
        if recurring_payments_processed > 0:
            report += f"\n🔄 \*Регулярные платежи:\* {esc(recurring_payments_processed)} обработано\n"

        # Статус системы
        report += f"\n⚡ \*Статус системы:\* {esc(system_status)}\n"

        # Ошибки
        if user_analytics['total_errors']:
            report += f"\n⚠️ \*Ошибки:\* {esc(user_analytics['total_errors'])} за день\n"

        report += f"\n⏰ Отчет сформирован: {esc(datetime.now().strftime('%H:%M'))}"

        # Отправляем отчет асинхронно
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(send_admin_alert(report, disable_notification=True))
        finally:
            _shutdown_event_loop(loop, label="send_daily_admin_report")

        logger.info(f"Расширенный ежедневный отчет за {yesterday} отправлен администратору")

    except Exception as e:
        logger.error(f"Ошибка отправки ежедневного отчета: {e}", exc_info=True)


@shared_task
def system_health_check():
    """Периодическая проверка здоровья системы и сохранение метрик"""
    try:
        from expenses.models import SystemHealthCheck, AIServiceMetrics
        from django.db import connection
        from django.core.cache import cache
        from django.utils import timezone
        from django.conf import settings
        import redis
        import requests
        import psutil
        import os
        from datetime import timedelta
        
        logger.info("Запуск проверки здоровья системы")
        
        # Временные метки
        check_start = timezone.now()
        issues = []
        
        # =====================================
        # 1. БАЗА ДАННЫХ
        # =====================================
        database_status = False
        database_response_time = None
        try:
            db_start = timezone.now()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM users_profile")
                result = cursor.fetchone()
            database_response_time = (timezone.now() - db_start).total_seconds()
            database_status = True
            logger.info(f"Database check: OK ({database_response_time:.3f}s)")
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            issues.append(f"Database connection failed: {str(e)[:100]}")
        
        # =====================================
        # 2. REDIS
        # =====================================
        redis_status = False
        redis_response_time = None
        redis_memory_usage = None
        try:
            redis_start = timezone.now()
            r = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=int(getattr(settings, 'REDIS_PORT', 6379)),
                db=0,
                socket_connect_timeout=5
            )
            r.ping()
            redis_response_time = (timezone.now() - redis_start).total_seconds()
            
            # Получаем информацию о памяти
            info = r.info('memory')
            redis_memory_usage = info.get('used_memory', 0)
            
            redis_status = True
            logger.info(f"Redis check: OK ({redis_response_time:.3f}s, {redis_memory_usage//1024//1024}MB)")
        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            issues.append(f"Redis connection failed: {str(e)[:100]}")
        
        # =====================================
        # 3. TELEGRAM API
        # =====================================
        telegram_api_status = False
        telegram_api_response_time = None
        try:
            telegram_start = timezone.now()
            bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
            if bot_token:
                response = requests.get(
                    f"https://api.telegram.org/bot{bot_token}/getMe",
                    timeout=10
                )
                if response.status_code == 200:
                    telegram_api_response_time = (timezone.now() - telegram_start).total_seconds()
                    telegram_api_status = True
                    logger.info(f"Telegram API check: OK ({telegram_api_response_time:.3f}s)")
                else:
                    issues.append(f"Telegram API returned status {response.status_code}")
            else:
                issues.append("Telegram bot token not configured")
        except Exception as e:
            logger.error(f"Telegram API check failed: {e}")
            issues.append(f"Telegram API check failed: {str(e)[:100]}")
        
        # =====================================
        # 4. OPENAI API
        # =====================================
        openai_api_status = False
        openai_api_response_time = None
        try:
            openai_start = timezone.now()
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                response = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    timeout=10
                )
                if response.status_code == 200:
                    openai_api_response_time = (timezone.now() - openai_start).total_seconds()
                    openai_api_status = True
                    logger.info(f"OpenAI API check: OK ({openai_api_response_time:.3f}s)")
                else:
                    issues.append(f"OpenAI API returned status {response.status_code}")
            else:
                logger.info("OpenAI API key not configured - skipping check")
        except Exception as e:
            logger.error(f"OpenAI API check failed: {e}")
            issues.append(f"OpenAI API check failed: {str(e)[:100]}")
        
        # =====================================
        # 5. GOOGLE AI API
        # =====================================
        google_ai_api_status = False
        google_ai_api_response_time = None
        try:
            google_start = timezone.now()
            google_key = os.getenv('GOOGLE_AI_KEY')
            if google_key:
                # Простая проверка доступности API
                response = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}",
                    timeout=10
                )
                if response.status_code == 200:
                    google_ai_api_response_time = (timezone.now() - google_start).total_seconds()
                    google_ai_api_status = True
                    logger.info(f"Google AI API check: OK ({google_ai_api_response_time:.3f}s)")
                else:
                    issues.append(f"Google AI API returned status {response.status_code}")
            else:
                logger.info("Google AI API key not configured - skipping check")
        except Exception as e:
            logger.error(f"Google AI API check failed: {e}")
            issues.append(f"Google AI API check failed: {str(e)[:100]}")

        # =====================================
        # 5a. DEEPSEEK API
        # =====================================
        deepseek_api_status = False
        deepseek_api_response_time = None
        try:
            ds_start = timezone.now()
            ds_key = os.getenv('DEEPSEEK_API_KEY')
            if ds_key:
                response = requests.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {ds_key}"},
                    timeout=10
                )
                if response.status_code == 200:
                    deepseek_api_response_time = (timezone.now() - ds_start).total_seconds()
                    deepseek_api_status = True
                    logger.info(f"DeepSeek API check: OK ({deepseek_api_response_time:.3f}s)")
                else:
                    issues.append(f"DeepSeek API returned status {response.status_code}")
            else:
                logger.info("DeepSeek API key not configured - skipping check")
        except Exception as e:
            logger.error(f"DeepSeek API check failed: {e}")
            issues.append(f"DeepSeek API check failed: {str(e)[:100]}")

        # =====================================
        # 5b. QWEN (DASHSCOPE) API
        # =====================================
        qwen_api_status = False
        qwen_api_response_time = None
        try:
            qwen_start = timezone.now()
            qwen_key = os.getenv('DASHSCOPE_API_KEY')
            if qwen_key:
                # DashScope requires explicit model access usually, but we can try a simple list or specific model info
                # Correct endpoint for DashScope is strict. Trying compatible-mode endpoint.
                response = requests.get(
                    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
                    headers={"Authorization": f"Bearer {qwen_key}"},
                    timeout=10
                )
                if response.status_code == 200:
                    qwen_api_response_time = (timezone.now() - qwen_start).total_seconds()
                    qwen_api_status = True
                    logger.info(f"Qwen API check: OK ({qwen_api_response_time:.3f}s)")
                else:
                    issues.append(f"Qwen API returned status {response.status_code}")
            else:
                logger.info("Qwen API key not configured - skipping check")
        except Exception as e:
            logger.error(f"Qwen API check failed: {e}")
            issues.append(f"Qwen API check failed: {str(e)[:100]}")
        
        # =====================================
        # 6. CELERY
        # =====================================
        celery_status = False
        celery_workers_count = None
        celery_queue_size = None
        try:
            # Импортируем celery app
            from expense_bot.celery import app
            
            # Получаем информацию о воркерах
            inspect = app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                celery_workers_count = len(stats)
                celery_status = True
                
                # Получаем размер очередей
                active_queues = inspect.active_queues()
                queue_lengths = {}
                for worker, queues in (active_queues or {}).items():
                    for queue in queues:
                        queue_name = queue.get('name', 'default')
                        # Здесь можно добавить получение длины очереди из Redis
                        # Пока просто считаем что очередь пуста если воркеры активны
                        queue_lengths[queue_name] = 0
                
                celery_queue_size = sum(queue_lengths.values())
                logger.info(f"Celery check: OK ({celery_workers_count} workers)")
            else:
                issues.append("No active Celery workers found")
        except Exception as e:
            logger.error(f"Celery check failed: {e}")
            issues.append(f"Celery check failed: {str(e)[:100]}")
        
        # =====================================
        # 7. СИСТЕМНЫЕ МЕТРИКИ
        # =====================================
        disk_free_gb = None
        memory_usage_percent = None
        cpu_usage_percent = None
        try:
            # Использование диска
            disk_usage = psutil.disk_usage('/')
            disk_free_gb = disk_usage.free / (1024**3)  # В гигабайтах
            
            # Использование памяти
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent
            
            # Использование CPU (среднее за 1 секунду)
            cpu_usage_percent = psutil.cpu_percent(interval=1)
            
            logger.info(f"System metrics: {disk_free_gb:.1f}GB free, {memory_usage_percent:.1f}% RAM, {cpu_usage_percent:.1f}% CPU")
            
            # Добавляем предупреждения
            if disk_free_gb < 1.0:  # Меньше 1 ГБ свободного места
                issues.append(f"Low disk space: {disk_free_gb:.1f}GB free")
            
            if memory_usage_percent > 90:
                issues.append(f"High memory usage: {memory_usage_percent:.1f}%")
            
            if cpu_usage_percent > 80:
                issues.append(f"High CPU usage: {cpu_usage_percent:.1f}%")
                
        except Exception as e:
            logger.error(f"System metrics collection failed: {e}")
            issues.append(f"System metrics failed: {str(e)[:100]}")
        
        # =====================================
        # 8. ОПРЕДЕЛЕНИЕ ОБЩЕГО СТАТУСА
        # =====================================
        critical_components = [database_status, redis_status]
        important_components = [telegram_api_status, celery_status]
        
        if all(critical_components):
            if all(important_components):
                overall_status = 'healthy'
            else:
                overall_status = 'degraded'
        else:
            overall_status = 'unhealthy'
        
        # =====================================
        # 9. СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
        # =====================================
        health_check = SystemHealthCheck.objects.create(
            timestamp=check_start,
            database_status=database_status,
            database_response_time=database_response_time,
            redis_status=redis_status,
            redis_response_time=redis_response_time,
            redis_memory_usage=redis_memory_usage,
            telegram_api_status=telegram_api_status,
            telegram_api_response_time=telegram_api_response_time,
            openai_api_status=openai_api_status,
            openai_api_response_time=openai_api_response_time,
            google_ai_api_status=google_ai_api_status,
            google_ai_api_response_time=google_ai_api_response_time,
            deepseek_api_status=deepseek_api_status,
            deepseek_api_response_time=deepseek_api_response_time,
            qwen_api_status=qwen_api_status,
            qwen_api_response_time=qwen_api_response_time,
            celery_status=celery_status,
            celery_workers_count=celery_workers_count,
            celery_queue_size=celery_queue_size,
            disk_free_gb=disk_free_gb,
            memory_usage_percent=memory_usage_percent,
            cpu_usage_percent=cpu_usage_percent,
            overall_status=overall_status,
            issues=issues
        )
        
        # =====================================
        # 10. ОТПРАВКА АЛЕРТОВ ЕСЛИ НЕОБХОДИМО
        # =====================================
        if overall_status in ['unhealthy', 'degraded'] or issues:
            try:
                from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2
                
                status_emoji = {'healthy': '✅', 'degraded': '⚠️', 'unhealthy': '🚨'}
                
                alert_message = (
                    f"{status_emoji.get(overall_status, '❓')} *Системный алерт*\n\n"
                    f"Статус: {escape_markdown_v2(overall_status.title())}\n"
                    f"Время: {escape_markdown_v2(check_start.strftime('%H:%M:%S'))}\n\n"
                )
                
                if issues:
                    alert_message += "*Проблемы:*\n"
                    for issue in issues[:5]:  # Ограничиваем количество проблем
                        alert_message += f"• {escape_markdown_v2(issue)}\n"
                    
                    if len(issues) > 5:
                        alert_message += f"• ... и еще {len(issues) - 5} проблем\n"
                
                # Отправляем алерт асинхронно
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(send_admin_alert(alert_message))
                finally:
                    _shutdown_event_loop(loop, label="system_health_check")
                
                logger.warning(f"System health alert sent: {overall_status} with {len(issues)} issues")
            
            except Exception as e:
                logger.error(f"Failed to send health alert: {e}")
        
        # =====================================
        # 11. ОЧИСТКА СТАРЫХ ЗАПИСЕЙ
        # =====================================
        try:
            # Удаляем записи старше 30 дней
            old_threshold = timezone.now() - timedelta(days=30)
            deleted_count, _ = SystemHealthCheck.objects.filter(
                timestamp__lt=old_threshold
            ).delete()
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old health check records")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old health checks: {e}")
        
        total_time = (timezone.now() - check_start).total_seconds()
        logger.info(f"System health check completed in {total_time:.2f}s: {overall_status}")
        
        return {
            'status': overall_status,
            'timestamp': check_start.isoformat(),
            'total_time': total_time,
            'issues_count': len(issues)
        }
        
    except Exception as e:
        logger.error(f"System health check task failed: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task
def collect_daily_analytics():
    """Сбор аналитических данных за день (запускается в конце дня)"""
    try:
        from expenses.models import (
            Profile, Expense, Income, UserAnalytics, 
            AIServiceMetrics, Subscription, AffiliateCommission
        )
        from django.utils import timezone
        from django.db.models import Count, Sum, Avg, Q
        from datetime import timedelta
        import json

        logger.info("Начинаем сбор ежедневной аналитики")
        
        # Вчерашняя дата (данные за которую собираем)
        target_date = timezone.localdate() - timedelta(days=1)
        target_start = timezone.make_aware(datetime.combine(target_date, time.min))
        target_end = timezone.make_aware(datetime.combine(target_date, time.max))
        
        processed_profiles = 0
        created_analytics = 0
        
        # Получаем всех пользователей, которые были активны вчера
        # (добавляли расходы, доходы, или имели другую активность)
        active_profiles = Profile.objects.filter(
            Q(expenses__created_at__gte=target_start, expenses__created_at__lte=target_end) |
            Q(incomes__created_at__gte=target_start, incomes__created_at__lte=target_end) |
            Q(subscriptions__created_at__gte=target_start, subscriptions__created_at__lte=target_end)
        ).distinct()
        
        logger.info(f"Найдено {active_profiles.count()} активных пользователей за {target_date}")
        
        for profile in active_profiles:
            try:
                # Проверяем, нет ли уже записи за этот день
                existing_analytics = UserAnalytics.objects.filter(
                    profile=profile,
                    date=target_date
                ).first()
                
                # Собираем статистику по расходам
                expenses = Expense.objects.filter(
                    profile=profile,
                    created_at__gte=target_start,
                    created_at__lte=target_end
                )
                
                expenses_stats = expenses.aggregate(
                    count=Count('id'),
                    ai_categorized_count=Count('id', filter=Q(ai_categorized=True)),
                    manual_categorized_count=Count('id', filter=Q(ai_categorized=False)),
                )
                
                # Собираем статистику по доходам
                incomes = Income.objects.filter(
                    profile=profile,
                    created_at__gte=target_start,
                    created_at__lte=target_end
                )
                
                incomes_count = incomes.count()
                
                # Собираем статистику по категориям (топ-5 используемых)
                categories_used = {}
                for expense in expenses:
                    if expense.category:
                        cat_id = str(expense.category.id)
                        categories_used[cat_id] = categories_used.get(cat_id, 0) + 1
                
                # Статистика по AI сервисам (приблизительно - по количеству AI категоризаций)
                ai_categorizations = expenses_stats['ai_categorized_count'] or 0
                manual_categorizations = expenses_stats['manual_categorized_count'] or 0
                
                # Рассчитываем кешбэк (если есть логика)
                cashback_calculated = 0  # Можно добавить расчет кешбэка если нужно
                cashback_transactions = 0
                
                # Подсчитываем ошибки (пока заглушка, можно интегрировать с логами)
                errors_encountered = 0
                error_types = {}
                
                # Примерное время сессии (заглушка)
                total_session_time = 0
                peak_hour = None
                
                # PDF отчеты (заглушка - можно интегрировать с логикой отчетов)
                pdf_reports_generated = 0
                
                # Recurring payments processed (для данного пользователя)
                recurring_payments_processed = 0
                
                # Budget checks (заглушка)
                budget_checks = 0
                
                # messages_sent — примерно по количеству расходов (заглушка)
                messages_sent = expenses_stats['count'] or 0
                # voice_messages и photos_sent инкрементируются в реальном времени
                # (VoiceToTextMiddleware и handle_photo_expense),
                # поэтому НЕ перезаписываем их нулями — сохраняем текущее значение из БД
                
                # Определяем команды (заглушка)
                commands_used = {}
                if expenses_stats['count']:
                    commands_used['expense_add'] = expenses_stats['count']
                if incomes_count:
                    commands_used['income_add'] = incomes_count
                
                # Создаем или обновляем запись аналитики
                if existing_analytics:
                    # Обновляем существующую запись
                    existing_analytics.messages_sent = messages_sent
                    # voice_messages и photos_sent НЕ трогаем —
                    # они инкрементируются в реальном времени из middleware/handlers
                    existing_analytics.commands_used = commands_used
                    existing_analytics.expenses_added = expenses_stats['count'] or 0
                    existing_analytics.incomes_added = incomes_count
                    existing_analytics.categories_used = categories_used
                    existing_analytics.ai_categorizations = ai_categorizations
                    existing_analytics.manual_categorizations = manual_categorizations
                    existing_analytics.cashback_calculated = cashback_calculated
                    existing_analytics.cashback_transactions = cashback_transactions
                    existing_analytics.errors_encountered = errors_encountered
                    existing_analytics.error_types = error_types
                    existing_analytics.total_session_time = total_session_time
                    existing_analytics.peak_hour = peak_hour
                    existing_analytics.pdf_reports_generated = pdf_reports_generated
                    existing_analytics.recurring_payments_processed = recurring_payments_processed
                    existing_analytics.budget_checks = budget_checks
                    existing_analytics.save()
                    
                    logger.info(f"Updated analytics for user {profile.telegram_id} for {target_date}")
                else:
                    # Создаем новую запись
                    # voice_messages и photos_sent не передаём — используется default=0.
                    # Если запись уже была создана через increment_analytics_counter,
                    # она попадёт в existing_analytics выше.
                    UserAnalytics.objects.create(
                        profile=profile,
                        date=target_date,
                        messages_sent=messages_sent,
                        commands_used=commands_used,
                        expenses_added=expenses_stats['count'] or 0,
                        incomes_added=incomes_count,
                        categories_used=categories_used,
                        ai_categorizations=ai_categorizations,
                        manual_categorizations=manual_categorizations,
                        cashback_calculated=cashback_calculated,
                        cashback_transactions=cashback_transactions,
                        errors_encountered=errors_encountered,
                        error_types=error_types,
                        total_session_time=total_session_time,
                        peak_hour=peak_hour,
                        pdf_reports_generated=pdf_reports_generated,
                        recurring_payments_processed=recurring_payments_processed,
                        budget_checks=budget_checks
                    )
                    created_analytics += 1
                    logger.debug(f"Created analytics for user {profile.telegram_id} for {target_date}")
                
                processed_profiles += 1
                
            except Exception as e:
                logger.error(f"Error processing analytics for user {profile.telegram_id}: {e}")
                continue
        
        # Очистка старых записей аналитики (старше 90 дней)
        try:
            old_threshold = timezone.now() - timedelta(days=90)
            deleted_count, _ = UserAnalytics.objects.filter(
                date__lt=old_threshold.date()
            ).delete()
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old analytics records")
        
        except Exception as e:
            logger.error(f"Failed to cleanup old analytics: {e}")
        
        logger.info(f"Daily analytics collection completed: {processed_profiles} users processed, {created_analytics} new records created")
        
        return {
            'date': target_date.isoformat(),
            'processed_profiles': processed_profiles,
            'created_analytics': created_analytics,
            'updated_analytics': processed_profiles - created_analytics
        }
    
    except Exception as e:
        logger.error(f"Daily analytics collection failed: {e}", exc_info=True)
        return {'error': str(e)}


@shared_task
def process_recurring_payments():
    """Process recurring payments for today at 12:00"""
    bot = None
    loop = None
    try:
        from bot.services.recurring import process_recurring_payments_for_today
        from bot.utils.expense_messages import format_expense_added_message, format_income_added_message
        from bot.utils import get_text
        from aiogram import Bot
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        # Use main bot token for user-facing notifications
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Process recurring payments
        processed_count, processed_payments = loop.run_until_complete(
            process_recurring_payments_for_today()
        )
        
        # Отправляем уведомления пользователям о списанных ежемесячных платежах
        for payment_info in processed_payments:
            try:
                user_id = payment_info['user_id']
                operation = payment_info['operation']
                operation_type = payment_info.get('operation_type')
                payment = payment_info['payment']
                
                # Получаем язык пользователя из профиля
                from expenses.models import Profile
                profile = Profile.objects.filter(telegram_id=user_id).first()
                user_lang = profile.language_code if profile else 'ru'
                
                cashback_text = ""
                
                # Форматируем сообщение, как при ручном создании операции
                if operation_type == 'income':
                    text = loop.run_until_complete(
                        format_income_added_message(
                            income=operation,
                            category=getattr(operation, 'category', None),
                            is_recurring=True,
                            lang=user_lang
                        )
                    )
                    edit_callback = f"edit_income_{operation.id}"
                else:
                    text = loop.run_until_complete(
                        format_expense_added_message(
                            expense=operation,
                            category=operation.category,
                            cashback_text=cashback_text,
                            is_recurring=True,
                            lang=user_lang
                        )
                    )
                    edit_callback = f"edit_expense_{operation.id}"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_text('edit_button', user_lang),
                            callback_data=edit_callback
                        )
                    ]
                ])
                
                loop.run_until_complete(
                    bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                )
                
                logger.info(f"Sent notification to user {user_id} about recurring payment")
                
            except Exception as e:
                logger.error(f"Error sending notification to user {payment_info.get('user_id')}: {e}")
        
        logger.info(f"Processed {processed_count} recurring payments")
        
    except Exception as e:
        logger.error(f"Error in process_recurring_payments task: {e}")

    finally:
        _shutdown_event_loop(loop, bot=bot, label="process_recurring_payments")


@shared_task
def update_keywords_weights(expense_id: int, old_category_id: int, new_category_id: int):
    """
    Обновление ключевых слов после ручного изменения категории.
    ИСПОЛЬЗУЕТ УНИВЕРСАЛЬНЫЙ КОД из keyword_service.py

    Сохраняет ПОЛНУЮ ФРАЗУ как keyword (не отдельные слова!)

    ВАЖНО: Ключевые слова должны быть уникальными - одно слово может быть только в одной категории!
    Если слово уже существует в другой категории, оно будет удалено оттуда.
    """
    try:
        from expenses.models import Expense, ExpenseCategory
        from bot.utils.keyword_service import normalize_keyword_text, ensure_unique_keyword

        # Получаем объекты
        expense = Expense.objects.select_related('profile').get(id=expense_id)
        new_category = ExpenseCategory.objects.select_related('profile').get(id=new_category_id)
        old_category = ExpenseCategory.objects.get(id=old_category_id) if old_category_id else None

        # Нормализуем description как ЦЕЛУЮ ФРАЗУ
        keyword = normalize_keyword_text(expense.description)

        if not keyword or len(keyword) < 3:
            logger.info(f"Keyword too short after normalization, skipping for expense {expense_id}")
            return

        # Обеспечиваем уникальность и создаем/обновляем keyword
        kw_obj, created, removed = ensure_unique_keyword(
            profile=expense.profile,
            category=new_category,
            word=keyword,
            is_income=False
        )

        if not kw_obj:
            logger.warning(f"Failed to create/update keyword '{keyword}' for expense {expense_id}")
            return

        # Увеличиваем счетчик использований (ручное исправление = сильный сигнал)
        kw_obj.usage_count += 1
        kw_obj.save()

        # Логирование
        old_cat_name = old_category.name if old_category else 'None'
        new_cat_name = new_category.name or new_category.name_ru or new_category.name_en or f'ID:{new_category.id}'

        action = "Created" if created else "Updated"
        logger.info(
            f"{action} keyword '{keyword}' for expense {expense_id}: "
            f"'{old_cat_name}' -> '{new_cat_name}' "
            f"(removed {removed} duplicates, user {expense.profile.telegram_id})"
        )

        # Очистка старых keywords если их слишком много
        cleanup_old_keywords(profile_id=expense.profile.id, is_income=False)

        # Проверяем лимит 50 слов на категорию
        check_category_keywords_limit(new_category)
        if old_category:
            check_category_keywords_limit(old_category)

        logger.info(f"Successfully updated keywords weights for expense {expense_id}")

    except Exception as e:
        logger.error(f"Error in update_keywords_weights task: {e}", exc_info=True)


def cleanup_old_keywords(profile_id: int, is_income: bool = False):
    """
    Очистка старых ключевых слов если их больше 1000 у пользователя.
    Удаляет самые давно неиспользуемые слова (по полю last_used).

    Args:
        profile_id: ID профиля пользователя
        is_income: True для доходов, False для расходов
    """
    try:
        from expenses.models import CategoryKeyword, IncomeCategoryKeyword

        # Выбираем модель в зависимости от типа
        KeywordModel = IncomeCategoryKeyword if is_income else CategoryKeyword

        # Подсчитываем общее количество слов пользователя
        total = KeywordModel.objects.filter(
            category__profile_id=profile_id
        ).count()

        if total >= 1000:
            logger.info(f"User {profile_id} has {total} keywords, cleaning up...")

            # Удаляем 100 самых давно неиспользуемых слов (по last_used, ascending)
            keywords_to_delete = KeywordModel.objects.filter(
                category__profile_id=profile_id
            ).order_by('last_used')[:100].values_list('id', flat=True)

            # Удалить только 100 самых старых по последнему использованию
            deleted = KeywordModel.objects.filter(
                id__in=list(keywords_to_delete)
            ).delete()

            logger.info(f"Deleted {deleted[0]} old keywords for user {profile_id}")

            # Финальное количество
            final_total = KeywordModel.objects.filter(
                category__profile_id=profile_id
            ).count()

            logger.info(f"Cleanup complete for user {profile_id}: {total} -> {final_total} keywords")

    except Exception as e:
        logger.error(f"Error in cleanup_old_keywords for user {profile_id}: {e}")


@shared_task
def learn_keywords_on_create(expense_id: int, category_id: int):
    """
    Обучение системы при создании новой траты с AI-категоризацией.
    ИСПОЛЬЗУЕТ УНИВЕРСАЛЬНЫЙ КОД из keyword_service.py

    Сохраняет ОЧИЩЕННУЮ ФРАЗУ description как единый keyword:
    - Удаляет stop words (предлоги, глаголы, валюты)
    - Нормализует (lowercase, убирает emoji/пунктуацию)
    - Если фраза слишком длинная (>4 слов) — не сохраняет

    Пример: "Вчера купил кофе в старбаксе 350р" → "кофе старбаксе"
    """
    try:
        from expenses.models import Expense, ExpenseCategory
        from bot.utils.keyword_service import ensure_unique_keyword

        expense = Expense.objects.select_related('profile', 'category').get(id=expense_id)
        category = ExpenseCategory.objects.get(id=category_id)

        if not category:
            return

        # ensure_unique_keyword сам нормализует и удаляет stop words через prepare_keyword_for_save()
        # Передаём оригинальный description — вся очистка происходит внутри
        kw_obj, created, removed = ensure_unique_keyword(
            profile=expense.profile,
            category=category,
            word=expense.description,  # ← оригинальный текст, очистка внутри
            is_income=False
        )

        if not kw_obj:
            return

        # Увеличиваем счетчик
        if created:
            kw_obj.usage_count = 1
        else:
            kw_obj.usage_count += 1

        kw_obj.save()

        # Получаем имя категории для логов
        cat_name = category.name or category.name_ru or category.name_en or f'ID:{category.id}'

        logger.info(
            f"Learned keyword '{kw_obj.keyword}' for expense category '{cat_name}' "
            f"(user {expense.profile.telegram_id}, original: '{expense.description}', removed {removed} duplicates)"
        )

        # Очистка старых ключевых слов только если создали новый
        if created:
            cleanup_old_keywords(profile_id=expense.profile.id, is_income=False)

        # Проверяем лимит 50 слов на категорию
        check_category_keywords_limit(category)

    except Exception as e:
        logger.error(f"Error in learn_keywords_on_create: {e}")


def extract_words_from_description(description: str) -> List[str]:
    """Извлекает значимые слова из описания расхода"""
    # Удаляем числа, валюту, знаки препинания
    text = re.sub(r'\d+', '', description)
    # ВАЖНО: не удаляем букву "р" - она часть многих слов (гренки, горох и т.д.)
    # Валюту "р" фильтруем через стоп-слова
    text = re.sub(r'[₽$€£¥\.,"\'!?;:\-\(\)]', ' ', text)

    # Разбиваем на слова
    words = text.lower().split()

    # Фильтруем стоп-слова
    stop_words = {
        'и', 'в', 'на', 'с', 'за', 'по', 'для', 'от', 'до', 'из',
        'или', 'но', 'а', 'к', 'у', 'о', 'об', 'под', 'над',
        'купил', 'купила', 'купили', 'взял', 'взяла', 'взяли',
        'потратил', 'потратила', 'потратили', 'оплатил', 'оплатила',
        'рубль', 'рубля', 'рублей', 'руб', 'р', 'тыс', 'тысяч'
    }

    # Фильтруем слова
    filtered_words = []
    for word in words:
        word = word.strip()
        if word and len(word) >= 3 and word not in stop_words:
            filtered_words.append(word)

    return filtered_words


def filter_keywords_for_saving(words: List[str]) -> List[str]:
    """
    Фильтрует ключевые слова перед сохранением в БД по правилам:
    1. Если слов > 4 → не сохраняем ничего (список покупок)
    2. Если слов > 2 И есть глагол → удаляем глаголы и берем максимум 2 слова
    3. В остальных случаях → берем максимум 3 слова

    Args:
        words: Список отфильтрованных слов из описания

    Returns:
        Список слов для сохранения в БД (0-3 слова)
    """
    # Правило 1: Более 4 слов → список покупок, не сохраняем
    if len(words) > 4:
        logger.debug(f"Too many words ({len(words)} > 4), skipping keyword saving")
        return []

    # Список распространенных глаголов (расширенный список)
    verbs = {
        # Уже в стоп-словах, но на всякий случай дублируем
        'купил', 'купила', 'купили', 'взял', 'взяла', 'взяли',
        'потратил', 'потратила', 'потратили', 'оплатил', 'оплатила', 'оплатили',
        # Дополнительные глаголы
        'заказал', 'заказала', 'заказали', 'приобрел', 'приобрела', 'приобрели',
        'купила', 'съел', 'съела', 'съели', 'выпил', 'выпила', 'выпили',
        'сходил', 'сходила', 'сходили', 'отдал', 'отдала', 'отдали',
        'заплатил', 'заплатила', 'заплатили', 'внес', 'внесла', 'внесли',
        'перевел', 'перевела', 'перевели', 'отправил', 'отправила', 'отправили',
        'положил', 'положила', 'положили', 'снял', 'сняла', 'сняли'
    }

    # Ищем глаголы в списке слов
    words_without_verbs = [word for word in words if word not in verbs]
    has_verbs = len(words_without_verbs) < len(words)

    # Правило 2: Более 2 слов И есть глагол → берем 2 слова без глагола
    if len(words) > 2 and has_verbs:
        result = words_without_verbs[:2]
        logger.debug(f"Found verbs in {len(words)} words, saving first 2 non-verb words: {result}")
        return result

    # Правило 3: В остальных случаях → максимум 3 слова
    result = words[:3]
    logger.debug(f"Saving up to 3 words from {len(words)} total: {result}")
    return result


def check_category_keywords_limit(category):
    """
    Проверяет и ограничивает количество ключевых слов в категории (максимум 50)

    Работает как для расходов (ExpenseCategory), так и для доходов (IncomeCategory)
    через duck typing - определяет тип модели автоматически.
    """
    from expenses.models import CategoryKeyword, IncomeCategoryKeyword, ExpenseCategory, IncomeCategory

    try:
        # Определяем тип категории через duck typing
        if isinstance(category, IncomeCategory):
            KeywordModel = IncomeCategoryKeyword
            category_type = "income"
        elif isinstance(category, ExpenseCategory):
            KeywordModel = CategoryKeyword
            category_type = "expense"
        else:
            logger.warning(f"Unknown category type: {type(category)}")
            return

        keywords = KeywordModel.objects.filter(category=category)

        if keywords.count() > 50:
            # Оставляем топ-50 по usage_count
            keywords_list = list(keywords)
            keywords_list.sort(key=lambda k: k.usage_count, reverse=True)

            # Удаляем слова с наименьшим использованием
            keywords_to_delete = keywords_list[50:]
            for kw in keywords_to_delete:
                cat_name = category.name or category.name_ru or category.name_en or '(no name)'
                logger.info(f"Deleting {category_type} keyword '{kw.keyword}' from category '{cat_name}' (low usage)")
                kw.delete()

            cat_name = category.name or category.name_ru or category.name_en or '(no name)'
            logger.info(f"Limited {category_type} keywords for category '{cat_name}' to 50 items")

    except Exception as e:
        logger.error(f"Error checking category keywords limit: {e}")


# Backward compatible entry-point that now calls the new task implementation
@shared_task
def process_held_affiliate_commissions():
    from expenses.tasks import process_affiliate_commissions

    logger.warning(
        "process_held_affiliate_commissions is deprecated; routing to expenses.tasks.process_affiliate_commissions"
    )
    return process_affiliate_commissions()


@shared_task
def update_top5_keyboards():
    """Ежедневно в 05:00 MSK: пересчитать Топ‑5 и обновить клавиатуры закреплённых сообщений."""
    bot = None
    loop = None
    try:
        from expenses.models import Profile, Top5Snapshot, Top5Pin
        from bot.services.top5 import (
            calculate_top5_sync, save_snapshot, build_top5_keyboard, get_profiles_with_activity
        )
        from datetime import date
        from calendar import monthrange

        # Бот для вызова editMessageReplyMarkup
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Окно: последние 90 дней включительно (rolling)
        today = date.today()
        from datetime import timedelta
        window_end = today
        window_start = today - timedelta(days=89)

        # Пользователи с активностью
        profiles = loop.run_until_complete(get_profiles_with_activity(window_start, window_end))

        updated = 0
        for profile in profiles:
            try:
                items, digest = loop.run_until_complete(calculate_top5_sync(profile, window_start, window_end))
                snap = Top5Snapshot.objects.filter(profile=profile).first()
                if not snap or snap.hash != digest or snap.window_start != window_start or snap.window_end != window_end:
                    loop.run_until_complete(
                        save_snapshot(profile, window_start, window_end, items, digest)
                    )
                # Обновляем закреплённое сообщение, если знаем ids
                pin = Top5Pin.objects.filter(profile=profile).first()
                if pin:
                    try:
                        kb: InlineKeyboardMarkup = build_top5_keyboard(items)
                        loop.run_until_complete(
                            bot.edit_message_reply_markup(chat_id=pin.chat_id, message_id=pin.message_id, reply_markup=kb)
                        )
                        updated += 1

                    except (TelegramBadRequest, TelegramNotFound) as e:
                        # Telegram-специфичные ошибки
                        error_text = str(e).lower()

                        # Сообщение удалено пользователем или не существует
                        if any(msg in error_text for msg in [
                            "message to edit not found",
                            "message not found",
                            "message to delete not found"
                        ]):
                            logger.info(
                                f"Top-5 pin removed for user {profile.telegram_id}: "
                                f"message {pin.message_id} not found (probably deleted by user)"
                            )
                            try:
                                pin.delete()
                            except Exception as delete_err:
                                logger.error(
                                    f"Failed to delete Top-5 pin for user {profile.telegram_id}: {delete_err}",
                                    exc_info=True
                                )
                        else:
                            # Другие TelegramBadRequest (например, invalid chat_id)
                            logger.warning(
                                f"Top-5 Telegram error for user {profile.telegram_id}: {e}"
                            )

                    except Exception as e:
                        # Неожиданные ошибки (сеть, БД, Python)
                        logger.error(
                            f"Top-5 unexpected error for user {profile.telegram_id}: {e}",
                            exc_info=True
                        )
            except Exception as user_err:
                logger.error(f"Top-5 update error for user {profile.telegram_id}: {user_err}")
                continue
        logger.info(f"Top-5 updated for {updated} pinned messages (profiles processed: {len(profiles)})")
    except Exception as e:
        logger.error(f"Error in update_top5_keyboards: {e}")

    finally:
        _shutdown_event_loop(loop, bot=bot, label="update_top5_keyboards")


# ==================== INCOME KEYWORDS LEARNING ====================
# Задачи для обучения ключевых слов доходов (аналог расходов)


@shared_task
def update_income_keywords(income_id: int, old_category_id: int, new_category_id: int):
    """
    Обновление ключевых слов после ручного изменения категории дохода.
    ИСПОЛЬЗУЕТ УНИВЕРСАЛЬНЫЙ КОД из keyword_service.py

    Сохраняет ОЧИЩЕННУЮ ФРАЗУ description как единый keyword:
    - Удаляет stop words (предлоги, глаголы, валюты)
    - Нормализует (lowercase, убирает emoji/пунктуацию)
    - Если фраза слишком длинная (>4 слов) — не сохраняет

    Пример: "Получил зарплату за декабрь 50000р" → "зарплату декабрь"
    """
    try:
        from expenses.models import Income, IncomeCategory
        from bot.utils.keyword_service import ensure_unique_keyword

        # Получаем объекты
        income = Income.objects.select_related('profile').get(id=income_id)
        new_category = IncomeCategory.objects.select_related('profile').get(id=new_category_id)
        old_category = IncomeCategory.objects.get(id=old_category_id) if old_category_id else None

        # ensure_unique_keyword сам нормализует и удаляет stop words через prepare_keyword_for_save()
        kw_obj, created, removed = ensure_unique_keyword(
            profile=income.profile,
            category=new_category,
            word=income.description,  # ← оригинальный текст, очистка внутри
            is_income=True
        )

        if not kw_obj:
            logger.info(f"Could not create/find keyword for income {income_id}")
            return

        # Увеличиваем счетчик использований
        kw_obj.usage_count += 1
        kw_obj.save()

        # Логируем итоги
        old_cat_name = old_category.name if old_category else 'None'
        new_cat_name = new_category.name or new_category.name_ru or new_category.name_en or f'ID:{new_category.id}'

        # kw_obj содержит очищенную фразу
        saved_keyword = getattr(kw_obj, 'keyword', income.description)
        logger.info(
            f"[CELERY] Updated income keyword '{saved_keyword}' from '{old_cat_name}' to '{new_cat_name}' "
            f"(removed {removed} duplicates, user {income.profile.telegram_id})"
        )

        # Проверяем лимит 50 слов на категорию (используем универсальную функцию)
        check_category_keywords_limit(new_category)
        if old_category:
            check_category_keywords_limit(old_category)

        logger.info(f"Successfully updated income keywords for income {income_id}")

    except Exception as e:
        logger.error(f"Error in update_income_keywords task: {e}")


@shared_task(name='prefetch_cbrf_rates')
def prefetch_cbrf_rates():
    """
    Предзагрузка курсов ЦБ РФ.
    Запускается в 23:30 МСК для кеширования на следующий день.

    Использует собственный event loop и свежий экземпляр CurrencyConverter,
    чтобы избежать проблемы "Event loop is closed" при использовании
    singleton-сессии из другого (уже закрытого) event loop.
    """
    import asyncio
    from bot.services.currency_conversion import CurrencyConverter

    async def _prefetch() -> int:
        converter = CurrencyConverter()
        try:
            rates = await converter.fetch_daily_rates()
            if rates:
                logger.info(f"CBRF: Prefetched {len(rates)} rates")
                return len(rates)
            else:
                logger.error("CBRF: Failed to prefetch rates")
                return 0
        finally:
            if converter.session and not converter.session.closed:
                await converter.session.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        count = loop.run_until_complete(_prefetch())
    finally:
        _shutdown_event_loop(loop, label="prefetch_cbrf_rates")
    return f"Prefetched {count} CBRF rates"


@shared_task
def learn_income_keywords_on_create(income_id: int):
    """
    Обучение системы при создании нового дохода с AI-категоризацией.
    ИСПОЛЬЗУЕТ УНИВЕРСАЛЬНЫЙ КОД из keyword_service.py

    Сохраняет ОЧИЩЕННУЮ ФРАЗУ description как единый keyword:
    - Удаляет stop words (предлоги, глаголы, валюты)
    - Нормализует (lowercase, убирает emoji/пунктуацию)
    - Если фраза слишком длинная (>4 слов) — не сохраняет

    Пример: "Получил зарплату за декабрь 50000р" → "зарплату декабрь"
    """
    try:
        from expenses.models import Income
        from bot.utils.keyword_service import ensure_unique_keyword

        income = Income.objects.select_related('profile', 'category').get(id=income_id)

        if not income.ai_categorized or not income.category:
            return

        category = income.category

        # ensure_unique_keyword сам нормализует и удаляет stop words через prepare_keyword_for_save()
        kw_obj, created, removed = ensure_unique_keyword(
            profile=income.profile,
            category=category,
            word=income.description,  # ← оригинальный текст, очистка внутри
            is_income=True
        )

        if not kw_obj:
            return

        # Увеличиваем счетчик
        if created:
            kw_obj.usage_count = 1
        else:
            kw_obj.usage_count += 1

        kw_obj.save()

        # Получаем имя категории для логов
        cat_name = category.name or category.name_ru or category.name_en or f'ID:{category.id}'

        # kw_obj — это IncomeKeyword, атрибут keyword содержит очищенную фразу
        saved_keyword = getattr(kw_obj, 'keyword', income.description)
        logger.info(
            f"Learned keyword '{saved_keyword}' for income category '{cat_name}' "
            f"(user {income.profile.telegram_id}, removed {removed} duplicates)"
        )

        # Очистка старых ключевых слов только если создали новый
        if created:
            cleanup_old_keywords(profile_id=income.profile.id, is_income=True)

        # Проверяем лимит 50 слов на категорию
        check_category_keywords_limit(category)

    except Exception as e:
        logger.error(f"Error in learn_income_keywords_on_create: {e}")


# ---------------------------------------------------------------------------
# Cross-server monitoring: expense_bot checks nutrition_bot availability
# ---------------------------------------------------------------------------

REMOTE_SERVER_NAME = "Nutrition Bot"
REMOTE_SERVER_IP = "45.93.201.222"
REMOTE_HEALTH_URL = "https://showmefood.duckdns.org/health/"
REMOTE_CHECK_TIMEOUT = 15  # seconds
REMOTE_FAILURES_BEFORE_ALERT = 1  # alert on first failure

CACHE_KEY_REMOTE_FAILURES = "remote_server:failures"
CACHE_KEY_REMOTE_ALERT_SENT = "remote_server:alert_sent"
CACHE_KEY_REMOTE_DOWN_SINCE = "remote_server:down_since"


@shared_task
def check_remote_server_health():
    """
    Периодическая проверка доступности удалённого сервера (Nutrition Bot).
    Если сервер недоступен REMOTE_FAILURES_BEFORE_ALERT раз подряд — шлёт алерт.
    При восстановлении — уведомляет о recovery с временем простоя.
    """
    import requests as http_requests
    from django.core.cache import cache

    # 1. Проверяем доступность
    is_up = False
    error_detail = ""
    try:
        resp = http_requests.get(REMOTE_HEALTH_URL, timeout=REMOTE_CHECK_TIMEOUT)
        is_up = resp.status_code == 200
        if not is_up:
            error_detail = f"HTTP {resp.status_code}"
    except http_requests.exceptions.Timeout:
        error_detail = "Timeout"
    except http_requests.exceptions.ConnectionError:
        error_detail = "Connection refused"
    except Exception as e:
        error_detail = str(e)[:100]

    # 2. Обрабатываем результат
    if is_up:
        _handle_remote_server_up(cache)
    else:
        _handle_remote_server_down(cache, error_detail)


def _handle_remote_server_up(cache) -> None:
    """Сервер доступен — сбрасываем счётчик, шлём recovery если был алерт."""
    was_alert_sent = cache.get(CACHE_KEY_REMOTE_ALERT_SENT)

    if was_alert_sent:
        # Считаем время простоя
        down_since_iso = cache.get(CACHE_KEY_REMOTE_DOWN_SINCE)
        downtime_str = "неизвестно"
        if down_since_iso:
            try:
                down_since = datetime.fromisoformat(down_since_iso)
                delta = datetime.now() - down_since
                minutes = int(delta.total_seconds() // 60)
                downtime_str = f"~{minutes} мин" if minutes > 0 else "<1 мин"
            except (ValueError, TypeError):
                pass

        recovery_sent = _send_remote_alert(
            f"✅ СЕРВЕР ВОССТАНОВЛЕН\n\n"
            f"Сервер: {REMOTE_SERVER_NAME} ({REMOTE_SERVER_IP})\n"
            f"Время простоя: {downtime_str}"
        )
        if recovery_sent:
            cache.delete(CACHE_KEY_REMOTE_ALERT_SENT)
            cache.delete(CACHE_KEY_REMOTE_DOWN_SINCE)
            logger.info(f"[REMOTE_MONITOR] {REMOTE_SERVER_NAME} recovered, downtime={downtime_str}")
        else:
            logger.warning(f"[REMOTE_MONITOR] Recovery message failed to send, keeping alert flag")

    cache.set(CACHE_KEY_REMOTE_FAILURES, 0, 3600)


def _handle_remote_server_down(cache, error_detail: str) -> None:
    """Сервер недоступен — увеличиваем счётчик, шлём алерт если порог превышен."""
    failures = (cache.get(CACHE_KEY_REMOTE_FAILURES) or 0) + 1
    cache.set(CACHE_KEY_REMOTE_FAILURES, failures, 3600)

    # Запоминаем момент начала недоступности
    if failures == 1:
        cache.set(CACHE_KEY_REMOTE_DOWN_SINCE, datetime.now().isoformat(), 86400)

    logger.warning(
        f"[REMOTE_MONITOR] {REMOTE_SERVER_NAME} unreachable "
        f"(attempt {failures}, error: {error_detail})"
    )

    if failures >= REMOTE_FAILURES_BEFORE_ALERT and not cache.get(CACHE_KEY_REMOTE_ALERT_SENT):
        import pytz
        moscow_tz = pytz.timezone('Europe/Moscow')
        now_msk = datetime.now(moscow_tz).strftime('%H:%M')

        sent = _send_remote_alert(
            f"🚨 СЕРВЕР НЕДОСТУПЕН\n\n"
            f"Сервер: {REMOTE_SERVER_NAME} ({REMOTE_SERVER_IP})\n"
            f"URL: {REMOTE_HEALTH_URL}\n"
            f"Недоступен с: {now_msk} MSK\n"
            f"Проверок подряд: {failures}\n"
            f"Ошибка: {error_detail}\n\n"
            f"Проверь сервер!"
        )
        if sent:
            cache.set(CACHE_KEY_REMOTE_ALERT_SENT, True, 86400)
            logger.error(f"[REMOTE_MONITOR] Alert sent: {REMOTE_SERVER_NAME} is DOWN")
        else:
            logger.error(f"[REMOTE_MONITOR] Failed to send alert, will retry next check")


def _send_remote_alert(message: str) -> bool:
    """Отправить уведомление админу через async admin_notifier. Возвращает True при успехе."""
    try:
        from bot.services.admin_notifier import send_admin_alert
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(send_admin_alert(message))
        finally:
            _shutdown_event_loop(loop, label="check_remote_server_health")
        return bool(result)
    except Exception as e:
        logger.error(f"[REMOTE_MONITOR] Failed to send alert: {e}")
        return False
