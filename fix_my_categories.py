#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Исправление категорий для пользователя 881292737
"""

import os
import sys
import django
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense
from django.db import transaction
from bot.utils.default_categories import UNIFIED_CATEGORIES

def fix_categories():
    """Исправление категорий"""
    telegram_id = 881292737
    
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"Fixing categories for user {telegram_id}")
        print(f"Profile ID: {profile.id}")
        print("-" * 60)
        
        with transaction.atomic():
            # Исправляем категорию ID=147 (name_en без name_ru)
            try:
                cat = ExpenseCategory.objects.get(id=147, profile=profile)
                print(f"\nFixing category ID=147:")
                print(f"  Current: name_ru='{cat.name_ru}', name_en='{cat.name_en}'")
                
                # Эта категория имеет name_en='Delivery club', заполним name_ru
                cat.name_ru = 'Доставка еды'
                cat.original_language = 'en'
                cat.is_translatable = True
                cat.save()
                print(f"  Fixed: name_ru='Доставка еды'")
            except ExpenseCategory.DoesNotExist:
                print("Category ID=147 not found")
                
            # Исправляем категорию ID=131 (name_ru без name_en)
            try:
                cat = ExpenseCategory.objects.get(id=131, profile=profile)
                print(f"\nFixing category ID=131:")
                print(f"  Current: name_ru='{cat.name_ru}', name_en='{cat.name_en}'")
                
                # Эта категория имеет name_ru='Красотища', заполним name_en
                cat.name_en = 'Beauty'
                cat.original_language = 'ru'
                cat.is_translatable = True
                cat.save()
                print(f"  Fixed: name_en='Beauty'")
            except ExpenseCategory.DoesNotExist:
                print("Category ID=131 not found")
                
            # Исправляем категорию ID=153 (name_ru без name_en)
            try:
                cat = ExpenseCategory.objects.get(id=153, profile=profile)
                print(f"\nFixing category ID=153:")
                print(f"  Current: name_ru='{cat.name_ru}', name_en='{cat.name_en}'")
                
                # Эта категория имеет name_ru='Другие продукты', заполним name_en
                if 'Другие продукты' in cat.name_ru:
                    cat.name_en = 'Other groceries'
                    cat.original_language = 'ru'
                    cat.is_translatable = True
                    cat.save()
                    print(f"  Fixed: name_en='Other groceries'")
            except ExpenseCategory.DoesNotExist:
                print("Category ID=153 not found")
                
            # Синхронизируем поле name для всех категорий
            print("\n" + "=" * 60)
            print("Synchronizing 'name' field for all categories...")
            
            categories = profile.categories.filter(is_active=True)
            synced_count = 0
            
            for category in categories:
                old_name = category.name
                
                # Определяем язык пользователя
                user_lang = profile.language_code or 'ru'
                
                # Формируем правильное значение для поля name
                if user_lang == 'ru' and category.name_ru:
                    new_name = f"{category.icon or ''} {category.name_ru}".strip()
                elif user_lang == 'en' and category.name_en:
                    new_name = f"{category.icon or ''} {category.name_en}".strip()
                elif category.name_ru:
                    new_name = f"{category.icon or ''} {category.name_ru}".strip()
                elif category.name_en:
                    new_name = f"{category.icon or ''} {category.name_en}".strip()
                else:
                    continue
                    
                if old_name != new_name:
                    category.name = new_name
                    category.save()
                    synced_count += 1
                    print(f"  Synced ID={category.id}: '{old_name}' -> '{new_name}'")
                    
            print(f"\nSynced {synced_count} categories")
            
            # Проверяем и объединяем дубликаты
            print("\n" + "=" * 60)
            print("Checking for duplicates...")
            
            # Группируем по name_ru
            name_groups = {}
            for cat in categories:
                if cat.name_ru:
                    key = cat.name_ru.lower()
                    if key not in name_groups:
                        name_groups[key] = []
                    name_groups[key].append(cat)
            
            merged_count = 0
            for name, cats in name_groups.items():
                if len(cats) > 1:
                    print(f"\nFound duplicates for '{name}':")
                    
                    # Выбираем основную категорию (с максимальным количеством расходов)
                    main_cat = None
                    max_expenses = 0
                    
                    for cat in cats:
                        expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                        print(f"  - ID={cat.id}: {expense_count} expenses")
                        if expense_count > max_expenses:
                            max_expenses = expense_count
                            main_cat = cat
                    
                    if not main_cat:
                        main_cat = cats[0]
                    
                    # Переносим все расходы на основную категорию
                    for cat in cats:
                        if cat.id != main_cat.id:
                            moved = Expense.objects.filter(
                                profile=profile,
                                category=cat
                            ).update(category=main_cat)
                            
                            if moved > 0:
                                print(f"  Moved {moved} expenses from ID={cat.id} to ID={main_cat.id}")
                            
                            # Деактивируем дубликат
                            cat.is_active = False
                            cat.save()
                            merged_count += 1
                            print(f"  Deactivated duplicate ID={cat.id}")
            
            print(f"\nMerged {merged_count} duplicate categories")
            
        print("\n" + "=" * 60)
        print("SUCCESS! All categories have been fixed.")
        print("The PDF report should now display all categories correctly.")
        
    except Profile.DoesNotExist:
        print(f"User {telegram_id} not found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_categories()