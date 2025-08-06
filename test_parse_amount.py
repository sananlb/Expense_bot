#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: почему не парсится сумма в "платная дорога 750"
"""

import os
import sys
import django
import io
import re
from decimal import Decimal

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import AMOUNT_PATTERNS

test_cases = [
    "платная дорога 750",
    "Платная дорога 750",
    "платная дорога",
    "подарки 300",
    "кофе 200",
]

print("=" * 80)
print("ТЕСТ ПАРСИНГА СУММЫ")
print("=" * 80)

for text in test_cases:
    print(f"\n📝 Текст: '{text}'")
    print("-" * 40)
    
    # Нормализуем как в парсере
    text_normalized = text.strip().lower()
    print(f"Нормализовано: '{text_normalized}'")
    
    amount_found = False
    for i, pattern in enumerate(AMOUNT_PATTERNS):
        match = re.search(pattern, text_normalized, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = Decimal(amount_str)
                print(f"✅ Паттерн #{i+1} нашел: {amount}")
                print(f"   Совпадение: '{match.group(0)}'")
                amount_found = True
                break
            except Exception as e:
                print(f"❌ Паттерн #{i+1} нашел '{match.group(0)}', но ошибка: {e}")
    
    if not amount_found:
        print("❌ Сумма НЕ найдена!")
        print("   Проверьте паттерны AMOUNT_PATTERNS")

print("\n" + "=" * 80)
print("ПАТТЕРНЫ ДЛЯ ПОИСКА СУММЫ:")
print("=" * 80)
for i, pattern in enumerate(AMOUNT_PATTERNS):
    print(f"{i+1}. {pattern}")