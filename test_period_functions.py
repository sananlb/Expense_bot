#!/usr/bin/env python
"""
Тест всех функций работающих с периодами на поддержку месяцев и сезонов
"""

import os
import sys
import django
from datetime import date, datetime

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.expense_functions import ExpenseFunctions
from bot.utils.date_utils import get_period_dates

def test_period_dates():
    """Тестируем функцию get_period_dates"""
    print("=" * 50)
    print("Тестируем get_period_dates")
    print("=" * 50)

    test_periods = [
        'today', 'yesterday', 'week', 'month', 'year',
        'last_week', 'last_month',
        'январь', 'февраль', 'март', 'август', 'декабрь',
        'january', 'february', 'august', 'december',
        'зима', 'весна', 'лето', 'осень',
        'winter', 'spring', 'summer', 'autumn'
    ]

    for period in test_periods:
        try:
            start, end = get_period_dates(period)
            print(f"OK {period:15} -> {start} до {end}")
        except Exception as e:
            print(f"ERROR {period:15} -> ОШИБКА: {e}")

def test_expense_functions():
    """Тестируем функции расходов с периодами"""
    print("\n" + "=" * 50)
    print("Функции РАСХОДОВ с периодами")
    print("=" * 50)

    # ID тестового пользователя (замените на реальный)
    TEST_USER_ID = 6943130316

    test_periods = ['август', 'лето', 'august', 'summer']

    functions = [
        ('get_period_total', ExpenseFunctions.get_period_total),
        ('get_max_single_expense', ExpenseFunctions.get_max_single_expense),
        ('get_category_total', lambda uid, period: ExpenseFunctions.get_category_total(uid, 'продукты', period))
    ]

    for func_name, func in functions:
        print(f"\n{func_name}:")
        for period in test_periods:
            try:
                # Убираем декоратор @sync_to_async если он есть
                if hasattr(func, '__wrapped__'):
                    sync_func = func.__wrapped__
                else:
                    sync_func = func

                result = sync_func(TEST_USER_ID, period)
                if result.get('success'):
                    if 'start_date' in result and 'end_date' in result:
                        print(f"  OK {period:10} -> {result['start_date']} до {result['end_date']}")
                    else:
                        print(f"  OK {period:10} -> OK")
                else:
                    print(f"  ERROR {period:10} -> {result.get('message', 'Ошибка')}")
            except Exception as e:
                print(f"  ERROR {period:10} -> ОШИБКА: {e}")

def test_income_functions():
    """Тестируем функции доходов с периодами"""
    print("\n" + "=" * 50)
    print("Функции ДОХОДОВ с периодами")
    print("=" * 50)

    TEST_USER_ID = 6943130316
    test_periods = ['август', 'лето', 'august', 'summer']

    functions = [
        ('get_income_total', ExpenseFunctions.get_income_total),
        ('get_income_period_total', ExpenseFunctions.get_income_period_total),
        ('get_max_single_income', ExpenseFunctions.get_max_single_income),
        ('get_income_category_total', lambda uid, period: ExpenseFunctions.get_income_category_total(uid, 'зарплата', period))
    ]

    for func_name, func in functions:
        print(f"\n{func_name}:")
        for period in test_periods:
            try:
                # Убираем декоратор @sync_to_async если он есть
                if hasattr(func, '__wrapped__'):
                    sync_func = func.__wrapped__
                else:
                    sync_func = func

                result = sync_func(TEST_USER_ID, period)
                if result.get('success'):
                    if 'start_date' in result and 'end_date' in result:
                        print(f"  OK {period:10} -> {result['start_date']} до {result['end_date']}")
                    else:
                        print(f"  OK {period:10} -> OK")
                else:
                    print(f"  ERROR {period:10} -> {result.get('message', 'Ошибка')}")
            except Exception as e:
                print(f"  ERROR {period:10} -> ОШИБКА: {e}")

def test_combined_functions():
    """Тестируем комбинированные функции"""
    print("\n" + "=" * 50)
    print("КОМБИНИРОВАННЫЕ функции (доходы + расходы)")
    print("=" * 50)

    TEST_USER_ID = 6943130316
    test_periods = ['август', 'лето', 'august', 'summer']

    print("\nget_financial_summary:")
    for period in test_periods:
        try:
            func = ExpenseFunctions.get_financial_summary
            if hasattr(func, '__wrapped__'):
                sync_func = func.__wrapped__
            else:
                sync_func = func

            result = sync_func(TEST_USER_ID, period)
            if result.get('success'):
                if 'start_date' in result and 'end_date' in result:
                    print(f"  OK {period:10} -> {result['start_date']} до {result['end_date']}")
                    print(f"     Доходы: {result['income']['total']:.0f} RUB")
                    print(f"     Расходы: {result['expenses']['total']:.0f} RUB")
                    print(f"     Баланс: {result['balance']['net']:.0f} RUB")
                else:
                    print(f"  ✅ {period:10} -> OK")
            else:
                print(f"  ❌ {period:10} -> {result.get('message', 'Ошибка')}")
        except Exception as e:
            print(f"  ❌ {period:10} -> ОШИБКА: {e}")

def test_search_with_periods():
    """Тестируем функцию поиска с периодами"""
    print("\n" + "=" * 50)
    print("Функция ПОИСКА с периодами")
    print("=" * 50)

    TEST_USER_ID = 6943130316

    print("\nsearch_expenses с периодами:")
    test_cases = [
        ('продукты', 'август'),
        ('кофе', 'лето'),
        ('транспорт', 'last_month')
    ]

    for query, period in test_cases:
        try:
            func = ExpenseFunctions.search_expenses
            if hasattr(func, '__wrapped__'):
                sync_func = func.__wrapped__
            else:
                sync_func = func

            result = sync_func(TEST_USER_ID, query, period=period)
            if result.get('success'):
                print(f"  OK Поиск '{query}' за {period}: найдено {result['count']} трат на {result['total']:.0f} RUB")
            else:
                print(f"  ERROR Поиск '{query}' за {period}: {result.get('message', 'Ошибка')}")
        except Exception as e:
            print(f"  ERROR Поиск '{query}' за {period}: ОШИБКА: {e}")

if __name__ == '__main__':
    test_period_dates()
    test_expense_functions()
    test_income_functions()
    test_combined_functions()
    test_search_with_periods()

    print("\n" + "=" * 50)
    print("Тестирование завершено!")
    print("=" * 50)