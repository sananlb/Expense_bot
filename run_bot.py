#!/usr/bin/env python
"""
Запуск ExpenseBot на aiogram 3.x
Поддерживает Windows, Linux и macOS
"""
import os
import sys
import django
import logging
import platform
import io
import multiprocessing as mp

# Настройка кодировки для Windows
if platform.system() == 'Windows':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    # Для Windows используем spawn для multiprocessing (для Google AI)
    mp.set_start_method('spawn', force=True)

# Добавляем текущую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def print_header():
    """Печать заголовка"""
    print("=" * 60)
    print("    EXPENSE BOT (aiogram 3.x) - Telegram Bot Launcher")
    print("=" * 60)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print()


def main():
    """Основная функция запуска"""
    print_header()
    
    # Очищаем кэш AI сервисов при старте
    try:
        from bot.services.ai_selector import AISelector
        AISelector.clear_cache()
        logger.info("AI service cache cleared on startup")
    except Exception as e:
        logger.warning(f"Could not clear AI cache: {e}")
    
    # Очищаем все FSM состояния при старте (для исправления зависших состояний)
    try:
        import asyncio
        import redis
        
        async def clear_all_fsm_states():
            """Очистка всех FSM состояний из Redis"""
            try:
                # Подключаемся к Redis используя REDIS_URL (с поддержкой пароля)
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                r = redis.from_url(redis_url, decode_responses=True)

                # Проверяем подключение
                r.ping()
                
                # Ищем все ключи FSM состояний (обычно они имеют паттерн fsm:*)
                fsm_keys = r.keys("fsm:*")
                
                if fsm_keys:
                    # Удаляем все найденные ключи
                    deleted = r.delete(*fsm_keys)
                    logger.info(f"Cleared {deleted} FSM states from Redis")
                else:
                    logger.info("No FSM states found in Redis")
                    
            except Exception as e:
                logger.warning(f"Could not connect to Redis to clear FSM states: {e}")
        
        # Запускаем асинхронную очистку
        asyncio.run(clear_all_fsm_states())
        
    except Exception as e:
        logger.warning(f"Could not clear FSM states: {e}")
    
    logger.info("=== Запуск ExpenseBot (новая версия) ===")
    
    # Проверяем настройки
    if not os.getenv('BOT_TOKEN'):
        logger.error("ОШИБКА: Не указан BOT_TOKEN в переменных окружения!")
        logger.error("Создайте файл .env и добавьте BOT_TOKEN=ваш_токен")
        return
    
    try:
        # Импортируем и запускаем нового бота
        from bot.main import run
        
        logger.info("Бот запускается в режиме: %s", os.getenv("BOT_MODE", "polling"))
        logger.info("Для остановки нажмите Ctrl+C")
        
        # Запускаем бота
        run()
        
    except KeyboardInterrupt:
        logger.info("\nОстановка по Ctrl+C...")
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        logger.error("Убедитесь, что установлены все зависимости: pip install -r requirements.txt")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise
    finally:
        logger.info("Бот остановлен")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nЗавершение работы")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)