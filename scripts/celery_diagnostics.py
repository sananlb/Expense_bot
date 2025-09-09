#!/usr/bin/env python
"""
Скрипт диагностики Celery для ExpenseBot
Проверяет состояние периодических задач и выявляет проблемы
"""

import os
import sys
import django
from datetime import datetime, timedelta
import pytz

# Добавляем путь к проекту
sys.path.insert(0, '/home/batman/expense_bot')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.conf import settings
from django.utils import timezone as django_timezone
import redis
from celery import Celery

def check_timezone():
    """Проверка настроек timezone"""
    print("=" * 50)
    print("🕐 ПРОВЕРКА TIMEZONE")
    print("=" * 50)
    
    print(f"Django TIME_ZONE: {settings.TIME_ZONE}")
    print(f"Django USE_TZ: {settings.USE_TZ}")
    print(f"Celery TIMEZONE: {getattr(settings, 'CELERY_TIMEZONE', 'не установлен')}")
    
    # Текущее время
    now = datetime.now()
    now_tz = django_timezone.now()
    moscow_tz = pytz.timezone('Europe/Moscow')
    moscow_time = datetime.now(moscow_tz)
    
    print(f"\nТекущее время:")
    print(f"  Системное (без TZ): {now}")
    print(f"  Django (с TZ): {now_tz}")
    print(f"  Москва: {moscow_time}")
    print()

def check_redis_connection():
    """Проверка подключения к Redis"""
    print("=" * 50)
    print("📡 ПРОВЕРКА REDIS")
    print("=" * 50)
    
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        print("✅ Redis доступен")
        
        # Проверяем очереди
        queues = ['celery', 'default', 'reports', 'recurring', 'maintenance', 'notifications']
        for queue in queues:
            queue_len = r.llen(queue)
            if queue_len > 0:
                print(f"  Очередь '{queue}': {queue_len} задач")
    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
    print()

def check_periodic_tasks():
    """Проверка периодических задач в БД"""
    print("=" * 50)
    print("📋 ПЕРИОДИЧЕСКИЕ ЗАДАЧИ В БД")
    print("=" * 50)
    
    tasks = PeriodicTask.objects.all()
    
    if not tasks:
        print("⚠️ Нет периодических задач в БД!")
        print("Это основная проблема - задачи не созданы в django_celery_beat")
        return
    
    for task in tasks:
        print(f"\n📌 Задача: {task.name}")
        print(f"  Enabled: {'✅' if task.enabled else '❌'}")
        print(f"  Task: {task.task}")
        
        # Время выполнения
        if task.crontab:
            cron = task.crontab
            print(f"  Расписание (cron): {cron.minute} {cron.hour} * * {cron.day_of_week}")
            print(f"    Время: {cron.hour}:{cron.minute:02d}")
            print(f"    Дни недели: {cron.day_of_week if cron.day_of_week != '*' else 'каждый день'}")
        elif task.interval:
            print(f"  Интервал: каждые {task.interval.every} {task.interval.period}")
        
        # Последний запуск
        if task.last_run_at:
            moscow_tz = pytz.timezone('Europe/Moscow')
            last_run_moscow = task.last_run_at.astimezone(moscow_tz)
            print(f"  Последний запуск: {last_run_moscow.strftime('%Y-%m-%d %H:%M:%S')} MSK")
            
            # Проверяем, должна ли была задача запуститься сегодня
            if task.crontab and task.crontab.hour == 10 and task.crontab.minute == 0:
                today_10am = datetime.now(moscow_tz).replace(hour=10, minute=0, second=0, microsecond=0)
                if datetime.now(moscow_tz) > today_10am:
                    if last_run_moscow.date() < today_10am.date():
                        print(f"  ⚠️ ПРОБЛЕМА: Задача должна была запуститься сегодня в 10:00, но не запустилась!")
                    else:
                        print(f"  ✅ Задача запускалась сегодня")
        else:
            print(f"  ⚠️ Никогда не запускалась!")
        
        print(f"  Total runs: {task.total_run_count}")
        print(f"  Queue: {task.queue if task.queue else 'default'}")

def check_celery_beat_schedule():
    """Проверка расписания из settings.py"""
    print("\n" + "=" * 50)
    print("⚙️ РАСПИСАНИЕ ИЗ SETTINGS.PY")
    print("=" * 50)
    
    beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
    
    if not beat_schedule:
        print("⚠️ CELERY_BEAT_SCHEDULE не настроен в settings.py!")
        return
    
    for name, config in beat_schedule.items():
        print(f"\n📌 {name}")
        print(f"  Task: {config.get('task')}")
        print(f"  Schedule: {config.get('schedule')}")
        if 'options' in config:
            print(f"  Queue: {config['options'].get('queue', 'default')}")

def check_daily_admin_report():
    """Специальная проверка задачи отчета админу в 10:00"""
    print("\n" + "=" * 50)
    print("🎯 ПРОВЕРКА ЗАДАЧИ ЕЖЕДНЕВНОГО ОТЧЕТА (10:00)")
    print("=" * 50)
    
    # Ищем задачу в БД
    task = PeriodicTask.objects.filter(
        task='expense_bot.celery_tasks.send_daily_admin_report'
    ).first()
    
    if not task:
        print("❌ Задача 'send_daily_admin_report' НЕ НАЙДЕНА в БД!")
        print("\n🔧 РЕШЕНИЕ:")
        print("Нужно создать задачу в БД. Выполните на сервере:")
        print("""
docker exec -it expense_bot_web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask, CrontabSchedule
>>> from django.utils import timezone
>>> 
>>> # Создаем расписание для 10:00
>>> schedule, _ = CrontabSchedule.objects.get_or_create(
...     minute=0,
...     hour=10,
...     day_of_week='*',
...     day_of_month='*',
...     month_of_year='*',
...     timezone=timezone.get_current_timezone()
... )
>>> 
>>> # Создаем задачу
>>> PeriodicTask.objects.create(
...     crontab=schedule,
...     name='Daily Admin Report at 10:00',
...     task='expense_bot.celery_tasks.send_daily_admin_report',
...     queue='reports',
...     enabled=True
... )
>>> exit()
        """)
        return
    
    print(f"✅ Задача найдена: {task.name}")
    print(f"  Enabled: {'✅' if task.enabled else '❌ ЗАДАЧА ОТКЛЮЧЕНА!'}")
    
    if task.crontab:
        print(f"  Время запуска: {task.crontab.hour}:{task.crontab.minute:02d}")
        if task.crontab.hour != 10 or task.crontab.minute != 0:
            print("  ⚠️ ПРОБЛЕМА: Время запуска не 10:00!")
    
    if not task.enabled:
        print("\n🔧 РЕШЕНИЕ: Включить задачу:")
        print("""
docker exec -it expense_bot_web python manage.py shell
>>> from django_celery_beat.models import PeriodicTask
>>> task = PeriodicTask.objects.get(task='expense_bot.celery_tasks.send_daily_admin_report')
>>> task.enabled = True
>>> task.save()
>>> exit()
        """)

def test_task_execution():
    """Тест запуска задачи вручную"""
    print("\n" + "=" * 50)
    print("🧪 ТЕСТ ЗАПУСКА ЗАДАЧИ")
    print("=" * 50)
    
    print("Для теста выполнения задачи вручную, выполните на сервере:")
    print("""
docker exec -it expense_bot_web python manage.py shell
>>> from expense_bot.celery_tasks import send_daily_admin_report
>>> result = send_daily_admin_report.delay()
>>> print(f"Task ID: {result.id}")
>>> print(f"Status: {result.status}")
>>> # Подождите несколько секунд
>>> result.get(timeout=30)  # Получить результат
>>> exit()
    """)

def main():
    print("\n" + "🔍 ДИАГНОСТИКА CELERY ПЕРИОДИЧЕСКИХ ЗАДАЧ" + "\n")
    print(f"Время запуска: {datetime.now()}")
    print(f"Сервер: 80.66.87.178")
    print()
    
    check_timezone()
    check_redis_connection()
    check_periodic_tasks()
    check_celery_beat_schedule()
    check_daily_admin_report()
    test_task_execution()
    
    print("\n" + "=" * 50)
    print("📊 ИТОГИ ДИАГНОСТИКИ")
    print("=" * 50)
    print("""
Основные проблемы, которые могут быть:
1. ❌ Задачи не созданы в django_celery_beat (БД)
2. ❌ Celery Beat не запущен или упал
3. ❌ Неправильная timezone
4. ❌ Задача отключена (enabled=False)
5. ❌ Redis недоступен или переполнен

Команды для проверки на сервере:
- docker logs expense_bot_celery_beat --tail 100
- docker logs expense_bot_celery --tail 100
- docker exec expense_bot_redis redis-cli ping
- docker ps | grep celery
    """)

if __name__ == "__main__":
    main()