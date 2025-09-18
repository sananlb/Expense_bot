#!/usr/bin/env python3
"""
Отладочный скрипт для проверки категорий и поиска
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.append('/mnt/c/Users/_batman_/Desktop/expense_bot')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

# Настройка Django
django.setup()

from expenses.models import Profile, ExpenseCategory
from bot.services.cashback_free_text import _resolve_category, _normalize_letters
import asyncio
from asgiref.sync import sync_to_async

@sync_to_async
def get_test_profile():
    """Получаем первый доступный профиль для тестирования"""
    try:
        return Profile.objects.first()
    except:
        return None

async def test_category_search():
    """Тестируем поиск категорий"""
    print("=== Отладка поиска категорий ===\n")
    
    # Получаем тестовый профиль
    profile = await get_test_profile()
    if not profile:
        print("❌ Нет профилей в базе данных")
        return
    
    print(f"📱 Тестовый профиль: {profile.telegram_id}")
    
    # Получаем все категории профиля
    categories = await sync_to_async(list)(profile.categories.all())
    print(f"📂 Всего категорий: {len(categories)}\n")
    
    print("📋 Список всех категорий:")
    for i, cat in enumerate(categories, 1):
        print(f"{i:2}. {cat.name}")
    print()
    
    # Тестовые поиски
    test_searches = [
        "подарки",
        "Подарки", 
        "подарок",
        "🎁 Подарки",
        "кафе",
        "кафе и рестораны",
        "рестораны",
        "продукты",
        "супермаркеты",
    ]
    
    print("🔍 Тестирование поиска категорий:")
    for search_term in test_searches:
        result = await _resolve_category(profile, search_term)
        status = "✅" if result else "❌"
        found_name = result.name if result else "НЕ НАЙДЕНА"
        print(f"{status} '{search_term}' -> {found_name}")
    
    print("\n🔧 Анализ нормализации:")
    test_normalizations = [
        "подарки",
        "Подарки",
        "🎁 Подарки",
        "🎁подарки",
    ]
    
    for term in test_normalizations:
        normalized = _normalize_letters(term)
        print(f"'{term}' -> '{normalized}'")
    
    print("\n📊 Анализ токенизации для поиска подарков:")
    gift_categories = [cat for cat in categories if 'подарк' in cat.name.lower() or 'подар' in cat.name.lower()]
    
    if gift_categories:
        for cat in gift_categories:
            from bot.services.cashback_free_text import tokenize
            import re
            
            def tokenize(s: str):
                s = _normalize_letters(s)
                toks = re.findall(r"[\wа-яА-Я]+", s)
                stop = {"и", "в", "на", "по"}
                return {t for t in toks if t and t not in stop}
            
            tokens = tokenize(cat.name)
            print(f"Категория: '{cat.name}' -> токены: {tokens}")
            
            # Проверяем поиск разными способами
            for search in ["подарки", "подарок"]:
                search_tokens = tokenize(search)
                is_subset = search_tokens.issubset(tokens)
                print(f"  '{search}' ({search_tokens}) подмножество? {is_subset}")
    else:
        print("❌ Категории с 'подарк' не найдены")

if __name__ == "__main__":
    asyncio.run(test_category_search())