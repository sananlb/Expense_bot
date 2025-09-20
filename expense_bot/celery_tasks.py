from celery import shared_task
from datetime import datetime, date, timedelta, time
import asyncio
import logging
import re
import os
from typing import List

from django.conf import settings
from django.db.models import Count, Sum, Q, Avg, Case, When, FloatField
from django.utils import timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)



@shared_task
def send_monthly_reports():
    """Send monthly expense reports to all users on the last day at 20:00"""
    try:
        from expenses.models import Profile, Expense
        from bot.services.notifications import NotificationService
        from calendar import monthrange
        # Use main bot token for user-facing notifications
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)
        service = NotificationService(bot)
        
        # Check if today is the last day of month and time is 20:00
        today = datetime.now()
        last_day = monthrange(today.year, today.month)[1]
        
        if today.day != last_day:
            logger.info(f"Not the last day of month ({today.day}/{last_day}), skipping monthly reports")
            return
        
        if today.hour != 20:
            logger.info(f"Not 20:00 ({today.hour}:00), skipping monthly reports")
            return
        
        # Get all active profiles who have expenses this month
        month_start = today.replace(day=1)
        profiles_with_expenses = Expense.objects.filter(
            expense_date__gte=month_start,
            expense_date__lte=today
        ).values_list('profile_id', flat=True).distinct()
        
        profiles = Profile.objects.filter(
            id__in=profiles_with_expenses
        )
        
        logger.info(f"Sending monthly reports to {profiles.count()} users with expenses")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for profile in profiles:
            try:
                loop.run_until_complete(
                    service.send_monthly_report(profile.telegram_id, profile)
                )
                logger.info(f"Monthly report sent to user {profile.telegram_id}")
            except Exception as e:
                logger.error(f"Error sending monthly report to user {profile.telegram_id}: {e}")
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in send_monthly_reports task: {e}")


@shared_task
def check_budget_limits():
    """Check budget limits and send warnings"""
    try:
        from expenses.models import Profile, Budget, Expense
        from bot.services.notifications import NotificationService
        from decimal import Decimal
        # Use main bot token for user-facing notifications
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('MONITORING_BOT_TOKEN')
        bot = Bot(token=bot_token)
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

        yesterday = timezone.now().date() - timedelta(days=1)
        today = timezone.now().date()
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
                
            if openai_stats['requests'] and google_stats['requests']:
                openai_success = openai_stats.get('success_rate', 0) * 100
                google_success = google_stats.get('success_rate', 0) * 100
                report += (
                    f"  • OpenAI: {esc(openai_stats['requests'])} зап\\., "
                    f"{esc(f'{openai_success:.0f}')}% успех\n"
                    f"  • Google: {esc(google_stats['requests'])} зап\\., "
                    f"{esc(f'{google_success:.0f}')}% успех\n"
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

        loop.run_until_complete(send_admin_alert(report, disable_notification=True))

        loop.close()

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
                loop.run_until_complete(send_admin_alert(alert_message))
                loop.close()
                
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
        target_date = (timezone.now() - timedelta(days=1)).date()
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
                
                # Примерная активность по сообщениям/фото (заглушка)
                messages_sent = expenses_stats['count'] or 0  # Примерно по количеству расходов
                voice_messages = 0  # Заглушка
                photos_sent = 0     # Заглушка
                
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
                    existing_analytics.voice_messages = voice_messages
                    existing_analytics.photos_sent = photos_sent
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
                    UserAnalytics.objects.create(
                        profile=profile,
                        date=target_date,
                        messages_sent=messages_sent,
                        voice_messages=voice_messages,
                        photos_sent=photos_sent,
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
    try:
        from bot.services.recurring import process_recurring_payments_for_today
        from bot.utils.expense_messages import format_expense_added_message
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
                expense = payment_info['expense']
                payment = payment_info['payment']
                
                # Получаем язык пользователя из профиля
                from expenses.models import Profile
                profile = Profile.objects.filter(telegram_id=user_id).first()
                user_lang = profile.language_code if profile else 'ru'
                
                # Для ежемесячных платежей не считаем кешбэк
                cashback_text = ""
                
                # Форматируем сообщение используя стандартную функцию
                text = loop.run_until_complete(
                    format_expense_added_message(
                        expense=expense,
                        category=expense.category,
                        cashback_text=cashback_text,
                        is_recurring=True,  # Флаг для ежемесячного платежа
                        lang=user_lang
                    )
                )
                
                # Создаем клавиатуру с кнопками редактирования
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_expense_{expense.id}"),
                        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_expense_{expense.id}")
                    ]
                ])
                
                # Отправляем уведомление
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
                logger.error(f"Error sending notification to user {payment_info['user_id']}: {e}")
        
        loop.close()
        
        logger.info(f"Processed {processed_count} recurring payments")
        
    except Exception as e:
        logger.error(f"Error in process_recurring_payments task: {e}")


@shared_task
def update_keywords_weights(expense_id: int, old_category_id: int, new_category_id: int):
    """
    Обновление весов ключевых слов после изменения категории пользователем.
    Запускается в фоне после редактирования.
    """
    try:
        from expenses.models import Expense, ExpenseCategory, CategoryKeyword
        
        # Попробуем импортировать spellchecker, если не получится - используем без проверки
        try:
            from bot.utils.spellchecker import check_and_correct_text
        except ImportError:
            def check_and_correct_text(text):
                return text  # Возвращаем текст без изменений
        
        # Получаем объекты
        expense = Expense.objects.get(id=expense_id)
        new_category = ExpenseCategory.objects.get(id=new_category_id)
        old_category = ExpenseCategory.objects.get(id=old_category_id) if old_category_id else None
        
        # Извлекаем и очищаем слова из описания
        words = extract_words_from_description(expense.description)
        
        # Проверяем правописание
        corrected_words = []
        for word in words:
            corrected = check_and_correct_text(word)
            if corrected and len(corrected) >= 3:  # Минимум 3 буквы
                corrected_words.append(corrected.lower())
        
        words = corrected_words
        
        # Обновляем ключевые слова для НОВОЙ категории (пользователь исправил)
        for word in words:
            keyword, created = CategoryKeyword.objects.get_or_create(
                category=new_category,
                keyword=word,
                defaults={'normalized_weight': 1.0, 'usage_count': 0}
            )
            
            # Увеличиваем счетчик использований
            keyword.usage_count += 1
            keyword.save()
            
            logger.info(f"Updated keyword '{word}' for category '{new_category.name}' (user {expense.profile.telegram_id})")
        
        # Пересчитываем нормализованные веса для конфликтующих слов
        recalculate_normalized_weights(expense.profile.id, words)
        
        # Проверяем лимит 50 слов на категорию
        check_category_keywords_limit(new_category)
        if old_category:
            check_category_keywords_limit(old_category)
        
        logger.info(f"Successfully updated keywords weights for expense {expense_id}")
        
    except Exception as e:
        logger.error(f"Error in update_keywords_weights task: {e}")


def extract_words_from_description(description: str) -> List[str]:
    """Извлекает значимые слова из описания расхода"""
    # Удаляем числа, валюту, знаки препинания
    text = re.sub(r'\d+', '', description)
    text = re.sub(r'[₽$€£¥р\.,"\'!?;:\-\(\)]', ' ', text)
    
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


def recalculate_normalized_weights(profile_id: int, words: List[str]):
    """Пересчитывает нормализованные веса для слов, встречающихся в нескольких категориях"""
    from expenses.models import CategoryKeyword, Profile
    
    try:
        profile = Profile.objects.get(id=profile_id)
        
        for word in words:
            # Находим все вхождения слова у данного пользователя
            keywords = CategoryKeyword.objects.filter(
                category__profile=profile,
                keyword=word
            )
            
            if keywords.count() > 1:
                # Слово встречается в нескольких категориях
                total_usage = sum(kw.usage_count for kw in keywords)
                
                if total_usage > 0:
                    for kw in keywords:
                        # Нормализуем вес от 0 до 1 на основе частоты использования
                        kw.normalized_weight = kw.usage_count / total_usage
                        kw.save()
                        
                    logger.info(f"Recalculated weights for word '{word}' across {keywords.count()} categories")
    
    except Exception as e:
        logger.error(f"Error recalculating weights: {e}")


def check_category_keywords_limit(category):
    """Проверяет и ограничивает количество ключевых слов в категории (максимум 50)"""
    from expenses.models import CategoryKeyword
    
    try:
        keywords = CategoryKeyword.objects.filter(category=category)
        
        if keywords.count() > 50:
            # Оставляем топ-50 по usage_count
            keywords_list = list(keywords)
            keywords_list.sort(key=lambda k: k.usage_count, reverse=True)
            
            # Удаляем слова с наименьшим использованием
            keywords_to_delete = keywords_list[50:]
            for kw in keywords_to_delete:
                logger.info(f"Deleting keyword '{kw.keyword}' from category '{category.name}' (low usage)")
                kw.delete()
            
            logger.info(f"Limited keywords for category '{category.name}' to 50 items")
    
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

        # Окно: последние 90 дней включительно (rolling)
        today = date.today()
        from datetime import timedelta
        window_end = today
        window_start = today - timedelta(days=89)

        # Пользователи с активностью
        profiles = asyncio.get_event_loop().run_until_complete(get_profiles_with_activity(window_start, window_end))

        updated = 0
        for profile in profiles:
            try:
                items, digest = asyncio.get_event_loop().run_until_complete(calculate_top5_sync(profile, window_start, window_end))
                snap = Top5Snapshot.objects.filter(profile=profile).first()
                if not snap or snap.hash != digest or snap.window_start != window_start or snap.window_end != window_end:
                    asyncio.get_event_loop().run_until_complete(
                        save_snapshot(profile, window_start, window_end, items, digest)
                    )
                # Обновляем закреплённое сообщение, если знаем ids
                pin = Top5Pin.objects.filter(profile=profile).first()
                if pin:
                    kb: InlineKeyboardMarkup = build_top5_keyboard(items)
                    asyncio.get_event_loop().run_until_complete(
                        bot.edit_message_reply_markup(chat_id=pin.chat_id, message_id=pin.message_id, reply_markup=kb)
                    )
                    updated += 1
            except Exception as user_err:
                logger.error(f"Top-5 update error for user {profile.telegram_id}: {user_err}")
                continue
        logger.info(f"Top-5 updated for {updated} pinned messages (profiles processed: {len(profiles)})")
    except Exception as e:
        logger.error(f"Error in update_top5_keyboards: {e}")
