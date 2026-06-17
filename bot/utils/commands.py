"""
Установка команд бота
"""
import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Устанавливаем команды бота - все основные функции"""
    commands = [
        BotCommand(command="expenses", description="📊 Расходы"),
        BotCommand(command="categories", description="📁 Категории"),
        BotCommand(command="tools", description="🛠️ Инструменты"),
        BotCommand(command="subscription", description="⭐ Subscription"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="start", description="📖 Информация"),
    ]

    try:
        await bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeDefault(),
            request_timeout=15,
        )
    except Exception:
        logger.error("Failed to set bot commands", exc_info=True)


async def update_user_commands(bot: Bot, user_id: int):
    """Обновляем команды для конкретного пользователя с учетом языка.

    Кешбэк и повторяющиеся платежи доступны через меню «Инструменты» (/tools),
    поэтому отдельных команд /cashback и /recurring в списке больше нет.
    """
    # Получаем язык пользователя
    from bot.utils import get_user_language
    from bot.utils import get_text

    lang = await get_user_language(user_id)

    # Формируем команды (эмодзи для tools уже содержится в ключе tools_menu)
    commands = [
        BotCommand(command="expenses", description=f"📊 {get_text('expenses_today', lang)}"),
        BotCommand(command="categories", description=f"📁 {get_text('categories_menu', lang)}"),
        BotCommand(command="tools", description=get_text('tools_menu', lang)),
        BotCommand(command="subscription", description=get_text('subscription_menu', lang)),
        BotCommand(command="settings", description=f"⚙️ {get_text('settings', lang)}"),
        BotCommand(command="start", description=f"📖 {get_text('info', lang)}"),
    ]

    try:
        # Устанавливаем команды для конкретного пользователя
        scope = BotCommandScopeChat(chat_id=user_id)
        await bot.set_my_commands(commands, scope=scope, request_timeout=15)
    except Exception:
        logger.error(
            "Failed to set user commands for %s",
            log_safe_id(user_id, "user"),
            exc_info=True,
        )
