#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: полное удаление категории и откат к статическим ключевым словам
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
from bot.services.category import get_or_create_category
from expenses.models import Profile
from asgiref.sync import sync_to_async

# Ваш telegram ID
user_id = 881292737

async def test_full_flow():
    """Тестируем полный цикл при удаленной категории"""
    
    # Получаем профиль асинхронно
    @sync_to_async
    def get_profile():
        try:
            return Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            return Profile.objects.create(telegram_id=user_id)
    
    profile = await get_profile()
    
    print("=" * 80)
    print("ПОЛНЫЙ ЦИКЛ: Парсинг → Категоризация → Получение категории")
    print("=" * 80)
    
    test_input = "кофе 200"
    
    print(f"\n📝 Входные данные: '{test_input}'")
    print("-" * 40)
    
    # Шаг 1: Парсинг
    print("\n1️⃣ ПАРСИНГ:")
    parsed = await parse_expense_message(test_input, user_id=user_id, profile=profile, use_ai=False)
    
    if parsed:
        print(f"   Категория из парсера: '{parsed['category']}'")
        print(f"   (это статическая категория из CATEGORY_KEYWORDS)")
        
        # Шаг 2: get_or_create_category
        print(f"\n2️⃣ GET_OR_CREATE_CATEGORY:")
        print(f"   Получает: '{parsed['category']}'")
        
        category = await get_or_create_category(user_id, parsed['category'])
        
        print(f"   Возвращает: '{category.name}'")
        
        # Анализ
        print("\n" + "=" * 80)
        print("АНАЛИЗ:")
        print("=" * 80)
        
        if parsed['category'] == 'кафе':
            print("✅ Парсер вернул 'кафе' из статических ключевых слов")
        
        if 'кафе' in category.name.lower() or 'ресторан' in category.name.lower():
            print("✅ get_or_create_category нашла подходящую категорию пользователя")
        elif 'прочие' in category.name.lower():
            print("⚠️ get_or_create_category не нашла 'кафе' и вернула 'Прочие расходы'")
            print("   Это происходит, если у пользователя нет категории с 'кафе' в названии")
    
    print("\n" + "=" * 80)
    print("ВЫВОД:")
    print("=" * 80)
    print("""
Если пользователь удалит категорию "🍽️ Кафе и рестораны":

1. Парсер все равно вернет "кафе" из статических ключевых слов
2. get_or_create_category попытается найти категорию с "кафе" в названии
3. Если не найдет - создаст/вернет "💰 Прочие расходы"

Таким образом, статические ключевые слова ВСЕГДА работают,
но расход может попасть в "Прочие", если нет подходящей категории.
    """)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_full_flow())