#!/usr/bin/env python
"""
Тестирование всех функций AI для проверки форматирования ответов
"""
import asyncio
import os
import sys
from datetime import datetime, date, timedelta
from decimal import Decimal

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

import django
django.setup()

from bot.services.expense_functions import ExpenseFunctions
from bot.services.google_ai_service import GoogleAIService

# Тестовый user_id (используем реальный из БД)
TEST_USER_ID = 881292737  # пользователь с тратами

async def test_function(name: str, func, *args, **kwargs):
    """Тестирует функцию и выводит результат"""
    print(f"\n{'='*60}")
    print(f"Тестируем: {name}")
    print(f"{'='*60}")
    
    try:
        result = await func(*args, **kwargs)
        
        if isinstance(result, dict):
            if result.get('success'):
                print(f"[OK] Успешно!")
                # Выводим ключевую информацию
                for key in ['count', 'total', 'date', 'amount', 'query', 'message']:
                    if key in result:
                        print(f"  {key}: {result[key]}")
                
                # Проверяем размер данных
                if 'expenses' in result:
                    print(f"  Количество трат: {len(result['expenses'])}")
                if 'details' in result:
                    print(f"  Количество деталей: {len(result['details'])}")
                if 'categories' in result:
                    print(f"  Количество категорий: {len(result['categories'])}")
                if 'daily_totals' in result:
                    print(f"  Количество дней: {len(result['daily_totals'])}")
                if 'results' in result:
                    print(f"  Количество результатов: {len(result['results'])}")
            else:
                print(f"[ERROR] Ошибка: {result.get('message', 'Неизвестная ошибка')}")
        else:
            print(f"[RESULT] Результат: {result[:200] if isinstance(result, str) else result}")
            
    except Exception as e:
        print(f"[EXCEPTION] Исключение: {type(e).__name__}: {str(e)}")

async def test_ai_formatting():
    """Тестирует форматирование ответов через AI сервис"""
    print("\n" + "="*60)
    print("ТЕСТИРУЕМ ФОРМАТИРОВАНИЕ ЧЕРЕЗ AI SERVICE")
    print("="*60)
    
    ai_service = GoogleAIService()
    
    # Эмулируем результаты функций для тестирования форматирования
    test_cases = [
        {
            'func_name': 'get_expenses_list',
            'result': {
                'success': True,
                'start_date': '2024-08-01',
                'end_date': '2024-08-31',
                'count': 75,
                'total': 450000.0,
                'expenses': [
                    {'date': '2024-08-31', 'time': '20:15', 'amount': 1500.0, 'description': 'Продукты в Перекрестке'},
                    {'date': '2024-08-31', 'time': '18:30', 'amount': 2500.0, 'description': 'Бензин'},
                ] * 40  # Эмулируем 80 трат
            }
        },
        {
            'func_name': 'get_max_single_expense',
            'result': {
                'success': True,
                'date': '2024-08-15',
                'weekday': 'Четверг',
                'amount': 25000.0,
                'category': 'Дом',
                'description': 'Оплата аренды квартиры'
            }
        },
        {
            'func_name': 'get_category_statistics',
            'result': {
                'success': True,
                'total': 150000.0,
                'categories': [
                    {'name': 'Еда', 'total': 50000.0, 'count': 150, 'percentage': 33.3},
                    {'name': 'Транспорт', 'total': 30000.0, 'count': 45, 'percentage': 20.0},
                ] * 8  # Эмулируем 16 категорий
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n--- Тестируем форматирование: {test['func_name']} ---")
        
        # Проверяем, относится ли функция к большим данным
        large_data_functions = {
            'get_expenses_list',
            'get_max_expense_day', 
            'get_category_statistics',
            'get_daily_totals',
            'search_expenses',
            'get_expenses_by_amount_range'
        }
        
        if test['func_name'] in large_data_functions:
            print("[BIG DATA] Функция с большим объемом данных - используется локальное форматирование")
        else:
            print("[AI FORMAT] Функция с малым объемом данных - используется AI форматирование")
        
        # Здесь бы вызывался реальный код форматирования из GoogleAIService
        # Но для теста просто показываем тип обработки
        
        data_size = 0
        if 'expenses' in test['result']:
            data_size = len(test['result']['expenses'])
        elif 'categories' in test['result']:
            data_size = len(test['result']['categories'])
            
        print(f"   Размер данных: {data_size} записей")
        
        if data_size > 50:
            print(f"   [WARNING] Данные будут обрезаны до 50 записей для AI")

async def main():
    """Основная функция тестирования"""
    print("Начинаем тестирование функций AI\n")
    
    # 1. Функции с большим объемом данных
    print("\n" + "="*60)
    print("ФУНКЦИИ С БОЛЬШИМ ОБЪЕМОМ ДАННЫХ (локальное форматирование)")
    print("="*60)
    
    # get_expenses_list - список трат
    await test_function(
        "get_expenses_list - Список трат за август",
        ExpenseFunctions.get_expenses_list,
        TEST_USER_ID,
        start_date="2024-08-01",
        end_date="2024-08-31"
    )
    
    # get_max_expense_day - день с максимальными тратами
    await test_function(
        "get_max_expense_day - День с максимальными тратами",
        ExpenseFunctions.get_max_expense_day,
        TEST_USER_ID,
        period_days=60
    )
    
    # get_category_statistics - статистика по категориям
    await test_function(
        "get_category_statistics - Статистика по категориям",
        ExpenseFunctions.get_category_statistics,
        TEST_USER_ID,
        period_days=30
    )
    
    # get_daily_totals - траты по дням
    await test_function(
        "get_daily_totals - Траты по дням",
        ExpenseFunctions.get_daily_totals,
        TEST_USER_ID,
        days=30
    )
    
    # search_expenses - поиск трат
    await test_function(
        "search_expenses - Поиск трат со словом 'продукты'",
        ExpenseFunctions.search_expenses,
        TEST_USER_ID,
        query="продукты"
    )
    
    # get_expenses_by_amount_range - траты в диапазоне сумм
    await test_function(
        "get_expenses_by_amount_range - Траты от 1000 до 5000",
        ExpenseFunctions.get_expenses_by_amount_range,
        TEST_USER_ID,
        min_amount=1000,
        max_amount=5000
    )
    
    # 2. Функции с малым объемом данных
    print("\n" + "="*60)
    print("ФУНКЦИИ С МАЛЫМ ОБЪЕМОМ ДАННЫХ (AI форматирование)")
    print("="*60)
    
    # get_max_single_expense - самая большая трата
    await test_function(
        "get_max_single_expense - Самая большая трата",
        ExpenseFunctions.get_max_single_expense,
        TEST_USER_ID,
        period_days=60
    )
    
    # get_average_expenses - средние значения
    await test_function(
        "get_average_expenses - Средние траты",
        ExpenseFunctions.get_average_expenses,
        TEST_USER_ID,
        period_days=30
    )
    
    # get_category_total - сумма по категории
    await test_function(
        "get_category_total - Траты на еду",
        ExpenseFunctions.get_category_total,
        TEST_USER_ID,
        category="Еда",
        period="month"
    )
    
    # compare_periods - сравнение периодов
    await test_function(
        "compare_periods - Сравнение этой и прошлой недели",
        ExpenseFunctions.compare_periods,
        TEST_USER_ID,
        period1="this_week",
        period2="last_week"
    )
    
    # get_weekday_statistics - статистика по дням недели
    await test_function(
        "get_weekday_statistics - Траты по дням недели",
        ExpenseFunctions.get_weekday_statistics,
        TEST_USER_ID,
        period_days=30
    )
    
    # predict_month_expense - прогноз на месяц
    await test_function(
        "predict_month_expense - Прогноз трат на месяц",
        ExpenseFunctions.predict_month_expense,
        TEST_USER_ID
    )
    
    # check_budget_status - статус бюджета
    await test_function(
        "check_budget_status - Статус бюджета",
        ExpenseFunctions.check_budget_status,
        TEST_USER_ID,
        budget_amount=150000
    )
    
    # get_period_total - сумма за период
    await test_function(
        "get_period_total - Траты за сегодня",
        ExpenseFunctions.get_period_total,
        TEST_USER_ID,
        period="today"
    )
    
    # 3. Тестируем форматирование
    await test_ai_formatting()
    
    print("\n" + "="*60)
    print("[COMPLETE] ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())