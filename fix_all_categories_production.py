#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PRODUCTION SCRIPT: Универсальное исправление категорий для всех пользователей
Запускать на сервере для полной очистки и исправления категорий
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense, Cashback, Budget, Income, IncomeCategory
from django.db import transaction, connection
from django.db.models import Count, Sum, Q
from bot.utils.default_categories import UNIFIED_CATEGORIES

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'category_fix_production_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CategoryFixer:
    """Класс для исправления категорий"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.global_stats = {
            'profiles_processed': 0,
            'profiles_skipped': 0,
            'profiles_with_issues': 0,
            'categories_fixed': 0,
            'duplicates_merged': 0,
            'expenses_moved': 0,
            'cashbacks_moved': 0,
            'budgets_moved': 0,
            'incomes_moved': 0,
            'categories_deleted': 0,
            'errors': 0
        }
        
    def run(self):
        """Главный метод запуска"""
        logger.info("="*80)
        logger.info(f"CATEGORY FIX PRODUCTION SCRIPT")
        logger.info(f"Mode: {'DRY RUN - No changes will be made' if self.dry_run else '⚠️ EXECUTE - Will modify database!'}")
        logger.info("="*80)
        
        if not self.dry_run:
            logger.warning("⚠️ WARNING: This script will modify the database!")
            logger.warning("Make sure you have a backup before proceeding!")
            input("Press Enter to continue or Ctrl+C to abort...")
        
        # Получаем всех активных пользователей
        profiles = Profile.objects.filter(is_active=True).order_by('id')
        total_profiles = profiles.count()
        
        logger.info(f"\nFound {total_profiles} active profiles to process")
        logger.info("-"*80)
        
        # Обрабатываем каждого пользователя
        for idx, profile in enumerate(profiles, 1):
            logger.info(f"\n[{idx}/{total_profiles}] Processing profile ID={profile.id}, TG={profile.telegram_id}")
            
            try:
                self.fix_user_categories(profile)
                self.global_stats['profiles_processed'] += 1
            except Exception as e:
                logger.error(f"  ERROR processing profile {profile.id}: {e}")
                self.global_stats['errors'] += 1
                if not self.dry_run:
                    # В production режиме продолжаем даже при ошибках
                    continue
        
        # Выводим итоговую статистику
        self.print_summary()
        
    def fix_user_categories(self, profile: Profile):
        """Исправление категорий одного пользователя"""
        
        # Получаем все категории пользователя
        all_categories = profile.categories.all()
        initial_count = all_categories.count()
        
        if initial_count == 0:
            logger.info(f"  No categories found, skipping")
            self.global_stats['profiles_skipped'] += 1
            return
        
        logger.info(f"  Found {initial_count} categories (active: {all_categories.filter(is_active=True).count()})")
        
        local_stats = {
            'fixed_fields': 0,
            'merged_duplicates': 0,
            'moved_expenses': 0,
            'moved_cashbacks': 0,
            'moved_budgets': 0,
            'deleted_categories': 0
        }
        
        with transaction.atomic():
            # Шаг 1: Исправляем мультиязычные поля
            self.fix_multilingual_fields(profile, all_categories, local_stats)
            
            # Шаг 2: Объединяем дубликаты
            self.merge_duplicates(profile, local_stats)
            
            # Шаг 3: Очистка неактивных пустых категорий
            self.cleanup_empty_categories(profile, local_stats)
        
        # Финальная проверка
        final_count = profile.categories.filter(is_active=True).count()
        
        # Обновляем глобальную статистику
        self.global_stats['categories_fixed'] += local_stats['fixed_fields']
        self.global_stats['duplicates_merged'] += local_stats['merged_duplicates']
        self.global_stats['expenses_moved'] += local_stats['moved_expenses']
        self.global_stats['cashbacks_moved'] += local_stats['moved_cashbacks']
        self.global_stats['budgets_moved'] += local_stats['moved_budgets']
        self.global_stats['categories_deleted'] += local_stats['deleted_categories']
        
        if local_stats['merged_duplicates'] > 0 or local_stats['fixed_fields'] > 0:
            self.global_stats['profiles_with_issues'] += 1
        
        logger.info(f"  Result: {initial_count} -> {final_count} active categories")
        if any(local_stats.values()):
            logger.info(f"  Actions: fixed={local_stats['fixed_fields']}, merged={local_stats['merged_duplicates']}, " +
                       f"expenses_moved={local_stats['moved_expenses']}, deleted={local_stats['deleted_categories']}")
    
    def fix_multilingual_fields(self, profile: Profile, categories, local_stats: Dict):
        """Исправление пустых мультиязычных полей"""
        
        for category in categories:
            needs_save = False
            
            # Исправляем пустое name_ru
            if not category.name_ru:
                if category.name:
                    # Извлекаем название из старого поля
                    import re
                    clean_name = category.name
                    if category.icon:
                        clean_name = clean_name.replace(category.icon, '').strip()
                    
                    # Проверяем на кириллицу
                    if clean_name and any('\u0400' <= c <= '\u04FF' for c in clean_name):
                        category.name_ru = clean_name
                        needs_save = True
                        logger.debug(f"    Fixed name_ru for category {category.id}: '{clean_name}'")
            
            # Исправляем пустое name_en
            if not category.name_en:
                # Ищем в стандартных категориях
                if category.name_ru:
                    for unified_cat in UNIFIED_CATEGORIES:
                        if unified_cat['name_ru'].lower() == category.name_ru.lower():
                            category.name_en = unified_cat['name_en']
                            needs_save = True
                            logger.debug(f"    Fixed name_en for category {category.id}: '{unified_cat['name_en']}'")
                            break
                
                # Если не нашли в стандартных, проверяем старое поле name
                if not category.name_en and category.name:
                    clean_name = category.name
                    if category.icon:
                        clean_name = clean_name.replace(category.icon, '').strip()
                    
                    # Проверяем на латиницу
                    if clean_name and not any('\u0400' <= c <= '\u04FF' for c in clean_name):
                        category.name_en = clean_name
                        needs_save = True
                        logger.debug(f"    Fixed name_en for category {category.id}: '{clean_name}'")
            
            # Исправляем icon если его нет
            if not category.icon and (category.name_ru or category.name_en):
                # Ищем в стандартных категориях
                for unified_cat in UNIFIED_CATEGORIES:
                    if (category.name_ru and unified_cat['name_ru'].lower() == category.name_ru.lower()) or \
                       (category.name_en and unified_cat['name_en'].lower() == category.name_en.lower()):
                        category.icon = unified_cat['icon']
                        needs_save = True
                        logger.debug(f"    Fixed icon for category {category.id}: '{unified_cat['icon']}'")
                        break
            
            # Устанавливаем original_language
            if not category.original_language or category.original_language == 'mixed':
                if category.name_ru and not category.name_en:
                    category.original_language = 'ru'
                    needs_save = True
                elif category.name_en and not category.name_ru:
                    category.original_language = 'en'
                    needs_save = True
                elif category.name_ru and category.name_en:
                    category.original_language = 'ru'
                    needs_save = True
            
            # Устанавливаем is_translatable
            if category.name_ru and category.name_en and not category.is_translatable:
                category.is_translatable = True
                needs_save = True
            
            # Синхронизируем поле name
            user_lang = profile.language_code or 'ru'
            if user_lang == 'ru' and category.name_ru:
                expected_name = f"{category.icon or ''} {category.name_ru}".strip()
            elif user_lang == 'en' and category.name_en:
                expected_name = f"{category.icon or ''} {category.name_en}".strip()
            elif category.name_ru:
                expected_name = f"{category.icon or ''} {category.name_ru}".strip()
            elif category.name_en:
                expected_name = f"{category.icon or ''} {category.name_en}".strip()
            else:
                expected_name = category.name or "Unknown"
            
            if category.name != expected_name:
                category.name = expected_name
                needs_save = True
            
            if needs_save and not self.dry_run:
                category.save()
                local_stats['fixed_fields'] += 1
            elif needs_save:
                local_stats['fixed_fields'] += 1
    
    def merge_duplicates(self, profile: Profile, local_stats: Dict):
        """Объединение дублирующихся категорий"""
        
        # Получаем все категории пользователя (включая неактивные)
        all_categories = profile.categories.all()
        
        # Группируем категории по ключу
        category_groups = {}
        
        for cat in all_categories:
            # Определяем ключ для группировки
            if cat.name_ru:
                key = cat.name_ru.lower().strip()
            elif cat.name_en:
                key = cat.name_en.lower().strip()
            elif cat.name:
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
        for key, cats in category_groups.items():
            if len(cats) > 1:
                logger.debug(f"    Found duplicate group '{key}': {len(cats)} categories")
                
                # Выбираем главную категорию по приоритетам
                main_cat = None
                max_score = -1
                
                for cat in cats:
                    score = 0
                    
                    # Активная категория имеет высший приоритет
                    if cat.is_active:
                        score += 10000
                    
                    # Количество расходов
                    expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                    score += expense_count * 100
                    
                    # Наличие кешбеков и бюджетов
                    cashback_count = Cashback.objects.filter(profile=profile, category=cat).count()
                    budget_count = Budget.objects.filter(profile=profile, category=cat).count()
                    score += (cashback_count + budget_count) * 50
                    
                    # Полнота данных
                    if cat.name_ru and cat.name_en:
                        score += 1000
                    elif cat.name_ru or cat.name_en:
                        score += 500
                    
                    if cat.icon:
                        score += 100
                    
                    # Старые категории приоритетнее (меньший ID)
                    score -= cat.id * 0.001
                    
                    if score > max_score:
                        max_score = score
                        main_cat = cat
                
                # Переносим все данные на главную категорию
                for cat in cats:
                    if cat.id != main_cat.id:
                        # Переносим расходы
                        moved_expenses = 0
                        if not self.dry_run:
                            moved_expenses = Expense.objects.filter(
                                profile=profile, category=cat
                            ).update(category=main_cat)
                        else:
                            moved_expenses = Expense.objects.filter(
                                profile=profile, category=cat
                            ).count()
                        
                        if moved_expenses > 0:
                            local_stats['moved_expenses'] += moved_expenses
                            logger.debug(f"      {'Would move' if self.dry_run else 'Moved'} {moved_expenses} expenses from {cat.id} to {main_cat.id}")
                        
                        # Переносим кешбеки
                        cashbacks = Cashback.objects.filter(profile=profile, category=cat)
                        if cashbacks.exists():
                            if not self.dry_run:
                                for cb in cashbacks:
                                    existing = Cashback.objects.filter(
                                        profile=profile,
                                        category=main_cat,
                                        month=cb.month
                                    ).first()
                                    if not existing:
                                        cb.category = main_cat
                                        cb.save()
                                        local_stats['moved_cashbacks'] += 1
                                    else:
                                        # Берем максимальный процент
                                        if cb.cashback_percent > existing.cashback_percent:
                                            existing.cashback_percent = cb.cashback_percent
                                            existing.limit_amount = cb.limit_amount
                                            existing.save()
                                        cb.delete()
                            else:
                                local_stats['moved_cashbacks'] += cashbacks.count()
                        
                        # Переносим бюджеты
                        budgets = Budget.objects.filter(profile=profile, category=cat)
                        if budgets.exists():
                            if not self.dry_run:
                                for budget in budgets:
                                    existing = Budget.objects.filter(
                                        profile=profile,
                                        category=main_cat,
                                        period_type=budget.period_type
                                    ).first()
                                    if not existing:
                                        budget.category = main_cat
                                        budget.save()
                                        local_stats['moved_budgets'] += 1
                                    else:
                                        # Берем максимальный бюджет
                                        if budget.amount > existing.amount:
                                            existing.amount = budget.amount
                                            existing.save()
                                        budget.delete()
                            else:
                                local_stats['moved_budgets'] += budgets.count()
                        
                        # Удаляем дубликат
                        if not self.dry_run:
                            cat.delete()
                        local_stats['merged_duplicates'] += 1
                        local_stats['deleted_categories'] += 1
                        logger.debug(f"      {'Would delete' if self.dry_run else 'Deleted'} duplicate category {cat.id}")
                
                # Обновляем главную категорию
                if not self.dry_run:
                    # Дополняем пустые поля из дубликатов
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
    
    def cleanup_empty_categories(self, profile: Profile, local_stats: Dict):
        """Удаление пустых неактивных категорий"""
        
        # Находим неактивные категории без расходов
        empty_categories = profile.categories.filter(
            is_active=False
        ).exclude(
            expenses__profile=profile
        ).exclude(
            cashbacks__profile=profile
        ).exclude(
            budgets__profile=profile
        )
        
        count = empty_categories.count()
        if count > 0:
            if not self.dry_run:
                empty_categories.delete()
            local_stats['deleted_categories'] += count
            logger.debug(f"    {'Would delete' if self.dry_run else 'Deleted'} {count} empty inactive categories")
    
    def print_summary(self):
        """Вывод итоговой статистики"""
        
        logger.info("\n" + "="*80)
        logger.info("FINAL SUMMARY")
        logger.info("="*80)
        
        logger.info(f"\nProfiles:")
        logger.info(f"  Processed: {self.global_stats['profiles_processed']}")
        logger.info(f"  Skipped (no categories): {self.global_stats['profiles_skipped']}")
        logger.info(f"  With issues fixed: {self.global_stats['profiles_with_issues']}")
        logger.info(f"  Errors: {self.global_stats['errors']}")
        
        logger.info(f"\nCategories:")
        logger.info(f"  Fixed multilingual fields: {self.global_stats['categories_fixed']}")
        logger.info(f"  Duplicates merged: {self.global_stats['duplicates_merged']}")
        logger.info(f"  Categories deleted: {self.global_stats['categories_deleted']}")
        
        logger.info(f"\nData moved:")
        logger.info(f"  Expenses moved: {self.global_stats['expenses_moved']}")
        logger.info(f"  Cashbacks moved: {self.global_stats['cashbacks_moved']}")
        logger.info(f"  Budgets moved: {self.global_stats['budgets_moved']}")
        
        if self.dry_run:
            logger.info("\n" + "⚠️ "*20)
            logger.info("This was a DRY RUN - no changes were made to the database")
            logger.info("To execute changes, run with --execute flag")
            logger.info("⚠️ "*20)
        else:
            logger.info("\n" + "✅ "*20)
            logger.info("MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("All categories have been fixed")
            logger.info("✅ "*20)


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix categories for all users in production',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no changes)
  python fix_all_categories_production.py
  
  # Execute changes
  python fix_all_categories_production.py --execute
  
  # Process specific user only
  python fix_all_categories_production.py --user 881292737
  
  # Process specific user with execution
  python fix_all_categories_production.py --user 881292737 --execute
        """
    )
    
    parser.add_argument('--execute', action='store_true',
                        help='Execute changes (default is dry run)')
    parser.add_argument('--user', type=int,
                        help='Process only specific user by Telegram ID')
    
    args = parser.parse_args()
    
    fixer = CategoryFixer(dry_run=not args.execute)
    
    if args.user:
        # Обработка только одного пользователя
        try:
            profile = Profile.objects.get(telegram_id=args.user)
            logger.info(f"Processing single user: {args.user}")
            fixer.fix_user_categories(profile)
            fixer.print_summary()
        except Profile.DoesNotExist:
            logger.error(f"User with Telegram ID {args.user} not found")
            return 1
    else:
        # Обработка всех пользователей
        fixer.run()
    
    return 0


if __name__ == "__main__":
    exit(main())