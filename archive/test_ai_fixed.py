#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: исправленная логика подключения AI
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
import logging

# Включаем логирование для отслеживания
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Ваш telegram ID
user_id = 881292737

async def test_ai_fixed():
    """Тестируем исправленную логику AI"""
    
    # Получаем профиль
    @sync_to_async
    def get_profile():
        try:
            return Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            return Profile.objects.create(telegram_id=user_id)
    
    profile = await get_profile()
    
    print("=" * 80)
    print("ТЕСТ: ИСПРАВЛЕННАЯ ЛОГИКА AI")
    print("=" * 80)
    
    test_cases = [
        ("кофе 200", "Есть в статических ключевых словах → AI не нужен"),
        ("абракадабра 500", "НЕТ в ключевых словах → должен подключиться AI"),
        ("странная покупка 300", "НЕТ в ключевых словах → должен подключиться AI"),
        ("пицца 400", "Есть в статических ключевых словах → AI не нужен"),
    ]
    
    for text, scenario in test_cases:
        print(f"\n{'='*60}")
        print(f"📝 Тест: '{text}'")
        print(f"Сценарий: {scenario}")
        print("-" * 60)
        
        # Тест БЕЗ AI
        print("\n1️⃣ БЕЗ AI (use_ai=False):")
        parsed_no_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
        if parsed_no_ai:
            print(f"   Категория: {parsed_no_ai['category']}")
            print(f"   Уверенность: {parsed_no_ai.get('confidence', 0):.0%}")
        
        # Тест С AI
        print("\n2️⃣ С AI (use_ai=True):")
        parsed_with_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
        if parsed_with_ai:
            print(f"   Категория: {parsed_with_ai['category']}")
            print(f"   Уверенность: {parsed_with_ai.get('confidence', 0):.0%}")
            
            if parsed_with_ai.get('ai_enhanced'):
                print(f"   ✨ AI ИСПОЛЬЗОВАЛСЯ! (провайдер: {parsed_with_ai.get('ai_provider', 'unknown')})")
                print(f"   ✅ AI успешно подключился для неизвестного слова!")
            else:
                if "абракадабра" in text or "странная" in text:
                    print(f"   ⚠️ AI НЕ использовался (хотя должен был)")
                else:
                    print(f"   ✅ AI не использовался (правильно, слово найдено в ключевых)")
    
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТ ИСПРАВЛЕНИЯ:")
    print("=" * 80)
    print("""
Теперь AI должен подключаться в правильных случаях:

✅ AI подключается когда:
   - Слово НЕ найдено в ключевых словах (БД и статических)
   - Категория найдена, но её нет у пользователя

✅ AI НЕ подключается когда:
   - Слово найдено и категория есть у пользователя
   
Цепочка теперь работает правильно:
1. CategoryKeyword (БД) → 2. CATEGORY_KEYWORDS (код) → 3. AI → 4. "Прочие расходы"
    """)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ai_fixed())