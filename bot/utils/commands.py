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
        BotCommand(command="recurring", description="🔄 Ежемесячные платежи"),
        BotCommand(command="subscription", description="⭐ Подписка"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="start", description="📖 Информация"),
    ]
    
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeDefault()
    )


async def update_user_commands(bot: Bot, user_id: int):
    """Обновляем команды для конкретного пользователя с учетом языка"""
    # Получаем язык пользователя
    from bot.utils import get_user_language
    from bot.utils import get_text
    
    lang = await get_user_language(user_id)
    
    # Формируем команды с учетом языка
    commands = [
        BotCommand(command="expenses", description=f"📊 {get_text('expenses_today', lang)}"),
        BotCommand(command="cashback", description=f"💳 {get_text('cashback_menu', lang)}"),
        BotCommand(command="categories", description=f"📁 {get_text('categories_menu', lang)}"),
        BotCommand(command="recurring", description=f"🔄 Регулярные платежи"),
        BotCommand(command="subscription", description="⭐ Подписка"),
        BotCommand(command="settings", description=f"⚙️ {get_text('settings_menu', lang)}"),
        BotCommand(command="start", description=f"📖 {get_text('info', lang)}"),
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