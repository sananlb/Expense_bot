#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Комплексный скрипт для анализа, очистки и миграции категорий после внедрения мультиязычности
"""

import os
import sys
import django
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set
from datetime import datetime
import re

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, IncomeCategory, Expense, Income, CategoryKeyword
from django.db import transaction
from django.db.models import Q, Count
from bot.utils.default_categories import UNIFIED_CATEGORIES


class CategoryMigrationAnalyzer:
    """Анализатор и мигратор категорий"""
    
    def __init__(self):
        self.stats = {
            'total_profiles': 0,
            'total_categories': 0,
            'empty_multilingual_fields': 0,
            'potential_duplicates': 0,
            'orphaned_expenses': 0,
            'categories_fixed': 0,
            'expenses_migrated': 0,
            'categories_deleted': 0,
        }
        self.issues_log = []
        
    def log_issue(self, issue_type: str, message: str, profile_id: int = None):
        """Логирование проблем"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {issue_type}: {message}"
        if profile_id:
            log_entry += f" (Profile: {profile_id})"
        self.issues_log.append(log_entry)
        print(log_entry)
    
    def detect_language(self, text: str) -> str:
        """Определение языка текста"""
        if not text:
            return 'unknown'
        
        # Убираем эмодзи и специальные символы
        clean_text = re.sub(r'[^\w\s\-а-яА-ЯёЁa-zA-Z]', ' ', text).strip()
        
        has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', clean_text))
        has_latin = bool(re.search(r'[a-zA-Z]', clean_text))
        
        if has_cyrillic and not has_latin:
            return 'ru'
        elif has_latin and not has_cyrillic:
            return 'en'
        elif has_cyrillic and has_latin:
            return 'mixed'
        else:
            return 'unknown'
    
    def extract_emoji(self, text: str) -> str:
        """Извлечь эмодзи из текста"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        emojis = emoji_pattern.findall(text)
        return emojis[0] if emojis else ''
    
    def remove_emoji(self, text: str) -> str:
        """Удалить эмодзи из текста"""
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        return emoji_pattern.sub('', text).strip()
    
    def analyze_all_categories(self) -> Dict:
        """Полный анализ всех категорий в системе"""
        print("=" * 80)
        print("АНАЛИЗ КАТЕГОРИЙ ПОСЛЕ МУЛЬТИЯЗЫЧНОЙ МИГРАЦИИ")
        print("=" * 80)
        
        profiles = Profile.objects.all()
        all_categories = ExpenseCategory.objects.all()
        
        self.stats['total_profiles'] = profiles.count()
        self.stats['total_categories'] = all_categories.count()
        
        print(f"\nОбщая статистика:")
        print(f"  Всего профилей: {self.stats['total_profiles']}")
        print(f"  Всего категорий расходов: {self.stats['total_categories']}")
        
        # Анализ мультиязычных полей
        categories_with_empty_fields = all_categories.filter(
            Q(name_ru__isnull=True) | Q(name_ru='') |
            Q(name_en__isnull=True) | Q(name_en='')
        )
        self.stats['empty_multilingual_fields'] = categories_with_empty_fields.count()
        
        print(f"\nПроблемы с мультиязычными полями:")
        print(f"  Категории с пустыми полями: {self.stats['empty_multilingual_fields']}")
        
        # Анализ дубликатов
        self.analyze_duplicates()
        
        # Анализ привязки расходов
        self.analyze_expense_bindings()
        
        return self.stats
    
    def analyze_duplicates(self):
        """Анализ потенциальных дубликатов"""
        print(f"\nАнализ дубликатов:")
        
        # Группируем категории по профилям
        profiles = Profile.objects.all()
        total_duplicates = 0
        
        for profile in profiles:
            categories = profile.categories.filter(is_active=True)
            
            # Создаем мапинг нормализованных названий
            normalized_categories = defaultdict(list)
            
            for cat in categories:
                # Нормализуем все варианты названий
                names_to_check = []
                
                if cat.name_ru:
                    names_to_check.append(self.remove_emoji(cat.name_ru).lower().strip())
                if cat.name_en:
                    names_to_check.append(self.remove_emoji(cat.name_en).lower().strip())
                if cat.name:
                    names_to_check.append(self.remove_emoji(cat.name).lower().strip())
                
                for name in names_to_check:
                    if name:
                        normalized_categories[name].append(cat)
            
            # Ищем дубликаты
            duplicates_in_profile = 0
            for name, cats in normalized_categories.items():
                if len(cats) > 1:
                    duplicates_in_profile += len(cats) - 1
                    self.log_issue("DUPLICATE", f"Found {len(cats)} categories with similar name '{name}'", profile.telegram_id)
            
            total_duplicates += duplicates_in_profile
        
        self.stats['potential_duplicates'] = total_duplicates
        print(f"  Потенциальных дубликатов: {total_duplicates}")
    
    def analyze_expense_bindings(self):
        """Анализ привязки расходов к категориям"""
        print(f"\nАнализ привязки расходов:")
        
        orphaned_expenses = Expense.objects.filter(category__isnull=True).count()
        inactive_category_expenses = Expense.objects.filter(category__is_active=False).count()
        
        self.stats['orphaned_expenses'] = orphaned_expenses
        
        print(f"  Расходы без категории: {orphaned_expenses}")
        print(f"  Расходы с неактивными категориями: {inactive_category_expenses}")
    
    def fix_empty_multilingual_fields(self, profile_id: int = None, dry_run: bool = True):
        """Исправление пустых мультиязычных полей"""
        print(f"\n{'[DRY RUN] ' if dry_run else ''}ИСПРАВЛЕНИЕ ПУСТЫХ МУЛЬТИЯЗЫЧНЫХ ПОЛЕЙ")
        print("-" * 50)
        
        if profile_id:
            categories = ExpenseCategory.objects.filter(
                profile__telegram_id=profile_id,
                is_active=True
            )
            print(f"Обрабатываем категории пользователя {profile_id}")
        else:
            categories = ExpenseCategory.objects.filter(is_active=True)
            print("Обрабатываем все категории")
        
        categories_with_issues = categories.filter(
            Q(name_ru__isnull=True) | Q(name_ru='') |
            Q(name_en__isnull=True) | Q(name_en='')
        )
        
        fixed_count = 0
        
        for category in categories_with_issues:
            original_text = self.remove_emoji(category.name).strip()
            detected_lang = self.detect_language(original_text)
            
            changes_made = []
            
            # Исправляем пустые поля
            if not category.name_ru:
                if detected_lang == 'ru':
                    category.name_ru = original_text
                    changes_made.append(f"name_ru = '{original_text}'")
                else:
                    # Попробуем найти русский вариант из стандартных категорий
                    for unified_cat in UNIFIED_CATEGORIES:
                        if (unified_cat['name_en'].lower() == original_text.lower() or
                            any(kw.lower() == original_text.lower() for kw in unified_cat.get('keywords_en', []))):
                            category.name_ru = unified_cat['name_ru']
                            changes_made.append(f"name_ru = '{unified_cat['name_ru']}' (from unified)")
                            break
            
            if not category.name_en:
                if detected_lang == 'en':
                    category.name_en = original_text
                    changes_made.append(f"name_en = '{original_text}'")
                else:
                    # Попробуем найти английский вариант из стандартных категорий
                    for unified_cat in UNIFIED_CATEGORIES:
                        if (unified_cat['name_ru'].lower() == original_text.lower() or
                            any(kw.lower() == original_text.lower() for kw in unified_cat.get('keywords_ru', []))):
                            category.name_en = unified_cat['name_en']
                            changes_made.append(f"name_en = '{unified_cat['name_en']}' (from unified)")
                            break
            
            # Обновляем метаданные
            if not category.original_language or category.original_language == 'mixed':
                category.original_language = detected_lang if detected_lang in ['ru', 'en'] else 'ru'
                changes_made.append(f"original_language = '{category.original_language}'")
            
            if changes_made:
                self.log_issue("FIX", f"Category '{category.name}': {', '.join(changes_made)}", 
                             category.profile.telegram_id)
                
                if not dry_run:
                    category.save()
                fixed_count += 1
        
        print(f"Исправлено категорий: {fixed_count}")
        self.stats['categories_fixed'] += fixed_count
        
        return fixed_count
    
    def migrate_duplicate_categories(self, profile_id: int = None, dry_run: bool = True):
        """Миграция дубликатов категорий"""
        print(f"\n{'[DRY RUN] ' if dry_run else ''}МИГРАЦИЯ ДУБЛИКАТОВ КАТЕГОРИЙ")
        print("-" * 50)
        
        if profile_id:
            profiles = Profile.objects.filter(telegram_id=profile_id)
        else:
            profiles = Profile.objects.all()
        
        migrated_expenses = 0
        deleted_categories = 0
        
        for profile in profiles:
            categories = profile.categories.filter(is_active=True)
            
            # Группируем по нормализованным названиям
            normalized_groups = defaultdict(list)
            
            for cat in categories:
                # Создаем нормализованный ключ из всех названий
                key_parts = []
                if cat.name_ru:
                    key_parts.append(self.remove_emoji(cat.name_ru).lower().strip())
                if cat.name_en:
                    key_parts.append(self.remove_emoji(cat.name_en).lower().strip())
                
                # Используем самый длинный ключ как основной
                if key_parts:
                    primary_key = max(key_parts, key=len)
                    normalized_groups[primary_key].append(cat)
            
            # Обрабатываем группы с дубликатами
            for group_name, group_categories in normalized_groups.items():
                if len(group_categories) > 1:
                    # Сортируем по приоритету: сначала с заполненными мультиязычными полями
                    group_categories.sort(key=lambda c: (
                        bool(c.name_ru and c.name_en),  # Приоритет полным категориям
                        c.created_at  # Потом по дате создания
                    ), reverse=True)
                    
                    primary_category = group_categories[0]
                    duplicate_categories = group_categories[1:]
                    
                    self.log_issue("MERGE", f"Merging {len(duplicate_categories)} duplicates into '{primary_category.name}'", 
                                 profile.telegram_id)
                    
                    # Мигрируем расходы
                    for duplicate in duplicate_categories:
                        expenses_to_migrate = duplicate.expenses.all()
                        expense_count = expenses_to_migrate.count()
                        
                        if expense_count > 0:
                            self.log_issue("MIGRATE", f"Moving {expense_count} expenses from '{duplicate.name}' to '{primary_category.name}'", 
                                         profile.telegram_id)
                            
                            if not dry_run:
                                expenses_to_migrate.update(category=primary_category)
                            migrated_expenses += expense_count
                        
                        # Мигрируем ключевые слова
                        keywords_to_migrate = duplicate.keywords.all()
                        if keywords_to_migrate.exists():
                            for keyword in keywords_to_migrate:
                                # Проверяем, нет ли уже такого ключевого слова у основной категории
                                if not primary_category.keywords.filter(
                                    keyword=keyword.keyword,
                                    language=keyword.language
                                ).exists():
                                    if not dry_run:
                                        keyword.category = primary_category
                                        keyword.save()
                        
                        # Удаляем дубликат
                        self.log_issue("DELETE", f"Deleting duplicate category '{duplicate.name}'", 
                                     profile.telegram_id)
                        
                        if not dry_run:
                            duplicate.delete()
                        deleted_categories += 1
        
        print(f"Мигрировано расходов: {migrated_expenses}")
        print(f"Удалено дублированных категорий: {deleted_categories}")
        
        self.stats['expenses_migrated'] += migrated_expenses
        self.stats['categories_deleted'] += deleted_categories
        
        return migrated_expenses, deleted_categories
    
    def create_missing_default_categories(self, profile_id: int = None, dry_run: bool = True):
        """Создание недостающих стандартных категорий"""
        print(f"\n{'[DRY RUN] ' if dry_run else ''}СОЗДАНИЕ НЕДОСТАЮЩИХ СТАНДАРТНЫХ КАТЕГОРИЙ")
        print("-" * 50)
        
        if profile_id:
            profiles = Profile.objects.filter(telegram_id=profile_id)
        else:
            profiles = Profile.objects.all()
        
        created_categories = 0
        
        for profile in profiles:
            user_lang = profile.language_code or 'ru'
            existing_categories = set()
            
            # Собираем существующие названия категорий
            for cat in profile.categories.filter(is_active=True):
                if cat.name_ru:
                    existing_categories.add(cat.name_ru.lower())
                if cat.name_en:
                    existing_categories.add(cat.name_en.lower())
            
            # Проверяем каждую стандартную категорию
            for unified_cat in UNIFIED_CATEGORIES:
                ru_name = unified_cat['name_ru'].lower()
                en_name = unified_cat['name_en'].lower()
                
                # Проверяем, есть ли уже такая категория
                if ru_name not in existing_categories and en_name not in existing_categories:
                    # Создаем недостающую категорию
                    self.log_issue("CREATE", f"Creating missing category '{unified_cat['name_ru']}'", 
                                 profile.telegram_id)
                    
                    if not dry_run:
                        category = ExpenseCategory.objects.create(
                            profile=profile,
                            name=f"{unified_cat['icon']} {unified_cat[f'name_{user_lang}']}",
                            name_ru=unified_cat['name_ru'],
                            name_en=unified_cat['name_en'],
                            icon=unified_cat['icon'],
                            original_language='mixed',  # Стандартные категории поддерживают оба языка
                            is_translatable=True
                        )
                        
                        # Добавляем ключевые слова
                        for lang in ['ru', 'en']:
                            keywords = unified_cat.get(f'keywords_{lang}', [])
                            for keyword in keywords:
                                CategoryKeyword.objects.create(
                                    category=category,
                                    keyword=keyword,
                                    language=lang
                                )
                    
                    created_categories += 1
        
        print(f"Создано категорий: {created_categories}")
        return created_categories
    
    def run_full_migration(self, profile_id: int = None, dry_run: bool = True):
        """Полная миграция категорий"""
        print("=" * 80)
        print(f"{'[DRY RUN] ' if dry_run else ''}ПОЛНАЯ МИГРАЦИЯ КАТЕГОРИЙ")
        print("=" * 80)
        
        if profile_id:
            print(f"Обрабатываем пользователя: {profile_id}")
        else:
            print("Обрабатываем всех пользователей")
        
        # Сначала анализируем текущее состояние
        self.analyze_all_categories()
        
        if not dry_run:
            response = input("\nВы уверены, что хотите выполнить миграцию? (yes/no): ")
            if response.lower() != 'yes':
                print("Миграция отменена")
                return
        
        # Выполняем миграцию по шагам
        print("\nШаг 1: Исправление пустых мультиязычных полей")
        self.fix_empty_multilingual_fields(profile_id, dry_run)
        
        print("\nШаг 2: Миграция дубликатов")
        self.migrate_duplicate_categories(profile_id, dry_run)
        
        print("\nШаг 3: Создание недостающих стандартных категорий")
        self.create_missing_default_categories(profile_id, dry_run)
        
        # Финальная статистика
        print("\n" + "=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА МИГРАЦИИ")
        print("=" * 80)
        for key, value in self.stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        
        if self.issues_log:
            print(f"\nВсего записей в логе: {len(self.issues_log)}")
        
        return self.stats


def main():
    """Главная функция"""
    analyzer = CategoryMigrationAnalyzer()
    
    import argparse
    parser = argparse.ArgumentParser(description='Миграция и анализ категорий')
    parser.add_argument('--profile-id', type=int, help='ID профиля для обработки')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Режим симуляции (по умолчанию)')
    parser.add_argument('--execute', action='store_true', help='Выполнить реальные изменения')
    parser.add_argument('--analyze-only', action='store_true', help='Только анализ, без миграции')
    
    args = parser.parse_args()
    
    # Если указан --execute, отключаем dry_run
    if args.execute:
        dry_run = False
    else:
        dry_run = args.dry_run
    
    if args.analyze_only:
        analyzer.analyze_all_categories()
    else:
        analyzer.run_full_migration(args.profile_id, dry_run)
    
    # Сохраняем лог в файл
    if analyzer.issues_log:
        log_filename = f"category_migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"Лог миграции категорий - {datetime.now()}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Статистика:\n")
            for key, value in analyzer.stats.items():
                f.write(f"  {key.replace('_', ' ').title()}: {value}\n")
            f.write("\n" + "=" * 80 + "\n\n")
            f.write("Детальный лог:\n")
            for entry in analyzer.issues_log:
                f.write(entry + "\n")
        
        print(f"\nЛог сохранен в файл: {log_filename}")


if __name__ == "__main__":
    main()