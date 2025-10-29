#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Универсальный скрипт миграции категорий для всех пользователей
Запускать на сервере для исправления проблем с мультиязычными категориями
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense
from django.db import transaction
from django.db.models import Count, Sum
from bot.utils.default_categories import UNIFIED_CATEGORIES
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'category_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CategoryMigrator:
    """Класс для миграции категорий"""
    
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.stats = {
            'profiles_processed': 0,
            'categories_fixed': 0,
            'duplicates_merged': 0,
            'expenses_moved': 0,
            'errors': 0
        }
        
    def migrate_all_users(self):
        """Миграция категорий для всех пользователей"""
        logger.info("=" * 70)
        logger.info(f"Starting category migration {'[DRY RUN]' if self.dry_run else '[EXECUTE]'}")
        logger.info("=" * 70)
        
        profiles = Profile.objects.filter(is_active=True).order_by('id')
        total_profiles = profiles.count()
        
        logger.info(f"Found {total_profiles} active profiles")
        
        for idx, profile in enumerate(profiles, 1):
            logger.info(f"\n--- Processing profile {idx}/{total_profiles}: ID={profile.id}, TG={profile.telegram_id} ---")
            self.migrate_user_categories(profile)
            self.stats['profiles_processed'] += 1
            
        self.print_summary()
        
    def migrate_user_categories(self, profile):
        """Миграция категорий одного пользователя"""
        try:
            categories = profile.categories.filter(is_active=True)
            total_categories = categories.count()
            
            if total_categories == 0:
                logger.info(f"  No categories found for profile {profile.id}")
                return
                
            logger.info(f"  Found {total_categories} active categories")
            
            # 1. Исправляем пустые мультиязычные поля
            self.fix_multilingual_fields(profile, categories)
            
            # 2. Синхронизируем поле name
            self.sync_name_field(profile, categories)
            
            # 3. Объединяем дубликаты
            self.merge_duplicates(profile, categories)
            
        except Exception as e:
            logger.error(f"  ERROR processing profile {profile.id}: {e}")
            self.stats['errors'] += 1
            
    def fix_multilingual_fields(self, profile, categories):
        """Исправление пустых мультиязычных полей"""
        fixed_count = 0
        
        for category in categories:
            needs_save = False
            
            # Исправляем пустое name_ru
            if not category.name_ru and category.name:
                # Пытаемся извлечь название из старого поля name
                clean_name = category.name
                if category.icon:
                    clean_name = clean_name.replace(category.icon, '').strip()
                
                # Проверяем на кириллицу
                if any(ord(c) >= 1040 and ord(c) <= 1103 for c in clean_name):
                    category.name_ru = clean_name
                    needs_save = True
                    logger.debug(f"    Set name_ru='{clean_name}' for category {category.id}")
                    
            # Исправляем пустое name_en
            if not category.name_en:
                # Ищем перевод в стандартных категориях
                if category.name_ru:
                    for unified_cat in UNIFIED_CATEGORIES:
                        if unified_cat['name_ru'].lower() == category.name_ru.lower():
                            category.name_en = unified_cat['name_en']
                            needs_save = True
                            logger.debug(f"    Set name_en='{unified_cat['name_en']}' for category {category.id}")
                            break
                            
                # Если не нашли в стандартных, пытаемся извлечь из name
                if not category.name_en and category.name:
                    clean_name = category.name
                    if category.icon:
                        clean_name = clean_name.replace(category.icon, '').strip()
                    
                    # Проверяем на латиницу
                    if clean_name and not any(ord(c) >= 1040 and ord(c) <= 1103 for c in clean_name):
                        category.name_en = clean_name
                        needs_save = True
                        logger.debug(f"    Set name_en='{clean_name}' for category {category.id}")
                        
            # Исправляем original_language
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
                
            if needs_save and not self.dry_run:
                category.save()
                fixed_count += 1
                
        if fixed_count > 0:
            logger.info(f"  Fixed multilingual fields for {fixed_count} categories")
            self.stats['categories_fixed'] += fixed_count
            
    def sync_name_field(self, profile, categories):
        """Синхронизация поля name с мультиязычными полями"""
        synced_count = 0
        user_lang = profile.language_code or 'ru'
        
        for category in categories:
            old_name = category.name
            
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
                if not self.dry_run:
                    category.save()
                synced_count += 1
                logger.debug(f"    Synced name: '{old_name}' -> '{new_name}' for category {category.id}")
                
        if synced_count > 0:
            logger.info(f"  Synchronized name field for {synced_count} categories")
            
    def merge_duplicates(self, profile, categories):
        """Объединение дублирующихся категорий"""
        # Группируем по name_ru
        name_groups = {}
        for cat in categories:
            if cat.name_ru:
                key = cat.name_ru.lower()
                if key not in name_groups:
                    name_groups[key] = []
                name_groups[key].append(cat)
                
        merged_count = 0
        expenses_moved = 0
        
        for name, cats in name_groups.items():
            if len(cats) > 1:
                # Находим основную категорию (с максимальным количеством расходов)
                main_cat = None
                max_expenses = 0
                
                for cat in cats:
                    expense_count = Expense.objects.filter(profile=profile, category=cat).count()
                    if expense_count > max_expenses:
                        max_expenses = expense_count
                        main_cat = cat
                        
                if not main_cat:
                    main_cat = cats[0]
                    
                logger.info(f"  Found {len(cats)} duplicates for '{name}', main category ID={main_cat.id}")
                
                # Переносим расходы и деактивируем дубликаты
                for cat in cats:
                    if cat.id != main_cat.id:
                        if not self.dry_run:
                            # Переносим расходы
                            moved = Expense.objects.filter(
                                profile=profile,
                                category=cat
                            ).update(category=main_cat)
                            
                            # Деактивируем дубликат
                            cat.is_active = False
                            cat.save()
                        else:
                            moved = Expense.objects.filter(
                                profile=profile,
                                category=cat
                            ).count()
                            
                        if moved > 0:
                            logger.debug(f"    {'Would move' if self.dry_run else 'Moved'} {moved} expenses from ID={cat.id} to ID={main_cat.id}")
                            expenses_moved += moved
                            
                        merged_count += 1
                        
        if merged_count > 0:
            logger.info(f"  {'Would merge' if self.dry_run else 'Merged'} {merged_count} duplicate categories, moving {expenses_moved} expenses")
            self.stats['duplicates_merged'] += merged_count
            self.stats['expenses_moved'] += expenses_moved
            
    def print_summary(self):
        """Вывод итоговой статистики"""
        logger.info("\n" + "=" * 70)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'EXECUTED'}")
        logger.info(f"Profiles processed: {self.stats['profiles_processed']}")
        logger.info(f"Categories fixed: {self.stats['categories_fixed']}")
        logger.info(f"Duplicates merged: {self.stats['duplicates_merged']}")
        logger.info(f"Expenses moved: {self.stats['expenses_moved']}")
        logger.info(f"Errors: {self.stats['errors']}")
        
        if self.dry_run:
            logger.info("\n⚠️  This was a DRY RUN. No changes were made.")
            logger.info("To execute the migration, run with --execute flag")
        else:
            logger.info("\n✅ Migration completed successfully!")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate categories to multilingual structure')
    parser.add_argument('--execute', action='store_true', help='Execute the migration (default is dry-run)')
    parser.add_argument('--profile-id', type=int, help='Migrate only specific profile ID')
    parser.add_argument('--telegram-id', type=int, help='Migrate only specific Telegram ID')
    
    args = parser.parse_args()
    
    migrator = CategoryMigrator(dry_run=not args.execute)
    
    if args.profile_id:
        try:
            profile = Profile.objects.get(id=args.profile_id)
            logger.info(f"Migrating single profile ID={args.profile_id}")
            migrator.migrate_user_categories(profile)
            migrator.print_summary()
        except Profile.DoesNotExist:
            logger.error(f"Profile with ID={args.profile_id} not found")
            
    elif args.telegram_id:
        try:
            profile = Profile.objects.get(telegram_id=args.telegram_id)
            logger.info(f"Migrating single profile with Telegram ID={args.telegram_id}")
            migrator.migrate_user_categories(profile)
            migrator.print_summary()
        except Profile.DoesNotExist:
            logger.error(f"Profile with Telegram ID={args.telegram_id} not found")
            
    else:
        migrator.migrate_all_users()


if __name__ == "__main__":
    main()