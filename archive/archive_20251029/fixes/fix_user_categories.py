#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для восстановления недостающих категорий пользователя
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

from expenses.models import Profile, ExpenseCategory

# Стандартные категории для русского языка
DEFAULT_CATEGORIES_RU = [
    "🛒 Супермаркеты",
    "🫑 Другие продукты",
    "🍽️ Рестораны и кафе",
    "⛽ АЗС",
    "🚕 Такси",
    "🚌 Общественный транспорт",
    "🚗 Автомобиль",
    "🏠 Жилье",
    "💊 Аптеки",
    "🏥 Медицина",
    "🏃 Спорт",
    "🏀 Спортивные товары",
    "👔 Одежда и обувь",
    "🌹 Цветы",
    "🎭 Развлечения",
    "📚 Образование",
    "🎁 Подарки",
    "✈️ Путешествия",
    "📱 Связь и интернет",
    "💰 Прочие расходы",
]

def fix_user_categories(telegram_id):
    """Восстановление недостающих категорий пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"[OK] Профиль найден для пользователя {telegram_id}")
        print(f"   ID профиля: {profile.id}")
        
        existing_categories = profile.categories.all()
        print(f"\nТекущие категории ({existing_categories.count()}):")
        existing_names = set()
        for cat in existing_categories:
            # Убираем эмодзи для вывода в консоль Windows
            cat_name_clean = ''.join(c for c in cat.name if ord(c) < 128 or c.isalpha())
            print(f"   - {cat_name_clean} (полное: см. базу)")
            existing_names.add(cat.name)
        
        # Создаем недостающие категории
        created_count = 0
        print("\nДобавление недостающих категорий:")
        for cat_name in DEFAULT_CATEGORIES_RU:
            if cat_name not in existing_names:
                category = ExpenseCategory.objects.create(
                    profile=profile,
                    name=cat_name
                )
                cat_name_clean = ''.join(c for c in cat_name if ord(c) < 128 or c.isalpha())
                print(f"   [+] Создана категория: {cat_name_clean}")
                created_count += 1
        
        if created_count > 0:
            print(f"\n[OK] Создано {created_count} категорий")
        else:
            print(f"\n[INFO] Все категории уже существуют")
        
        # Проверяем результат
        final_categories = profile.categories.all().order_by('name')
        print(f"\nВсего категорий теперь: {final_categories.count()}")
        
        # Проверяем наличие категории "Подарки"
        if final_categories.filter(name__icontains='подарки').exists():
            print("[OK] Категория 'Подарки' успешно добавлена")
        else:
            print("[WARNING] Категория 'Подарки' не найдена")
            
    except Profile.DoesNotExist:
        print(f"[ERROR] Профиль не найден для пользователя {telegram_id}")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # ID пользователя Alexey Nalbantov
    user_id = 881292737
    
    print(f"Восстановление категорий для пользователя {user_id}\n")
    print("=" * 50)
    
    fix_user_categories(user_id)