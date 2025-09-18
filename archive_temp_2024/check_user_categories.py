#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки категорий пользователя в базе данных
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

def check_user_categories(telegram_id):
    """Проверка категорий пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        print(f"[OK] Профиль найден для пользователя {telegram_id}")
        print(f"   ID профиля: {profile.id}")
        
        categories = profile.categories.all().order_by('name')
        print(f"\nВсего категорий: {categories.count()}")
        
        print("\nСписок категорий:")
        for i, cat in enumerate(categories, 1):
            print(f"   {i}. {cat.name} (ID: {cat.id})")
            # Проверяем на наличие слова "подарки" или "gifts"
            name_lower = cat.name.lower()
            if 'подарки' in name_lower:
                print(f"      [OK] Содержит 'подарки'")
            if 'gifts' in name_lower:
                print(f"      [OK] Содержит 'gifts'")
                
        # Поиск категории подарков
        print("\nПоиск категории 'подарки':")
        gift_cats = categories.filter(name__icontains='подарки')
        if gift_cats.exists():
            for cat in gift_cats:
                print(f"   [OK] Найдена: {cat.name}")
        else:
            print(f"   [ERROR] Не найдена категория с 'подарки'")
            
        gift_cats_en = categories.filter(name__icontains='gifts')
        if gift_cats_en.exists():
            for cat in gift_cats_en:
                print(f"   [WARNING] Найдена английская версия: {cat.name}")
                
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
    
    print(f"Проверка категорий для пользователя {user_id}\n")
    print("=" * 50)
    
    check_user_categories(user_id)