#!/usr/bin/env python
"""
Скрипт для получения вашего Telegram ID
Отправьте боту любое сообщение и узнайте свой ID
"""

import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Берем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    print("ОШИБКА: Не найден токен бота в .env файле!")
    print("Добавьте BOT_TOKEN или TELEGRAM_BOT_TOKEN в .env")
    exit(1)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    full_name = message.from_user.full_name
    
    response = (
        f"🔍 <b>Ваша информация:</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{username}\n"
        f"<b>Имя:</b> {full_name}\n\n"
        f"📝 <b>Что делать дальше:</b>\n"
        f"1. Скопируйте ваш ID: <code>{user_id}</code>\n"
        f"2. Добавьте в файл .env:\n"
        f"   <code>ADMIN_TELEGRAM_ID={user_id}</code>\n\n"
        f"После этого вы будете получать:\n"
        f"• Ежедневные отчеты о работе бота\n"
        f"• Уведомления о новых пользователях\n"
        f"• Алерты об ошибках\n"
        f"• Статистику использования"
    )
    
    await message.answer(response, parse_mode="HTML")
    
    # Выводим в консоль
    print("=" * 50)
    print(f"Получен ID пользователя: {user_id}")
    print(f"Username: @{username}")
    print(f"Имя: {full_name}")
    print("=" * 50)
    print(f"\nДобавьте в .env файл:")
    print(f"ADMIN_TELEGRAM_ID={user_id}")
    print("=" * 50)

@dp.message()
async def echo_id(message: types.Message):
    """Обработчик любых сообщений"""
    user_id = message.from_user.id
    
    await message.answer(
        f"Ваш Telegram ID: <code>{user_id}</code>\n"
        f"Добавьте в .env: <code>ADMIN_TELEGRAM_ID={user_id}</code>",
        parse_mode="HTML"
    )
    
    print(f"ID пользователя: {user_id}")

async def main():
    """Главная функция"""
    print("=" * 50)
    print("БОТ ДЛЯ ПОЛУЧЕНИЯ TELEGRAM ID")
    print("=" * 50)
    print("\n1. Откройте Telegram")
    print("2. Найдите вашего бота")
    print("3. Отправьте /start или любое сообщение")
    print("4. Бот покажет ваш ID")
    print("\nДля остановки нажмите Ctrl+C")
    print("=" * 50)
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nБот остановлен.")