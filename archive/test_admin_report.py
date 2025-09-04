#!/usr/bin/env python
"""
Тестовый скрипт для проверки отправки отчетов администратору
"""

import os
import sys
import asyncio
import django
from datetime import datetime

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

async def test_admin_notification():
    """Тестирование отправки уведомления администратору"""
    from bot.services.admin_notifier import send_admin_alert, send_daily_report
    
    print("=" * 60)
    print("ТЕСТ ОТПРАВКИ ОТЧЕТОВ АДМИНИСТРАТОРУ")
    print("=" * 60)
    
    # Проверка переменных окружения
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    monitoring_token = os.getenv('MONITORING_BOT_TOKEN')
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', os.getenv('BOT_TOKEN'))
    
    print("\n[CONFIG] Конфигурация:")
    print(f"   ADMIN_TELEGRAM_ID: {admin_id if admin_id else '[X] НЕ УСТАНОВЛЕН'}")
    print(f"   MONITORING_BOT_TOKEN: {'[OK] Установлен' if monitoring_token else '[!] Не установлен (будет использован основной токен)'}")
    print(f"   BOT_TOKEN: {'[OK] Установлен' if bot_token else '[X] НЕ УСТАНОВЛЕН'}")
    
    if not admin_id:
        print("\n[ERROR] ОШИБКА: ADMIN_TELEGRAM_ID не установлен в .env файле!")
        print("   Добавьте в .env: ADMIN_TELEGRAM_ID=ваш_telegram_id")
        return False
    
    if not (monitoring_token or bot_token):
        print("\n[ERROR] ОШИБКА: Ни MONITORING_BOT_TOKEN, ни BOT_TOKEN не установлены!")
        return False
    
    print("\n[TEST 1] Отправка простого уведомления...")
    try:
        # Экранируем специальные символы для MarkdownV2
        test_message = (
            f"*\\[TEST\\] Тестовое уведомление*\n\n"
            f"Время: {datetime.now().strftime('%H:%M:%S')}\n"
            f"Статус: Проверка работы системы уведомлений\n\n"
            f"Если вы видите это сообщение, значит отправка отчетов работает\\!"
        ).replace('.', '\\.').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')
        
        result = await send_admin_alert(test_message)
        
        if result:
            print("   [OK] Уведомление отправлено успешно!")
        else:
            print("   [ERROR] Не удалось отправить уведомление")
            print("   Проверьте логи для деталей ошибки")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Ошибка при отправке: {e}")
        return False
    
    print("\n[TEST 2] Отправка ежедневного отчета...")
    try:
        result = await send_daily_report()
        
        if result:
            print("   [OK] Ежедневный отчет отправлен успешно!")
        else:
            print("   [ERROR] Не удалось отправить ежедневный отчет")
            print("   Проверьте логи для деталей ошибки")
            
    except Exception as e:
        print(f"   [ERROR] Ошибка при отправке отчета: {e}")
        return False
    
    print("\n[DONE] Все тесты завершены!")
    print("\n[INFO] Проверьте Telegram для получения сообщений.")
    print("   Сообщения должны прийти от бота в чат с ID:", admin_id)
    
    return True

async def test_celery_tasks():
    """Проверка настройки Celery задач"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА CELERY ЗАДАЧ")
    print("=" * 60)
    
    try:
        from expense_bot.celery import app
        from celery.schedules import crontab
        
        # Получаем расписание задач
        beat_schedule = app.conf.beat_schedule
        
        print("\n[SCHEDULE] Настроенные периодические задачи:")
        
        if 'send-daily-admin-report' in beat_schedule:
            task = beat_schedule['send-daily-admin-report']
            print(f"\n[OK] send-daily-admin-report:")
            print(f"   Задача: {task['task']}")
            print(f"   Расписание: {task['schedule']}")
            print(f"   Очередь: {task.get('options', {}).get('queue', 'default')}")
        else:
            print("\n[WARNING] Задача send-daily-admin-report НЕ настроена в CELERY_BEAT_SCHEDULE!")
            
        # Показываем все задачи
        print("\n[LIST] Все периодические задачи:")
        for name, task_info in beat_schedule.items():
            print(f"   - {name}: {task_info['task']}")
            
    except ImportError as e:
        print(f"[ERROR] Ошибка импорта Celery: {e}")
        print("   Убедитесь, что Celery установлен и настроен")
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке Celery: {e}")

async def main():
    """Главная функция"""
    print("\n[START] Запуск тестов системы отчетов администратору\n")
    
    # Тест отправки уведомлений
    success = await test_admin_notification()
    
    # Тест Celery задач
    await test_celery_tasks()
    
    if success:
        print("\n[SUCCESS] Система отчетов работает корректно!")
    else:
        print("\n[FAIL] Обнаружены проблемы в системе отчетов")
        print("\nРекомендации по исправлению:")
        print("1. Проверьте правильность ADMIN_TELEGRAM_ID в .env")
        print("2. Убедитесь, что бот с токеном MONITORING_BOT_TOKEN запущен")
        print("3. Проверьте, что у бота есть права на отправку сообщений")
        print("4. Проверьте логи Django для деталей ошибок")

if __name__ == "__main__":
    asyncio.run(main())