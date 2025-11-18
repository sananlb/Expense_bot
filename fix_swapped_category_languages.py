#!/usr/bin/env python
"""
Скрипт для исправления категорий с перепутанными языками (name_ru ↔ name_en)

Проблема: В некоторых категориях name_ru содержит английский текст,
а name_en содержит русский текст (они перепутаны местами).

Дата создания проблемных категорий: 10 ноября 2025
Затронуто: 11 категорий, 2 пользователя

Использование:
    python fix_swapped_category_languages.py           # Тестовый прогон (dry-run)
    python fix_swapped_category_languages.py --apply   # Применить изменения
"""

import os
import sys
import django
import re
from datetime import datetime

# Настройка Django окружения
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory
from django.db import transaction


def has_cyrillic(text: str) -> bool:
    """Проверяет есть ли кириллица в тексте"""
    if not text:
        return False
    return bool(re.search(r'[А-Яа-яёЁ]', text))


def has_latin(text: str) -> bool:
    """Проверяет есть ли латиница в тексте"""
    if not text:
        return False
    return bool(re.search(r'[A-Za-z]', text))


def is_swapped(category: ExpenseCategory) -> bool:
    """
    Определяет, перепутаны ли языки в категории

    Returns:
        True если name_ru содержит английский, а name_en русский
    """
    name_ru = category.name_ru or ''
    name_en = category.name_en or ''

    # Пропускаем категории без мультиязычных полей
    if not name_ru or not name_en:
        return False

    # Проверяем что в name_ru есть латиница И в name_en есть кириллица
    ru_has_latin = has_latin(name_ru)
    en_has_cyrillic = has_cyrillic(name_en)

    # Проверяем что в name_ru НЕТ кириллицы И в name_en НЕТ латиницы
    ru_no_cyrillic = not has_cyrillic(name_ru)
    en_no_latin = not has_latin(name_en)

    # Языки перепутаны если:
    # 1. name_ru содержит ТОЛЬКО латиницу (английский)
    # 2. name_en содержит ТОЛЬКО кириллицу (русский)
    return (ru_has_latin and ru_no_cyrillic) and (en_has_cyrillic and en_no_latin)


def find_swapped_categories():
    """Найти все категории с перепутанными языками"""
    # Ищем категории где original_language='ru' И языки перепутаны
    candidates = ExpenseCategory.objects.filter(
        original_language='ru'
    ).select_related('profile')

    swapped = []
    for cat in candidates:
        if is_swapped(cat):
            swapped.append(cat)

    return swapped


def fix_category(category: ExpenseCategory, dry_run: bool = True) -> dict:
    """
    Исправить категорию (поменять name_ru ↔ name_en местами)

    Returns:
        dict с информацией об изменении
    """
    old_name_ru = category.name_ru
    old_name_en = category.name_en

    if dry_run:
        return {
            'id': category.id,
            'profile_id': category.profile_id,
            'telegram_id': category.profile.telegram_id,
            'old_name_ru': old_name_ru,
            'old_name_en': old_name_en,
            'new_name_ru': old_name_en,  # SWAP!
            'new_name_en': old_name_ru,  # SWAP!
            'applied': False
        }

    # Применяем изменения
    category.name_ru = old_name_en  # Русский <- был в name_en
    category.name_en = old_name_ru  # Английский <- был в name_ru
    category.save(update_fields=['name_ru', 'name_en'])

    return {
        'id': category.id,
        'profile_id': category.profile_id,
        'telegram_id': category.profile.telegram_id,
        'old_name_ru': old_name_ru,
        'old_name_en': old_name_en,
        'new_name_ru': category.name_ru,
        'new_name_en': category.name_en,
        'applied': True
    }


def main():
    """Главная функция"""
    # Проверяем флаг --apply
    apply_changes = '--apply' in sys.argv

    print("=" * 80)
    print("ИСПРАВЛЕНИЕ КАТЕГОРИЙ С ПЕРЕПУТАННЫМИ ЯЗЫКАМИ")
    print("=" * 80)
    print()

    if apply_changes:
        print("[!] РЕЖИМ: ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ")
        print()
    else:
        print("[i] РЕЖИМ: ТЕСТОВЫЙ ПРОГОН (dry-run)")
        print("   Для применения изменений запустите: python fix_swapped_category_languages.py --apply")
        print()

    # Находим проблемные категории
    print("Поиск категорий с перепутанными языками...")
    swapped_categories = find_swapped_categories()

    if not swapped_categories:
        print("[OK] Проблемных категорий не найдено!")
        return

    print(f"Найдено категорий с перепутанными языками: {len(swapped_categories)}")
    print()

    # Группируем по пользователям
    users_affected = set()
    for cat in swapped_categories:
        users_affected.add((cat.profile_id, cat.profile.telegram_id))

    print(f"Затронуто пользователей: {len(users_affected)}")
    for profile_id, telegram_id in sorted(users_affected):
        print(f"  - Profile ID: {profile_id}, Telegram ID: {telegram_id}")
    print()

    # Исправляем категории
    results = []

    if apply_changes:
        with transaction.atomic():
            for cat in swapped_categories:
                result = fix_category(cat, dry_run=False)
                results.append(result)
    else:
        for cat in swapped_categories:
            result = fix_category(cat, dry_run=True)
            results.append(result)

    # Выводим детальный отчет
    print("-" * 80)
    print("ДЕТАЛЬНЫЙ ОТЧЕТ ПО ИЗМЕНЕНИЯМ:")
    print("-" * 80)
    print()

    for i, result in enumerate(results, 1):
        print(f"{i}. Категория ID: {result['id']} (Profile: {result['profile_id']}, User: {result['telegram_id']})")
        print(f"   БЫЛО:")
        print(f"     name_ru: {result['old_name_ru']}")
        print(f"     name_en: {result['old_name_en']}")
        print(f"   СТАЛО:")
        print(f"     name_ru: {result['new_name_ru']}")
        print(f"     name_en: {result['new_name_en']}")

        if result['applied']:
            print(f"   [OK] ИЗМЕНЕНИЯ ПРИМЕНЕНЫ")
        else:
            print(f"   [i] Тестовый режим (изменения НЕ применены)")
        print()

    # Итоговая статистика
    print("=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА:")
    print("=" * 80)
    print(f"Всего исправлено категорий: {len(results)}")
    print(f"Затронуто пользователей: {len(users_affected)}")

    if apply_changes:
        print()
        print("[OK] ВСЕ ИЗМЕНЕНИЯ УСПЕШНО ПРИМЕНЕНЫ!")
        print()
        print("Рекомендации:")
        print("1. Проверьте категории затронутых пользователей:")
        for profile_id, telegram_id in sorted(users_affected):
            print(f"   SELECT id, name_ru, name_en FROM expenses_category WHERE profile_id = {profile_id};")
        print()
        print("2. Попросите пользователей проверить отображение категорий в боте")
    else:
        print()
        print("[i] Это был тестовый прогон. Изменения НЕ применены.")
        print("   Для применения изменений запустите:")
        print("   python fix_swapped_category_languages.py --apply")

    print()
    print(f"Дата и время выполнения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == '__main__':
    main()
