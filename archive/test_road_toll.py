#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: почему "платная дорога" не категоризируется
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

from bot.utils.expense_parser import parse_expense_message
from bot.utils.expense_categorizer import categorize_expense
from expenses.models import Profile, CATEGORY_KEYWORDS
from asgiref.sync import sync_to_async

# Ваш telegram ID
user_id = 881292737

async def test_road_toll():
    """Тестируем категоризацию 'платная дорога'"""
    
    # Получаем профиль
    @sync_to_async
    def get_profile():
        try:
            return Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            return Profile.objects.create(telegram_id=user_id)
    
    profile = await get_profile()
    
    text = "платная дорога 750"
    
    print("=" * 80)
    print(f"ТЕСТ: '{text}'")
    print("=" * 80)
    
    # 1. Проверяем, есть ли в статических ключевых словах
    print("\n1️⃣ ПРОВЕРКА СТАТИЧЕСКИХ КЛЮЧЕВЫХ СЛОВ:")
    print("-" * 40)
    
    found_in_static = False
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if 'платн' in keyword.lower() or 'дорог' in keyword.lower():
                print(f"✅ Найдено в категории '{cat_name}':")
                print(f"   Ключевое слово: '{keyword}'")
                found_in_static = True
                
    if not found_in_static:
        print("❌ НЕ найдено в статических ключевых словах")
        print("   Слова 'платная' и 'дорога' отсутствуют")
    
    # 2. Тест категоризации БЕЗ AI
    print("\n2️⃣ КАТЕГОРИЗАЦИЯ БЕЗ AI:")
    print("-" * 40)
    
    parsed_no_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
    if parsed_no_ai:
        print(f"Категория: {parsed_no_ai['category']}")
        print(f"Уверенность: {parsed_no_ai.get('confidence', 0):.0%}")
        
        if parsed_no_ai['category'] == 'Прочие расходы':
            print("⚠️ Определилось как 'Прочие расходы' (ожидаемо, слов нет в ключевых)")
    
    # 3. Тест категоризации С AI
    print("\n3️⃣ КАТЕГОРИЗАЦИЯ С AI:")
    print("-" * 40)
    
    import time
    start_time = time.time()
    
    parsed_with_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    
    elapsed_time = time.time() - start_time
    
    if parsed_with_ai:
        print(f"Категория: {parsed_with_ai['category']}")
        print(f"Уверенность: {parsed_with_ai.get('confidence', 0):.0%}")
        print(f"Время обработки: {elapsed_time:.2f} сек")
        
        if parsed_with_ai.get('ai_enhanced'):
            print(f"✅ AI использовался (провайдер: {parsed_with_ai.get('ai_provider', 'unknown')})")
        else:
            print("❌ AI НЕ использовался")
            
        if elapsed_time < 0.5:
            print("⚠️ Очень быстро! Возможно, AI не подключался")
    
    # 4. Анализ
    print("\n" + "=" * 80)
    print("АНАЛИЗ:")
    print("=" * 80)
    
    print("""
Если "платная дорога" определилась как "Прочие расходы" быстро:

1. Слов нет в статических ключевых словах
2. AI должен был подключиться (слово не найдено)
3. Если обработка < 0.5 сек - AI точно не подключался

РЕКОМЕНДАЦИИ:
1. Добавить "платная дорога", "платная трасса", "toll" в категорию "Автомобиль"
2. Проверить, почему AI не подключается (возможно, ошибка в логике)
    """)
    
    # Проверим, какие слова есть для автомобиля
    print("\n📋 Ключевые слова для категории 'Автомобиль':")
    if 'Автомобиль' in CATEGORY_KEYWORDS:
        for kw in CATEGORY_KEYWORDS['Автомобиль'][:20]:
            print(f"   - {kw}")
        if len(CATEGORY_KEYWORDS['Автомобиль']) > 20:
            print(f"   ... и еще {len(CATEGORY_KEYWORDS['Автомобиль']) - 20}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_road_toll())