#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Финальное исправление категорий - объединение дубликатов с переносом расходов
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense, Cashback, Budget
from django.db import transaction
from django.db.models import Count, Sum


def fix_user_categories(telegram_id: int, dry_run: bool = True):
    """Полное исправление категорий пользователя"""
    
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"\n{'='*70}")
        print(f"FIXING CATEGORIES FOR USER {telegram_id}")
        print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        print(f"{'='*70}\n")
        
        # Шаг 1: Анализ текущего состояния
        print("STEP 1: Analyzing current state...")
        all_categories = profile.categories.all().order_by('id')
        active_categories = profile.categories.filter(is_active=True)
        
        print(f"Total categories: {all_categories.count()}")
        print(f"Active categories: {active_categories.count()}")
        
        # Находим все расходы пользователя
        all_expenses = Expense.objects.filter(profile=profile)
        print(f"Total expenses: {all_expenses.count()}")
        
        # Шаг 2: Находим дубликаты и объединяем их
        print("\nSTEP 2: Finding and merging duplicates...")
        
        # Словарь для группировки по уникальному ключу
        category_groups = {}
        
        for cat in all_categories:
            # Определяем ключ для группировки
            # Приоритет: name_ru, затем name_en, затем очищенное name
            if cat.name_ru:
                key = cat.name_ru.lower().strip()
            elif cat.name_en:
                key = cat.name_en.lower().strip()
            elif cat.name:
                # Убираем эмодзи из name для ключа
                import re
                clean_name = re.sub(r'[^\w\s]', '', cat.name).strip().lower()
                if clean_name:
                    key = clean_name
                else:
                    key = f"unknown_{cat.id}"
            else:
                key = f"unknown_{cat.id}"
            
            if key not in category_groups:
                category_groups[key] = []
            category_groups[key].append(cat)
        
        # Обрабатываем группы с дубликатами
        total_moved_expenses = 0
        total_merged_categories = 0
        
        with transaction.atomic():
            for key, cats in category_groups.items():
                if len(cats) > 1:
                    print(f"\nFound duplicate group '{key}': {len(cats)} categories")
                    
                    # Выбираем главную категорию
                    # Приоритеты: 1) активная, 2) с расходами, 3) с полными данными, 4) первая по ID
                    main_cat = None
                    max_score = -1
                    
                    for cat in cats:
                        score = 0
                        if cat.is_active:
                            score += 1000
                        
                        expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                        score += expense_count * 10
                        
                        if cat.name_ru and cat.name_en:
                            score += 100
                        elif cat.name_ru or cat.name_en:
                            score += 50
                        
                        if cat.icon:
                            score += 5
                        
                        # Меньший ID = старше = приоритетнее
                        score -= cat.id * 0.001
                        
                        print(f"  - ID={cat.id}: active={cat.is_active}, expenses={expense_count}, score={score:.1f}")
                        
                        if score > max_score:
                            max_score = score
                            main_cat = cat
                    
                    print(f"  Main category: ID={main_cat.id}")
                    
                    # Переносим данные из дубликатов в главную
                    for cat in cats:
                        if cat.id != main_cat.id:
                            # Переносим расходы
                            expenses_to_move = Expense.objects.filter(profile=profile, category=cat)
                            moved_count = expenses_to_move.count()
                            
                            if moved_count > 0:
                                if not dry_run:
                                    expenses_to_move.update(category=main_cat)
                                print(f"  {'Would move' if dry_run else 'Moved'} {moved_count} expenses from ID={cat.id} to ID={main_cat.id}")
                                total_moved_expenses += moved_count
                            
                            # Переносим кешбеки
                            cashbacks = Cashback.objects.filter(profile=profile, category=cat)
                            if cashbacks.exists():
                                if not dry_run:
                                    for cb in cashbacks:
                                        # Проверяем нет ли уже такого кешбека
                                        existing = Cashback.objects.filter(
                                            profile=profile,
                                            category=main_cat,
                                            month=cb.month
                                        ).first()
                                        if not existing:
                                            cb.category = main_cat
                                            cb.save()
                                        else:
                                            cb.delete()
                                print(f"  {'Would move' if dry_run else 'Moved'} cashbacks from ID={cat.id}")
                            
                            # Переносим бюджеты
                            budgets = Budget.objects.filter(profile=profile, category=cat)
                            if budgets.exists():
                                if not dry_run:
                                    for budget in budgets:
                                        # Проверяем нет ли уже такого бюджета
                                        existing = Budget.objects.filter(
                                            profile=profile,
                                            category=main_cat,
                                            period_type=budget.period_type
                                        ).first()
                                        if not existing:
                                            budget.category = main_cat
                                            budget.save()
                                        else:
                                            budget.delete()
                                print(f"  {'Would move' if dry_run else 'Moved'} budgets from ID={cat.id}")
                            
                            # Удаляем дубликат
                            if not dry_run:
                                cat.delete()
                            print(f"  {'Would delete' if dry_run else 'Deleted'} duplicate ID={cat.id}")
                            total_merged_categories += 1
                    
                    # Обновляем главную категорию
                    if not dry_run:
                        # Заполняем пустые поля если есть данные из дубликатов
                        updated = False
                        for cat in cats:
                            if cat.id != main_cat.id:
                                if not main_cat.name_ru and cat.name_ru:
                                    main_cat.name_ru = cat.name_ru
                                    updated = True
                                if not main_cat.name_en and cat.name_en:
                                    main_cat.name_en = cat.name_en
                                    updated = True
                                if not main_cat.icon and cat.icon:
                                    main_cat.icon = cat.icon
                                    updated = True
                        
                        # Убеждаемся что категория активна
                        if not main_cat.is_active:
                            main_cat.is_active = True
                            updated = True
                        
                        if updated:
                            main_cat.save()
                            print(f"  Updated main category ID={main_cat.id}")
        
        # Шаг 3: Проверка результатов
        print(f"\n{'='*70}")
        print("STEP 3: Verification")
        print(f"{'='*70}\n")
        
        # Проверяем финальное состояние
        final_active = profile.categories.filter(is_active=True).count()
        final_total = profile.categories.all().count()
        orphan_expenses = Expense.objects.filter(profile=profile, category__isnull=True).count()
        
        print(f"Final active categories: {final_active}")
        print(f"Final total categories: {final_total}")
        print(f"Orphan expenses (without category): {orphan_expenses}")
        
        # Проверяем расходы по категориям
        print("\nExpenses by category:")
        categories_with_expenses = profile.categories.filter(
            is_active=True,
            expenses__profile=profile
        ).distinct().annotate(
            expense_count=Count('expenses'),
            expense_sum=Sum('expenses__amount')
        ).order_by('-expense_sum')
        
        for cat in categories_with_expenses[:10]:
            print(f"  ID={cat.id}: {cat.name_ru or cat.name_en or cat.name} - {cat.expense_count} expenses, sum={cat.expense_sum:.0f}")
        
        # Итоги
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}\n")
        print(f"Categories merged: {total_merged_categories}")
        print(f"Expenses moved: {total_moved_expenses}")
        print(f"Active categories reduced from {active_categories.count()} to {final_active}")
        
        if dry_run:
            print("\n⚠️  This was a DRY RUN. No changes were made.")
            print("To execute, run with --execute flag")
        else:
            print("\n✅ All categories have been fixed successfully!")
            print("The PDF report should now display all categories correctly.")
        
        return True
        
    except Profile.DoesNotExist:
        print(f"❌ User {telegram_id} not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix user categories completely')
    parser.add_argument('telegram_id', type=int, nargs='?', default=881292737,
                        help='Telegram ID (default: 881292737)')
    parser.add_argument('--execute', action='store_true',
                        help='Execute changes (default is dry run)')
    
    args = parser.parse_args()
    
    success = fix_user_categories(args.telegram_id, dry_run=not args.execute)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())