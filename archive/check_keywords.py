#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Проверка ключевых слов в базе данных
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

from expenses.models import Profile, ExpenseCategory, CategoryKeyword

# Ваш telegram ID
user_id = 881292737

try:
    profile = Profile.objects.get(telegram_id=user_id)
    print(f"Профиль найден: {profile.telegram_id}")
    
    categories = ExpenseCategory.objects.filter(profile=profile)
    
    print("\n" + "=" * 60)
    print("КЛЮЧЕВЫЕ СЛОВА В БАЗЕ ДАННЫХ")
    print("=" * 60)
    
    for cat in categories:
        keywords = CategoryKeyword.objects.filter(category=cat).order_by('-usage_count')
        
        if keywords.exists():
            print(f"\n📁 {cat.name}:")
            for kw in keywords[:10]:  # Показываем первые 10
                weight_str = f"(вес: {kw.normalized_weight:.2f})" if kw.normalized_weight != 1.0 else ""
                print(f"  - '{kw.keyword}' (использований: {kw.usage_count}) {weight_str}")
            
            if keywords.count() > 10:
                print(f"  ... и еще {keywords.count() - 10} слов")
    
    # Подсчет общего количества
    total_keywords = CategoryKeyword.objects.filter(category__profile=profile).count()
    print(f"\n📊 Всего ключевых слов в БД: {total_keywords}")
    
    # Проверяем конфликтующие слова (встречаются в разных категориях)
    print("\n" + "=" * 60)
    print("КОНФЛИКТУЮЩИЕ СЛОВА (в нескольких категориях):")
    print("=" * 60)
    
    from django.db.models import Count
    conflicting = CategoryKeyword.objects.filter(
        category__profile=profile
    ).values('keyword').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')
    
    if conflicting:
        for conf in conflicting[:10]:
            word = conf['keyword']
            print(f"\n'{word}' встречается в {conf['count']} категориях:")
            
            # Показываем в каких категориях
            kws = CategoryKeyword.objects.filter(
                category__profile=profile,
                keyword=word
            ).select_related('category')
            
            for kw in kws:
                print(f"  - {kw.category.name}: вес {kw.normalized_weight:.2f}, использований {kw.usage_count}")
    else:
        print("\nНет конфликтующих слов")
        
except Profile.DoesNotExist:
    print(f"Профиль с ID {user_id} не найден")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()