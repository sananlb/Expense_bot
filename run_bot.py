#!/usr/bin/env python
"""
Запуск Telegram бота
Автоматически проверяет и запускает фоновые сервисы (Redis, Celery) если они не запущены
Поддерживает Windows, Linux и macOS
"""
import os
import sys
import django
import logging
import platform
import io
import multiprocessing as mp
import subprocess
import time

# Настройка кодировки для Windows
if platform.system() == 'Windows':
    # Используем UTF-8 с обработкой ошибок для корректного отображения эмодзи и Unicode
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    # Для Windows используем spawn для multiprocessing (для Google AI)
    mp.set_start_method('spawn', force=True)

# Добавляем текущую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Логирование настраивается в expense_bot/settings.py через Django LOGGING
# Не используем basicConfig - Django уже настроил логирование
logger = logging.getLogger(__name__)

# Глобальная переменная для процесса фоновых сервисов
background_services_process = None


def check_redis():
    """Проверяет доступность Redis"""
    try:
        result = subprocess.run(
            ['redis-cli', 'ping'],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0 and 'PONG' in result.stdout
    except Exception:
        return False


def check_celery_running():
    """Проверяет работают ли процессы Celery"""
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'celery' in ' '.join(cmdline).lower() and 'expense_bot' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # Если psutil не установлен, просто пропускаем проверку
        pass
    return False


def start_background_services():
    """Запускает фоновые сервисы (Redis + Celery) через start_local_dev.py"""
    global background_services_process

    logger.info("🚀 Запуск фоновых сервисов (Redis + Celery)...")

    try:
        # Запускаем start_local_dev.py в фоновом режиме
        if platform.system() == 'Windows':
            # На Windows запускаем в новом окне
            background_services_process = subprocess.Popen(
                [sys.executable, 'start_local_dev.py'],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # На Linux/macOS запускаем в фоне
            background_services_process = subprocess.Popen(
                [sys.executable, 'start_local_dev.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        # Ждем пока сервисы запустятся
        logger.info("⏳ Ожидание запуска сервисов...")
        for _ in range(15):
            time.sleep(1)
            if check_redis():
                logger.info("✅ Фоновые сервисы запущены успешно!")
                return True

        logger.error("❌ Не удалось дождаться запуска сервисов")
        return False

    except Exception as e:
        logger.error(f"❌ Ошибка запуска фоновых сервисов: {e}")
        return False


def cleanup_background_services():
    """Останавливает фоновые сервисы при выходе"""
    global background_services_process

    if background_services_process:
        try:
            logger.info("🛑 Остановка фоновых сервисов...")
            background_services_process.terminate()
            background_services_process.wait(timeout=5)
            logger.info("✅ Фоновые сервисы остановлены")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось корректно остановить фоновые сервисы: {e}")
            try:
                background_services_process.kill()
            except:
                pass


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

    # Проверяем фоновые сервисы
    redis_running = check_redis()
    celery_running = check_celery_running()

    if not redis_running or not celery_running:
        logger.info("⚠️ Фоновые сервисы не запущены")
        logger.info(f"   Redis: {'✅' if redis_running else '❌'}")
        logger.info(f"   Celery: {'✅' if celery_running else '❌'}")

        # Автоматически запускаем сервисы
        if not start_background_services():
            logger.error("❌ Не удалось запустить фоновые сервисы!")
            logger.error("   Попробуйте запустить вручную: python start_local_dev.py")
            return
    else:
        logger.info("✅ Фоновые сервисы уже запущены")
        logger.info(f"   Redis: ✅")
        logger.info(f"   Celery: ✅")

    # Очищаем кэш AI сервисов при старте
    try:
        from bot.services.ai_selector import AISelector
        AISelector.clear_cache()
        logger.info("AI service cache cleared on startup")
    except Exception as e:
        logger.warning(f"Could not clear AI cache: {e}")

    # Очищаем все FSM состояния при старте (для исправления зависших состояний)
    try:
        import redis
        from typing import cast

        # Подключаемся к Redis СИНХРОННО
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url, decode_responses=True)

        # Проверяем подключение
        r.ping()
        logger.info("✅ Redis connection OK")

        # Ищем все ключи FSM состояний (обычно они имеют паттерн fsm:*)
        # Cast для IDE - синхронный Redis.keys() возвращает list, не awaitable
        fsm_keys = cast(list, r.keys("fsm:*"))

        if fsm_keys:
            # Удаляем все найденные ключи
            deleted = r.delete(*fsm_keys)
            logger.info(f"Cleared {deleted} FSM states from Redis")
        else:
            logger.info("No FSM states found in Redis")

    except Exception as e:
        logger.warning(f"Could not connect to Redis or clear FSM states: {e}")

    logger.info("=== Запуск ExpenseBot (новая версия) ===")

    # Проверяем настройки
    if not os.getenv('BOT_TOKEN'):
        logger.error("ОШИБКА: Не указан BOT_TOKEN в переменных окружения!")
        logger.error("Создайте файл .env и добавьте BOT_TOKEN=ваш_токен")
        cleanup_background_services()
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
        cleanup_background_services()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nЗавершение работы")
        cleanup_background_services()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        cleanup_background_services()
        sys.exit(1)
