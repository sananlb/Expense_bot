#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: поиск похожих трат в истории
"""

import os
import sys
import django
import asyncio
import io
from datetime import datetime, timedelta

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.expense import find_similar_expenses

async def test():
    user_id = 881292737
    
    test_cases = [
        "платная дорога",
        "кофе",
        "продукты", 
        "бензин",
        "такси"
    ]
    
    print("=" * 80)
    print("ТЕСТ ПОИСКА ПОХОЖИХ ТРАТ")
    print("=" * 80)
    
    for description in test_cases:
        print(f"\n📝 Ищем похожие траты для: '{description}'")
        print("-" * 40)
        
        similar = await find_similar_expenses(user_id, description)
        
        if similar:
            print(f"✅ Найдено {len(similar)} вариантов:")
            for i, item in enumerate(similar, 1):
                print(f"   {i}. {item['amount']} {item['currency']} - {item['category']}")
                print(f"      Использовано {item['count']} раз(а)")
                print(f"      Последний раз: {item['last_date']}")
        else:
            print("❌ Похожие траты не найдены")

if __name__ == "__main__":
    asyncio.run(test())