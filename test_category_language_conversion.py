"""
Регрессионный тест для проверки правильности языковой конвертации категорий.

Проверяет что:
1. Русский пользователь с русскими словами получает русские категории
2. Русский пользователь с английскими словами получает русские категории (с конвертацией)
3. Английский пользователь с английскими словами получает английские категории
4. Английский пользователь с русскими словами получает английские категории (с конвертацией)
"""

import os
import sys
import django
import asyncio

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message
from expenses.models import Profile


def create_test_profile(telegram_id, language_code):
    """Создает тестовый профиль с указанным языком"""
    # Проверяем существует ли профиль
    profile = Profile.objects.filter(telegram_id=telegram_id).first()
    if profile:
        profile.language_code = language_code
        profile.save()
        return profile

    # Создаем новый профиль (без User - не требуется)
    profile = Profile.objects.create(
        telegram_id=telegram_id,
        language_code=language_code,
        currency='RUB'
    )
    return profile


async def test_category_language_conversion(ru_profile, en_profile):
    """Тестирует правильность языковой конвертации категорий"""

    print("=" * 80)
    print("ТЕСТ ЯЗЫКОВОЙ КОНВЕРТАЦИИ КАТЕГОРИЙ")
    print("=" * 80)

    test_cases = [
        # (text, profile, expected_category, test_description)
        ("хлеб 50", ru_profile, "Продукты", "RU user + RU word"),
        ("bread 50", ru_profile, "Продукты", "RU user + EN word (convert)"),
        ("бензин 1000", ru_profile, "АЗС", "RU user + benzin (RU)"),
        ("gasoline 1000", ru_profile, "АЗС", "RU user + gasoline (EN convert)"),

        ("bread 50", en_profile, "Groceries", "EN user + EN word"),
        ("хлеб 50", en_profile, "Groceries", "EN user + RU word (convert)"),
        ("gasoline 1000", en_profile, "Gas Station", "EN user + gasoline (EN)"),
        ("бензин 1000", en_profile, "Gas Station", "EN user + benzin (RU convert)"),

        # Additional test cases
        ("кофе 200", ru_profile, "Кафе и рестораны", "RU user + kofe"),
        ("coffee 200", ru_profile, "Кафе и рестораны", "RU user + coffee"),
        ("coffee 200", en_profile, "Cafes and Restaurants", "EN user + coffee"),
        ("кофе 200", en_profile, "Cafes and Restaurants", "EN user + kofe"),
    ]

    passed = 0
    failed = 0

    for text, profile, expected_category, description in test_cases:
        result = await parse_expense_message(text, profile=profile)
        actual_category = result.get('category')

        status = "[PASS]" if actual_category == expected_category else "[FAIL]"
        if actual_category == expected_category:
            passed += 1
        else:
            failed += 1

        print(f"\n{status}")
        print(f"  Test: {description}")
        print(f"  Text: '{text}'")
        print(f"  User language: {profile.language_code}")
        print(f"  Expected: '{expected_category}'")
        print(f"  Got: '{actual_category}'")

        if actual_category != expected_category:
            print(f"  [!] MISMATCH!")

    print("\n" + "=" * 80)
    print(f"РЕЗУЛЬТАТЫ: {passed} успешных, {failed} провальных")
    print("=" * 80)

    return failed == 0


if __name__ == '__main__':
    # Создаем тестовые профили (синхронно, до async контекста)
    ru_profile = create_test_profile(999991, 'ru')
    en_profile = create_test_profile(999992, 'en')

    try:
        # Запускаем тесты
        success = asyncio.run(test_category_language_conversion(ru_profile, en_profile))
    finally:
        # Очищаем тестовые профили
        Profile.objects.filter(telegram_id__in=[999991, 999992]).delete()

    sys.exit(0 if success else 1)
