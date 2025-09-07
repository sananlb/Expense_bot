#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для удаления дублированных категорий
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
from django.db.models import Count, Sum, Q


def analyze_duplicates(telegram_id: int):
    """Анализ дублированных категорий"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"\n{'='*70}")
        print(f"АНАЛИЗ ДУБЛИКАТОВ КАТЕГОРИЙ")
        print(f"Пользователь: {telegram_id} (Profile ID: {profile.id})")
        print(f"{'='*70}")
        
        # Получаем все активные категории
        categories = profile.categories.filter(is_active=True).order_by('name_ru', 'name_en', 'id')
        total = categories.count()
        print(f"\nВсего активных категорий: {total}")
        
        # Группируем по name_ru (основной критерий для русскоязычных)
        duplicates_ru = {}
        for cat in categories:
            if cat.name_ru:
                key = cat.name_ru.lower().strip()
                if key not in duplicates_ru:
                    duplicates_ru[key] = []
                duplicates_ru[key].append(cat)
        
        # Группируем по name_en (для англоязычных категорий)
        duplicates_en = {}
        for cat in categories:
            if cat.name_en:
                key = cat.name_en.lower().strip()
                if key not in duplicates_en:
                    duplicates_en[key] = []
                duplicates_en[key].append(cat)
        
        # Находим реальные дубликаты
        real_duplicates = {}
        
        # Дубликаты по name_ru
        for name, cats in duplicates_ru.items():
            if len(cats) > 1:
                real_duplicates[f"ru:{name}"] = cats
        
        # Дубликаты по name_en (только если нет name_ru)
        for name, cats in duplicates_en.items():
            if len(cats) > 1:
                # Проверяем что это не те же самые категории что уже есть в ru дубликатах
                is_new_group = True
                for existing_cats in real_duplicates.values():
                    if set(c.id for c in cats) == set(c.id for c in existing_cats):
                        is_new_group = False
                        break
                if is_new_group:
                    # Только категории без name_ru
                    cats_without_ru = [c for c in cats if not c.name_ru]
                    if len(cats_without_ru) > 1:
                        real_duplicates[f"en:{name}"] = cats_without_ru
        
        if not real_duplicates:
            print("\n✅ Дубликатов не найдено!")
            return None
        
        print(f"\n⚠️  НАЙДЕНО ГРУПП ДУБЛИКАТОВ: {len(real_duplicates)}")
        print("-" * 70)
        
        merge_plan = []
        
        for group_key, cats in real_duplicates.items():
            lang_type = group_key.split(':')[0]
            name = group_key.split(':', 1)[1]
            
            print(f"\n📁 Группа дубликатов: '{name}' ({lang_type})")
            print(f"   Количество дубликатов: {len(cats)}")
            
            # Анализируем каждую категорию в группе
            cat_stats = []
            for cat in cats:
                # Считаем связанные данные
                expenses = Expense.objects.filter(profile=profile, category=cat)
                expense_count = expenses.count()
                expense_sum = expenses.aggregate(total=Sum('amount'))['total'] or 0
                
                cashbacks = Cashback.objects.filter(profile=profile, category=cat).count()
                budgets = Budget.objects.filter(profile=profile, category=cat).count()
                
                cat_info = {
                    'category': cat,
                    'expense_count': expense_count,
                    'expense_sum': expense_sum,
                    'cashbacks': cashbacks,
                    'budgets': budgets,
                    'total_links': expense_count + cashbacks + budgets
                }
                cat_stats.append(cat_info)
                
                print(f"\n   ID={cat.id}:")
                print(f"     name: '{cat.name}'")
                print(f"     name_ru: '{cat.name_ru or 'NULL'}'")
                print(f"     name_en: '{cat.name_en or 'NULL'}'")
                print(f"     icon: '{cat.icon or 'NULL'}'")
                print(f"     Расходов: {expense_count} шт на сумму {expense_sum:.0f}")
                print(f"     Кешбеков: {cashbacks}")
                print(f"     Бюджетов: {budgets}")
            
            # Выбираем главную категорию (с максимальным количеством связей)
            cat_stats.sort(key=lambda x: (x['total_links'], x['expense_sum'], -x['category'].id), reverse=True)
            main_cat_info = cat_stats[0]
            main_cat = main_cat_info['category']
            
            print(f"\n   ➡️  ГЛАВНАЯ КАТЕГОРИЯ: ID={main_cat.id} (связей: {main_cat_info['total_links']})")
            
            # Формируем план слияния
            for cat_info in cat_stats[1:]:
                cat = cat_info['category']
                merge_plan.append({
                    'duplicate': cat,
                    'main': main_cat,
                    'expenses_to_move': cat_info['expense_count'],
                    'cashbacks_to_move': cat_info['cashbacks'],
                    'budgets_to_move': cat_info['budgets']
                })
                print(f"   🔄 Будет объединено: ID={cat.id} -> ID={main_cat.id}")
        
        return merge_plan
        
    except Profile.DoesNotExist:
        print(f"❌ Пользователь {telegram_id} не найден")
        return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return None


def merge_duplicates(telegram_id: int, dry_run: bool = True):
    """Объединение дублированных категорий"""
    merge_plan = analyze_duplicates(telegram_id)
    
    if not merge_plan:
        return
    
    print(f"\n{'='*70}")
    print(f"{'ПЛАН ОБЪЕДИНЕНИЯ (DRY RUN)' if dry_run else '🚀 ВЫПОЛНЕНИЕ ОБЪЕДИНЕНИЯ'}")
    print(f"{'='*70}")
    
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        
        total_expenses_moved = 0
        total_cashbacks_moved = 0
        total_budgets_moved = 0
        total_categories_removed = 0
        
        with transaction.atomic():
            for item in merge_plan:
                duplicate = item['duplicate']
                main = item['main']
                
                print(f"\nОбработка дубликата ID={duplicate.id} -> ID={main.id}")
                
                if not dry_run:
                    # Переносим расходы
                    if item['expenses_to_move'] > 0:
                        moved = Expense.objects.filter(
                            profile=profile,
                            category=duplicate
                        ).update(category=main)
                        print(f"  ✓ Перенесено расходов: {moved}")
                        total_expenses_moved += moved
                    
                    # Переносим кешбеки
                    if item['cashbacks_to_move'] > 0:
                        # Проверяем нет ли уже кешбека для главной категории
                        for cashback in Cashback.objects.filter(profile=profile, category=duplicate):
                            existing = Cashback.objects.filter(
                                profile=profile,
                                category=main,
                                month=cashback.month
                            ).first()
                            
                            if existing:
                                # Обновляем существующий (берем максимальный процент)
                                if cashback.cashback_percent > existing.cashback_percent:
                                    existing.cashback_percent = cashback.cashback_percent
                                    existing.limit_amount = cashback.limit_amount
                                    existing.save()
                                cashback.delete()
                            else:
                                # Переносим кешбек
                                cashback.category = main
                                cashback.save()
                            total_cashbacks_moved += 1
                        print(f"  ✓ Перенесено кешбеков: {total_cashbacks_moved}")
                    
                    # Переносим бюджеты
                    if item['budgets_to_move'] > 0:
                        # Проверяем нет ли уже бюджета для главной категории
                        for budget in Budget.objects.filter(profile=profile, category=duplicate):
                            existing = Budget.objects.filter(
                                profile=profile,
                                category=main,
                                period_type=budget.period_type
                            ).first()
                            
                            if existing:
                                # Обновляем существующий (берем максимальную сумму)
                                if budget.amount > existing.amount:
                                    existing.amount = budget.amount
                                    existing.save()
                                budget.delete()
                            else:
                                # Переносим бюджет
                                budget.category = main
                                budget.save()
                            total_budgets_moved += 1
                        print(f"  ✓ Перенесено бюджетов: {total_budgets_moved}")
                    
                    # Деактивируем дубликат
                    duplicate.is_active = False
                    duplicate.save()
                    print(f"  ✓ Категория ID={duplicate.id} деактивирована")
                    total_categories_removed += 1
                else:
                    print(f"  [DRY RUN] Будет перенесено:")
                    print(f"    - Расходов: {item['expenses_to_move']}")
                    print(f"    - Кешбеков: {item['cashbacks_to_move']}")  
                    print(f"    - Бюджетов: {item['budgets_to_move']}")
                    print(f"    - Категория ID={duplicate.id} будет деактивирована")
                    
                    total_expenses_moved += item['expenses_to_move']
                    total_cashbacks_moved += item['cashbacks_to_move']
                    total_budgets_moved += item['budgets_to_move']
                    total_categories_removed += 1
        
        print(f"\n{'='*70}")
        print(f"{'ИТОГИ (DRY RUN)' if dry_run else '✅ ИТОГИ ОБЪЕДИНЕНИЯ'}")
        print(f"{'='*70}")
        print(f"Удалено дубликатов категорий: {total_categories_removed}")
        print(f"Перенесено расходов: {total_expenses_moved}")
        print(f"Перенесено кешбеков: {total_cashbacks_moved}")
        print(f"Перенесено бюджетов: {total_budgets_moved}")
        
        if dry_run:
            print("\n⚠️  Это был тестовый прогон. Изменения НЕ внесены.")
            print("Для выполнения объединения запустите с флагом --execute")
        else:
            print("\n✅ Объединение выполнено успешно!")
            
    except Exception as e:
        print(f"\n❌ Ошибка при объединении: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка дублированных категорий')
    parser.add_argument('telegram_id', type=int, help='Telegram ID пользователя')
    parser.add_argument('--execute', action='store_true', help='Выполнить объединение (по умолчанию - dry run)')
    parser.add_argument('--analyze-only', action='store_true', help='Только анализ без плана объединения')
    
    args = parser.parse_args()
    
    if args.analyze_only:
        analyze_duplicates(args.telegram_id)
    else:
        merge_duplicates(args.telegram_id, dry_run=not args.execute)


if __name__ == "__main__":
    # Если запущено без аргументов, используем ваш ID
    if len(sys.argv) == 1:
        print("Использование:")
        print("  python clean_duplicate_categories.py 881292737")
        print("  python clean_duplicate_categories.py 881292737 --analyze-only")
        print("  python clean_duplicate_categories.py 881292737 --execute")
        print("\nЗапускаем анализ для пользователя 881292737...")
        analyze_duplicates(881292737)
    else:
        main()