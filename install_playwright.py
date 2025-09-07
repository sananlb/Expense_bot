#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Установка браузеров для Playwright
"""

import subprocess
import sys
import os
import io

# Установка UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def install_playwright_browsers():
    """Установка браузеров для Playwright"""
    try:
        print("Устанавливаем браузеры для Playwright...")
        
        # Установка через subprocess
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            env={**os.environ, 'PLAYWRIGHT_BROWSERS_PATH': '0'}  # Использовать стандартный путь
        )
        
        if result.returncode == 0:
            print("[OK] Браузеры успешно установлены!")
            print(result.stdout)
        else:
            print("[ERROR] Ошибка при установке браузеров:")
            print(result.stderr)
            
            # Попробуем альтернативный метод
            print("\nПробуем альтернативный метод...")
            from playwright.sync_api import sync_playwright
            
            # Это автоматически скачает браузеры при первом запуске
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("[OK] Браузер установлен альтернативным методом!")
                
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        print("\nПопробуйте выполнить команду вручную:")
        print("playwright install chromium")

if __name__ == "__main__":
    install_playwright_browsers()