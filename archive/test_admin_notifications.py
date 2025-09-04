#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестирование системы уведомлений администратора
"""
import os
import sys
import django
import asyncio
from datetime import datetime
import io

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.admin_notifier import (
    send_admin_alert,
    notify_critical_error,
    notify_bot_started,
    notify_bot_stopped
)


async def test_notifications():
    """Тестирование различных типов уведомлений"""
    
    print("🔧 Тестирование системы уведомлений администратора...")
    print("-" * 50)
    
    # 1. Тест простого уведомления
    print("\n1. Отправка простого уведомления...")
    from bot.services.admin_notifier import escape_markdown_v2
    result = await send_admin_alert(
        "✅ *\\[Coins\\] Тестовое уведомление*\n\n"
        f"Это тестовое сообщение от системы уведомлений\\.\n"
        f"Время: {escape_markdown_v2(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )
    if result:
        print("   ✅ Успешно отправлено")
    else:
        print("   ❌ Ошибка отправки")
    
    await asyncio.sleep(1)
    
    # 2. Тест уведомления о критической ошибке
    print("\n2. Уведомление о критической ошибке...")
    await notify_critical_error(
        error_type="TEST_ERROR",
        details="Это тестовая ошибка для проверки системы уведомлений",
        user_id=987654321
    )
    print("   ✅ Отправлено")
    
    await asyncio.sleep(1)
    
    # 3. Тест уведомления о запуске бота
    print("\n3. Уведомление о запуске бота...")
    await notify_bot_started()
    print("   ✅ Отправлено")
    
    await asyncio.sleep(1)
    
    # 4. Тест уведомления об остановке бота
    print("\n4. Уведомление об остановке бота...")
    await notify_bot_stopped()
    print("   ✅ Отправлено")
    
    print("\n" + "-" * 50)
    print("✅ Все тесты завершены!")
    print("\nПроверьте Telegram бота для администратора на наличие сообщений.")
    print(f"ID администратора: {os.getenv('ADMIN_TELEGRAM_ID')}")


async def test_daily_report():
    """Тестирование ежедневного отчета"""
    from bot.services.admin_notifier import send_daily_report
    
    print("\n📊 Генерация тестового ежедневного отчета...")
    result = await send_daily_report()
    
    if result:
        print("✅ Ежедневный отчет успешно отправлен")
    else:
        print("❌ Ошибка отправки ежедневного отчета")


async def main():
    """Главная функция"""
    print("=" * 60)
    print("   ТЕСТИРОВАНИЕ СИСТЕМЫ УВЕДОМЛЕНИЙ АДМИНИСТРАТОРА")
    print("=" * 60)
    
    # Проверяем настройки
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    monitoring_token = os.getenv('MONITORING_BOT_TOKEN')
    
    if not admin_id:
        print("❌ ADMIN_TELEGRAM_ID не настроен в .env файле")
        return
    
    if not monitoring_token:
        print("⚠️  MONITORING_BOT_TOKEN не настроен, используется основной токен бота")
    
    print(f"\nНастройки:")
    print(f"   • Admin ID: {admin_id}")
    print(f"   • Monitoring Bot: {'Настроен' if monitoring_token else 'Используется основной бот'}")
    
    # Запускаем тесты
    await test_notifications()
    
    # Автоматически отправляем ежедневный отчет
    print("\n" + "=" * 60)
    print("\nОтправка тестового ежедневного отчета...")
    await test_daily_report()
    
    print("\n✨ Тестирование завершено!")


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())