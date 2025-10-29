#!/usr/bin/env python
"""
Проверка настроек для отправки отчетов
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.conf import settings
from bot.services.admin_notifier import send_admin_alert
import asyncio

def check_settings():
    """Проверка настроек"""
    print("=" * 50)
    print("ПРОВЕРКА НАСТРОЕК")
    print("=" * 50)
    
    # Проверяем ADMIN_TELEGRAM_ID
    admin_id = settings.ADMIN_TELEGRAM_ID
    print(f"ADMIN_TELEGRAM_ID: {admin_id}")
    
    if not admin_id:
        print("❌ ADMIN_TELEGRAM_ID не установлен!")
        return False
    
    # Проверяем BOT_TOKEN
    bot_token = settings.BOT_TOKEN
    print(f"BOT_TOKEN: {'✅ Установлен' if bot_token else '❌ НЕ установлен'}")
    
    if not bot_token:
        print("❌ BOT_TOKEN не установлен!")
        return False
    
    # Проверяем MONITORING_BOT_TOKEN
    monitoring_token = getattr(settings, 'MONITORING_BOT_TOKEN', None)
    print(f"MONITORING_BOT_TOKEN: {'✅ Установлен' if monitoring_token else '⚠️ Не установлен (будет использован BOT_TOKEN)'}")
    
    return True

async def test_send_message():
    """Тест отправки простого сообщения"""
    print("\n" + "=" * 50)
    print("ТЕСТ ОТПРАВКИ СООБЩЕНИЯ")
    print("=" * 50)
    
    test_message = "🧪 Тестовое сообщение от ExpenseBot\\!\n\nПроверка связи\\.\n\n✅ Если вы видите это сообщение, значит отправка работает\\!"
    
    print("Отправка тестового сообщения...")
    try:
        result = await send_admin_alert(test_message)
        if result:
            print("✅ Сообщение успешно отправлено!")
        else:
            print("❌ Не удалось отправить сообщение")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("\n🔍 ПРОВЕРКА НАСТРОЕК ДЛЯ ОТПРАВКИ ОТЧЕТОВ\n")
    
    # Проверяем настройки
    if not check_settings():
        print("\n❌ Настройки некорректны! Проверьте файл .env")
        return
    
    # Спрашиваем про тест
    print("\nОтправить тестовое сообщение администратору?")
    choice = input("(y/n): ").strip().lower()
    
    if choice == 'y':
        asyncio.run(test_send_message())
    
    print("\n✅ Проверка завершена!")

if __name__ == "__main__":
    main()