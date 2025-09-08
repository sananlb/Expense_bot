#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для исправления категорий всех пользователей
- Добавляет иконки если их нет
- Заполняет мультиязычные поля
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, IncomeCategory
from django.db import transaction


# Стандартные категории с иконками и переводами
EXPENSE_CATEGORIES = {
    'продукты': {'icon': '🛒', 'en': 'Products'},
    'кафе и рестораны': {'icon': '☕', 'en': 'Cafes and restaurants'},
    'азс': {'icon': '⛽', 'en': 'Gas stations'},
    'транспорт': {'icon': '🚌', 'en': 'Transport'},
    'такси': {'icon': '🚕', 'en': 'Taxi'},
    'автомобиль': {'icon': '🚗', 'en': 'Car'},
    'жилье': {'icon': '🏠', 'en': 'Housing'},
    'жкх': {'icon': '🏠', 'en': 'Utilities'},
    'аптеки': {'icon': '💊', 'en': 'Pharmacies'},
    'медицина': {'icon': '🏥', 'en': 'Medicine'},
    'красота': {'icon': '💅', 'en': 'Beauty'},
    'спорт и фитнес': {'icon': '⚽', 'en': 'Sports and fitness'},
    'одежда и обувь': {'icon': '👕', 'en': 'Clothes and shoes'},
    'развлечения': {'icon': '🎮', 'en': 'Entertainment'},
    'образование': {'icon': '📚', 'en': 'Education'},
    'подарки': {'icon': '🎁', 'en': 'Gifts'},
    'путешествия': {'icon': '✈️', 'en': 'Travel'},
    'родственники': {'icon': '👨‍👩‍👧‍👦', 'en': 'Relatives'},
    'коммунальные услуги и подписки': {'icon': '📱', 'en': 'Utilities and subscriptions'},
    'прочие расходы': {'icon': '💰', 'en': 'Other expenses'},
    'благотворительность': {'icon': '❤️', 'en': 'Charity'},
    'мои проекты': {'icon': '💼', 'en': 'My projects'},
    # Английские версии
    'products': {'icon': '🛒', 'ru': 'Продукты'},
    'cafes and restaurants': {'icon': '☕', 'ru': 'Кафе и рестораны'},
    'gas stations': {'icon': '⛽', 'ru': 'АЗС'},
    'transport': {'icon': '🚌', 'ru': 'Транспорт'},
    'taxi': {'icon': '🚕', 'ru': 'Такси'},
    'car': {'icon': '🚗', 'ru': 'Автомобиль'},
    'housing': {'icon': '🏠', 'ru': 'Жилье'},
    'utilities': {'icon': '🏠', 'ru': 'ЖКХ'},
    'pharmacies': {'icon': '💊', 'ru': 'Аптеки'},
    'medicine': {'icon': '🏥', 'ru': 'Медицина'},
    'beauty': {'icon': '💅', 'ru': 'Красота'},
    'sports and fitness': {'icon': '⚽', 'ru': 'Спорт и фитнес'},
    'clothes and shoes': {'icon': '👕', 'ru': 'Одежда и обувь'},
    'entertainment': {'icon': '🎮', 'ru': 'Развлечения'},
    'education': {'icon': '📚', 'ru': 'Образование'},
    'gifts': {'icon': '🎁', 'ru': 'Подарки'},
    'travel': {'icon': '✈️', 'ru': 'Путешествия'},
    'relatives': {'icon': '👨‍👩‍👧‍👦', 'ru': 'Родственники'},
    'utilities and subscriptions': {'icon': '📱', 'ru': 'Коммунальные услуги и подписки'},
    'other expenses': {'icon': '💰', 'ru': 'Прочие расходы'},
    'charity': {'icon': '❤️', 'ru': 'Благотворительность'},
    'my projects': {'icon': '💼', 'ru': 'Мои проекты'},
}

INCOME_CATEGORIES = {
    'зарплата': {'icon': '💵', 'en': 'Salary'},
    'подработка': {'icon': '💼', 'en': 'Part-time job'},
    'фриланс': {'icon': '💻', 'en': 'Freelance'},
    'инвестиции': {'icon': '📈', 'en': 'Investments'},
    'подарки': {'icon': '🎁', 'en': 'Gifts'},
    'возврат средств': {'icon': '↩️', 'en': 'Refund'},
    'продажа': {'icon': '💸', 'en': 'Sale'},
    'аренда': {'icon': '🏠', 'en': 'Rent'},
    'прочие доходы': {'icon': '💰', 'en': 'Other income'},
    # Английские версии
    'salary': {'icon': '💵', 'ru': 'Зарплата'},
    'part-time job': {'icon': '💼', 'ru': 'Подработка'},
    'freelance': {'icon': '💻', 'ru': 'Фриланс'},
    'investments': {'icon': '📈', 'ru': 'Инвестиции'},
    'gifts': {'icon': '🎁', 'ru': 'Подарки'},
    'refund': {'icon': '↩️', 'ru': 'Возврат средств'},
    'sale': {'icon': '💸', 'ru': 'Продажа'},
    'rent': {'icon': '🏠', 'ru': 'Аренда'},
    'other income': {'icon': '💰', 'ru': 'Прочие доходы'},
}


def extract_emoji(text):
    """Извлекает эмодзи из начала строки"""
    import re
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+'
    match = re.match(emoji_pattern, text)
    return match.group(0) if match else None


def clean_name(text):
    """Очищает название от эмодзи"""
    import re
    # Удаляем эмодзи из начала строки
    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+\s*'
    return re.sub(emoji_pattern, '', text).strip()


def fix_expense_categories():
    """Исправляет категории расходов"""
    print("\n" + "="*70)
    print("ИСПРАВЛЕНИЕ КАТЕГОРИЙ РАСХОДОВ")
    print("="*70)
    
    categories = ExpenseCategory.objects.filter(is_active=True)
    total = categories.count()
    fixed = 0
    
    with transaction.atomic():
        for cat in categories:
            changed = False
            
            # Извлекаем эмодзи из name если есть
            current_emoji = extract_emoji(cat.name)
            clean_cat_name = clean_name(cat.name).lower()
            
            # Если в name есть эмодзи, но нет в icon - переносим
            if current_emoji and not cat.icon:
                cat.icon = current_emoji
                cat.name = clean_name(cat.name)
                changed = True
            
            # Ищем соответствие в стандартных категориях
            if clean_cat_name in EXPENSE_CATEGORIES:
                std_cat = EXPENSE_CATEGORIES[clean_cat_name]
                
                # Добавляем иконку если нет
                if not cat.icon:
                    cat.icon = std_cat['icon']
                    changed = True
                
                # Заполняем мультиязычные поля
                if not cat.name_ru:
                    cat.name_ru = clean_name(cat.name)
                    changed = True
                
                if not cat.name_en and 'en' in std_cat:
                    cat.name_en = std_cat['en']
                    changed = True
                    
            # Если это английская категория
            elif cat.name.lower() in EXPENSE_CATEGORIES:
                std_cat = EXPENSE_CATEGORIES[cat.name.lower()]
                
                if not cat.icon:
                    cat.icon = std_cat['icon']
                    changed = True
                    
                if not cat.name_en:
                    cat.name_en = cat.name
                    changed = True
                    
                if not cat.name_ru and 'ru' in std_cat:
                    cat.name_ru = std_cat['ru']
                    changed = True
            
            # Убираем эмодзи из name если они есть
            if extract_emoji(cat.name):
                cat.name = clean_name(cat.name)
                changed = True
            
            # Если нет icon, ставим по умолчанию
            if not cat.icon:
                cat.icon = '💰'
                changed = True
            
            # Заполняем пустые мультиязычные поля
            if not cat.name_ru and not cat.name_en:
                # Если name похож на русский
                if any(ord(c) > 1000 for c in cat.name):
                    cat.name_ru = cat.name
                else:
                    cat.name_en = cat.name
                changed = True
            
            if changed:
                cat.save()
                fixed += 1
                print(f"✓ Исправлена категория: {cat.name} (Profile: {cat.profile.telegram_id})")
    
    print(f"\nИсправлено категорий расходов: {fixed}/{total}")
    return fixed


def fix_income_categories():
    """Исправляет категории доходов"""
    print("\n" + "="*70)
    print("ИСПРАВЛЕНИЕ КАТЕГОРИЙ ДОХОДОВ")
    print("="*70)
    
    categories = IncomeCategory.objects.filter(is_active=True)
    total = categories.count()
    fixed = 0
    
    with transaction.atomic():
        for cat in categories:
            changed = False
            
            # Извлекаем эмодзи из name если есть
            current_emoji = extract_emoji(cat.name)
            clean_cat_name = clean_name(cat.name).lower()
            
            # Если в name есть эмодзи, но нет в icon - переносим
            if current_emoji and not cat.icon:
                cat.icon = current_emoji
                cat.name = clean_name(cat.name)
                changed = True
            
            # Ищем соответствие в стандартных категориях
            if clean_cat_name in INCOME_CATEGORIES:
                std_cat = INCOME_CATEGORIES[clean_cat_name]
                
                # Добавляем иконку если нет
                if not cat.icon:
                    cat.icon = std_cat['icon']
                    changed = True
                
                # Заполняем мультиязычные поля
                if not cat.name_ru:
                    cat.name_ru = clean_name(cat.name)
                    changed = True
                
                if not cat.name_en and 'en' in std_cat:
                    cat.name_en = std_cat['en']
                    changed = True
                    
            # Если это английская категория
            elif cat.name.lower() in INCOME_CATEGORIES:
                std_cat = INCOME_CATEGORIES[cat.name.lower()]
                
                if not cat.icon:
                    cat.icon = std_cat['icon']
                    changed = True
                    
                if not cat.name_en:
                    cat.name_en = cat.name
                    changed = True
                    
                if not cat.name_ru and 'ru' in std_cat:
                    cat.name_ru = std_cat['ru']
                    changed = True
            
            # Убираем эмодзи из name если они есть
            if extract_emoji(cat.name):
                cat.name = clean_name(cat.name)
                changed = True
            
            # Если нет icon, ставим по умолчанию
            if not cat.icon:
                cat.icon = '💵'
                changed = True
            
            # Заполняем пустые мультиязычные поля
            if not cat.name_ru and not cat.name_en:
                # Если name похож на русский
                if any(ord(c) > 1000 for c in cat.name):
                    cat.name_ru = cat.name
                else:
                    cat.name_en = cat.name
                changed = True
            
            if changed:
                cat.save()
                fixed += 1
                print(f"✓ Исправлена категория: {cat.name} (Profile: {cat.profile.telegram_id})")
    
    print(f"\nИсправлено категорий доходов: {fixed}/{total}")
    return fixed


def main():
    """Главная функция"""
    print("\n" + "="*70)
    print("СКРИПТ ИСПРАВЛЕНИЯ КАТЕГОРИЙ")
    print(f"Время запуска: {datetime.now()}")
    print("="*70)
    
    # Исправляем категории расходов
    expense_fixed = fix_expense_categories()
    
    # Исправляем категории доходов  
    income_fixed = fix_income_categories()
    
    # Итоги
    print("\n" + "="*70)
    print("ИТОГИ")
    print("="*70)
    print(f"Исправлено категорий расходов: {expense_fixed}")
    print(f"Исправлено категорий доходов: {income_fixed}")
    print(f"Всего исправлено: {expense_fixed + income_fixed}")
    print("\n✅ Скрипт выполнен успешно!")


if __name__ == "__main__":
    main()