#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: AI с реальными словами
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
from expenses.models import Profile
from asgiref.sync import sync_to_async

# Ваш telegram ID
user_id = 881292737

async def test_ai_real():
    """Тестируем AI с реальными словами"""
    
    # Получаем профиль
    @sync_to_async
    def get_profile():
        try:
            return Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            return Profile.objects.create(telegram_id=user_id)
    
    profile = await get_profile()
    
    print("=" * 80)
    print("ТЕСТ AI С РЕАЛЬНЫМИ СЛОВАМИ")
    print("=" * 80)
    
    # Реальные слова, которых нет в ключевых
    test_cases = [
        ("книга 800", "Книга - нет в ключевых словах"),
        ("подписка 500", "Подписка - нет в ключевых словах"),
        ("ноутбук 50000", "Ноутбук - нет в ключевых словах"),
        ("парковка 200", "Парковка - есть в Автомобиль"),
        ("кофе 150", "Кофе - есть в Кафе"),
    ]
    
    for text, description in test_cases:
        print(f"\n{'='*60}")
        print(f"📝 Тест: '{text}'")
        print(f"   {description}")
        print("-" * 60)
        
        # С AI
        parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
        if parsed:
            print(f"✅ Результат:")
            print(f"   Категория: {parsed['category']}")
            print(f"   Уверенность: {parsed.get('confidence', 0):.0%}")
            
            if parsed.get('ai_enhanced'):
                print(f"   ✨ AI ИСПОЛЬЗОВАЛСЯ!")
                print(f"   Провайдер: {parsed.get('ai_provider', 'unknown')}")
                print(f"   AI определил более подходящую категорию")
            else:
                if any(word in text for word in ['книга', 'подписка', 'ноутбук']):
                    print(f"   ℹ️ AI должен был подключиться (слова нет в ключевых)")
                else:
                    print(f"   ✅ Найдено в ключевых словах")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ai_real())