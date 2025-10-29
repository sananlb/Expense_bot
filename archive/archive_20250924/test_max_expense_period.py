#!/usr/bin/env python3
"""
Тест для проверки обработки временных периодов в функции get_max_single_expense
"""
import sys
import os
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.function_call_utils import normalize_function_call

def test_max_expense_with_periods():
    """Тестируем различные временные периоды для get_max_single_expense"""

    test_cases = [
        {
            "message": "какая моя самая большая трата на прошлой неделе?",
            "func_name": "get_max_single_expense",
            "params": {"period": "week"},
            "expected_days": 7
        },
        {
            "message": "какая моя самая большая трата за последний месяц?",
            "func_name": "get_max_single_expense",
            "params": {"period": "month"},
            "expected_days": 31
        },
        {
            "message": "какая моя самая большая трата за год?",
            "func_name": "get_max_single_expense",
            "params": {"period": "year"},
            "expected_days": 365
        },
        {
            "message": "какая моя самая большая трата?",
            "func_name": "get_max_single_expense",
            "params": {},
            "expected_days": 60  # Default
        }
    ]

    print("Тестирование обработки временных периодов для get_max_single_expense:\n")

    for test in test_cases:
        func_name, params = normalize_function_call(
            message=test["message"],
            func_name=test["func_name"],
            params=test["params"],
            user_id=12345
        )

        print(f"Сообщение: {test['message']}")
        print(f"Входные параметры: {test['params']}")
        print(f"Результат: func_name={func_name}, params={params}")
        print(f"Ожидалось period_days={test['expected_days']}")
        print(f"Получено period_days={params.get('period_days', 'НЕ УСТАНОВЛЕНО')}")

        if params.get('period_days') == test['expected_days']:
            print("OK: TEST PASSED")
        else:
            print("ERROR: period_days does not match expected value")
        print("-" * 50 + "\n")

if __name__ == "__main__":
    test_max_expense_with_periods()