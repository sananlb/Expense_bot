#!/usr/bin/env python3
"""
Скрипт для проверки соответствия языка категорий доходов языку настроек пользователя.

Проблема: У некоторых пользователей категории доходов могут быть на неправильном языке.
Например, при русском языке пользователя категории на английском, и наоборот.

Скрипт проверяет:
1. Соответствие original_language категории и language пользователя
2. Заполненность правильных мультиязычных полей (name_ru или name_en)
3. Соответствие отображаемого названия языку пользователя
"""

import os
import sys
import django

# Настройка Django окружения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from expenses.models import Profile, IncomeCategory
from django.db.models import Count


def check_income_categories_language():
    """Проверка соответствия языка категорий доходов языку пользователя"""

    print("=" * 80)
    print("ПРОВЕРКА КАТЕГОРИЙ ДОХОДОВ НА СООТВЕТСТВИЕ ЯЗЫКУ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 80)
    print()

    # Получаем всех пользователей у которых есть категории доходов
    profiles_with_income_cats = Profile.objects.annotate(
        income_cats_count=Count('income_categories')
    ).filter(income_cats_count__gt=0).order_by('telegram_id')

    total_users = profiles_with_income_cats.count()
    print(f"📊 Всего пользователей с категориями доходов: {total_users}")
    print()

    issues_found = []
    users_checked = 0

    for profile in profiles_with_income_cats:
        users_checked += 1
        user_lang = profile.language_code  # Язык пользователя (ru или en)
        telegram_id = profile.telegram_id

        # Получаем все категории доходов пользователя
        categories = IncomeCategory.objects.filter(profile=profile).order_by('id')

        user_issues = []

        for category in categories:
            cat_issues = []

            # Проверка 1: Соответствие original_language языку пользователя
            if category.original_language != user_lang:
                cat_issues.append(
                    f"  ❌ Несоответствие языка: пользователь={user_lang}, "
                    f"категория={category.original_language}"
                )

            # Проверка 2: Заполненность правильного мультиязычного поля
            if user_lang == 'ru':
                if not category.name_ru:
                    cat_issues.append(
                        f"  ⚠️  Пустое поле name_ru при русском языке пользователя"
                    )
                if category.name_en and not category.name_ru:
                    cat_issues.append(
                        f"  ⚠️  Заполнено только name_en, но пользователь русский"
                    )
            elif user_lang == 'en':
                if not category.name_en:
                    cat_issues.append(
                        f"  ⚠️  Пустое поле name_en при английском языке пользователя"
                    )
                if category.name_ru and not category.name_en:
                    cat_issues.append(
                        f"  ⚠️  Заполнено только name_ru, но пользователь английский"
                    )

            # Проверка 3: Соответствие отображаемого name
            # name должно содержать текст на языке пользователя
            if user_lang == 'ru' and category.name_ru:
                # Проверяем что name содержит русское название
                if category.name_ru.lower() not in category.name.lower():
                    cat_issues.append(
                        f"  ⚠️  Поле name не содержит name_ru: "
                        f"name='{category.name}', name_ru='{category.name_ru}'"
                    )
            elif user_lang == 'en' and category.name_en:
                # Проверяем что name содержит английское название
                if category.name_en.lower() not in category.name.lower():
                    cat_issues.append(
                        f"  ⚠️  Поле name не содержит name_en: "
                        f"name='{category.name}', name_en='{category.name_en}'"
                    )

            if cat_issues:
                user_issues.append({
                    'category_id': category.id,
                    'category_name': category.name,
                    'name_ru': category.name_ru,
                    'name_en': category.name_en,
                    'original_language': category.original_language,
                    'icon': category.icon,
                    'issues': cat_issues
                })

        if user_issues:
            issues_found.append({
                'telegram_id': telegram_id,
                'user_lang': user_lang,
                'profile_id': profile.id,
                'categories_count': categories.count(),
                'issues': user_issues
            })

    # Выводим результаты
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ ПРОВЕРКИ")
    print("=" * 80)
    print()
    print(f"✅ Проверено пользователей: {users_checked}")
    print(f"❌ Найдено пользователей с проблемами: {len(issues_found)}")
    print()

    if issues_found:
        print("📋 ДЕТАЛЬНЫЙ ОТЧЕТ ПО ПРОБЛЕМАМ:")
        print()

        for user_data in issues_found:
            print("─" * 80)
            print(f"👤 Пользователь: telegram_id={user_data['telegram_id']}, "
                  f"profile_id={user_data['profile_id']}")
            print(f"   Язык пользователя: {user_data['user_lang']}")
            print(f"   Категорий доходов: {user_data['categories_count']}")
            print()

            for cat_data in user_data['issues']:
                print(f"  📁 Категория ID={cat_data['category_id']}")
                print(f"     name: {cat_data['category_name']}")
                print(f"     icon: {cat_data['icon']}")
                print(f"     name_ru: {cat_data['name_ru']}")
                print(f"     name_en: {cat_data['name_en']}")
                print(f"     original_language: {cat_data['original_language']}")
                print()
                print(f"     Проблемы:")
                for issue in cat_data['issues']:
                    print(f"     {issue}")
                print()

        print("=" * 80)
        print()
        print("💡 РЕКОМЕНДАЦИЯ:")
        print("   Создайте скрипт исправления с помощью fix_income_categories_language.py")
        print()

        # Сохраняем отчет в файл
        with open('income_categories_language_issues.txt', 'w', encoding='utf-8') as f:
            f.write("ОТЧЕТ О ПРОБЛЕМАХ С ЯЗЫКАМИ КАТЕГОРИЙ ДОХОДОВ\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Проверено пользователей: {users_checked}\n")
            f.write(f"Найдено пользователей с проблемами: {len(issues_found)}\n\n")

            for user_data in issues_found:
                f.write("─" * 80 + "\n")
                f.write(f"Telegram ID: {user_data['telegram_id']}\n")
                f.write(f"Profile ID: {user_data['profile_id']}\n")
                f.write(f"Язык пользователя: {user_data['user_lang']}\n")
                f.write(f"Категорий доходов: {user_data['categories_count']}\n\n")

                for cat_data in user_data['issues']:
                    f.write(f"  Категория ID={cat_data['category_id']}\n")
                    f.write(f"  name: {cat_data['category_name']}\n")
                    f.write(f"  icon: {cat_data['icon']}\n")
                    f.write(f"  name_ru: {cat_data['name_ru']}\n")
                    f.write(f"  name_en: {cat_data['name_en']}\n")
                    f.write(f"  original_language: {cat_data['original_language']}\n\n")
                    f.write(f"  Проблемы:\n")
                    for issue in cat_data['issues']:
                        f.write(f"  {issue}\n")
                    f.write("\n")

        print(f"📄 Отчет сохранен в файл: income_categories_language_issues.txt")
        print()
    else:
        print("✅ ВСЕ В ПОРЯДКЕ!")
        print("   Проблем с языками категорий доходов не найдено.")
        print()

    print("=" * 80)


if __name__ == '__main__':
    check_income_categories_language()
