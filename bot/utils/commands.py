"""
Установка команд бота
"""
import asyncio
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat


async def set_bot_commands(bot: Bot):
    """Устанавливаем команды бота - все основные функции"""
    commands = [
        BotCommand(command="expenses", description="📊 Расходы"),
        BotCommand(command="cashback", description="💳 Кешбэк"),
        BotCommand(command="categories", description="📁 Категории"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="start", description="ℹ️ Информация"),
    ]
    
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeDefault()
    )


async def update_user_commands(bot: Bot, user_id: int):
    """Обновляем команды для конкретного пользователя"""
    commands = [
        BotCommand(command="expenses", description="📊 Расходы"),
        BotCommand(command="cashback", description="💳 Кешбэк"),
        BotCommand(command="categories", description="📁 Категории"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="start", description="ℹ️ Информация"),
    ]
    
    try:
        # Сначала удаляем все команды для пользователя
        scope = BotCommandScopeChat(chat_id=user_id)
        await bot.delete_my_commands(scope=scope)
        
        # Небольшая задержка для сброса кеша
        await asyncio.sleep(0.5)
        
        # Устанавливаем команды для конкретного пользователя
        await bot.set_my_commands(commands, scope=scope)
    except Exception as e:
        # Логируем ошибку, но не прерываем работу
        pass