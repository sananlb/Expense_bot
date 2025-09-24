#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестирование распознавания доходов со словом "плюс"
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import detect_income_intent
from bot.utils.validators import parse_description_amount

def test_income_detection():
    """Тестируем распознавание дохода"""

    test_cases = [
        # Знак +
        ("+5000", True, "Начинается с +"),
        ("+5000 зарплата", True, "Знак + в начале с описанием"),
        ("долг +1200", True, "Знак + в середине"),
        ("возврат +500 рублей", True, "Знак + с валютой"),

        # Слово "плюс"
        ("плюс 5000", True, "Слово 'плюс' в начале"),
        ("зарплата плюс 3000", True, "Слово 'плюс' в середине"),
        ("плюс 1000 долг", True, "Слово 'плюс' с описанием"),
        ("бонус плюс 2500 руб", True, "Слово 'плюс' с валютой"),

        # Не доход
        ("кофе 200", False, "Обычный расход"),
        ("зарплата 100000", False, "Нет знака + или 'плюс'"),
        ("получил 5000", False, "Нет знака + или 'плюс'"),
        ("заработал 3000", False, "Нет знака + или 'плюс'"),
        ("продукты 1500", False, "Обычный расход"),
    ]

    print("=" * 60)
    print("Тестирование функции detect_income_intent")
    print("=" * 60)

    for text, expected, description in test_cases:
        result = detect_income_intent(text)
        status = "OK" if result == expected else "FAIL"
        print(f"{status} '{text}' -> {result} (ожидалось {expected}) - {description}")

    print("\n" + "=" * 60)
    print("Тестирование функции parse_description_amount")
    print("=" * 60)

    parse_test_cases = [
        # Знак +
        ("+5000", True, 5000.0, None),
        ("зарплата +10000", True, 10000.0, "Зарплата"),  # С большой буквы

        # Слово "плюс" отдельно
        ("плюс 5000", True, 5000.0, None),
        ("зарплата плюс 10000", True, 10000.0, "Зарплата"),  # С большой буквы
        ("бонус плюс 2500", True, 2500.0, "Бонус"),  # С большой буквы

        # Слово "плюс" слитно с суммой
        ("плюс5000", True, 5000.0, None),

        # Обычные расходы
        ("кофе 200", False, 200.0, "Кофе"),  # С большой буквы
        ("1500", False, 1500.0, None),
    ]

    for text, expected_income, expected_amount, expected_desc in parse_test_cases:
        try:
            result = parse_description_amount(text, allow_only_amount=True)
            is_income = result.get('is_income', False)
            amount = result.get('amount')
            description = result.get('description')

            income_ok = is_income == expected_income
            amount_ok = amount == expected_amount
            desc_ok = description == expected_desc

            if income_ok and amount_ok and desc_ok:
                print(f"OK   '{text}' -> доход={is_income}, сумма={amount}, описание={description}")
            else:
                print(f"FAIL '{text}' -> доход={is_income} (ожидалось {expected_income}), "
                      f"сумма={amount} (ожидалось {expected_amount}), "
                      f"описание={description} (ожидалось {expected_desc})")
        except ValueError as e:
            print(f"ERR  '{text}' -> Ошибка: {e}")

if __name__ == "__main__":
    test_income_detection()