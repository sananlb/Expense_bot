#!/usr/bin/env python3
"""
Тест для проверки исправления промокодов на 100% скидку
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import PromoCode
from decimal import Decimal

def test_promo_code_discount():
    """Тестируем применение скидок промокодов"""

    print("=" * 50)
    print("ТЕСТ ПРОМОКОДОВ")
    print("=" * 50)

    # Тестовые данные
    base_prices = [150, 600]  # Месячная и полугодовая подписки

    # Создаем тестовые промокоды
    test_cases = [
        {'type': 'percent', 'value': 10, 'desc': '10% скидка'},
        {'type': 'percent', 'value': 50, 'desc': '50% скидка'},
        {'type': 'percent', 'value': 100, 'desc': '100% скидка (бесплатно)'},
        {'type': 'percent', 'value': 120, 'desc': '120% скидка (некорректно)'},
        {'type': 'fixed', 'value': 50, 'desc': 'Фиксированная скидка 50 звезд'},
        {'type': 'fixed', 'value': 200, 'desc': 'Фиксированная скидка 200 звезд (больше цены)'},
        {'type': 'days', 'value': 30, 'desc': '30 дополнительных дней'},
    ]

    for case in test_cases:
        print(f"\n{case['desc']}:")
        print("-" * 30)

        # Создаем временный промокод
        promo = PromoCode(
            code=f"TEST_{case['type'].upper()}_{case['value']}",
            discount_type=case['type'],
            discount_value=Decimal(str(case['value']))
        )

        for base_price in base_prices:
            if case['type'] == 'days':
                print(f"  Базовая цена {base_price} звезд -> Промокод типа 'days' не влияет на цену")
            else:
                result = promo.apply_discount(base_price)
                print(f"  Базовая цена {base_price} звезд -> {result} звезд")

                # Проверяем что результат не отрицательный
                if result < 0:
                    print(f"    ❌ ОШИБКА: Получен отрицательный результат!")
                elif result == 0:
                    print(f"    ⚠️  ВНИМАНИЕ: Результат 0 звезд (нужна специальная обработка)")
                else:
                    print(f"    ✅ OK: Корректный результат")

def test_edge_cases():
    """Тестируем граничные случаи"""
    print("\n" + "=" * 50)
    print("ТЕСТ ГРАНИЧНЫХ СЛУЧАЕВ")
    print("=" * 50)

    # Тест с негативными значениями
    print("\n1. Тест с некорректными значениями скидки:")
    promo_negative = PromoCode(
        code="TEST_NEGATIVE",
        discount_type='percent',
        discount_value=Decimal('-10')
    )

    result = promo_negative.apply_discount(150)
    print(f"  Скидка -10% на 150 звезд -> {result} звезд")

    # Тест с очень большими значениями
    print("\n2. Тест с очень большой скидкой:")
    promo_big = PromoCode(
        code="TEST_BIG",
        discount_type='percent',
        discount_value=Decimal('999')
    )

    result = promo_big.apply_discount(150)
    print(f"  Скидка 999% на 150 звезд -> {result} звезд")

if __name__ == "__main__":
    test_promo_code_discount()
    test_edge_cases()
    print("\n" + "=" * 50)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 50)