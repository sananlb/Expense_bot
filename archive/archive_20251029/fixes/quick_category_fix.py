#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Быстрые исправления категорий для конкретных пользователей
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
from django.db import transaction
from bot.utils.default_categories import UNIFIED_CATEGORIES


def quick_fix_user_categories(telegram_id: int, execute: bool = False):
    """
    Быстрое исправление категорий конкретного пользователя
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"{'[DRY RUN] ' if not execute else ''}Исправление категорий для пользователя {telegram_id}")
        print(f"Profile ID: {profile.id}")
        print("-" * 60)
        
        categories = profile.categories.filter(is_active=True).order_by('name')
        print(f"Всего активных категорий: {categories.count()}")
        
        fixed_count = 0
        issues = []
        
        # Проверяем каждую категорию
        for category in categories:
            category_issues = []
            fixes_needed = []
            
            # Проверка 1: Пустые мультиязычные поля
            if not category.name_ru:
                category_issues.append("❌ Пустое поле name_ru")
                # Пытаемся заполнить из name
                if category.name:
                    clean_name = category.name.replace(category.icon or '', '').strip()
                    if any(ord(c) >= 1040 and ord(c) <= 1103 for c in clean_name):  # Есть кириллица
                        fixes_needed.append(f"name_ru = '{clean_name}'")
                        if execute:
                            category.name_ru = clean_name
            
            if not category.name_en:
                category_issues.append("❌ Пустое поле name_en")
                # Ищем в стандартных категориях
                if category.name_ru:
                    for unified_cat in UNIFIED_CATEGORIES:
                        if unified_cat['name_ru'].lower() == category.name_ru.lower():
                            fixes_needed.append(f"name_en = '{unified_cat['name_en']}'")
                            if execute:
                                category.name_en = unified_cat['name_en']
                            break
            
            # Проверка 2: Несинхронизированное поле name
            if category.name_ru or category.name_en:
                user_lang = profile.language_code or 'ru'
                expected_name = f"{category.icon or ''} {category.name_ru if user_lang == 'ru' else (category.name_en or category.name_ru)}"
                expected_name = expected_name.strip()
                
                if category.name != expected_name:
                    category_issues.append(f"❌ Несинхронизированное поле name: '{category.name}' != '{expected_name}'")
                    fixes_needed.append(f"name = '{expected_name}'")
                    if execute:
                        category.name = expected_name
            
            # Проверка 3: Неправильные метаданные
            if not category.original_language or category.original_language == 'mixed':
                if category.name_ru and not category.name_en:
                    fixes_needed.append("original_language = 'ru'")
                    if execute:
                        category.original_language = 'ru'
                elif category.name_en and not category.name_ru:
                    fixes_needed.append("original_language = 'en'")
                    if execute:
                        category.original_language = 'en'
            
            # Выводим информацию о категории
            if category_issues or fixes_needed:
                print(f"\n📁 Категория: {category.name}")
                print(f"   ID: {category.id}")
                print(f"   name_ru: '{category.name_ru or 'NULL'}'")
                print(f"   name_en: '{category.name_en or 'NULL'}'")
                print(f"   original_language: {category.original_language}")
                print(f"   is_translatable: {category.is_translatable}")
                
                for issue in category_issues:
                    print(f"   {issue}")
                
                if fixes_needed:
                    print("   🔧 Исправления:")
                    for fix in fixes_needed:
                        print(f"      {fix}")
                    
                    if execute:
                        category.save()
                        print("   ✅ Исправления применены")
                    
                    fixed_count += 1
            else:
                print(f"✅ {category.name} - OK")
        
        print(f"\n{'=' * 60}")
        print(f"Категорий с проблемами: {fixed_count}")
        
        # Проверяем расходы без категории
        orphaned_expenses = profile.expenses.filter(category__isnull=True).count()
        if orphaned_expenses > 0:
            print(f"⚠️  Расходов без категории: {orphaned_expenses}")
        
        # Проверяем недостающие стандартные категории
        existing_names = set()
        for cat in categories:
            if cat.name_ru:
                existing_names.add(cat.name_ru.lower())
            if cat.name_en:
                existing_names.add(cat.name_en.lower())
        
        missing_categories = []
        for unified_cat in UNIFIED_CATEGORIES:
            if (unified_cat['name_ru'].lower() not in existing_names and 
                unified_cat['name_en'].lower() not in existing_names):
                missing_categories.append(unified_cat)
        
        if missing_categories:
            print(f"\n⚠️  Недостающие стандартные категории ({len(missing_categories)}):")
            for cat in missing_categories[:5]:  # Показываем первые 5
                print(f"   - {cat['icon']} {cat['name_ru']} / {cat['name_en']}")
            if len(missing_categories) > 5:
                print(f"   ... и еще {len(missing_categories) - 5}")
        
        return fixed_count
        
    except Profile.DoesNotExist:
        print(f"❌ Профиль {telegram_id} не найден")
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 0


def show_category_stats(telegram_id: int):
    """
    Показать детальную статистику по категориям пользователя
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        categories = profile.categories.filter(is_active=True)
        
        print(f"📊 СТАТИСТИКА КАТЕГОРИЙ ПОЛЬЗОВАТЕЛЯ {telegram_id}")
        print("=" * 60)
        
        print(f"Всего активных категорий: {categories.count()}")
        
        # Группировка по типам
        with_both_languages = categories.filter(name_ru__isnull=False, name_en__isnull=False).exclude(name_ru='').exclude(name_en='')
        only_ru = categories.filter(name_ru__isnull=False, name_en__isnull=True).exclude(name_ru='') | categories.filter(name_ru__isnull=False, name_en='').exclude(name_ru='')
        only_en = categories.filter(name_en__isnull=False, name_ru__isnull=True).exclude(name_en='') | categories.filter(name_en__isnull=False, name_ru='').exclude(name_en='')
        empty_multilingual = categories.filter(
            (models.Q(name_ru__isnull=True) | models.Q(name_ru='')) &
            (models.Q(name_en__isnull=True) | models.Q(name_en=''))
        )
        
        print(f"С обоими языками: {with_both_languages.count()}")
        print(f"Только русский: {only_ru.count()}")
        print(f"Только английский: {only_en.count()}")
        print(f"Без мультиязычных полей: {empty_multilingual.count()}")
        
        # Статистика по расходам
        total_expenses = profile.expenses.count()
        expenses_with_category = profile.expenses.filter(category__isnull=False).count()
        
        print(f"\n💰 СТАТИСТИКА РАСХОДОВ:")
        print(f"Всего расходов: {total_expenses}")
        print(f"С категорией: {expenses_with_category}")
        print(f"Без категории: {total_expenses - expenses_with_category}")
        
        # Топ-5 категорий по количеству расходов
        from django.db.models import Count
        top_categories = categories.annotate(
            expense_count=Count('expenses')
        ).filter(expense_count__gt=0).order_by('-expense_count')[:5]
        
        if top_categories:
            print(f"\n🏆 ТОП-5 КАТЕГОРИЙ ПО РАСХОДАМ:")
            for i, cat in enumerate(top_categories, 1):
                print(f"{i}. {cat.name} - {cat.expense_count} расходов")
        
    except Profile.DoesNotExist:
        print(f"❌ Профиль {telegram_id} не найден")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


def main():
    """Главная функция для интерактивной работы"""
    print("🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ КАТЕГОРИЙ")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        # Запуск с параметрами командной строки
        telegram_id = int(sys.argv[1])
        action = sys.argv[2] if len(sys.argv) > 2 else 'check'
        execute = '--execute' in sys.argv
        
        if action == 'stats':
            show_category_stats(telegram_id)
        else:
            quick_fix_user_categories(telegram_id, execute)
    else:
        # Интерактивный режим
        while True:
            print("\nВыберите действие:")
            print("1. Проверить категории пользователя")
            print("2. Исправить категории пользователя")
            print("3. Показать статистику пользователя")
            print("0. Выход")
            
            choice = input("\nВведите номер: ").strip()
            
            if choice == '0':
                break
            elif choice in ['1', '2', '3']:
                telegram_id = input("Введите Telegram ID пользователя: ").strip()
                try:
                    telegram_id = int(telegram_id)
                    
                    if choice == '1':
                        quick_fix_user_categories(telegram_id, False)
                    elif choice == '2':
                        quick_fix_user_categories(telegram_id, True)
                    elif choice == '3':
                        show_category_stats(telegram_id)
                        
                except ValueError:
                    print("❌ Неверный формат ID")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
            else:
                print("❌ Неверный выбор")


if __name__ == "__main__":
    main()