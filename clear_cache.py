#!/usr/bin/env python
"""
Скрипт для очистки кэша AI сервисов
Аналог из nutrition_bot
"""
import os
import sys
import shutil

def clear_cache():
    """Очищает различные виды кэша"""
    
    print("=" * 50)
    print("EXPENSE BOT - Cache Cleaner")
    print("=" * 50)
    
    # 1. Очистка __pycache__ директорий
    cache_dirs_removed = 0
    for root, dirs, files in os.walk('.'):
        # Пропускаем виртуальное окружение и .git
        if 'venv' in root or '.git' in root:
            continue
            
        for dir_name in dirs:
            if dir_name == '__pycache__':
                cache_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(cache_path)
                    cache_dirs_removed += 1
                    print(f"[OK] Удален кэш: {cache_path}")
                except Exception as e:
                    print(f"[ERROR] Ошибка при удалении {cache_path}: {e}")
    
    # 2. Очистка .pyc файлов
    pyc_files_removed = 0
    for root, dirs, files in os.walk('.'):
        # Пропускаем виртуальное окружение и .git
        if 'venv' in root or '.git' in root:
            continue
            
        for file_name in files:
            if file_name.endswith('.pyc'):
                file_path = os.path.join(root, file_name)
                try:
                    os.remove(file_path)
                    pyc_files_removed += 1
                except Exception as e:
                    print(f"[ERROR] Ошибка при удалении {file_path}: {e}")
    
    # 3. Очистка кэша AI сервисов (если они сохраняют что-то локально)
    ai_cache_paths = [
        '.cache',
        'cache',
        'tmp',
        '.tmp'
    ]
    
    for cache_dir in ai_cache_paths:
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(f"[OK] Удален кэш AI: {cache_dir}")
            except Exception as e:
                print(f"[ERROR] Ошибка при удалении {cache_dir}: {e}")
    
    # 4. Сброс кэша импортов Python (требует перезапуска)
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТ:")
    print(f"  • Удалено __pycache__ директорий: {cache_dirs_removed}")
    print(f"  • Удалено .pyc файлов: {pyc_files_removed}")
    print("=" * 50)
    
    # 5. Инструкция по перезапуску
    print("\n[!] ВАЖНО:")
    print("Для полной очистки кэша AI сервисов необходимо:")
    print("1. Остановить бота (Ctrl+C)")
    print("2. Запустить этот скрипт")
    print("3. Запустить бота заново: python run_bot.py")
    print("\nКэш очищен! Теперь перезапустите бота.")
    print("=" * 50)
    
    return True

def main():
    """Главная функция"""
    try:
        # Проверяем, что мы в правильной директории
        if not os.path.exists('run_bot.py'):
            print("[ERROR] Ошибка: Запустите скрипт из корневой директории expense_bot")
            print("        где находится файл run_bot.py")
            return 1
        
        # Очищаем кэш
        success = clear_cache()
        
        if success:
            print("\n[SUCCESS] Кэш успешно очищен!")
            print("          Теперь можете запустить бота: python run_bot.py")
            return 0
        else:
            print("\n[ERROR] Произошли ошибки при очистке кэша")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n[WARNING] Очистка прервана пользователем")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())