#!/usr/bin/env python
"""
Тест исправления индикатора печатания
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_intent import is_show_expenses_request

def test_expense_intent():
    """Тест определения намерений"""
    print("=" * 60)
    print("ТЕСТ ОПРЕДЕЛЕНИЯ НАМЕРЕНИЙ")
    print("=" * 60)
    
    test_cases = [
        # (текст, ожидается_показ_трат)
        ("Кофе 450 вчера", False),
        ("Кофе 450", False),
        ("450 кофе", False),
        ("продукты 1200 вчера", False),
        ("вчера", True),
        ("траты вчера", True),
        ("покажи траты", True),
        ("показать расходы за вчера", True),
        ("сколько потратил вчера", True),
        ("что я купил вчера", False),  # Аналитический вопрос
        ("на что больше всего потратил", False),  # Аналитический вопрос
    ]
    
    for text, expected_show in test_cases:
        is_show, confidence = is_show_expenses_request(text)
        
        # Проверяем результат
        status = "OK" if (is_show and confidence >= 0.7) == expected_show else "FAIL"
        result = "показ трат" if is_show and confidence >= 0.7 else "добавление траты"
        
        print(f"{status:4} '{text}' -> {result} (confidence: {confidence:.2f})")
        if status == "FAIL":
            print(f"   ОШИБКА: Ожидалось {'показ трат' if expected_show else 'добавление траты'}")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    test_expense_intent()