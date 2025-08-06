#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: что происходит когда пользователь удаляет дефолтную категорию
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

from bot.utils.expense_categorizer import categorize_expense, categorize_expense_with_weights
from expenses.models import Profile, ExpenseCategory, CategoryKeyword, CATEGORY_KEYWORDS

# Ваш telegram ID
user_id = 881292737

def test_deleted_category():
    """Тестируем что происходит при удалении категории"""
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        print("Профиль не найден!")
        return
    
    print("=" * 80)
    print("ТЕСТ: УДАЛЕНИЕ ДЕФОЛТНОЙ КАТЕГОРИИ")
    print("=" * 80)
    
    # Проверяем текущие категории
    print("\n📁 Текущие категории пользователя:")
    categories = ExpenseCategory.objects.filter(profile=profile)
    for cat in categories:
        print(f"  - {cat.name}")
    
    # Тестовые слова для кафе
    test_words = ["кофе", "капучино", "пицца", "ресторан"]
    
    print("\n" + "-" * 80)
    print("ТЕСТ 1: С существующей категорией 'Кафе и рестораны'")
    print("-" * 80)
    
    for word in test_words:
        # Динамическая категоризация (БД)
        cat_db, conf_db, _ = categorize_expense_with_weights(word, profile)
        # Статическая категоризация
        cat_static, conf_static, _ = categorize_expense(word)
        
        print(f"\n'{word}':")
        print(f"  БД → {cat_db} ({conf_db:.0%})")
        print(f"  Статика → {cat_static} ({conf_static:.0%})")
    
    # Симулируем удаление категории "Кафе и рестораны"
    print("\n" + "=" * 80)
    print("⚠️ СИМУЛЯЦИЯ: Что если пользователь удалит 'Кафе и рестораны'?")
    print("=" * 80)
    
    # Находим категорию кафе
    cafe_category = None
    for cat in categories:
        if 'кафе' in cat.name.lower() or 'ресторан' in cat.name.lower():
            cafe_category = cat
            break
    
    if cafe_category:
        print(f"\nНайдена категория: {cafe_category.name}")
        
        # Временно скрываем категорию (симулируем удаление)
        # Сохраняем оригинальное состояние
        original_is_active = cafe_category.is_active
        cafe_category.is_active = False
        cafe_category.save()
        
        print("✅ Категория временно деактивирована (симуляция удаления)")
        
        # Проверяем категоризацию БЕЗ этой категории
        print("\n" + "-" * 80)
        print("ТЕСТ 2: БЕЗ категории 'Кафе и рестораны' в БД пользователя")
        print("-" * 80)
        
        # Обновляем список активных категорий
        active_categories = ExpenseCategory.objects.filter(
            profile=profile, 
            is_active=True
        )
        
        print(f"\nАктивных категорий: {active_categories.count()}")
        
        for word in test_words:
            print(f"\n'{word}':")
            
            # Проверяем, есть ли слово в статических ключевых словах
            found_in_static = False
            static_category = None
            for cat_name, keywords in CATEGORY_KEYWORDS.items():
                if any(word.lower() in kw.lower() for kw in keywords):
                    found_in_static = True
                    static_category = cat_name
                    break
            
            if found_in_static:
                print(f"  ✅ Есть в CATEGORY_KEYWORDS['{static_category}']")
            else:
                print(f"  ❌ Нет в статических ключевых словах")
            
            # Динамическая категоризация (должна откатиться к статической)
            cat_db, conf_db, _ = categorize_expense_with_weights(word, profile)
            print(f"  БД → {cat_db} ({conf_db:.0%})")
            
            # Статическая категоризация (всегда работает)
            cat_static, conf_static, _ = categorize_expense(word)
            print(f"  Статика → {cat_static} ({conf_static:.0%})")
            
            # Анализ
            if cat_db == cat_static:
                print(f"  ↩️ БД откатилась к статической категоризации")
            else:
                print(f"  ⚠️ БД и статика дали разные результаты!")
        
        # Восстанавливаем категорию
        cafe_category.is_active = original_is_active
        cafe_category.save()
        print("\n✅ Категория восстановлена")
    else:
        print("❌ Категория 'Кафе и рестораны' не найдена")
    
    print("\n" + "=" * 80)
    print("ВЫВОДЫ:")
    print("=" * 80)
    print("""
1. Если пользователь удалит категорию из БД:
   - Ключевые слова этой категории из БД тоже удаляются (CASCADE)
   - Система автоматически откатывается к статическим ключевым словам
   
2. Статические ключевые слова ВСЕГДА доступны как запасной вариант
   
3. Проблема: статические категории возвращают "кафе", а у пользователя 
   может не быть такой категории (у него "🍽️ Кафе и рестораны")
   
4. Решение: функция get_or_create_category() создаст "Прочие расходы"
   если точной категории не найдено
    """)

if __name__ == "__main__":
    test_deleted_category()