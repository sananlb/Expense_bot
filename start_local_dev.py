"""
Скрипт для запуска локальной разработки - Redis + Celery Worker + Celery Beat
НЕ запускает сам бот - только инфраструктуру

Использование:
    python start_local_dev.py

После запуска этого скрипта, в другом терминале запусти бота:
    python run_bot.py
"""
import os
import sys
import time
import subprocess
import signal
from pathlib import Path

# Цвета для вывода
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_colored(text, color):
    """Печать цветного текста"""
    print(f"{color}{text}{Colors.END}")

def check_redis():
    """Проверить запущен ли Redis"""
    try:
        result = subprocess.run(
            ['redis-cli', 'ping'],
            capture_output=True,
            text=True,
            timeout=3
        )
        return result.returncode == 0 and 'PONG' in result.stdout
    except Exception:
        return False

def start_redis():
    """Запустить Redis сервер"""
    print_colored("\n🔧 Запуск Redis сервера...", Colors.BLUE)

    if check_redis():
        print_colored("✅ Redis уже запущен!", Colors.GREEN)
        return None

    try:
        # Пытаемся запустить Redis
        process = subprocess.Popen(
            ['redis-server', '--daemonize', 'yes'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Ждем запуска
        time.sleep(2)

        if check_redis():
            print_colored("✅ Redis запущен успешно!", Colors.GREEN)
            return None  # Redis daemon, не нужен процесс
        else:
            print_colored("❌ Не удалось запустить Redis", Colors.RED)
            return None

    except FileNotFoundError:
        print_colored("❌ Redis не установлен! Установите Redis для Windows.", Colors.RED)
        print_colored("   Скачать: https://github.com/microsoftarchive/redis/releases", Colors.YELLOW)
        return None
    except Exception as e:
        print_colored(f"❌ Ошибка запуска Redis: {e}", Colors.RED)
        return None

def start_celery_worker():
    """Запустить Celery Worker"""
    print_colored("\n🔧 Запуск Celery Worker...", Colors.BLUE)

    # Активируем виртуальное окружение и запускаем Celery
    venv_python = Path('venv/Scripts/python.exe')

    if not venv_python.exists():
        print_colored("❌ Виртуальное окружение не найдено!", Colors.RED)
        return None

    try:
        # Важно: используем expense_bot, НЕ config!
        cmd = [
            str(venv_python),
            '-m', 'celery',
            '-A', 'expense_bot',
            'worker',
            '-l', 'INFO',
            '--pool=solo'  # Для Windows
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, 'PYTHONPATH': os.getcwd()}
        )

        time.sleep(3)

        if process.poll() is None:
            print_colored("✅ Celery Worker запущен!", Colors.GREEN)
            return process
        else:
            print_colored("❌ Celery Worker не запустился", Colors.RED)
            return None

    except Exception as e:
        print_colored(f"❌ Ошибка запуска Celery Worker: {e}", Colors.RED)
        return None

def start_celery_beat():
    """Запустить Celery Beat"""
    print_colored("\n🔧 Запуск Celery Beat...", Colors.BLUE)

    venv_python = Path('venv/Scripts/python.exe')

    if not venv_python.exists():
        print_colored("❌ Виртуальное окружение не найдено!", Colors.RED)
        return None

    try:
        cmd = [
            str(venv_python),
            '-m', 'celery',
            '-A', 'expense_bot',
            'beat',
            '-l', 'INFO'
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={**os.environ, 'PYTHONPATH': os.getcwd()}
        )

        time.sleep(3)

        if process.poll() is None:
            print_colored("✅ Celery Beat запущен!", Colors.GREEN)
            return process
        else:
            print_colored("❌ Celery Beat не запустился", Colors.RED)
            return None

    except Exception as e:
        print_colored(f"❌ Ошибка запуска Celery Beat: {e}", Colors.RED)
        return None

def main():
    """Главная функция"""
    print_colored("="*60, Colors.BLUE)
    print_colored("  EXPENSE BOT - Локальная разработка", Colors.BLUE)
    print_colored("  Запуск Redis + Celery Worker + Celery Beat", Colors.BLUE)
    print_colored("="*60, Colors.BLUE)

    processes = []

    try:
        # 1. Запускаем Redis
        redis_proc = start_redis()

        # 2. Запускаем Celery Worker
        worker_proc = start_celery_worker()
        if worker_proc:
            processes.append(('Celery Worker', worker_proc))

        # 3. Запускаем Celery Beat
        beat_proc = start_celery_beat()
        if beat_proc:
            processes.append(('Celery Beat', beat_proc))

        if not processes:
            print_colored("\n❌ Не удалось запустить сервисы!", Colors.RED)
            return

        print_colored("\n" + "="*60, Colors.GREEN)
        print_colored("✅ Все сервисы запущены!", Colors.GREEN)
        print_colored("="*60, Colors.GREEN)
        print_colored("\n📋 Запущенные сервисы:", Colors.BLUE)
        print_colored("   - Redis Server (daemon)", Colors.GREEN)
        for name, _ in processes:
            print_colored(f"   - {name}", Colors.GREEN)

        print_colored("\n🤖 Теперь запустите бота в другом терминале:", Colors.YELLOW)
        print_colored("   python run_bot.py", Colors.YELLOW)

        print_colored("\n⏹️  Для остановки нажмите Ctrl+C", Colors.YELLOW)

        # Ждем и показываем логи
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print_colored(f"\n❌ {name} остановлен!", Colors.RED)
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print_colored("\n\n🛑 Остановка сервисов...", Colors.YELLOW)

        # Останавливаем все процессы
        for name, proc in processes:
            try:
                print_colored(f"   Остановка {name}...", Colors.YELLOW)
                proc.terminate()
                proc.wait(timeout=5)
                print_colored(f"   ✅ {name} остановлен", Colors.GREEN)
            except Exception as e:
                print_colored(f"   ⚠️ Ошибка остановки {name}: {e}", Colors.YELLOW)
                try:
                    proc.kill()
                except:
                    pass

        print_colored("\n✅ Все сервисы остановлены", Colors.GREEN)
        print_colored("💡 Redis продолжает работать (daemon), остановить: redis-cli shutdown", Colors.YELLOW)

if __name__ == "__main__":
    main()
