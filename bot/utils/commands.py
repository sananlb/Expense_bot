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
        BotCommand(command="cashback", description="💳 Кешбэк"),
        BotCommand(command="categories", description="📁 Категории"),
        BotCommand(command="recurring", description="🔄 Recurring payments"),
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
    """Обновляем команды для конкретного пользователя с учетом языка, подписки и настроек"""
    # Получаем язык пользователя
    from bot.utils import get_user_language
    from bot.utils import get_text
    from bot.services.subscription import check_subscription
    from bot.services.profile import get_user_settings

    lang = await get_user_language(user_id)

    # Проверяем наличие активной подписки
    has_subscription = await check_subscription(user_id)

    # Получаем настройки пользователя (включен ли кешбек)
    user_settings = await get_user_settings(user_id)
    cashback_enabled = user_settings.cashback_enabled

    # Формируем базовые команды
    commands = [
        BotCommand(command="expenses", description=f"📊 {get_text('expenses_today', lang)}"),
    ]

    # Добавляем команду cashback только если есть активная подписка И кешбек включен
    if has_subscription and cashback_enabled:
        commands.append(BotCommand(command="cashback", description=f"💳 {get_text('cashback_menu', lang)}"))
    
    # Добавляем остальные команды
    commands.extend([
        BotCommand(command="categories", description=f"📁 {get_text('categories_menu', lang)}"),
        BotCommand(command="recurring", description=get_text('recurring_menu', lang)),
        BotCommand(command="subscription", description=get_text('subscription_menu', lang)),
        BotCommand(command="settings", description=f"⚙️ {get_text('settings', lang)}"),
        BotCommand(command="start", description=f"📖 {get_text('info', lang)}"),
    ])
    
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
