#!/usr/bin/env python
"""
Тест парсера трат
"""

import os
import sys
import django
import asyncio

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message, extract_date_from_text
from datetime import date, timedelta

async def test_parser():
    """Тест парсера"""
    print("=" * 60)
    print("ТЕСТ ПАРСЕРА ТРАТ")
    print("=" * 60)
    
    test_cases = [
        "Кофе 440 вчера",
        "Кофе 440",
        "Продукты 1200 08.09",
        "Такси 650",
        "08.09 продукты 1500",
        "Обед в кафе 890",
    ]
    
    for text in test_cases:
        print(f"\nТекст: '{text}'")
        
        # Тест извлечения даты
        expense_date, text_without_date = extract_date_from_text(text)
        print(f"  Дата: {expense_date if expense_date else 'не найдена'}")
        print(f"  Текст без даты: '{text_without_date}'")
        
        # Тест полного парсинга (без AI)
        result = await parse_expense_message(text, use_ai=False)
        if result:
            print(f"  Результат парсинга:")
            print(f"    Сумма: {result.get('amount')}")
            print(f"    Описание: '{result.get('description')}'")
            print(f"    Категория: {result.get('category')}")
            print(f"    Дата: {result.get('expense_date')}")
        else:
            print(f"  Результат: не удалось распарсить")
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_parser())