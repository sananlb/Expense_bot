#!/usr/bin/env python
"""
Тестирование парсинга трат с датами
"""
import asyncio
import os
import sys
import django
from datetime import date

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message


async def test_date_parsing():
    """Тестирование парсинга дат в тратах"""
    
    test_cases = [
        # Формат дд.мм.гггг
        {
            'text': 'Кофе 200 15.03.2024',
            'expected': {
                'amount': 200,
                'description': 'Кофе',
                'expense_date': date(2024, 3, 15)
            }
        },
        # Дата в начале
        {
            'text': '25.12.2023 подарки 5000',
            'expected': {
                'amount': 5000,
                'description': 'подарки',
                'expense_date': date(2023, 12, 25)
            }
        },
        # Формат дд.мм.гг
        {
            'text': 'АЗС 3500 10.03.24',
            'expected': {
                'amount': 3500,
                'description': 'АЗС',
                'expense_date': date(2024, 3, 10)
            }
        },
        # Формат дд/мм/гггг
        {
            'text': 'Продукты 1500 01/01/2024',
            'expected': {
                'amount': 1500,
                'description': 'Продукты',
                'expense_date': date(2024, 1, 1)
            }
        },
        # Короткая дата дд.мм (текущий год)
        {
            'text': '31.12 фейерверки 3000',
            'expected': {
                'amount': 3000,
                'description': 'фейерверки',
                'expense_date': date(date.today().year, 12, 31)
            }
        },
        # Без даты (должно быть None)
        {
            'text': 'Такси 500',
            'expected': {
                'amount': 500,
                'description': 'Такси',
                'expense_date': None
            }
        },
        # С валютой и датой
        {
            'text': 'Обед 50 долларов 10.11.2023',
            'expected': {
                'amount': 50,
                'description': 'Обед',
                'currency': 'USD',
                'expense_date': date(2023, 11, 10)
            }
        },
        # Сложный текст с датой
        {
            'text': 'Купил продукты в магните за 2500 рублей 28.02.2024',
            'expected': {
                'amount': 2500,
                'description': 'Купил продукты в магните',
                'expense_date': date(2024, 2, 28)
            }
        }
    ]
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПАРСИНГА ДАТ В ТРАТАХ")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        text = test['text']
        expected = test['expected']
        
        print(f"\nТест {i}: '{text}'")
        
        # Парсим текст
        result = await parse_expense_message(text, use_ai=False)
        
        if not result:
            print(f"  [X] Парсинг не удался")
            failed += 1
            continue
        
        # Проверяем результаты
        errors = []
        
        # Проверка суммы
        if result.get('amount') != expected['amount']:
            errors.append(f"Сумма: ожидалось {expected['amount']}, получено {result.get('amount')}")
        
        # Проверка даты
        if result.get('expense_date') != expected.get('expense_date'):
            errors.append(f"Дата: ожидалось {expected.get('expense_date')}, получено {result.get('expense_date')}")
        
        # Проверка валюты (если указана в ожиданиях)
        if 'currency' in expected and result.get('currency') != expected['currency']:
            errors.append(f"Валюта: ожидалось {expected['currency']}, получено {result.get('currency')}")
        
        if errors:
            print(f"  [X] Ошибки:")
            for error in errors:
                print(f"     - {error}")
            failed += 1
        else:
            print(f"  [OK] Успешно!")
            print(f"     Сумма: {result['amount']}")
            print(f"     Описание: {result['description']}")
            print(f"     Дата: {result.get('expense_date', 'не указана')}")
            if result.get('currency') != 'RUB':
                print(f"     Валюта: {result['currency']}")
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТЫ: [OK] Успешно: {passed}, [X] Провалено: {failed}")
    print("=" * 60)
    
    if failed == 0:
        print("\n[SUCCESS] Все тесты пройдены успешно!")
    else:
        print(f"\n[WARNING] {failed} тестов провалились")


async def test_time_assignment():
    """Тестирование установки времени для трат задним числом"""
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ВРЕМЕНИ ДЛЯ ТРАТ ЗАДНИМ ЧИСЛОМ")
    print("=" * 60)
    
    from bot.services.expense import create_expense
    from expenses.models import Profile
    
    # Получаем или создаем тестовый профиль
    try:
        profile = await Profile.objects.aget(telegram_id=881292737)
        user_id = profile.telegram_id
    except Profile.DoesNotExist:
        print("[ERROR] Профиль не найден. Создайте профиль с ID 881292737")
        return
    
    # Тест 1: Трата с датой задним числом
    print("\nТест 1: Трата задним числом (должно быть 12:00)")
    expense1 = await create_expense(
        user_id=user_id,
        amount=1000,
        description="Тестовая трата задним числом",
        expense_date=date(2024, 1, 15)
    )
    
    if expense1:
        print(f"  Дата: {expense1.expense_date}")
        print(f"  Время: {expense1.expense_time}")
        if expense1.expense_time.hour == 12 and expense1.expense_time.minute == 0:
            print("  [OK] Время установлено корректно (12:00)")
        else:
            print(f"  [ERROR] Неправильное время! Ожидалось 12:00")
        
        # Удаляем тестовую трату
        await expense1.adelete()
    
    # Тест 2: Трата на сегодня
    print("\nТест 2: Трата на сегодня (должно быть текущее время)")
    expense2 = await create_expense(
        user_id=user_id,
        amount=500,
        description="Тестовая трата сегодня",
        expense_date=date.today()
    )
    
    if expense2:
        print(f"  Дата: {expense2.expense_date}")
        print(f"  Время: {expense2.expense_time}")
        from datetime import datetime
        now = datetime.now().time()
        time_diff = abs(
            expense2.expense_time.hour * 60 + expense2.expense_time.minute -
            (now.hour * 60 + now.minute)
        )
        if time_diff < 2:  # Разница менее 2 минут
            print("  [OK] Время установлено корректно (текущее)")
        else:
            print(f"  [WARNING] Время отличается от текущего на {time_diff} минут")
        
        # Удаляем тестовую трату
        await expense2.adelete()


async def main():
    """Главная функция"""
    print("\n[START] ЗАПУСК ТЕСТОВ ПАРСИНГА ДАТ\n")
    
    # Тестируем парсинг дат
    await test_date_parsing()
    
    # Тестируем установку времени
    await test_time_assignment()
    
    print("\n[DONE] Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())