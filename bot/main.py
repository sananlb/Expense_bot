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
    recurring_router,
    settings_router,
    reports_router,
    info_router,
    chat_router,
    subscription_router,
    referral_router,
    top5_router,
    household_router,
    blogger_stats_router,
    # pdf_report_router  # Временно отключено
)
from .middlewares import (
    DatabaseMiddleware,
    LocalizationMiddleware,
    MenuCleanupMiddleware,
    RateLimitMiddleware,
    SecurityCheckMiddleware,
    LoggingMiddleware,
    PrivacyCheckMiddleware
)
from .middlewares.fsm_cleanup import FSMCleanupMiddleware
from .middlewares.state_reset import StateResetMiddleware
from .middleware import ActivityTrackerMiddleware, RateLimitMiddleware as AdminRateLimitMiddleware
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

    # Предзагрузка модулей для устранения "холодного старта" Celery задач
    # Это загружает модули expense.py и income.py сразу при старте бота,
    # а значит импорты Celery задач в них выполнятся сразу (не при первом запросе)
    try:
        from bot.services import expense, income
        logger.info("Preloaded expense and income modules with Celery tasks")

        # Прогреваем @sync_to_async функции для устранения холодного старта
        # ВАЖНО: Thread pool инициализируется при первом ПОЛНОМ выполнении запроса к БД
        # Вызываем функцию которая ГАРАНТИРОВАННО выполнит запрос
        import time
        from asgiref.sync import sync_to_async
        from bot.utils.db_utils import get_or_create_user_profile_sync

        warmup_start = time.time()
        try:
            # Вызываем СИНХРОННУЮ функцию через sync_to_async - это гарантирует полную инициализацию
            # Создаем временный профиль, который выполнит реальный запрос к БД
            warmup_profile = await sync_to_async(get_or_create_user_profile_sync)(999999999)
            warmup_duration = time.time() - warmup_start
            logger.info(f"Warmed up @sync_to_async thread pool in {warmup_duration:.2f}s")
        except Exception as e:
            warmup_duration = time.time() - warmup_start
            logger.warning(f"Warmup completed in {warmup_duration:.2f}s with error: {e}")

    except Exception as e:
        logger.warning(f"Could not preload service modules: {e}")

    # Запускаем задачу уведомлений о подписках
    from bot.tasks.subscription_notifications import run_notification_task
    asyncio.create_task(run_notification_task(bot))

    # Отправляем уведомление админу о запуске бота - отключено
    # from bot.services.admin_notifier import notify_bot_started
    # asyncio.create_task(notify_bot_started())

    logger.info("Бот запущен и готов к работе")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    # Отправляем уведомление админу об остановке бота - отключено
    # from bot.services.admin_notifier import notify_bot_stopped
    # await notify_bot_stopped()
    
    # Закрываем AI сервисы если они есть
    try:
        from bot.services.ai_selector import AISelector
        for provider_type, service in AISelector._instances.items():
            if hasattr(service, 'close'):
                service.close()
                logger.info(f"Closed {provider_type} AI service")
    except Exception as e:
        logger.warning(f"Error closing AI services: {e}")
    
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
    
    # Подключение middlewares (порядок важен!)
    # 1. Activity Tracker - отслеживает активность и отправляет уведомления админу
    activity_tracker = ActivityTrackerMiddleware()
    dp.message.middleware(activity_tracker)
    dp.callback_query.middleware(activity_tracker)
    
    # 2. Admin Rate Limiter - более строгий rate limiter с уведомлениями
    admin_rate_limiter = AdminRateLimitMiddleware()
    dp.message.middleware(admin_rate_limiter)
    dp.callback_query.middleware(admin_rate_limiter)
    
    # 3. Logging - логирует все запросы
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # 4. AntiSpam - защита от массовых регистраций ботов
    from bot.middlewares import AntiSpamMiddleware
    dp.message.middleware(AntiSpamMiddleware())

    # 5. Security - проверяет контент на безопасность
    dp.message.middleware(SecurityCheckMiddleware())
    dp.callback_query.middleware(SecurityCheckMiddleware())

    # 6. Rate Limiting - ограничивает частоту запросов
    from bot.middleware.rate_limit import CommandRateLimitMiddleware
    dp.message.middleware(CommandRateLimitMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # 7. Database - подключает БД
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # 7.5. Privacy Check - КРИТИЧЕСКИ ВАЖНО! Проверяет принятие политики (GDPR compliance)
    # ДОЛЖЕН быть ПОСЛЕ DatabaseMiddleware (чтобы профиль был создан/получен)
    # и ДО всех остальных (блокирует использование без принятия политики)
    dp.message.middleware(PrivacyCheckMiddleware())
    dp.callback_query.middleware(PrivacyCheckMiddleware())

    # 8. Localization - устанавливает язык
    dp.message.middleware(LocalizationMiddleware())
    dp.callback_query.middleware(LocalizationMiddleware())

    # 8.5. FSM Cleanup - очищает PII из старых FSM states
    dp.message.middleware(FSMCleanupMiddleware())
    dp.callback_query.middleware(FSMCleanupMiddleware())

    # 9. Menu Cleanup и State Reset
    dp.message.middleware(MenuCleanupMiddleware())
    dp.message.middleware(StateResetMiddleware())
    
    # Подключение роутеров (порядок важен для приоритета обработки)
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(category_router)  # Перемещаем выше expense_router
    dp.include_router(recurring_router)
    dp.include_router(cashback_router)
    dp.include_router(subscription_router)  # Роутер подписок - ДОЛЖЕН БЫТЬ ДО expense_router для промокодов!
    dp.include_router(referral_router)     # Роутер реферальной системы
    dp.include_router(household_router)     # Роутер семейного бюджета (FSM состояния) - ДОЛЖЕН БЫТЬ ДО expense_router!
    dp.include_router(expense_router)  # Команды должны быть выше FSM состояний
    dp.include_router(reports_router)  # Команды должны быть выше FSM состояний
    dp.include_router(top5_router)
    dp.include_router(blogger_stats_router)  # Статистика для блогеров
    dp.include_router(settings_router)
    # dp.include_router(pdf_report_router)   # PDF отчеты - временно отключено из-за проблем с playwright
    dp.include_router(info_router)
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
    webhook_path = "/webhook/"  # Унифицированный путь без токена
    
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(app, path=webhook_path)
    
    setup_application(app, dp, bot=bot)

    # Установка webhook
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        full_webhook_url = f"{webhook_url}{webhook_path}"
        try:
            webhook_info = await bot.set_webhook(
                url=full_webhook_url,
                allowed_updates=["message", "callback_query", "pre_checkout_query"],
                drop_pending_updates=False
            )
            logger.info(f"✅ Webhook установлен успешно: {full_webhook_url}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
            logger.warning("⚠️ Бот продолжит работу, но webhook может не работать")
    else:
        logger.warning("⚠️ WEBHOOK_URL не задан в .env, webhook не будет установлен")

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
