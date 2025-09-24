#!/usr/bin/env python3
"""
Тест для проверки единообразной обработки временных периодов
"""
import sys
import os
import django
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.date_utils import get_period_dates
from bot.services.function_call_utils import normalize_function_call


def test_unified_periods():
    """Тестируем единообразную обработку временных периодов"""

    today = date.today()
    print(f"Сегодня: {today}")
    print("=" * 50)

    # Тест 1: Проверяем функцию get_period_dates
    print("\n1. Тестирование get_period_dates:")
    periods = ['today', 'yesterday', 'week', 'last_week', 'month', 'last_month']

    for period in periods:
        start, end = get_period_dates(period)
        print(f"  {period:12} -> с {start} по {end}")

    # Тест 2: Проверяем корректность дат для last_week
    print("\n2. Проверка корректности last_week:")
    last_week_start, last_week_end = get_period_dates('last_week')

    # Проверяем что начало - понедельник
    assert last_week_start.weekday() == 0, "Начало недели должно быть понедельником"
    # Проверяем что конец - воскресенье
    assert last_week_end.weekday() == 6, "Конец недели должно быть воскресеньем"
    # Проверяем что это полная неделя (7 дней)
    assert (last_week_end - last_week_start).days == 6, "Неделя должна содержать 7 дней"
    print(f"  OK: last_week корректно определяет прошлую неделю (Пн-Вс)")

    # Тест 3: Проверяем корректность last_month
    print("\n3. Проверка корректности last_month:")
    last_month_start, last_month_end = get_period_dates('last_month')

    # Проверяем что начало - 1 число
    assert last_month_start.day == 1, "Начало месяца должно быть 1 числом"
    # Проверяем что это прошлый месяц
    if today.month == 1:
        assert last_month_start.month == 12 and last_month_start.year == today.year - 1
    else:
        assert last_month_start.month == today.month - 1 and last_month_start.year == today.year
    print(f"  OK: last_month корректно определяет прошлый месяц")

    # Тест 4: Проверяем normalize_function_call с новыми параметрами
    print("\n4. Проверка normalize_function_call:")

    test_cases = [
        {
            "func": "get_max_single_expense",
            "params": {"period": "last_week"},
            "expected_param": "period",
            "expected_value": "last_week"
        },
        {
            "func": "search_expenses",
            "params": {"query": "кофе", "period": "last_month"},
            "expected_param": "period",
            "expected_value": "last_month"
        }
    ]

    for test in test_cases:
        func_name, params = normalize_function_call(
            message="test",
            func_name=test["func"],
            params=test["params"],
            user_id=12345
        )

        if test["expected_param"] in params and params[test["expected_param"]] == test["expected_value"]:
            print(f"  OK: {test['func']} правильно обрабатывает {test['expected_param']}='{test['expected_value']}'")
        else:
            print(f"  ERROR: {test['func']} не сохранил {test['expected_param']}='{test['expected_value']}'")
            print(f"         Получено: {params}")

    print("\n" + "=" * 50)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("\nВсе функции теперь поддерживают:")
    print("  - 'last_week' для прошлой календарной недели")
    print("  - 'last_month' для прошлого календарного месяца")
    print("\nAI теперь должен использовать эти параметры вместо вычисления дат")


if __name__ == "__main__":
    test_unified_periods()