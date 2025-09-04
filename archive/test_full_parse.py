#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: полный парсинг "платная дорога 750"
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
from expenses.models import Profile

async def test():
    user_id = 881292737
    
    # Тестируем разные варианты
    test_cases = [
        "платная дорога 750",
        "Платная дорога 750",
        "платная дорога",
        "Платная дорога",
    ]
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except:
        profile = None
    
    print("=" * 80)
    print("ТЕСТ ПОЛНОГО ПАРСИНГА")
    print("=" * 80)
    
    for text in test_cases:
        print(f"\n📝 Текст: '{text}'")
        print("-" * 40)
        
        result = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
        
        if result:
            print("✅ Парсинг успешный:")
            print(f"   Сумма: {result['amount']}")
            print(f"   Описание: {result['description']}")
            print(f"   Категория: {result['category']}")
        else:
            print("❌ Парсер вернул None!")
            print("   Бот пропустит это сообщение к chat_router")

if __name__ == "__main__":
    asyncio.run(test())