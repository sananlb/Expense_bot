#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: полная цепочка категоризации включая AI
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
from bot.utils.expense_categorizer import categorize_expense_with_weights
from expenses.models import Profile, CategoryKeyword
from asgiref.sync import sync_to_async

# Ваш telegram ID
user_id = 881292737

async def test_full_chain():
    """Тестируем полную цепочку категоризации"""
    
    # Получаем профиль
    @sync_to_async
    def get_profile():
        try:
            return Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            return Profile.objects.create(telegram_id=user_id)
    
    profile = await get_profile()
    
    print("=" * 80)
    print("ПОЛНАЯ ЦЕПОЧКА КАТЕГОРИЗАЦИИ")
    print("=" * 80)
    
    test_cases = [
        ("кофе 200", "Слово есть в статических ключевых словах"),
        ("непонятнаятрата 500", "Слова нет нигде - должен подключиться AI"),
        ("бургер 300", "Слово есть в статических ключевых словах"),
    ]
    
    for text, description in test_cases:
        print(f"\n📝 Тест: '{text}'")
        print(f"   ({description})")
        print("-" * 40)
        
        # 1. БЕЗ AI
        print("\n1️⃣ БЕЗ AI (use_ai=False):")
        parsed_no_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
        if parsed_no_ai:
            print(f"   Категория: {parsed_no_ai['category']}")
            print(f"   Уверенность: {parsed_no_ai.get('confidence', 0):.2%}")
            if parsed_no_ai.get('ai_enhanced'):
                print(f"   AI: Использовался")
            else:
                print(f"   AI: НЕ использовался")
        
        # 2. С AI
        print("\n2️⃣ С AI (use_ai=True):")
        parsed_with_ai = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
        if parsed_with_ai:
            print(f"   Категория: {parsed_with_ai['category']}")
            print(f"   Уверенность: {parsed_with_ai.get('confidence', 0):.2%}")
            if parsed_with_ai.get('ai_enhanced'):
                print(f"   ✨ AI: Использовался ({parsed_with_ai.get('ai_provider', 'unknown')})")
            else:
                print(f"   AI: НЕ использовался (нашли по ключевым словам)")
    
    print("\n" + "=" * 80)
    print("ПОЛНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ КАТЕГОРИЗАЦИИ:")
    print("=" * 80)
    print("""
1. categorize_expense_with_weights() - проверяет CategoryKeyword в БД
   ↓ не нашли
   
2. categorize_expense() - проверяет CATEGORY_KEYWORDS в коде  
   ↓ не нашли ИЛИ нашли, но категории нет у пользователя
   
3. AI Service (если use_ai=True) - анализирует с учетом категорий пользователя
   - OpenAI / Gemini / Claude (в зависимости от настроек)
   - Учитывает контекст последних трат
   - Выбирает из существующих категорий пользователя
   ↓ AI определил категорию
   
4. get_or_create_category() - маппинг на реальные категории
   ↓ не нашли подходящую
   
5. "💰 Прочие расходы" - финальный fallback
    """)
    
    # Проверим, есть ли ключевые слова в БД
    @sync_to_async
    def check_keywords():
        keywords = CategoryKeyword.objects.filter(
            category__profile=profile
        ).values_list('keyword', flat=True)
        return list(keywords)
    
    db_keywords = await check_keywords()
    
    print(f"\n📊 Статистика:")
    print(f"   Ключевых слов в БД: {len(db_keywords)}")
    if db_keywords:
        print(f"   Примеры: {', '.join(db_keywords[:5])}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_full_chain())