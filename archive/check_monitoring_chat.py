#!/usr/bin/env python
"""
Скрипт для проверки, куда отправляются уведомления от мониторинг-бота
"""

import os
import asyncio
from aiogram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def check_monitoring():
    """Проверка настроек мониторинга"""
    
    monitoring_token = os.getenv('MONITORING_BOT_TOKEN')
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    
    print("=" * 60)
    print("ПРОВЕРКА НАСТРОЕК МОНИТОРИНГА")
    print("=" * 60)
    
    print(f"\nMONITORING_BOT_TOKEN: {'[OK] Установлен' if monitoring_token else '[X] НЕ установлен'}")
    print(f"ADMIN_TELEGRAM_ID: {admin_id if admin_id else '[X] НЕ установлен'}")
    
    if not monitoring_token:
        print("\n[ERROR] MONITORING_BOT_TOKEN не установлен!")
        return
    
    if not admin_id:
        print("\n[ERROR] ADMIN_TELEGRAM_ID не установлен!")
        return
    
    # Создаем бота
    bot = Bot(token=monitoring_token)
    
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"\n[BOT INFO]")
        print(f"  Username: @{bot_info.username}")
        print(f"  Name: {bot_info.first_name}")
        print(f"  Bot ID: {bot_info.id}")
        
        # Пытаемся отправить тестовое сообщение
        print(f"\n[TEST] Отправка сообщения на ID: {admin_id}")
        
        try:
            # Отправляем тестовое сообщение
            msg = await bot.send_message(
                chat_id=int(admin_id),
                text="🔍 Тест системы мониторинга expense_bot\n\n"
                     f"Если вы видите это сообщение, значит:\n"
                     f"✅ MONITORING_BOT_TOKEN работает\n"
                     f"✅ ADMIN_TELEGRAM_ID={admin_id} настроен правильно\n\n"
                     f"Уведомления будут приходить сюда."
            )
            
            print(f"  [OK] Сообщение отправлено успешно!")
            print(f"  Chat ID: {msg.chat.id}")
            print(f"  Chat Type: {msg.chat.type}")
            
            if msg.chat.type == "private":
                print(f"  Это личный чат с пользователем")
                if msg.chat.username:
                    print(f"  Username: @{msg.chat.username}")
            elif msg.chat.type in ["group", "supergroup"]:
                print(f"  Это групповой чат: {msg.chat.title}")
            elif msg.chat.type == "channel":
                print(f"  Это канал: {msg.chat.title}")
                
        except Exception as e:
            print(f"  [ERROR] Не удалось отправить сообщение: {e}")
            print(f"\n  Возможные причины:")
            print(f"  1. Неправильный ADMIN_TELEGRAM_ID")
            print(f"  2. Бот не может писать по этому ID")
            print(f"  3. Вы не начали диалог с ботом (напишите /start боту)")
            
    except Exception as e:
        print(f"\n[ERROR] Ошибка при работе с ботом: {e}")
    finally:
        await bot.session.close()
    
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    print("\n1. Если сообщение не пришло:")
    print("   - Найдите в Telegram вашего мониторинг-бота")
    print("   - Напишите ему /start")
    print("   - Запустите этот скрипт снова")
    print("\n2. Если хотите получать в другое место:")
    print("   - Создайте канал/группу")
    print("   - Добавьте туда мониторинг-бота")
    print("   - Узнайте ID канала/группы")
    print("   - Измените ADMIN_TELEGRAM_ID на ID канала/группы")

if __name__ == "__main__":
    asyncio.run(check_monitoring())