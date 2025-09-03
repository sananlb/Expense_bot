со#!/usr/bin/env python
"""
Скрипт для получения ID канала или группы
Добавьте бота в канал/группу и он покажет ID
"""

import os
import asyncio
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Используем токен мониторинг-бота
BOT_TOKEN = os.getenv('MONITORING_BOT_TOKEN')

if not BOT_TOKEN:
    print("ОШИБКА: MONITORING_BOT_TOKEN не найден в .env файле!")
    exit(1)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def show_chat_id(message: types.Message):
    """Показывает ID любого чата"""
    chat_id = message.chat.id
    chat_type = message.chat.type
    chat_title = message.chat.title or "Личные сообщения"
    
    response = (
        f"📍 <b>Информация о чате:</b>\n\n"
        f"<b>ID чата:</b> <code>{chat_id}</code>\n"
        f"<b>Тип:</b> {chat_type}\n"
        f"<b>Название:</b> {chat_title}\n\n"
    )
    
    if chat_type in ['group', 'supergroup']:
        response += (
            f"✅ Это группа. Добавьте в .env:\n"
            f"<code>ADMIN_TELEGRAM_ID={chat_id}</code>"
        )
    elif chat_type == 'channel':
        response += (
            f"✅ Это канал. Добавьте в .env:\n"
            f"<code>ADMIN_TELEGRAM_ID={chat_id}</code>"
        )
    else:
        response += (
            f"✅ Это личный чат. Добавьте в .env:\n"
            f"<code>ADMIN_TELEGRAM_ID={chat_id}</code>"
        )
    
    await message.answer(response, parse_mode="HTML")
    
    # Выводим в консоль
    print("=" * 50)
    print(f"Получен ID чата: {chat_id}")
    print(f"Тип: {chat_type}")
    print(f"Название: {chat_title}")
    print("=" * 50)
    print(f"\nДобавьте в .env файл:")
    print(f"ADMIN_TELEGRAM_ID={chat_id}")
    print("=" * 50)

# Обработчик для добавления бота в группу/канал
@dp.my_chat_member()
async def on_chat_member_update(update: types.ChatMemberUpdated):
    """Срабатывает при добавлении бота в чат"""
    chat_id = update.chat.id
    chat_type = update.chat.type
    chat_title = update.chat.title or "Без названия"
    
    print("=" * 50)
    print(f"Бот добавлен в {chat_type}!")
    print(f"ID: {chat_id}")
    print(f"Название: {chat_title}")
    print("=" * 50)
    print(f"\nДобавьте в .env файл:")
    print(f"ADMIN_TELEGRAM_ID={chat_id}")
    print("=" * 50)
    
    # Пытаемся отправить сообщение в чат
    try:
        await bot.send_message(
            chat_id,
            f"✅ Бот успешно добавлен!\n\n"
            f"ID этого чата: <code>{chat_id}</code>\n\n"
            f"Добавьте в .env:\n"
            f"<code>ADMIN_TELEGRAM_ID={chat_id}</code>",
            parse_mode="HTML"
        )
    except:
        pass  # Может не быть прав на отправку

async def main():
    """Главная функция"""
    print("=" * 50)
    print("БОТ ДЛЯ ПОЛУЧЕНИЯ ID КАНАЛА/ГРУППЫ")
    print("=" * 50)
    print("\nИнструкция:")
    print("1. Создайте канал или группу в Telegram")
    print("2. Добавьте этого бота в канал/группу как администратора")
    print("3. Отправьте любое сообщение в канал/группу")
    print("4. Бот покажет ID")
    print("\nДля остановки нажмите Ctrl+C")
    print("=" * 50)
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nБот остановлен.")