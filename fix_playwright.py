#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Исправление установки Playwright
"""

import subprocess
import sys
import os

def fix_playwright():
    """Переустановка Playwright с браузерами"""
    try:
        print("Шаг 1: Удаляем старые версии браузеров...")
        # Удаляем старую папку ms-playwright
        import shutil
        playwright_dir = os.path.expanduser("~/AppData/Local/ms-playwright")
        if os.path.exists(playwright_dir):
            print(f"Удаляем {playwright_dir}...")
            shutil.rmtree(playwright_dir, ignore_errors=True)
            print("Старые браузеры удалены")
        
        print("\nШаг 2: Переустанавливаем Playwright...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "playwright", "-y"])
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright==1.47.0"])  # Стабильная версия
        
        print("\nШаг 3: Устанавливаем браузеры через синхронный API...")
        # Используем синхронный API для установки
        from playwright.sync_api import sync_playwright
        
        print("Запускаем установку браузера Chromium...")
        # При первом запуске автоматически скачаются браузеры
        try:
            with sync_playwright() as p:
                print("Загружаем Chromium...")
                browser = p.chromium.launch(
                    headless=True,
                    args=['--disable-dev-shm-usage', '--no-sandbox']
                )
                page = browser.new_page()
                page.goto("data:text/html,<h1>Test</h1>")
                content = page.content()
                browser.close()
                
                if "<h1>Test</h1>" in content:
                    print("\n✅ УСПЕХ! Playwright и браузеры установлены корректно!")
                    return True
        except Exception as browser_error:
            print(f"Ошибка при запуске браузера: {browser_error}")
            
            # Попробуем установить через CLI
            print("\nПробуем установить через CLI...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.stderr:
                print("Ошибки:", result.stderr)
                
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = fix_playwright()
    if success:
        print("\n" + "="*50)
        print("Playwright успешно настроен!")
        print("Теперь можете запустить бота: python run_bot.py")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("Не удалось настроить Playwright автоматически")
        print("Попробуйте выполнить вручную:")
        print("1. pip uninstall playwright -y")
        print("2. pip install playwright==1.47.0")
        print("3. playwright install chromium")
        print("="*50)