#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест полного цикла обработки траты
"""

import os
import sys
import django
import io
import asyncio

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message
from bot.services.category import get_or_create_category
from expenses.models import Profile

async def test_complete_flow():
    """Тестируем полный цикл: парсинг -> определение категории"""
    user_id = 881292737
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except:
        profile = None
    
    test_input = "капучино, пицца 500"
    
    print("=" * 60)
    print("ТЕСТ ПОЛНОГО ЦИКЛА ОБРАБОТКИ ТРАТЫ")
    print("=" * 60)
    
    print(f"\nВходной текст: '{test_input}'")
    print("-" * 40)
    
    # Шаг 1: Парсинг
    print("\nШаг 1: Парсинг сообщения")
    parsed = await parse_expense_message(test_input, user_id=user_id, profile=profile, use_ai=False)
    
    if parsed:
        print(f"  ✅ Успешно распарсено:")
        print(f"     Сумма: {parsed['amount']}")
        print(f"     Описание: {parsed['description']}")
        print(f"     Категория из парсера: {parsed['category']}")
        print(f"     Уверенность: {parsed['confidence']}")
        
        # Шаг 2: Получение/создание категории
        print(f"\nШаг 2: Получение категории пользователя")
        print(f"  Передаем в get_or_create_category: '{parsed['category']}'")
        
        category = await get_or_create_category(user_id, parsed['category'])
        
        print(f"  ✅ Получена категория: {category.name}")
        
        # Проверка результата
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ:")
        if "прочие" in category.name.lower():
            print("  ❌ ОШИБКА: Определилась категория 'Прочие расходы'!")
            print("     Ожидалось: Кафе и рестораны")
        elif "кафе" in category.name.lower() or "ресторан" in category.name.lower():
            print("  ✅ УСПЕХ: Трата корректно категоризована как расход на кафе!")
        else:
            print(f"  ⚠️ Неожиданная категория: {category.name}")
    else:
        print("  ❌ Не удалось распарсить сообщение")
    
    print("=" * 60)

# Запускаем тест
asyncio.run(test_complete_flow())