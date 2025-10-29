#!/usr/bin/env python3
"""
Скрипт для исправления существующих категорий доходов без эмодзи
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, '/Users/aleksejnalbantov/Desktop/expense_bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import IncomeCategory

# Словарь для сопоставления названий категорий с эмодзи
CATEGORY_EMOJIS = {
    'Зарплата': '💼',
    'Фриланс': '💻',
    'Инвестиции': '📈',
    'Подарок': '🎁',
    'Возврат': '↩️',
    'Премия': '🏆',
    'Кешбэк': '💳',
    'Дивиденды': '💵',
    'Продажа': '🛒',
    'Другое': '📝',
    
    # English categories (уже должны иметь эмодзи, но проверим)
    'Salary': '💼',
    'Freelance': '💻',
    'Investments': '📈',
    'Gift': '🎁',
    'Refund': '↩️',
    'Bonus': '🏆',
    'Cashback': '💳',
    'Dividends': '💵',
    'Sale': '🛒',
    'Other': '📝',
}

print("\n" + "="*60)
print("ИСПРАВЛЕНИЕ КАТЕГОРИЙ ДОХОДОВ БЕЗ ЭМОДЗИ")
print("="*60)

# Получаем все категории доходов
all_categories = IncomeCategory.objects.all()
print(f"\nВсего категорий доходов в БД: {all_categories.count()}")

# Счетчики
fixed_count = 0
already_has_emoji = 0
unknown_categories = []

# Проверяем каждую категорию
for category in all_categories:
    # Проверяем, начинается ли название с эмодзи
    if category.name and len(category.name) > 0:
        # Простая проверка: если первый символ не буква/цифра, возможно это эмодзи
        first_char = category.name[0]
        if not first_char.isalnum():
            already_has_emoji += 1
            print(f"✅ Уже есть эмодзи: {category.name} (user: {category.profile.telegram_id})")
            continue
    
    # Пытаемся найти соответствующий эмодзи
    clean_name = category.name.strip()
    emoji = None
    
    # Сначала проверяем точное совпадение
    if clean_name in CATEGORY_EMOJIS:
        emoji = CATEGORY_EMOJIS[clean_name]
    else:
        # Проверяем, может это название без эмодзи из словаря
        for cat_name, cat_emoji in CATEGORY_EMOJIS.items():
            if clean_name.lower() == cat_name.lower():
                emoji = cat_emoji
                break
    
    if emoji:
        # Обновляем название с эмодзи
        old_name = category.name
        category.name = f"{emoji} {clean_name}"
        category.icon = emoji  # Также обновляем поле icon
        category.save()
        fixed_count += 1
        print(f"🔧 Исправлено: '{old_name}' → '{category.name}' (user: {category.profile.telegram_id})")
    else:
        unknown_categories.append(f"{category.name} (user: {category.profile.telegram_id})")

print("\n" + "="*60)
print("РЕЗУЛЬТАТЫ:")
print("="*60)
print(f"✅ Уже имели эмодзи: {already_has_emoji}")
print(f"🔧 Исправлено: {fixed_count}")
print(f"❓ Неизвестные категории: {len(unknown_categories)}")

if unknown_categories:
    print("\nНеизвестные категории (требуют ручной проверки):")
    for cat in unknown_categories:
        print(f"  - {cat}")

print("\n✅ Исправление завершено!")
print("="*60)