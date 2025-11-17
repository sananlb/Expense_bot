"""
Скрипт для переименования категории "Коммунальные услуги и подписки" → "Коммуналка и подписки"

Проблема:
  - Все 34 пользователя получили старое название категории при регистрации.
  - Код создавал категорию с устаревшим названием до 2025-11-17.

Решение:
  - Обновить name_ru у всех затронутых категорий.
  - НЕ трогать пользовательские переименования (2 категории).

Использование:
    python fix_utilities_category_name.py              # Тестовый прогон (dry-run)
    python fix_utilities_category_name.py --apply      # Применить изменения
"""
import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from expenses.models import ExpenseCategory
from django.db import transaction


def fix_utilities_category_name(dry_run=True):
    """Переименовать категорию 'Коммунальные услуги и подписки' → 'Коммуналка и подписки'"""

    print("=" * 80)
    print(f"МИГРАЦИЯ: Переименование категории 'Коммунальные услуги и подписки'")
    print(f"Режим: {'DRY-RUN (тестовый прогон)' if dry_run else 'ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ'}")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Находим все категории со старым названием
    old_name = "Коммунальные услуги и подписки"
    new_name = "Коммуналка и подписки"

    categories_to_fix = ExpenseCategory.objects.filter(name_ru=old_name)
    count = categories_to_fix.count()

    print(f"Найдено категорий со старым названием: {count}")
    print()

    if count == 0:
        print("✅ Нет категорий для обновления.")
        return

    # Показываем затронутых пользователей
    profiles = set()
    for cat in categories_to_fix:
        profiles.add(cat.profile_id)

    print(f"Затронуто пользователей: {len(profiles)}")
    print()

    # Показываем первые 5 примеров
    print("Примеры категорий для обновления:")
    print("-" * 80)
    for i, cat in enumerate(categories_to_fix[:5], 1):
        print(f"{i}. ID={cat.id}, Profile={cat.profile_id}, "
              f"name_ru='{cat.name_ru}' → '{new_name}'")
    if count > 5:
        print(f"... и ещё {count - 5} категорий")
    print("-" * 80)
    print()

    if dry_run:
        print("⚠️  DRY-RUN режим: изменения НЕ будут применены.")
        print("⚠️  Для применения запустите с флагом --apply")
        return

    # Применяем изменения
    print("🔧 Применение изменений...")
    print()

    updated_count = 0
    with transaction.atomic():
        for cat in categories_to_fix:
            old_name_full = cat.name

            # Обновляем name_ru
            cat.name_ru = new_name

            # Обновляем старое поле name для обратной совместимости
            # Сохраняем эмодзи если есть
            if cat.icon:
                cat.name = f"{cat.icon} {new_name}"
            else:
                cat.name = new_name

            cat.save(update_fields=['name_ru', 'name', 'updated_at'])
            updated_count += 1

            print(f"✅ Обновлена категория ID={cat.id}, Profile={cat.profile_id}")
            print(f"   Было: name='{old_name_full}', name_ru='{old_name}'")
            print(f"   Стало: name='{cat.name}', name_ru='{new_name}'")
            print()

    print("=" * 80)
    print(f"✅ УСПЕШНО обновлено категорий: {updated_count}")
    print(f"✅ Затронуто пользователей: {len(profiles)}")
    print(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


def check_user_customized_categories(dry_run=True):
    """
    Проверить категории которые выглядят как 'битые' но на самом деле
    являются пользовательскими переименованиями
    """

    print()
    print("=" * 80)
    print("ПРОВЕРКА: Пользовательские переименования категорий")
    print("=" * 80)
    print()

    # Категория "Кофе" - пользователь переименовал
    custom_coffee = ExpenseCategory.objects.filter(
        name_ru__contains="Кофе",
        name_en="Utilities and subscriptions"
    )

    # Категория с пустым name_ru - пользователь оставил только EN
    custom_empty = ExpenseCategory.objects.filter(
        name_ru__isnull=True,
        name_en="Utilities and Subscriptions"
    ) | ExpenseCategory.objects.filter(
        name_ru="",
        name_en="Utilities and Subscriptions"
    )

    total_custom = custom_coffee.count() + custom_empty.count()

    if total_custom == 0:
        print("✅ Пользовательских переименований не найдено.")
        return

    print(f"Найдено пользовательских переименований: {total_custom}")
    print()
    print("⚠️  Эти категории были вручную переименованы пользователями:")
    print()

    if custom_coffee.exists():
        print("Пользовательская категория #1: 'Кофе'")
        for cat in custom_coffee:
            time_diff = (cat.updated_at - cat.created_at).total_seconds() / 3600
            print(f"  - ID={cat.id}, Profile={cat.profile_id}")
            print(f"    name_ru='{cat.name_ru}', name_en='{cat.name_en}'")
            print(f"    Обновлена через {time_diff:.1f} часов после создания")
        print()

    if custom_empty.exists():
        print("Пользовательская категория #2: Только английское название")
        for cat in custom_empty:
            time_diff = (cat.updated_at - cat.created_at).total_seconds() / 60
            print(f"  - ID={cat.id}, Profile={cat.profile_id}")
            print(f"    name_ru='{cat.name_ru or '(пусто)'}', name_en='{cat.name_en}'")
            print(f"    Обновлена через {time_diff:.1f} минут после создания")
        print()

    print("✅ Эти категории НЕ будут изменены - это пользовательские настройки.")
    print()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Переименование категории "Коммунальные услуги и подписки"')
    parser.add_argument('--apply', action='store_true', help='Применить изменения (по умолчанию dry-run)')
    args = parser.parse_args()

    dry_run = not args.apply

    try:
        # Основная миграция
        fix_utilities_category_name(dry_run=dry_run)

        # Проверка пользовательских переименований (информационно)
        check_user_customized_categories(dry_run=dry_run)

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ОШИБКА: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)
