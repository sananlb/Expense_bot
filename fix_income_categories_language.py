#!/usr/bin/env python3
"""
Скрипт для исправления несоответствия языка категорий доходов языку пользователя.

ВНИМАНИЕ: Скрипт работает в два режима:
1. Dry-run (по умолчанию): только показывает что будет исправлено
2. Apply (--apply): применяет исправления в БД

Использование:
    python fix_income_categories_language.py             # Тестовый прогон
    python fix_income_categories_language.py --apply     # Применить изменения
"""

import os
import sys
import django
import argparse

# Настройка Django окружения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from expenses.models import Profile, IncomeCategory
from django.db import transaction
from django.db.models import Count


def fix_income_categories_language(apply_changes=False):
    """Исправление несоответствия языка категорий доходов"""

    mode = "🔧 ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ" if apply_changes else "🔍 ТЕСТОВЫЙ ПРОГОН (DRY RUN)"

    print("=" * 80)
    print(f"ИСПРАВЛЕНИЕ ЯЗЫКОВ КАТЕГОРИЙ ДОХОДОВ - {mode}")
    print("=" * 80)
    print()

    if not apply_changes:
        print("⚠️  ВНИМАНИЕ: Запущен тестовый режим (dry-run)")
        print("   Изменения НЕ будут применены к базе данных")
        print("   Для применения изменений запустите: python fix_income_categories_language.py --apply")
        print()

    # Получаем всех пользователей у которых есть категории доходов
    profiles_with_income_cats = Profile.objects.annotate(
        income_cats_count=Count('income_categories')
    ).filter(income_cats_count__gt=0).order_by('telegram_id')

    total_users = profiles_with_income_cats.count()
    print(f"📊 Всего пользователей с категориями доходов: {total_users}")
    print()

    fixed_count = 0
    fixed_categories = []

    for profile in profiles_with_income_cats:
        user_lang = profile.language_code  # Язык пользователя (ru или en)
        telegram_id = profile.telegram_id

        # Получаем все категории доходов пользователя
        categories = IncomeCategory.objects.filter(profile=profile).order_by('id')

        for category in categories:
            needs_fix = False
            fix_actions = []

            # Проверка 1: Несоответствие original_language
            if category.original_language != user_lang:
                needs_fix = True
                fix_actions.append(
                    f"original_language: {category.original_language} -> {user_lang}"
                )

            # Проверка 2: Перепутанные мультиязычные поля
            if user_lang == 'ru':
                # Пользователь русский, но заполнено только name_en
                if category.name_en and not category.name_ru:
                    needs_fix = True
                    fix_actions.append(
                        f"name_ru: None -> '{category.name_en}' (swap from name_en)"
                    )
                    fix_actions.append(
                        f"name_en: '{category.name_en}' -> None (clear)"
                    )
            elif user_lang == 'en':
                # Пользователь английский, но заполнено только name_ru
                if category.name_ru and not category.name_en:
                    needs_fix = True
                    fix_actions.append(
                        f"name_en: None -> '{category.name_ru}' (swap from name_ru)"
                    )
                    fix_actions.append(
                        f"name_ru: '{category.name_ru}' -> None (clear)"
                    )

            if needs_fix:
                fixed_categories.append({
                    'telegram_id': telegram_id,
                    'profile_id': profile.id,
                    'user_lang': user_lang,
                    'category_id': category.id,
                    'category_name': category.name,
                    'icon': category.icon,
                    'old_original_language': category.original_language,
                    'old_name_ru': category.name_ru,
                    'old_name_en': category.name_en,
                    'fix_actions': fix_actions
                })

                if apply_changes:
                    # Применяем исправления
                    with transaction.atomic():
                        # Исправление 1: original_language
                        if category.original_language != user_lang:
                            category.original_language = user_lang

                        # Исправление 2: Swap мультиязычных полей
                        if user_lang == 'ru' and category.name_en and not category.name_ru:
                            # Перемещаем name_en в name_ru
                            category.name_ru = category.name_en
                            category.name_en = None
                        elif user_lang == 'en' and category.name_ru and not category.name_en:
                            # Перемещаем name_ru в name_en
                            category.name_en = category.name_ru
                            category.name_ru = None

                        category.save()
                        fixed_count += 1

    # Выводим результаты
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print()

    if fixed_categories:
        print(f"{'✅ Исправлено' if apply_changes else '🔍 Будет исправлено'} категорий: {len(fixed_categories)}")
        print()

        print("📋 ДЕТАЛЬНЫЙ ОТЧЕТ:")
        print()

        for cat_data in fixed_categories:
            print("─" * 80)
            print(f"👤 Пользователь: telegram_id={cat_data['telegram_id']}, "
                  f"profile_id={cat_data['profile_id']}, язык={cat_data['user_lang']}")
            print(f"📁 Категория ID={cat_data['category_id']}")
            print(f"   Название: {cat_data['category_name']} {cat_data['icon']}")
            print()
            print(f"   Было:")
            print(f"     original_language: {cat_data['old_original_language']}")
            print(f"     name_ru: {cat_data['old_name_ru']}")
            print(f"     name_en: {cat_data['old_name_en']}")
            print()
            print(f"   Изменения:")
            for action in cat_data['fix_actions']:
                print(f"     {action}")
            print()

        if apply_changes:
            print("=" * 80)
            print("✅ ИСПРАВЛЕНИЯ УСПЕШНО ПРИМЕНЕНЫ!")
            print("=" * 80)
        else:
            print("=" * 80)
            print("⚠️  ВНИМАНИЕ: Это был тестовый прогон (dry-run)")
            print("   Для применения изменений запустите:")
            print("   python fix_income_categories_language.py --apply")
            print("=" * 80)
    else:
        print("✅ ВСЕ В ПОРЯДКЕ!")
        print("   Категорий требующих исправления не найдено.")
        print()
        print("=" * 80)

    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Исправление несоответствия языка категорий доходов'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Применить изменения к БД (по умолчанию: dry-run)'
    )

    args = parser.parse_args()
    fix_income_categories_language(apply_changes=args.apply)
