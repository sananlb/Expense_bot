#!/usr/bin/env python
"""
Тестирование AI функций для доходов
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

# Выбираем сервис в зависимости от аргумента
if len(sys.argv) > 1 and sys.argv[1] == 'adaptive':
    from bot.services.google_ai_service_adaptive import GoogleAIService
    print("Используем АДАПТИВНЫЙ сервис (google_ai_service_adaptive)")
else:
    from bot.services.google_ai_service import GoogleAIService
    print("Используем ОСНОВНОЙ сервис с функциями (google_ai_service)")

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_income_query():
    """Тестирование запроса о доходах"""
    service = GoogleAIService()
    
    # Тестовые запросы о доходах
    test_queries = [
        "сколько у меня всего доходов в этом месяце?",
        "покажи мои доходы",
        "сколько я заработал за неделю?",
        "какие у меня доходы сегодня?",
    ]
    
    # Тестовый user_id 
    user_id = 123456789  # Замените на реальный ID для теста
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Запрос: {query}")
        print(f"{'='*60}")
        
        try:
            # Проверяем какой метод использовать
            if hasattr(service, 'chat_with_functions') and 'adaptive' not in sys.argv:
                # Используем chat_with_functions для основного сервиса
                response = await service.chat_with_functions(
                    message=query,
                    context=[],
                    user_context={'user_id': user_id},
                    user_id=user_id
                )
            else:
                # Используем обычный chat для адаптивного сервиса
                response = await service.chat(
                    message=query,
                    context=[],
                    user_context={'user_id': user_id}
                )
            
            # Безопасный вывод с обработкой эмодзи
            try:
                print(f"Ответ: {response}")
            except UnicodeEncodeError:
                # Заменяем эмодзи на текст для вывода в консоль
                safe_response = response.encode('ascii', 'ignore').decode('ascii')
                print(f"Ответ (без эмодзи): {safe_response}")
            
        except Exception as e:
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Тестирование AI функций для доходов")
    asyncio.run(test_income_query())