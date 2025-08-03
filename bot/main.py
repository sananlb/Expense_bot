"""
ExpenseBot - главный файл бота на aiogram 3.x
Соответствует техническому заданию
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import os
from dotenv import load_dotenv

# Импорт роутеров
from .routers import (
    start_router,
    menu_router,
    expense_router,
    cashback_router,
    category_router,
    settings_router,
    reports_router,
    info_router,
    chat_router
)
from .middlewares import DatabaseMiddleware, LocalizationMiddleware, MenuCleanupMiddleware
from .middlewares.state_reset import StateResetMiddleware
from .utils.commands import set_bot_commands

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    await set_bot_commands(bot)
    logger.info("Бот запущен и готов к работе")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Бот остановлен")


def create_bot() -> Bot:
    """Создание экземпляра бота"""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        sys.exit(1)
    
    return Bot(
        token=token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )


def create_dispatcher() -> Dispatcher:
    """Создание диспетчера с подключением к Redis"""
    redis_url = os.getenv("REDIS_URL")
    
    # Используем Redis если доступен, иначе MemoryStorage
    if redis_url:
        try:
            storage = RedisStorage.from_url(redis_url)
        except Exception as e:
            logger.warning(f"Не удалось подключиться к Redis: {e}. Используется MemoryStorage")
            storage = MemoryStorage()
    else:
        storage = MemoryStorage()
    
    dp = Dispatcher(storage=storage)
    
    # Подключение middlewares
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.message.middleware(LocalizationMiddleware())
    dp.callback_query.middleware(LocalizationMiddleware())
    dp.message.middleware(MenuCleanupMiddleware())  # Добавляем перед StateResetMiddleware
    dp.message.middleware(StateResetMiddleware())
    
    # Подключение роутеров (порядок важен для приоритета обработки)
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(category_router)  # Перемещаем выше expense_router
    dp.include_router(cashback_router)
    dp.include_router(settings_router)
    dp.include_router(reports_router)
    dp.include_router(info_router)
    dp.include_router(expense_router)  # Обработка расходов после специфичных роутеров
    dp.include_router(chat_router)     # Низкий приоритет для обработки чата
    
    return dp


async def main_polling():
    """Запуск бота в режиме polling"""
    bot = create_bot()
    dp = create_dispatcher()
    
    # Регистрация хэндлеров startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Удаление webhook перед polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск polling
    await dp.start_polling(bot)


async def main_webhook():
    """Запуск бота в режиме webhook"""
    bot = create_bot()
    dp = create_dispatcher()
    
    # Регистрация хэндлеров startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Настройка webhook
    app = web.Application()
    webhook_path = f"/webhook/{os.getenv('BOT_TOKEN')}"
    
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(app, path=webhook_path)
    
    setup_application(app, dp, bot=bot)
    
    # Установка webhook
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        await bot.set_webhook(f"{webhook_url}{webhook_path}")
    
    # Запуск веб-сервера
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8000)
    await site.start()
    
    logger.info("Webhook сервер запущен на порту 8000")
    
    # Бесконечный цикл
    await asyncio.Event().wait()


def run():
    """Основная функция запуска"""
    mode = os.getenv("BOT_MODE", "polling").lower()
    
    if mode == "webhook":
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())


if __name__ == "__main__":
    run()