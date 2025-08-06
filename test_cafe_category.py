#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест категоризации для кафе
"""

import os
import sys
import django
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.category import get_or_create_category
from expenses.models import Profile
import asyncio

async def test_categorization():
    """Тестируем категоризацию для кафе"""
    user_id = 881292737
    
    test_cases = [
        ("капучино, пицца", "Должно быть 'Кафе и рестораны'"),
        ("кафе", "Должно быть 'Кафе и рестораны'"),
        ("пицца", "Должно быть 'Кафе и рестораны'"),
        ("кофе", "Должно быть 'Кафе и рестораны'"),
    ]
    
    print("=" * 60)
    print("ТЕСТ ОПРЕДЕЛЕНИЯ КАТЕГОРИИ ЧЕРЕЗ get_or_create_category")
    print("=" * 60)
    
    for text, expected in test_cases:
        category = await get_or_create_category(user_id, text)
        print(f"\n'{text}':")
        print(f"  Результат: {category.name}")
        print(f"  Ожидание: {expected}")
        
        # Проверяем, что это не "Прочие расходы"
        if "прочие" in category.name.lower():
            print("  ❌ ОШИБКА: Определилась категория 'Прочие расходы'!")
        elif "кафе" in category.name.lower() or "ресторан" in category.name.lower():
            print("  ✅ Успешно: Определилась правильная категория!")
        else:
            print(f"  ⚠️ Предупреждение: Неожиданная категория")
    
    print("\n" + "=" * 60)

# Запускаем тест
asyncio.run(test_categorization())