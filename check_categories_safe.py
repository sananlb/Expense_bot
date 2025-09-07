#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Безопасная проверка категорий пользователя
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
from django.db.models import Count, Sum
import json

def safe_str(text):
    """Безопасное преобразование в строку"""
    if text is None:
        return 'NULL'
    try:
        return str(text).encode('ascii', 'replace').decode('ascii')
    except:
        return 'UNICODE_ERROR'

def check_user_categories(telegram_id: int):
    """Проверка категорий пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"=== Analysis for user {telegram_id} ===")
        print(f"Profile ID: {profile.id}")
        print(f"Language: {profile.language_code or 'ru'}")
        print("-" * 60)
        
        # Получаем все категории пользователя
        categories = profile.categories.filter(is_active=True).order_by('-id')
        total_categories = categories.count()
        print(f"\nTotal active categories: {total_categories}")
        print("-" * 60)
        
        # Собираем данные для анализа
        category_data = []
        problems_count = 0
        
        for category in categories:
            # Считаем расходы
            expense_count = Expense.objects.filter(
                profile=profile,
                category=category
            ).count()
            
            expense_sum = Expense.objects.filter(
                profile=profile,
                category=category
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Проверяем проблемы
            has_problems = False
            
            if not category.name_ru:
                has_problems = True
                problems_count += 1
                
            if not category.name_en:
                has_problems = True
                
            cat_info = {
                'id': category.id,
                'name': safe_str(category.name),
                'name_ru': category.name_ru or 'NULL',
                'name_en': category.name_en or 'NULL',
                'icon': safe_str(category.icon) if category.icon else 'NULL',
                'original_language': category.original_language or 'NULL',
                'is_translatable': category.is_translatable,
                'expense_count': expense_count,
                'expense_sum': float(expense_sum),
                'has_problems': has_problems
            }
            category_data.append(cat_info)
        
        # Сохраняем в JSON для анализа
        output_file = 'category_analysis.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'telegram_id': telegram_id,
                'profile_id': profile.id,
                'total_categories': total_categories,
                'categories_with_problems': problems_count,
                'categories': category_data
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\nAnalysis saved to: {output_file}")
        
        # Выводим краткую статистику
        print("\n=== SUMMARY ===")
        print(f"Total categories: {total_categories}")
        print(f"Categories with problems: {problems_count}")
        
        # Показываем топ категорий по расходам
        print("\n=== TOP CATEGORIES BY EXPENSES ===")
        sorted_cats = sorted(category_data, key=lambda x: x['expense_sum'], reverse=True)
        for i, cat in enumerate(sorted_cats[:10], 1):
            status = "[PROBLEM]" if cat['has_problems'] else "[OK]"
            print(f"{i}. {status} ID={cat['id']}: {cat['expense_count']} expenses, sum={cat['expense_sum']:.0f}")
            if cat['has_problems']:
                print(f"   -> name_ru: {cat['name_ru']}, name_en: {cat['name_en']}")
        
        if problems_count > 0:
            print("\n!!! PROBLEMS FOUND !!!")
            print("This could be the reason for showing only 6 categories in PDF report!")
            print("Categories with missing multilingual fields may not be processed correctly.")
            
            # Показываем проблемные категории
            print("\n=== PROBLEMATIC CATEGORIES ===")
            problem_cats = [c for c in category_data if c['has_problems']]
            for cat in problem_cats[:10]:
                print(f"ID={cat['id']}: name_ru={cat['name_ru']}, name_en={cat['name_en']}, expenses={cat['expense_count']}")
        else:
            print("\nAll categories look good!")
            
    except Profile.DoesNotExist:
        print(f"User {telegram_id} not found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ваш telegram_id
    check_user_categories(881292737)