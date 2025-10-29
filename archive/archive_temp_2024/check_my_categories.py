#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Проверка категорий пользователя
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

from expenses.models import Profile, ExpenseCategory, Expense
from django.db.models import Count, Sum

def check_user_categories(telegram_id: int):
    """Проверка категорий пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"=== Анализ категорий для пользователя {telegram_id} ===")
        print(f"Profile ID: {profile.id}")
        print(f"Язык: {profile.language_code or 'ru'}")
        print("-" * 60)
        
        # Получаем все категории пользователя
        categories = profile.categories.filter(is_active=True).order_by('-id')
        print(f"\nВсего активных категорий: {categories.count()}")
        print("-" * 60)
        
        # Анализ каждой категории
        problems_found = False
        for idx, category in enumerate(categories, 1):
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
            problems = []
            
            # Проблема 1: Пустые мультиязычные поля
            if not category.name_ru:
                problems.append("MISSING name_ru")
            if not category.name_en:
                problems.append("MISSING name_en")
                
            # Проблема 2: Несоответствие старого и нового форматов
            if category.name and category.name_ru:
                # Удаляем эмодзи для сравнения
                clean_name = category.name.replace(category.icon or '', '').strip()
                if clean_name != category.name_ru and clean_name != category.name_en:
                    problems.append(f"NAME_MISMATCH: '{category.name}' vs ru:'{category.name_ru}' en:'{category.name_en}'")
            
            # Выводим информацию
            print(f"\n{idx}. Категория ID={category.id}")
            print(f"   name: '{category.name}'")
            print(f"   name_ru: '{category.name_ru or 'NULL'}'")
            print(f"   name_en: '{category.name_en or 'NULL'}'")
            print(f"   icon: '{category.icon or 'NULL'}'")
            print(f"   original_language: {category.original_language or 'NULL'}")
            print(f"   is_translatable: {category.is_translatable}")
            print(f"   Расходов: {expense_count} шт на сумму {expense_sum:.0f}")
            
            if problems:
                problems_found = True
                print(f"   ⚠️ ПРОБЛЕМЫ: {', '.join(problems)}")
        
        print("\n" + "=" * 60)
        if problems_found:
            print("❌ НАЙДЕНЫ ПРОБЛЕМЫ С КАТЕГОРИЯМИ")
            print("Это может быть причиной отображения только 6 категорий в PDF отчете!")
            print("\nРекомендация: запустить миграцию категорий")
        else:
            print("✅ Все категории выглядят корректно")
            
        # Проверяем дубликаты
        print("\n=== Проверка на дубликаты ===")
        # Группируем по name_ru
        name_groups = {}
        for cat in categories:
            if cat.name_ru:
                key = cat.name_ru.lower()
                if key not in name_groups:
                    name_groups[key] = []
                name_groups[key].append(cat)
        
        duplicates_found = False
        for name, cats in name_groups.items():
            if len(cats) > 1:
                duplicates_found = True
                print(f"\n⚠️ Дубликаты для '{name}':")
                for cat in cats:
                    expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                    print(f"   - ID={cat.id}, name='{cat.name}', расходов={expense_count}")
        
        if not duplicates_found:
            print("✅ Дубликатов не найдено")
            
    except Profile.DoesNotExist:
        print(f"Пользователь {telegram_id} не найден")
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ваш telegram_id
    check_user_categories(881292737)