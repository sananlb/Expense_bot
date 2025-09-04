#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование локализации бота
"""

import asyncio
import sys
import os
import io

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from bot.texts import TEXTS, get_text
from expenses.models import Profile


async def test_localization():
    """Тестирование системы локализации"""
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ ЛОКАЛИЗАЦИИ")
    print("=" * 50)
    
    # Проверяем ключи, которые должны быть в обоих языках
    required_keys = [
        'recurring_payments',
        'no_recurring_payments',
        'add_recurring',
        'edit_recurring', 
        'delete_recurring',
        'subscription_menu',
        'no_active_subscription',
        'subscription_benefits',
        'back_to_subscription'
    ]
    
    missing_ru = []
    missing_en = []
    
    for key in required_keys:
        if key not in TEXTS['ru']:
            missing_ru.append(key)
        if key not in TEXTS['en']:
            missing_en.append(key)
    
    if missing_ru:
        print(f"❌ Отсутствуют русские переводы для ключей: {', '.join(missing_ru)}")
    else:
        print("✅ Все необходимые русские переводы присутствуют")
    
    if missing_en:
        print(f"❌ Отсутствуют английские переводы для ключей: {', '.join(missing_en)}")
    else:
        print("✅ Все необходимые английские переводы присутствуют")
    
    print("\n" + "=" * 50)
    print("ПРИМЕРЫ ПЕРЕВОДОВ")
    print("=" * 50)
    
    # Показываем примеры переводов
    test_keys = ['recurring_payments', 'subscription_menu', 'no_active_subscription']
    
    for key in test_keys:
        print(f"\nКлюч: {key}")
        print(f"  RU: {get_text(key, 'ru')[:50]}...")
        print(f"  EN: {get_text(key, 'en')[:50]}...")
    
    print("\n" + "=" * 50)
    print("ТЕСТ ПРОФИЛЯ")
    print("=" * 50)
    
    # Проверяем, что язык сохраняется в профиле
    try:
        test_profile = await Profile.objects.filter(telegram_id=123456789).afirst()
        if test_profile:
            print(f"Тестовый профиль найден")
            print(f"  Telegram ID: {test_profile.telegram_id}")
            print(f"  Язык: {test_profile.language_code or 'не установлен'}")
            
            # Проверяем изменение языка
            old_lang = test_profile.language_code
            test_profile.language_code = 'en'
            await test_profile.asave()
            print(f"  Язык изменен на: en")
            
            # Возвращаем обратно
            test_profile.language_code = old_lang
            await test_profile.asave()
            print(f"  Язык возвращен на: {old_lang}")
        else:
            print("Тестовый профиль не найден (это нормально)")
    except Exception as e:
        print(f"Ошибка при работе с профилем: {e}")
    
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТ")
    print("=" * 50)
    
    if not missing_ru and not missing_en:
        print("✅ Все тесты локализации пройдены успешно!")
    else:
        print("⚠️ Обнаружены проблемы с локализацией")
        

if __name__ == "__main__":
    asyncio.run(test_localization())