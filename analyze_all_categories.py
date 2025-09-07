#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Анализ всех категорий в базе данных
"""

import os
import sys
import django
from pathlib import Path
from collections import defaultdict

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory

def analyze_categories():
    """Анализ всех категорий в базе"""
    
    # Собираем статистику по всем категориям
    all_categories = ExpenseCategory.objects.all()
    category_stats = defaultdict(int)
    
    # По пользователям
    profiles = Profile.objects.all()
    
    print("=" * 70)
    print("АНАЛИЗ КАТЕГОРИЙ В БАЗЕ ДАННЫХ")
    print("=" * 70)
    
    print(f"\nВсего профилей: {profiles.count()}")
    print(f"Всего категорий: {all_categories.count()}")
    
    # Анализ по языкам
    ru_categories = set()
    en_categories = set()
    mixed_categories = set()
    
    for cat in all_categories:
        name = cat.name
        # Убираем эмодзи для анализа
        text_only = ''.join(c for c in name if c.isalpha() or c.isspace()).strip()
        
        has_cyrillic = any('а' <= c.lower() <= 'я' or c == 'ё' for c in text_only)
        has_latin = any('a' <= c.lower() <= 'z' for c in text_only)
        
        if has_cyrillic and has_latin:
            mixed_categories.add(name)
        elif has_cyrillic:
            ru_categories.add(name)
        elif has_latin:
            en_categories.add(name)
        
        category_stats[name] += 1
    
    print("\n" + "=" * 70)
    print("СТАТИСТИКА ПО ЯЗЫКАМ")
    print("=" * 70)
    
    print(f"\nКатегории на русском: {len(ru_categories)}")
    print(f"Категории на английском: {len(en_categories)}")
    print(f"Смешанные категории: {len(mixed_categories)}")
    
    # Топ категорий по популярности
    print("\n" + "=" * 70)
    print("ТОП-20 КАТЕГОРИЙ ПО ПОПУЛЯРНОСТИ")
    print("=" * 70)
    
    sorted_categories = sorted(category_stats.items(), key=lambda x: x[1], reverse=True)
    for i, (cat_name, count) in enumerate(sorted_categories[:20], 1):
        # Убираем эмодзи для вывода
        cat_clean = ''.join(c for c in cat_name if ord(c) < 128 or c.isalpha() or c.isspace())
        print(f"{i:3}. {cat_clean:<40} - {count} пользователей")
    
    # Анализ конкретного пользователя
    print("\n" + "=" * 70)
    print("КАТЕГОРИИ ПОЛЬЗОВАТЕЛЯ 881292737 (Alexey Nalbantov)")
    print("=" * 70)
    
    try:
        profile = Profile.objects.get(telegram_id=881292737)
        user_categories = profile.categories.all().order_by('name')
        
        print(f"\nВсего категорий: {user_categories.count()}")
        print("\nСписок категорий:")
        
        for cat in user_categories:
            text_only = ''.join(c for c in cat.name if c.isalpha() or c.isspace()).strip()
            has_cyrillic = any('а' <= c.lower() <= 'я' or c == 'ё' for c in text_only)
            has_latin = any('a' <= c.lower() <= 'z' for c in text_only)
            
            if has_cyrillic and has_latin:
                lang = "MIXED"
            elif has_cyrillic:
                lang = "RU"
            elif has_latin:
                lang = "EN"
            else:
                lang = "EMOJI"
            
            cat_clean = ''.join(c for c in cat.name if ord(c) < 128 or c.isalpha() or c.isspace())
            print(f"  [{lang:5}] {cat_clean}")
            
    except Profile.DoesNotExist:
        print("Профиль не найден")
    
    # Выявление дубликатов (одинаковые категории на разных языках)
    print("\n" + "=" * 70)
    print("ПОТЕНЦИАЛЬНЫЕ ДУБЛИКАТЫ")
    print("=" * 70)
    
    # Мапинг известных переводов
    known_translations = {
        'продукты': 'products',
        'супермаркеты': 'supermarkets',
        'рестораны': 'restaurants',
        'кафе': 'cafe',
        'подарки': 'gifts',
        'такси': 'taxi',
        'транспорт': 'transport',
        'автомобиль': 'car',
        'жилье': 'housing',
        'аптеки': 'pharmacies',
        'медицина': 'medicine',
        'спорт': 'sport',
        'одежда': 'clothes',
        'обувь': 'shoes',
        'развлечения': 'entertainment',
        'образование': 'education',
        'путешествия': 'travel',
        'связь': 'communication',
        'интернет': 'internet',
    }
    
    duplicates_found = []
    for ru_cat in ru_categories:
        ru_text = ''.join(c for c in ru_cat.lower() if c.isalpha() or c.isspace()).strip()
        for en_cat in en_categories:
            en_text = ''.join(c for c in en_cat.lower() if c.isalpha() or c.isspace()).strip()
            
            for ru_word, en_word in known_translations.items():
                if ru_word in ru_text and en_word in en_text:
                    duplicates_found.append((ru_cat, en_cat))
                    break
    
    if duplicates_found:
        print("\nНайдены потенциальные дубликаты (одна категория на разных языках):")
        for ru, en in duplicates_found[:10]:
            ru_clean = ''.join(c for c in ru if ord(c) < 128 or c.isalpha() or c.isspace())
            en_clean = ''.join(c for c in en if ord(c) < 128 or c.isalpha() or c.isspace())
            print(f"  RU: {ru_clean:<30} <-> EN: {en_clean}")
    else:
        print("\nДубликаты не найдены")

if __name__ == "__main__":
    analyze_categories()