#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест индикатора печатания
"""

import asyncio
import sys
import os
import io

# Исправляем проблемы с кодировкой в Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_typing_cancel():
    """Тест отмены индикатора печатания"""
    print("Тестирование отмены индикатора печатания...")
    
    typing_task = None
    typing_cancelled = False
    
    async def delayed_typing():
        """Имитация индикатора печатания"""
        nonlocal typing_cancelled
        await asyncio.sleep(2)  # Задержка 2 секунды перед началом
        
        if not typing_cancelled:
            print("⌨️ Начинаем показывать индикатор печатания...")
            for i in range(5):  # 5 итераций по 5 секунд
                if typing_cancelled:
                    print("❌ Индикатор печатания отменен!")
                    break
                print(f"   Печатаем... (итерация {i+1}/5)")
                await asyncio.sleep(1)
                if typing_cancelled:
                    print("❌ Индикатор печатания отменен!")
                    break
    
    def cancel_typing():
        """Отмена индикатора печатания"""
        nonlocal typing_cancelled
        typing_cancelled = True
        if typing_task and not typing_task.done():
            typing_task.cancel()
            print("✅ Задача индикатора отменена")
    
    # Запускаем задачу
    typing_task = asyncio.create_task(delayed_typing())
    print("📝 Задача индикатора запущена")
    
    # Ждем 1 секунду
    await asyncio.sleep(1)
    print("⏱️ Прошла 1 секунда...")
    
    # Отменяем индикатор (до того как он начнется)
    print("🛑 Отменяем индикатор...")
    cancel_typing()
    
    # Ждем завершения задачи
    try:
        await typing_task
    except asyncio.CancelledError:
        print("✅ Задача успешно отменена")
    
    print("\n" + "="*50)
    print("Тест завершен!")
    print("="*50)


async def test_typing_with_delay():
    """Тест индикатора с задержкой"""
    print("\n" + "="*50)
    print("Тест индикатора с задержкой")
    print("="*50)
    
    typing_task = None
    typing_cancelled = False
    
    async def delayed_typing():
        """Имитация индикатора печатания"""
        nonlocal typing_cancelled
        await asyncio.sleep(2)  # Задержка 2 секунды перед началом
        
        if not typing_cancelled:
            print("⌨️ Начинаем показывать индикатор печатания...")
            for i in range(5):  # 5 итераций
                if typing_cancelled:
                    print("❌ Индикатор печатания отменен!")
                    break
                print(f"   Печатаем... (итерация {i+1}/5)")
                await asyncio.sleep(1)
    
    def cancel_typing():
        """Отмена индикатора печатания"""
        nonlocal typing_cancelled
        typing_cancelled = True
        if typing_task and not typing_task.done():
            typing_task.cancel()
    
    # Запускаем задачу
    typing_task = asyncio.create_task(delayed_typing())
    print("📝 Задача индикатора запущена")
    
    # Ждем 3 секунды (индикатор должен начаться)
    await asyncio.sleep(3)
    print("⏱️ Прошло 3 секунды, индикатор должен работать...")
    
    # Отменяем индикатор
    print("🛑 Отменяем индикатор...")
    cancel_typing()
    
    # Ждем завершения задачи
    try:
        await typing_task
    except asyncio.CancelledError:
        print("✅ Задача успешно отменена")
    
    print("\nТест завершен!")


async def main():
    """Запуск тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ИНДИКАТОРА ПЕЧАТАНИЯ")
    print("="*60)
    
    # Тест 1: Отмена до начала индикатора
    await test_typing_cancel()
    
    # Тест 2: Отмена после начала индикатора
    await test_typing_with_delay()
    
    print("\n" + "="*60)
    print("Все тесты завершены!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())