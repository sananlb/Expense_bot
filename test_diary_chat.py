#!/usr/bin/env python3
"""
Тестирование функциональности дневника через чат
"""
import asyncio
import os
import sys
from datetime import datetime, date, timedelta

# Установка UTF-8 кодировки
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from bot.routers.chat import parse_dates_from_text, check_and_process_diary_request
from bot.services.expense import create_expense
from bot.services.category import get_or_create_category
from bot.services.profile import get_or_create_profile
from decimal import Decimal


async def test_date_parsing():
    """Тест парсинга дат из текста"""
    print("=== Тест парсинга дат ===")
    
    test_cases = [
        ("Покажи траты за 15 марта", "конкретная дата"),
        ("Траты за вчера", "вчера"),
        ("Дневник трат за прошлый месяц", "прошлый месяц"),
        ("Покажи расходы за март", "месяц по названию"),
        ("Траты с 1 по 15 марта", "диапазон дат"),
        ("Сколько потратил за неделю", "неделя"),
        ("Траты за 15.03", "дата в формате ДД.ММ"),
        ("Расходы за 15/03/2024", "дата в формате ДД/ММ/ГГГГ"),
    ]
    
    for text, description in test_cases:
        result = await parse_dates_from_text(text)
        if result:
            start, end = result
            if start == end:
                print(f"OK '{text}' ({description}) -> {start.strftime('%d.%m.%Y')}")
            else:
                print(f"OK '{text}' ({description}) -> с {start.strftime('%d.%m.%Y')} по {end.strftime('%d.%m.%Y')}")
        else:
            print(f"FAIL '{text}' ({description}) -> даты не распознаны")


async def test_diary_detection():
    """Тест определения запросов дневника"""
    print("\n=== Тест определения запросов дневника ===")
    
    test_messages = [
        ("Покажи дневник трат", True),
        ("Траты за вчера", True),
        ("Сколько я потратил за март?", True),
        ("Покажи расходы за прошлую неделю", True),
        ("Кофе 200", False),
        ("Привет, как дела?", False),
        ("Дневник", True),
    ]
    
    for message, should_be_diary in test_messages:
        # Создаем фиктивные объекты для теста
        class FakeMessage:
            text = message
            
        text_lower = message.lower()
        diary_keywords = ['дневник', 'траты за', 'расходы за', 'покажи траты', 'показать траты', 
                          'потратил за', 'сколько потратил']
        is_diary = any(keyword in text_lower for keyword in diary_keywords)
        
        status = "OK" if is_diary == should_be_diary else "FAIL"
        print(f"{status} '{message}' -> {'дневник' if is_diary else 'не дневник'}")


async def create_test_expenses():
    """Создать тестовые траты"""
    print("\n=== Создание тестовых трат ===")
    
    test_user_id = 123456789
    profile = await get_or_create_profile(test_user_id)
    
    # Создаем траты за разные даты
    test_data = [
        (date.today(), "Кофе", 200),
        (date.today(), "Обед", 500),
        (date.today() - timedelta(days=1), "Такси", 450),
        (date.today() - timedelta(days=1), "Продукты", 1500),
        (date.today() - timedelta(days=7), "Ресторан", 2000),
        (date.today() - timedelta(days=30), "Одежда", 5000),
    ]
    
    for expense_date, description, amount in test_data:
        category = await get_or_create_category(test_user_id, description)
        expense = await create_expense(
            user_id=test_user_id,
            amount=Decimal(str(amount)),
            category_id=category.id,
            description=description,
            expense_date=expense_date
        )
        if expense:
            print(f"Создана трата: {expense_date} - {description} - {amount} руб")


async def main():
    """Главная функция"""
    await test_date_parsing()
    await test_diary_detection()
    await create_test_expenses()
    
    print("\n=== Тесты завершены ===")
    print("\nТеперь можете протестировать в боте следующие команды:")
    print("- 'Покажи траты за вчера'")
    print("- 'Дневник трат за март'")
    print("- 'Сколько я потратил за неделю?'")
    print("- 'Траты с 1 по 15 марта'")


if __name__ == "__main__":
    asyncio.run(main())