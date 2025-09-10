#!/usr/bin/env python
"""
Тестирование отправки ежедневного отчета администратору
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expense_bot.celery_tasks import send_daily_admin_report
from bot.services.admin_notifier import escape_markdown_v2

def test_markdown_escaping():
    """Тест экранирования MarkdownV2"""
    print("=" * 50)
    print("ТЕСТ ЭКРАНИРОВАНИЯ MARKDOWNV2")
    print("=" * 50)
    
    test_cases = [
        "Текст со скобками (тест)",
        "Текст со *звездочками*",
        "Топ-5 категорий",
        "Дата 10.09.2024",
        "Сумма: 1,000 ₽ (25 записей)",
    ]
    
    for text in test_cases:
        escaped = escape_markdown_v2(text)
        print(f"Исходный: {text}")
        print(f"Экранированный: {escaped}")
        print()

def test_admin_report():
    """Тест отправки отчета администратору"""
    print("=" * 50)
    print("ТЕСТ ОТПРАВКИ ОТЧЕТА АДМИНИСТРАТОРУ")
    print("=" * 50)
    
    try:
        # Запускаем задачу напрямую (синхронно)
        print("Запуск функции send_daily_admin_report()...")
        result = send_daily_admin_report()
        print(f"✅ Задача выполнена успешно!")
        print(f"Результат: {result}")
    except Exception as e:
        print(f"❌ Ошибка при выполнении задачи: {e}")
        import traceback
        traceback.print_exc()

def test_celery_task():
    """Тест отправки через Celery (требует запущенный Celery)"""
    print("=" * 50)
    print("ТЕСТ ОТПРАВКИ ЧЕРЕЗ CELERY")
    print("=" * 50)
    
    try:
        from expense_bot.celery_tasks import send_daily_admin_report
        
        # Запускаем асинхронно через Celery
        print("Отправка задачи в Celery...")
        result = send_daily_admin_report.delay()
        print(f"Task ID: {result.id}")
        
        # Ждем результат
        print("Ожидание результата (до 10 секунд)...")
        try:
            result_value = result.get(timeout=10)
            print(f"✅ Задача выполнена через Celery!")
            print(f"Результат: {result_value}")
        except Exception as e:
            print(f"⚠️ Не удалось получить результат: {e}")
            print("Проверьте, что Celery запущен (python start_redis_celery_test.py)")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    print("\nТЕСТИРОВАНИЕ ОТЧЕТОВ АДМИНИСТРАТОРА\n")
    
    # Тест экранирования
    test_markdown_escaping()
    
    # Выбор теста
    print("\nВыберите тест:")
    print("1. Тест отправки напрямую (без Celery)")
    print("2. Тест отправки через Celery (требует запущенный Celery)")
    print("3. Выполнить оба теста")
    
    choice = input("\nВведите номер (1-3): ").strip()
    
    if choice == "1":
        test_admin_report()
    elif choice == "2":
        test_celery_task()
    elif choice == "3":
        test_admin_report()
        print()
        test_celery_task()
    else:
        print("Неверный выбор!")
        
    print("\n✅ Тестирование завершено!")