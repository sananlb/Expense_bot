import logging
from django.conf import settings


logger = logging.getLogger(__name__)


def ensure_periodic_tasks(startup: bool = False) -> None:
    """Ensure django-celery-beat PeriodicTask entries exist when USE_DB_BEAT is enabled.

    Idempotent: uses update_or_create by unique name. Safe to call multiple times.
    """
    # Only act if DB-based beat is enabled
    use_db = getattr(settings, 'USE_DB_BEAT', False)
    if not use_db:
        return

    try:
        from django_celery_beat.models import CrontabSchedule, PeriodicTask
    except Exception:
        # Library not installed or migrations not applied yet
        return

    tz = getattr(settings, 'TIME_ZONE', 'UTC')

    def crontab(minute: str, hour: str, day_of_week: str = '*', day_of_month: str = '*', month_of_year: str = '*'):
        """Get or create a CrontabSchedule. Thread-safe with UNIQUE constraint.

        After migration 0003_add_crontabschedule_unique_constraint, the DB has a UNIQUE
        constraint preventing duplicates. get_or_create will now properly handle
        concurrent creation attempts without creating duplicates.
        """
        try:
            return CrontabSchedule.objects.get_or_create(
                minute=minute,
                hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                timezone=tz,
            )[0]
        except CrontabSchedule.MultipleObjectsReturned:
            # Should not happen after cleanup + UNIQUE constraint,
            # but handle gracefully: return first and log warning
            logger.warning(
                "[crontab] Multiple CrontabSchedule found for %s %s %s %s %s %s - using first",
                minute, hour, day_of_week, day_of_month, month_of_year, tz
            )
            return CrontabSchedule.objects.filter(
                minute=minute,
                hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                timezone=tz,
            ).first()

    created_or_updated = []

    def upsert(name: str, task: str, schedule, queue: str, enabled: bool = True):
        obj, _ = PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                'task': task,
                'crontab': schedule,
                'interval': None,
                'enabled': enabled,
                'one_off': False,
                'queue': queue,
            }
        )
        created_or_updated.append(name)

    try:
        # 10:00 daily — Admin daily report
        upsert(
            name='send-daily-admin-report',
            task='expense_bot.celery_tasks.send_daily_admin_report',
            schedule=crontab(minute='0', hour='10'),
            queue='reports',
        )

        # 12:00 daily — Recurring payments
        upsert(
            name='process-recurring-payments',
            task='expense_bot.celery_tasks.process_recurring_payments',
            schedule=crontab(minute='0', hour='12'),
            queue='recurring',
        )

        # 06:00 on 1st day of month — Generate monthly AI insights
        upsert(
            name='generate-monthly-insights',
            task='expense_bot.celery_tasks.generate_monthly_insights',
            schedule=crontab(minute='0', hour='6', day_of_month='1'),
            queue='reports',
        )

        # 11:00 on 1st day of month — Send monthly reports to users
        upsert(
            name='send-monthly-reports',
            task='expense_bot.celery_tasks.send_monthly_reports',
            schedule=crontab(minute='0', hour='11', day_of_month='1'),
            queue='reports',
        )

        # Sunday 03:00 — Cleanup
        upsert(
            name='cleanup-old-expenses',
            task='expense_bot.celery_tasks.cleanup_old_expenses',
            schedule=crontab(minute='0', hour='3', day_of_week='0'),
            queue='maintenance',
        )

        # 05:00 MSK daily — Update Top-5 keyboards
        upsert(
            name='update-top5-keyboards',
            task='expense_bot.celery_tasks.update_top5_keyboards',
            schedule=crontab(minute='0', hour='5'),
            queue='reports',
        )

        # Отключено 30.10.2025 - требует psutil, не критично для работы
        upsert(
            name='system-health-check',
            task='expense_bot.celery_tasks.system_health_check',
            schedule=crontab(minute='*/15', hour='*'),
            queue='monitoring',
            enabled=False,  # Выключено
        )

        # 02:00 daily — Collect previous day analytics
        upsert(
            name='collect-daily-analytics',
            task='expense_bot.celery_tasks.collect_daily_analytics',
            schedule=crontab(minute='0', hour='2'),
            queue='analytics',
        )

        # 20:30 UTC (23:30 MSK) daily — Prefetch CBRF exchange rates for next day
        upsert(
            name='prefetch-cbrf-rates',
            task='prefetch_cbrf_rates',
            schedule=crontab(minute='30', hour='20'),
            queue='maintenance',
        )

        # Cleanup stale/deprecated tasks from DB
        stale_tasks = [
            'process-held-affiliate-commissions',
            'expense_bot.celery_tasks.process_held_affiliate_commissions',
        ]
        deleted, _ = PeriodicTask.objects.filter(name__in=stale_tasks).delete()
        if deleted:
            logger.info("[Beat setup] Removed %d stale PeriodicTask(s)", deleted)

        logger.info("[Beat setup] Ensured PeriodicTasks: %s", ", ".join(created_or_updated))
    except Exception as e:
        logger.error("[Beat setup] Error ensuring PeriodicTasks: %s", e)
        # Do not propagate exceptions during startup
