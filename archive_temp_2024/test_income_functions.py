#!/usr/bin/env python
"""
Тестирование функций для доходов через адаптивный сервис
"""

import os
import sys
import django
import asyncio
import logging

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.google_ai_service_adaptive import GoogleAIService

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_income_functions():
    """Тестирование функций для доходов"""
    service = GoogleAIService()
    
    # Тестовые запросы, которые должны вызывать функции
    test_queries = [
        "Какой мой самый большой доход?",
        "В какой день я больше всего заработал?",
        "Сколько я зарабатываю в среднем?",
        "Покажи мои доходы за месяц",
    ]
    
    # Тестовый user_id 
    user_id = 881292737  # Ваш реальный ID
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Запрос: {query}")
        print(f"{'='*60}")
        
        try:
            # Вызываем функцию чата с user_context
            response = await service.chat(
                message=query,
                context=[],
                user_context={'user_id': user_id}
            )
            
            print(f"Ответ: {response}")
            
        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Тестирование функций для доходов через адаптивный сервис")
    asyncio.run(test_income_functions())