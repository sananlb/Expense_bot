#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестирование мультиязычных категорий
"""

import os
import sys
import django
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, CategoryKeyword

def test_multilingual_categories():
    """Тестирование мультиязычных категорий"""
    
    # ID пользователя Alexey Nalbantov
    user_id = 881292737
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        print(f"[OK] Профиль найден для пользователя {user_id}")
        print(f"   ID профиля: {profile.id}")
        
        categories = profile.categories.all().order_by('name')
        print(f"\nВсего категорий: {categories.count()}")
        
        print("\n" + "=" * 80)
        print("ТЕСТИРОВАНИЕ МУЛЬТИЯЗЫЧНЫХ ПОЛЕЙ")
        print("=" * 80)
        
        # Проверяем несколько категорий
        test_categories = categories[:5]  # Берем первые 5 для теста
        
        for cat in test_categories:
            print(f"\nКатегория: {cat.name}")
            print(f"  name_ru: {cat.name_ru}")
            print(f"  name_en: {cat.name_en}")
            print(f"  original_language: {cat.original_language}")
            print(f"  is_translatable: {cat.is_translatable}")
            print(f"  icon: [emoji]")
            
            # Тестируем метод get_display_name
            print("\n  Отображение:")
            ru_display = ''.join(c for c in cat.get_display_name('ru') if ord(c) < 128 or c.isalpha() or c.isspace())
            en_display = ''.join(c for c in cat.get_display_name('en') if ord(c) < 128 or c.isalpha() or c.isspace())
            print(f"    На русском: {ru_display}")
            print(f"    На английском: {en_display}")
            
            # Проверяем ключевые слова
            keywords = cat.keywords.all()
            if keywords:
                print(f"\n  Ключевые слова ({keywords.count()}):")
                for kw in keywords[:3]:  # Показываем первые 3
                    print(f"    - {kw.keyword} ({kw.language})")
        
        print("\n" + "=" * 80)
        print("ПРОВЕРКА КАТЕГОРИИ 'ПОДАРКИ'")
        print("=" * 80)
        
        # Ищем категорию "Подарки" или "Gifts"
        gift_categories = categories.filter(name_ru='Подарки') | categories.filter(name_en='Gifts')
        
        if gift_categories.exists():
            for cat in gift_categories:
                print(f"\n[FOUND] {cat.name}")
                print(f"  name_ru: {cat.name_ru}")
                print(f"  name_en: {cat.name_en}")
                print(f"  is_translatable: {cat.is_translatable}")
        else:
            print("\n[WARNING] Категория 'Подарки'/'Gifts' не найдена")
            
            # Проверяем есть ли вообще категории с этими словами
            gift_like = categories.filter(name__icontains='gift') | categories.filter(name__icontains='подарк')
            if gift_like.exists():
                print("\nНайдены похожие категории:")
                for cat in gift_like:
                    print(f"  - {cat.name} (ru: {cat.name_ru}, en: {cat.name_en})")
        
        print("\n" + "=" * 80)
        print("ТЕСТ ЗАВЕРШЕН")
        print("=" * 80)
        
    except Profile.DoesNotExist:
        print(f"[ERROR] Профиль не найден для пользователя {user_id}")
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multilingual_categories()