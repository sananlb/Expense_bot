#!/usr/bin/env python3
"""
Тестирование функциональности чата
"""
import asyncio
import os
import sys
from datetime import datetime

# Установка UTF-8 кодировки
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from bot.services.ai_selector import get_service
from bot.routers.chat import classify_by_heuristics


async def test_classification():
    """Тест классификации сообщений"""
    print("=== Тест классификации сообщений ===")
    
    test_messages = [
        # Чат сообщения
        ("Что ты умеешь?", "chat"),
        ("Как мне записать трату?", "chat"),
        ("Покажи мои траты за сегодня", "report"),
        ("Сколько я потратил за месяц?", "report"),
        
        # Расходы
        ("Кофе 200", "expense"),
        ("Такси 450", "expense"),
        ("Потратил на продукты 1500", "expense"),
    ]
    
    for message, expected in test_messages:
        result = classify_by_heuristics(message, 'ru')
        status = "OK" if result == expected else "FAIL"
        print(f"{status} '{message}' -> {result} (ожидалось: {expected})")


async def test_ai_chat():
    """Тест AI чата"""
    print("\n=== Тест AI чата ===")
    
    try:
        # Получаем AI сервис
        ai_service = get_service('chat')
        
        # Тестовый контекст
        context = [
            {"role": "user", "content": "Привет!"},
            {"role": "assistant", "content": "Привет! Я помогу вам учитывать расходы."}
        ]
        
        # Тестовые сообщения
        test_messages = [
            "Как мне записать трату?",
            "Что ты умеешь?",
            "Покажи пример записи расхода"
        ]
        
        for message in test_messages:
            print(f"\nПользователь: {message}")
            
            # Вызываем AI
            response = await ai_service.chat(message, context, {})
            print(f"Ассистент: {response}")
            
            # Обновляем контекст
            context.append({"role": "user", "content": message})
            context.append({"role": "assistant", "content": response})
            
    except Exception as e:
        print(f"FAIL Ошибка при тестировании AI чата: {e}")


async def main():
    """Главная функция"""
    await test_classification()
    await test_ai_chat()


if __name__ == "__main__":
    asyncio.run(main())