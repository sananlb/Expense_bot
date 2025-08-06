#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест взаимодействия статических и динамических ключевых слов
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

from bot.utils.expense_categorizer import categorize_expense, categorize_expense_with_weights, categorize_expense_smart
from expenses.models import Profile, ExpenseCategory, CategoryKeyword, CATEGORY_KEYWORDS

# Ваш telegram ID
user_id = 881292737

def test_keyword_systems():
    """Тестируем разные системы ключевых слов"""
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        print("Профиль не найден!")
        return
    
    test_cases = [
        "капучино",
        "кофе",
        "пицца",
        "такси",
        "продукты",
        "бензин",
    ]
    
    print("=" * 80)
    print("СРАВНЕНИЕ СИСТЕМ КАТЕГОРИЗАЦИИ")
    print("=" * 80)
    
    for text in test_cases:
        print(f"\n📝 Текст: '{text}'")
        print("-" * 40)
        
        # 1. Статическая категоризация (из CATEGORY_KEYWORDS)
        cat_static, conf_static, _ = categorize_expense(text)
        print(f"1️⃣ Статическая (из кода):")
        print(f"   Категория: {cat_static}")
        print(f"   Уверенность: {conf_static:.2%}")
        
        # Проверяем, есть ли слово в статических ключевых словах
        found_in_static = False
        for cat_name, keywords in CATEGORY_KEYWORDS.items():
            if any(text.lower() in kw.lower() or kw.lower() in text.lower() for kw in keywords):
                found_in_static = True
                print(f"   ✅ Найдено в CATEGORY_KEYWORDS['{cat_name}']")
                break
        if not found_in_static:
            print(f"   ❌ НЕ найдено в статических ключевых словах")
        
        # 2. Динамическая категоризация (из БД с весами)
        cat_dynamic, conf_dynamic, _ = categorize_expense_with_weights(text, profile)
        print(f"\n2️⃣ Динамическая (из БД с весами):")
        print(f"   Категория: {cat_dynamic}")
        print(f"   Уверенность: {conf_dynamic:.2%}")
        
        # Проверяем, есть ли слово в БД
        keywords_in_db = CategoryKeyword.objects.filter(
            category__profile=profile,
            keyword__icontains=text.lower()
        )
        if keywords_in_db.exists():
            print(f"   ✅ Найдено в БД:")
            for kw in keywords_in_db:
                print(f"      - '{kw.keyword}' в категории '{kw.category.name}'")
                print(f"        Вес: {kw.normalized_weight:.2f}, Использований: {kw.usage_count}")
        else:
            print(f"   ❌ НЕ найдено в БД с ключевыми словами")
            # Если не найдено в БД, функция должна была откатиться к статической
            if cat_dynamic == cat_static:
                print(f"   ↩️ Откатилась к статической категоризации")
        
        # 3. Умная категоризация (комбинированная)
        cat_smart, conf_smart, _ = categorize_expense_smart(text, profile)
        print(f"\n3️⃣ Умная (комбинированная):")
        print(f"   Категория: {cat_smart}")
        print(f"   Уверенность: {conf_smart:.2%}")
        
        # Анализ результатов
        print(f"\n📊 Анализ:")
        if cat_static == cat_dynamic == cat_smart:
            print(f"   ✅ Все методы дали одинаковый результат")
        else:
            print(f"   ⚠️ Методы дали разные результаты:")
            if cat_static != cat_dynamic:
                print(f"      Статическая: {cat_static} vs Динамическая: {cat_dynamic}")
            if cat_dynamic != cat_smart:
                print(f"      Динамическая: {cat_dynamic} vs Умная: {cat_smart}")
    
    print("\n" + "=" * 80)
    print("ВЫВОДЫ:")
    print("=" * 80)
    print("""
1. Статическая категоризация использует CATEGORY_KEYWORDS из кода
2. Динамическая сначала ищет в БД (CategoryKeyword), если не находит - откатывается к статической
3. Умная категоризация - это обертка, которая выбирает между динамической и статической
4. Веса учитываются ТОЛЬКО для ключевых слов из БД
5. Статические ключевые слова НЕ имеют весов (все равнозначны)
    """)

if __name__ == "__main__":
    test_keyword_systems()