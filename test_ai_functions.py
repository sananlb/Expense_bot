#!/usr/bin/env python
"""
Тестовый скрипт для проверки работы AI функций бота
"""

import asyncio
import os
import sys
import django
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO)

# Исправляем кодировку для Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_ai_functions():
    """Тестирование AI функций"""
    
    # Импортируем после setup Django
    from bot.services.google_ai_service import GoogleAIService
    
    # Создаем сервис
    ai_service = GoogleAIService()
    
    # Тестовый user_id (можно заменить на свой)
    test_user_id = 349848835  # Alexey's ID
    
    # Тестовые вопросы
    test_questions = [
        "Какая моя самая большая трата?",
        "В какой день я больше всего потратил?",
        "Сколько я потратил сегодня?",
        "На что я трачу больше всего?",
    ]
    
    print("=" * 60)
    print("Тестирование AI функций бота")
    print("=" * 60)
    
    for question in test_questions:
        print(f"\nВопрос: {question}")
        print("-" * 40)
        
        try:
            # Вызываем функцию с контекстом
            response = await ai_service.chat_with_functions(
                message=question,
                context=[],
                user_context={'user_id': test_user_id},
                user_id=test_user_id
            )
            
            print(f"Ответ: {response}")
            
        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 40)
        await asyncio.sleep(1)  # Небольшая пауза между запросами

if __name__ == "__main__":
    asyncio.run(test_ai_functions())