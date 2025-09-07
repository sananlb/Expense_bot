#!/usr/bin/env python3
"""
Анализ проблем с категориями в системе
"""

import re

# Данные из кода бота
DEFAULT_CATEGORIES = [
    ('Продукты', '🛒'),
    ('Кафе и рестораны', '🍽️'),
    ('АЗС', '⛽'),
    ('Транспорт', '🚕'),
    ('Автомобиль', '🚗'),
    ('Жилье', '🏠'),
    ('Аптеки', '💊'),
    ('Медицина', '🏥'),
    ('Красота', '💄'),
    ('Спорт и фитнес', '🏃'),
    ('Одежда и обувь', '👔'),
    ('Развлечения', '🎭'),
    ('Образование', '📚'),
    ('Подарки', '🎁'),
    ('Путешествия', '✈️'),
    ('Родственники', '👪'),
    ('Коммунальные услуги и подписки', '📱'),
    ('Прочие расходы', '💰')
]

# Переводы из language.py
TRANSLATIONS = {
    'Продукты': 'Products',
    'Кафе и рестораны': 'Restaurants and Cafes',
    'АЗС': 'Gas Stations',
    'Транспорт': 'Transport',
    'Автомобиль': 'Car',
    'Жилье': 'Housing',
    'Аптеки': 'Pharmacies',
    'Медицина': 'Medicine',
    'Красота': 'Beauty',
    'Спорт и фитнес': 'Sports and Fitness',
    'Одежда и обувь': 'Clothes and Shoes',
    'Развлечения': 'Entertainment',
    'Образование': 'Education',
    'Подарки': 'Gifts',
    'Путешествия': 'Travel',
    'Родственники': 'Relatives',
    'Коммунальные услуги и подписки': 'Utilities and Subscriptions',
    'Прочие расходы': 'Other Expenses',
    # Обратные переводы
    'Products': 'Продукты',
    'Restaurants and Cafes': 'Кафе и рестораны',
    'Gas Stations': 'АЗС',
    'Transport': 'Транспорт',
    'Car': 'Автомобиль',
    'Housing': 'Жилье',
    'Pharmacies': 'Аптеки',
    'Medicine': 'Медицина',
    'Beauty': 'Красота',
    'Sports and Fitness': 'Спорт и фитнес',
    'Clothes and Shoes': 'Одежда и обувь',
    'Entertainment': 'Развлечения',
    'Education': 'Образование',
    'Gifts': 'Подарки',
    'Travel': 'Путешествия',
    'Relatives': 'Родственники',
    'Utilities and Subscriptions': 'Коммунальные услуги и подписки',
    'Other Expenses': 'Прочие расходы',
}

# Категории, создаваемые в user.py для английского языка
ENGLISH_CATEGORIES = [
    ('Supermarkets', '🛒'),
    ('Other Products', '🫑'),
    ('Restaurants and Cafes', '🍽️'),
    ('Gas Stations', '⛽'),
    ('Taxi', '🚕'),
    ('Public Transport', '🚌'),
    ('Car', '🚗'),
    ('Housing', '🏠'),
    ('Pharmacies', '💊'),
    ('Medicine', '🏥'),
    ('Sports', '🏃'),
    ('Sports Goods', '🏀'),
    ('Clothes and Shoes', '👔'),
    ('Flowers', '🌹'),
    ('Entertainment', '🎭'),
    ('Education', '📚'),
    ('Gifts', '🎁'),
    ('Travel', '✈️'),
    ('Communication and Internet', '📱'),
    ('Other Expenses', '💰')
]

def analyze_category_system():
    """Анализ проблем в системе категорий"""
    print("=== АНАЛИЗ ПРОБЛЕМ В СИСТЕМЕ КАТЕГОРИЙ ===\n")
    
    # 1. Несоответствие между DEFAULT_CATEGORIES и переводами
    print("1. Проблемы с переводами DEFAULT_CATEGORIES:")
    print("-" * 50)
    
    default_names = {name for name, _ in DEFAULT_CATEGORIES}
    
    for name, _ in DEFAULT_CATEGORIES:
        if name in TRANSLATIONS:
            translation = TRANSLATIONS[name]
            print(f"✅ {name} -> {translation}")
        else:
            print(f"❌ НЕТ ПЕРЕВОДА: {name}")
    
    # 2. Несоответствие между переводами и английскими категориями
    print("\n2. Различия между переводами и английскими категориями в user.py:")
    print("-" * 70)
    
    english_names = {name for name, _ in ENGLISH_CATEGORIES}
    
    # Проверяем какие переводы не соответствуют английским категориям
    for ru_name, en_name in TRANSLATIONS.items():
        if any(char in ru_name for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            if en_name not in english_names:
                print(f"⚠️  ПЕРЕВОД НЕ СОВПАДАЕТ: {ru_name} -> {en_name} (нет в user.py)")
    
    # Проверяем какие английские категории нет в переводах
    translated_en_names = {en for ru, en in TRANSLATIONS.items() 
                          if any(char in ru for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')}
    
    for en_name, _ in ENGLISH_CATEGORIES:
        if en_name not in translated_en_names:
            print(f"❌ НЕТ В ПЕРЕВОДАХ: {en_name} (есть в user.py)")
    
    # 3. Проблема с эмодзи
    print("\n3. Различия в эмодзи:")
    print("-" * 30)
    
    ru_emojis = {name: emoji for name, emoji in DEFAULT_CATEGORIES}
    en_emojis = {name: emoji for name, emoji in ENGLISH_CATEGORIES}
    
    for ru_name, ru_emoji in ru_emojis.items():
        if ru_name in TRANSLATIONS:
            en_name = TRANSLATIONS[ru_name]
            if en_name in en_emojis:
                en_emoji = en_emojis[en_name]
                if ru_emoji != en_emoji:
                    print(f"⚠️  РАЗНЫЕ ЭМОДЗИ: {ru_name} {ru_emoji} -> {en_name} {en_emoji}")
                else:
                    print(f"✅ {ru_name} {ru_emoji} -> {en_name} {en_emoji}")
    
    # 4. Эмодзи в названиях категорий
    print("\n4. Как сохраняются категории в коде:")
    print("-" * 40)
    
    print("В user.py категории сохраняются с эмодзи в поле name:")
    print("category_with_icon = f\"{icon} {name}\"")
    print("ExpenseCategory.objects.get_or_create(name=category_with_icon)")
    print()
    print("Пример русских категорий:")
    for name, icon in DEFAULT_CATEGORIES[:3]:
        print(f"  Сохраняется как: '{icon} {name}'")
    print()
    print("Пример английских категорий:")
    for name, icon in ENGLISH_CATEGORIES[:3]:
        print(f"  Сохраняется как: '{icon} {name}'")
    
    # 5. Выводы и рекомендации
    print("\n" + "=" * 60)
    print("ВЫВОДЫ И ПРИЧИНЫ СМЕШАННЫХ ЯЗЫКОВ:")
    print("=" * 60)
    print()
    
    print("🔍 ОСНОВНЫЕ ПРОБЛЕМЫ:")
    print("1. Несоответствие между DEFAULT_CATEGORIES и ENGLISH_CATEGORIES")
    print("2. Не все переводы в language.py соответствуют реальным категориям")
    print("3. При смене языка пользователя переводятся только стандартные категории")
    print("4. Пользователи могут создавать свои категории на любом языке")
    print()
    
    print("💡 СЦЕНАРИИ ПОЯВЛЕНИЯ СМЕШАННЫХ ЯЗЫКОВ:")
    print("1. Пользователь регистрируется на русском языке -> создаются русские категории")
    print("2. Пользователь меняет язык на английский -> переводятся только стандартные")
    print("3. Пользователь добавляет новые категории -> они создаются на текущем языке")
    print("4. AI/парсер предлагает категории на разных языках")
    print()
    
    print("🚨 ПРОБЛЕМНЫЕ МЕСТА В КОДЕ:")
    print("1. get_or_create_category() - использует маппинг категорий")
    print("2. AI категоризация - может предлагать названия на разных языках")
    print("3. Функция translate_category_name() - не всегда работает корректно")
    print("4. update_default_categories_language() - переводит не все категории")

if __name__ == "__main__":
    analyze_category_system()