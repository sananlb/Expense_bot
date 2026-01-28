#!/usr/bin/env python
"""
Универсальный скрипт для запуска Redis + Celery на Windows и Linux/Ubuntu
Автоматически определяет ОС и запускает все необходимые сервисы для Expense Bot

⚠️ ВАЖНО: ЭТОТ ФАЙЛ АКТИВНО ИСПОЛЬЗУЕТСЯ ДЛЯ ЛОКАЛЬНОЙ РАЗРАБОТКИ!
⚠️ НЕ ПЕРЕМЕЩАТЬ В АРХИВ БЕЗ СОГЛАСОВАНИЯ!
⚠️ Это основной скрипт для запуска Redis + Celery Worker + Celery Beat локально.
"""
import os
import sys
import platform
import subprocess
import time
import signal
import shutil
from pathlib import Path

# Цвета для красивого вывода
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Печать заголовка"""
    print(Colors.CYAN + "=" * 60 + Colors.ENDC)
    print(Colors.CYAN + Colors.BOLD + "    EXPENSE BOT - Redis & Celery Launcher" + Colors.ENDC)
    print(Colors.CYAN + "=" * 60 + Colors.ENDC)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print()

def check_installed(command):
    """Проверка, установлена ли программа"""
    return shutil.which(command) is not None

def find_redis_executable():
    """Поиск исполняемого файла Redis"""
    system = platform.system()

    if system == "Windows":
        # Стандартные пути для Windows
        possible_paths = [
            r"C:\Program Files\Redis\redis-server.exe",
            r"C:\Redis\redis-server.exe",
            r"D:\Redis\redis-server.exe",
            os.path.join(os.getcwd(), "redis", "redis-server.exe"),
            os.path.join(os.path.dirname(sys.executable), "Scripts", "redis-server.exe")
        ]

        # Проверяем PATH
        if check_installed("redis-server"):
            return "redis-server"

        # Проверяем известные пути
        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Поиск в текущей директории и подпапках
        for root, dirs, files in os.walk(os.getcwd()):
            if "redis-server.exe" in files:
                return os.path.join(root, "redis-server.exe")

    else:  # Linux/Mac
        if check_installed("redis-server"):
            return "redis-server"

    return None

class ServiceManager:
    def __init__(self):
        self.system = platform.system()
        self.processes = []
        self.redis_process = None
        self.worker_process = None
        self.beat_process = None

    def check_redis(self):
        """Проверка и запуск Redis"""
        print(Colors.BLUE + "Проверка Redis..." + Colors.ENDC)

        # Проверяем, запущен ли Redis
        try:
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and "PONG" in result.stdout:
                print(Colors.GREEN + "OK Redis уже запущен" + Colors.ENDC)
                return True
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            print(f"Ошибка при проверке Redis: {e}")

        # Ищем Redis
        redis_path = find_redis_executable()

        if not redis_path:
            print(Colors.FAIL + "ERROR Redis не найден!" + Colors.ENDC)
            print("\nУстановите Redis:")
            if self.system == "Windows":
                print("1. Скачайте: https://github.com/microsoftarchive/redis/releases")
                print("2. Распакуйте в C:\\Redis\\")
                print("3. Запустите этот скрипт снова")
            else:
                print("Ubuntu/Debian: sudo apt install redis-server")
                print("CentOS/RHEL: sudo yum install redis")
                print("macOS: brew install redis")
            return False

        # Запускаем Redis
        print(Colors.WARNING + f"Запуск Redis: {redis_path}" + Colors.ENDC)

        try:
            if self.system == "Windows":
                # На Windows запускаем в новом окне
                self.redis_process = subprocess.Popen(
                    [redis_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # На Linux/Mac запускаем в фоне
                self.redis_process = subprocess.Popen(
                    [redis_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            # Ждем запуска
            time.sleep(2)

            # Проверяем, что запустился
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and "PONG" in result.stdout:
                print(Colors.GREEN + "OK Redis успешно запущен" + Colors.ENDC)
                return True
            else:
                print(Colors.FAIL + "ERROR Redis не отвечает" + Colors.ENDC)
                return False

        except Exception as e:
            print(Colors.FAIL + f"ERROR Ошибка запуска Redis: {e}" + Colors.ENDC)
            return False

    def check_django(self):
        """Проверка Django и миграций"""
        print(Colors.BLUE + "\nПроверка Django..." + Colors.ENDC)

        try:
            # Устанавливаем переменную окружения
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

            # Проверяем миграции
            result = subprocess.run(
                [sys.executable, "manage.py", "showmigrations", "--plan"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                if "[ ]" in result.stdout:
                    print(Colors.WARNING + "Есть неприменённые миграции" + Colors.ENDC)
                    print("Применяю миграции...")
                    subprocess.run([sys.executable, "manage.py", "migrate"])
                print(Colors.GREEN + "OK Django настроен корректно" + Colors.ENDC)
                return True
            else:
                print(Colors.FAIL + "ERROR Ошибка Django" + Colors.ENDC)
                print(result.stderr)
                return False

        except Exception as e:
            print(Colors.FAIL + f"ERROR Ошибка: {e}" + Colors.ENDC)
            return False

    def start_celery(self):
        """Запуск Celery Worker и Beat"""
        print(Colors.BLUE + "\nЗапуск Celery..." + Colors.ENDC)

        # Команды для разных ОС
        if self.system == "Windows":
            # ВАЖНО: используем ЯВНЫЙ путь к Python из venv для предотвращения дублирования!
            venv_python = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
            if not os.path.exists(venv_python):
                print(Colors.FAIL + f"ERROR: Python из venv не найден: {venv_python}" + Colors.ENDC)
                return False

            worker_cmd = [venv_python, "-m", "celery", "-A", "expense_bot", "worker", "-l", "info", "--pool=solo", "--concurrency=1"]
            beat_cmd = [venv_python, "-m", "celery", "-A", "expense_bot", "beat", "-l", "info"]
        else:
            worker_cmd = ["celery", "-A", "expense_bot", "worker", "-l", "info"]
            beat_cmd = ["celery", "-A", "expense_bot", "beat", "-l", "info"]

        try:
            # Запуск Worker
            print(Colors.WARNING + "Запуск Celery Worker..." + Colors.ENDC)
            if self.system == "Windows":
                self.worker_process = subprocess.Popen(
                    worker_cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.worker_process = subprocess.Popen(worker_cmd)

            time.sleep(3)

            # Запуск Beat
            print(Colors.WARNING + "Запуск Celery Beat..." + Colors.ENDC)
            if self.system == "Windows":
                self.beat_process = subprocess.Popen(
                    beat_cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.beat_process = subprocess.Popen(beat_cmd)

            time.sleep(2)
            print(Colors.GREEN + "OK Celery запущен" + Colors.ENDC)
            return True

        except Exception as e:
            print(Colors.FAIL + f"ERROR Ошибка запуска Celery: {e}" + Colors.ENDC)
        return False

    def test_cache(self):
        """Быстрый тест кеша"""
        print(Colors.BLUE + "\nТестирование кеша..." + Colors.ENDC)

        try:
            # Импортируем Django
            import django
            django.setup()
            from django.core.cache import cache

            # Тест
            cache.set('test_key', 'test_value', 10)
            value = cache.get('test_key')

            if value == 'test_value':
                print(Colors.GREEN + "OK Кеш работает корректно" + Colors.ENDC)
                cache.delete('test_key')
                return True
            else:
                print(Colors.FAIL + "ERROR Кеш не работает" + Colors.ENDC)
                return False

        except Exception as e:
            print(Colors.FAIL + f"ERROR Ошибка теста: {e}" + Colors.ENDC)
            return False

    def show_status(self):
        """Показ статуса всех сервисов"""
        print(Colors.CYAN + "\nСТАТУС СЕРВИСОВ:" + Colors.ENDC)
        print("-" * 40)

        # Redis
        try:
            result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            redis_status = "Работает" if result.returncode == 0 else "Остановлен"
        except (subprocess.CalledProcessError, FileNotFoundError):
            redis_status = "Остановлен"
        print(f"Redis:         {redis_status}")

        # Celery Worker
        worker_status = "Работает" if self.worker_process and self.worker_process.poll() is None else "Остановлен"
        print(f"Celery Worker: {worker_status}")

        # Celery Beat
        beat_status = "Работает" if self.beat_process and self.beat_process.poll() is None else "Остановлен"
        print(f"Celery Beat:   {beat_status}")

        print("-" * 40)

    def check_celery_tasks(self):
        """Проверка зарегистрированных задач Celery"""
        print(Colors.BLUE + "\nПроверка задач Celery..." + Colors.ENDC)

        try:
            # Проверяем, что Celery tasks можно импортировать
            import expense_bot.celery_tasks
            print(Colors.GREEN + "OK Задачи Celery загружены" + Colors.ENDC)

        except Exception as e:
            print(Colors.WARNING + f"Не удалось загрузить задачи: {e}" + Colors.ENDC)

    def stop_all(self):
        """Остановка всех сервисов"""
        print(Colors.WARNING + "\nОстановка сервисов..." + Colors.ENDC)

        # Останавливаем Celery
        for proc, name in [(self.worker_process, "Worker"), (self.beat_process, "Beat")]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                    print(f"OK Celery {name} остановлен")
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print(f"Celery {name} принудительно завершён")
                except Exception as e:
                    print(f"Ошибка при остановке Celery {name}: {e}")

        # Останавливаем Redis (только если мы его запустили)
        if self.redis_process:
            try:
                if self.system == "Windows":
                    subprocess.run(["redis-cli", "shutdown", "nosave"], capture_output=True)
                else:
                    self.redis_process.terminate()
                    self.redis_process.wait(timeout=5)
                print("OK Redis остановлен")
            except subprocess.TimeoutExpired:
                if self.redis_process:
                    self.redis_process.kill()
                print("Redis принудительно завершён")
            except Exception as e:
                print(f"Ошибка при остановке Redis: {e}")

    def run(self):
        """Основной метод запуска"""
        print_header()

        # Проверяем и запускаем сервисы
        if not self.check_redis():
            return 1

        if not self.check_django():
            return 1

        if not self.start_celery():
            self.stop_all()
            return 1

        # Тестируем кеш
        time.sleep(2)
        self.test_cache()

        # Проверяем задачи
        self.check_celery_tasks()

        # Показываем статус
        self.show_status()

        # Инструкции
        print(Colors.CYAN + "\nИНСТРУКЦИИ:" + Colors.ENDC)
        print("1. Все сервисы запущены и работают")
        print("2. Теперь можете запустить бота: python run_bot.py")
        print("3. Для остановки нажмите Ctrl+C")

        if self.system == "Windows":
            print("\nПримечание: На Windows сервисы запущены в отдельных окнах")
            print("   - Celery использует --pool=solo для совместимости")

        print(Colors.GREEN + "\nВсе готово к работе!" + Colors.ENDC)

        # Задачи, выполняемые Celery Beat
        print(Colors.CYAN + "\nРАСПИСАНИЕ ЗАДАЧ:" + Colors.ENDC)
        print("- Уведомления о подписках: ежедневно в 10:00")
        print("- Обработка повторяющихся платежей: ежедневно в 12:00")

        # Ждём завершения
        try:
            print("\nНажмите Ctrl+C для остановки всех сервисов...")
            while True:
                time.sleep(1)
                # Проверяем, что процессы живы
                if self.worker_process and self.worker_process.poll() is not None:
                    print(Colors.WARNING + "\nCelery Worker остановился!" + Colors.ENDC)
                    break
                if self.beat_process and self.beat_process.poll() is not None:
                    print(Colors.WARNING + "\nCelery Beat остановился!" + Colors.ENDC)
                    break

        except KeyboardInterrupt:
            print(Colors.WARNING + "\n\nПолучен сигнал остановки..." + Colors.ENDC)

        # Останавливаем всё
        self.stop_all()
        print(Colors.GREEN + "\nВсе сервисы остановлены" + Colors.ENDC)
        return 0

def main():
    """Точка входа"""
    manager = ServiceManager()

    # Обработчик сигналов для корректного завершения
    def signal_handler(signum, frame):
        print(Colors.WARNING + "\n\nПолучен сигнал остановки..." + Colors.ENDC)
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, signal_handler)

    # Запускаем
    sys.exit(manager.run())

if __name__ == "__main__":
    main()
