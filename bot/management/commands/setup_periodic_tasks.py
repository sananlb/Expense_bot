from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Создает или обновляет периодические задачи Celery в БД'

    def handle(self, *args, **options):
        self.stdout.write('Настройка периодических задач Celery...')
        
        try:
            # 1. Задача ежедневного отчета админу в 10:00
            schedule_10am, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=10,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )
            if created:
                self.stdout.write(self.style.SUCCESS('✅ Создано расписание для 10:00'))

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.send_daily_admin_report',
                defaults={
                    'crontab': schedule_10am,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Daily Admin Report at 10:00',
                    'queue': 'reports',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Daily Admin Report at 10:00")
            )

            # 2. Ежемесячные отчеты в 20:00
            schedule_20pm, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=20,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.send_monthly_reports',
                defaults={
                    'crontab': schedule_20pm,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Monthly Reports at 20:00',
                    'queue': 'reports',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Monthly Reports at 20:00")
            )

            # 3. Проверка бюджетных лимитов каждые 30 минут
            # 4. Регулярные платежи в 12:00
            schedule_12pm, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=12,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.process_recurring_payments',
                defaults={
                    'crontab': schedule_12pm,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Process Recurring Payments at 12:00',
                    'queue': 'recurring',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Process Recurring Payments")
            )

            # 5. Очистка старых данных по воскресеньям в 03:00
            schedule_cleanup, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=3,
                day_of_week='0',  # 0 = воскресенье
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.cleanup_old_expenses',
                defaults={
                    'crontab': schedule_cleanup,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Cleanup Old Expenses on Sunday',
                    'queue': 'maintenance',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Cleanup Old Expenses")
            )

            # 6. Проверка здоровья системы каждый час
            interval_1hour, created = IntervalSchedule.objects.get_or_create(
                every=1,
                period=IntervalSchedule.HOURS
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.system_health_check',
                defaults={
                    'interval': interval_1hour,
                    'crontab': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'System Health Check',
                    'queue': 'monitoring',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: System Health Check")
            )

            # 7. Сбор ежедневной аналитики в 23:00
            schedule_23pm, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=23,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.collect_daily_analytics',
                defaults={
                    'crontab': schedule_23pm,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Collect Daily Analytics at 23:00',
                    'queue': 'analytics',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Collect Daily Analytics")
            )

            # 8. Обновление топ-5 клавиатур в 01:00
            schedule_1am, created = CrontabSchedule.objects.get_or_create(
                minute=0,
                hour=1,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=timezone.get_current_timezone()
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expense_bot.celery_tasks.update_top5_keyboards',
                defaults={
                    'crontab': schedule_1am,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Update Top5 Keyboards at 01:00',
                    'queue': 'maintenance',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Update Top5 Keyboards")
            )

            # 9. Предзагрузка курсов ЦБ РФ в 20:30 UTC (23:30 МСК)
            schedule_prefetch_rates, created = CrontabSchedule.objects.get_or_create(
                minute='30',
                hour='20',      # 20:30 UTC = 23:30 МСК
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
            )

            task, created = PeriodicTask.objects.update_or_create(
                name='Prefetch CBRF rates daily',
                defaults={
                    'task': 'prefetch_cbrf_rates',
                    'crontab': schedule_prefetch_rates,
                    'interval': None,
                    'clocked': None,
                    'solar': None,
                    'enabled': True,
                }
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Prefetch CBRF rates daily")
            )

            # 10. Проверка запланированных рассылок каждые 5 минут
            interval_5min, created = IntervalSchedule.objects.get_or_create(
                every=5,
                period=IntervalSchedule.MINUTES
            )

            task, created = PeriodicTask.objects.update_or_create(
                task='expenses.tasks.process_scheduled_broadcasts',
                defaults={
                    'interval': interval_5min,
                    'crontab': None,
                    'clocked': None,
                    'solar': None,
                    'name': 'Process Scheduled Broadcasts',
                    'queue': 'notifications',
                    'enabled': True
                }
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{'✅ Создана' if created else '✔️ Обновлена'} задача: Process Scheduled Broadcasts"
                )
            )

            # Выводим итоговую информацию
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS('📋 ИТОГИ:'))
            
            all_tasks = PeriodicTask.objects.filter(enabled=True)
            self.stdout.write(f'Всего активных задач: {all_tasks.count()}')
            
            for task in all_tasks:
                status = '✅' if task.enabled else '❌'
                self.stdout.write(f'{status} {task.name}: {task.task}')
                if task.crontab:
                    self.stdout.write(f'    ⏰ Время: {task.crontab.hour}:{task.crontab.minute:02d}')
                elif task.interval:
                    self.stdout.write(f'    ⏱️ Интервал: каждые {task.interval.every} {task.interval.period}')
            
            self.stdout.write('\n' + self.style.SUCCESS('✅ Все периодические задачи успешно настроены!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при создании задач: {e}'))
            logger.error(f"Ошибка при создании периодических задач: {e}", exc_info=True)
            raise
