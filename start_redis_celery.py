#!/usr/bin/env python
"""
Универсальный скрипт для запуска Redis + Celery на Windows, Linux и macOS
Автоматически определяет ОС и запускает все необходимые сервисы
"""
import os
import sys
import platform
import subprocess
import time
import signal
import shutil
from pathlib import Path
import psutil  # Нужно установить: pip install psutil

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
    print(Colors.CYAN + Colors.BOLD + "    EXPENSE BOT - Universal Launcher" + Colors.ENDC)
    print(Colors.CYAN + "=" * 60 + Colors.ENDC)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    print()

def check_installed(command):
    """Проверка, установлена ли программа"""
    return shutil.which(command) is not None

def is_process_running(process_name):
    """Проверка, запущен ли процесс"""
    for proc in psutil.process_iter(['name']):
        try:
            if process_name.lower() in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False

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
                
    else:  # Linux/macOS
        # Проверяем стандартные команды
        if check_installed("redis-server"):
            return "redis-server"
        
        # На macOS Redis может быть установлен через Homebrew
        if system == "Darwin":
            homebrew_paths = [
                "/usr/local/bin/redis-server",
                "/opt/homebrew/bin/redis-server",
                os.path.expanduser("~/homebrew/bin/redis-server")
            ]
            for path in homebrew_paths:
                if os.path.exists(path):
                    return path
            
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
        print(Colors.BLUE + "🔍 Проверка Redis..." + Colors.ENDC)
        
        # Проверяем, запущен ли Redis
        try:
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and "PONG" in result.stdout:
                print(Colors.GREEN + "✅ Redis уже запущен" + Colors.ENDC)
                return True
        except:
            pass
        
        # Ищем Redis
        redis_path = find_redis_executable()
        
        if not redis_path:
            print(Colors.FAIL + "❌ Redis не найден!" + Colors.ENDC)
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
        print(Colors.WARNING + f"🚀 Запуск Redis: {redis_path}" + Colors.ENDC)
        
        try:
            if self.system == "Windows":
                # На Windows запускаем в новом окне
                self.redis_process = subprocess.Popen(
                    [redis_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # На Linux/macOS запускаем в фоне
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
                print(Colors.GREEN + "✅ Redis успешно запущен" + Colors.ENDC)
                return True
            else:
                print(Colors.FAIL + "❌ Redis не отвечает" + Colors.ENDC)
                return False
                
        except Exception as e:
            print(Colors.FAIL + f"❌ Ошибка запуска Redis: {e}" + Colors.ENDC)
            return False
    
    def check_django(self):
        """Проверка Django и миграций"""
        print(Colors.BLUE + "\n🔍 Проверка Django..." + Colors.ENDC)
        
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
                    print(Colors.WARNING + "⚠️  Есть неприменённые миграции" + Colors.ENDC)
                    print("Применяю миграции...")
                    subprocess.run([sys.executable, "manage.py", "migrate"])
                print(Colors.GREEN + "✅ Django настроен корректно" + Colors.ENDC)
                return True
            else:
                print(Colors.FAIL + "❌ Ошибка Django" + Colors.ENDC)
                print(result.stderr)
                return False
                
        except Exception as e:
            print(Colors.FAIL + f"❌ Ошибка: {e}" + Colors.ENDC)
            return False
    
    def start_celery(self):
        """Запуск Celery Worker и Beat"""
        print(Colors.BLUE + "\n🔍 Запуск Celery..." + Colors.ENDC)
        
        # Команды для разных ОС
        if self.system == "Windows":
            # ВАЖНО: добавляем --pool=solo для Windows!
            worker_cmd = [sys.executable, "-m", "celery", "-A", "expense_bot", "worker", "-l", "info", "--pool=solo", "--concurrency=1"]
            beat_cmd = [sys.executable, "-m", "celery", "-A", "expense_bot", "beat", "-l", "info"]
        else:
            worker_cmd = ["celery", "-A", "expense_bot", "worker", "-l", "info"]
            beat_cmd = ["celery", "-A", "expense_bot", "beat", "-l", "info"]
        
        try:
            # Запуск Worker
            print(Colors.WARNING + "🚀 Запуск Celery Worker..." + Colors.ENDC)
            if self.system == "Windows":
                self.worker_process = subprocess.Popen(
                    worker_cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.worker_process = subprocess.Popen(worker_cmd)
            
            time.sleep(3)
            
            # Запуск Beat
            print(Colors.WARNING + "🚀 Запуск Celery Beat..." + Colors.ENDC)
            if self.system == "Windows":
                self.beat_process = subprocess.Popen(
                    beat_cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.beat_process = subprocess.Popen(beat_cmd)
            
            time.sleep(2)
            print(Colors.GREEN + "✅ Celery запущен" + Colors.ENDC)
            return True
            
        except Exception as e:
            print(Colors.FAIL + f"❌ Ошибка запуска Celery: {e}" + Colors.ENDC)
        return False

    def test_cache(self):
        """Быстрый тест кеша"""
        print(Colors.BLUE + "\n🧪 Тестирование кеша..." + Colors.ENDC)
        
        try:
            # Импортируем Django
            import django
            django.setup()
            from django.core.cache import cache
            
            # Тест
            cache.set('test_key', 'test_value', 10)
            value = cache.get('test_key')
            
            if value == 'test_value':
                print(Colors.GREEN + "✅ Кеш работает корректно" + Colors.ENDC)
                cache.delete('test_key')
                return True
            else:
                print(Colors.FAIL + "❌ Кеш не работает" + Colors.ENDC)
                return False
                
        except Exception as e:
            print(Colors.FAIL + f"❌ Ошибка теста: {e}" + Colors.ENDC)
            return False
    
    def show_status(self):
        """Показ статуса всех сервисов"""
        print(Colors.CYAN + "\n📊 СТАТУС СЕРВИСОВ:" + Colors.ENDC)
        print("─" * 40)
        
        # Redis
        try:
            result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
            redis_status = "🟢 Работает" if result.returncode == 0 else "🔴 Остановлен"
        except:
            redis_status = "🔴 Остановлен"
        print(f"Redis:         {redis_status}")
        
        # Celery Worker
        worker_status = "🟢 Работает" if self.worker_process and self.worker_process.poll() is None else "🔴 Остановлен"
        print(f"Celery Worker: {worker_status}")
        
        # Celery Beat
        beat_status = "🟢 Работает" if self.beat_process and self.beat_process.poll() is None else "🔴 Остановлен"
        print(f"Celery Beat:   {beat_status}")
        
        print("─" * 40)
    
    def stop_all(self):
        """Остановка всех сервисов"""
        print(Colors.WARNING + "\n⏹️  Остановка сервисов..." + Colors.ENDC)
        
        # Останавливаем Celery
        for proc, name in [(self.worker_process, "Worker"), (self.beat_process, "Beat")]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                    print(f"✅ Celery {name} остановлен")
                except:
                    proc.kill()
                    print(f"⚠️  Celery {name} принудительно завершён")
        
        # Останавливаем Redis (только если мы его запустили)
        if self.redis_process:
            try:
                if self.system == "Windows":
                    subprocess.run(["redis-cli", "shutdown", "nosave"], capture_output=True)
                else:
                    self.redis_process.terminate()
                    self.redis_process.wait(timeout=5)
                print("✅ Redis остановлен")
            except:
                if self.redis_process:
                    self.redis_process.kill()
                print("⚠️  Redis принудительно завершён")
    
    def run(self):
        """Основной метод запуска"""
        print_header()
        
        # Проверяем зависимости
        try:
            import psutil
        except ImportError:
            print(Colors.FAIL + "❌ Установите psutil: pip install psutil" + Colors.ENDC)
            return 1
        
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
        
        # Показываем статус
        self.show_status()
        
        # Инструкции
        print(Colors.CYAN + "\n💡 ИНСТРУКЦИИ:" + Colors.ENDC)
        print("1. Все сервисы запущены и работают")
        print("2. Теперь можете запустить бота: python run_bot.py")
        print("3. Для остановки нажмите Ctrl+C")
        
        if self.system == "Windows":
            print("\n📝 Примечание: На Windows сервисы запущены в отдельных окнах")
        
        print(Colors.GREEN + "\n✨ Все готово к работе!" + Colors.ENDC)
        
        # Ждём завершения
        try:
            print("\nНажмите Ctrl+C для остановки всех сервисов...")
            while True:
                time.sleep(1)
                # Проверяем, что процессы живы
                if self.worker_process and self.worker_process.poll() is not None:
                    print(Colors.WARNING + "\n⚠️  Celery Worker остановился!" + Colors.ENDC)
                    break
                if self.beat_process and self.beat_process.poll() is not None:
                    print(Colors.WARNING + "\n⚠️  Celery Beat остановился!" + Colors.ENDC)
                    break
                    
        except KeyboardInterrupt:
            print(Colors.WARNING + "\n\n🛑 Получен сигнал остановки..." + Colors.ENDC)
        
        # Останавливаем всё
        self.stop_all()
        print(Colors.GREEN + "\n✅ Все сервисы остановлены" + Colors.ENDC)
        return 0

def main():
    """Точка входа"""
    manager = ServiceManager()
    
    # Обработчик сигналов для корректного завершения
    def signal_handler(signum, frame):
        print(Colors.WARNING + "\n\n🛑 Получен сигнал остановки..." + Colors.ENDC)
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем
    sys.exit(manager.run())

if __name__ == "__main__":
    main()