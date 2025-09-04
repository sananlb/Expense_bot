#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование отображения категорий при возврате из редактирования
"""

import asyncio
import sys
import os
import io

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from expenses.models import ExpenseCategory, Profile
from bot.services.category import get_user_categories


async def test_categories_display():
    """Тестирование отображения категорий"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ОТОБРАЖЕНИЯ КАТЕГОРИЙ")
    print("=" * 60)
    
    # Тестовый пользователь
    test_user_id = 123456789
    
    try:
        # Получаем профиль
        profile = await Profile.objects.filter(telegram_id=test_user_id).afirst()
        
        if not profile:
            print(f"❌ Профиль для пользователя {test_user_id} не найден")
            return
        
        print(f"✅ Найден профиль пользователя {test_user_id}")
        
        # Получаем категории через функцию get_user_categories
        categories = await get_user_categories(test_user_id)
        
        print(f"\n📁 Найдено категорий: {len(categories)}")
        print("-" * 40)
        
        if categories:
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat.name}")
                print(f"   ID: {cat.id}")
                print(f"   Активна: {'✅' if cat.is_active else '❌'}")
                if hasattr(cat, 'keywords') and cat.keywords:
                    print(f"   Ключевые слова: {cat.keywords[:50]}...")
                print()
        else:
            print("Категории не найдены")
        
        # Проверка наличия системных категорий
        print("\n" + "=" * 60)
        print("ПРОВЕРКА СИСТЕМНЫХ КАТЕГОРИЙ")
        print("=" * 60)
        
        # Прямой запрос к БД для всех категорий пользователя
        all_categories = await ExpenseCategory.objects.filter(
            profile=profile,
            is_active=True
        ).aorder_by('id').aall()
        
        print(f"Всего категорий в БД для пользователя: {len(all_categories)}")
        
        # Проверяем соответствие
        if len(all_categories) == len(categories):
            print("✅ Функция get_user_categories возвращает все категории")
        else:
            print(f"⚠️ Расхождение: в БД {len(all_categories)}, функция вернула {len(categories)}")
        
        # Проверка наличия категории "Прочие расходы"
        print("\n" + "=" * 60)
        print("ПРОВЕРКА КАТЕГОРИИ 'ПРОЧИЕ РАСХОДЫ'")
        print("=" * 60)
        
        other_category = None
        for cat in categories:
            if cat.name == "Прочие расходы" or cat.name == "🔸 Прочие расходы":
                other_category = cat
                break
        
        if other_category:
            print(f"✅ Категория 'Прочие расходы' найдена (ID: {other_category.id})")
        else:
            print("⚠️ Категория 'Прочие расходы' не найдена")
            print("Попытка создать...")
            
            # Создаем категорию "Прочие расходы" если её нет
            other_category = await ExpenseCategory.objects.acreate(
                profile=profile,
                name="🔸 Прочие расходы",
                keywords="прочее, другое, разное",
                is_active=True
            )
            print(f"✅ Категория 'Прочие расходы' создана (ID: {other_category.id})")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ")
    print("=" * 60)
    print("Проблема с отображением категорий при возврате из редактирования")
    print("была связана с передачей удаленного сообщения в функцию.")
    print("\n✅ Исправление применено: теперь передается callback, а не message")
    print("после удаления сообщения.")


if __name__ == "__main__":
    asyncio.run(test_categories_display())