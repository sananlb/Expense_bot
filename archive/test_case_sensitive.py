#!/usr/bin/env python
import os
import sys
import django
from pathlib import Path

# Добавляем корневую директорию проекта в путь
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

import asyncio
from bot.utils.expense_parser import parse_expense_message

async def test_case_sensitive():
    """Тестирование обработки регистра в описаниях расходов"""
    
    test_cases = [
        ('МТС 500 руб', 'МТС'),  # Должно остаться МТС, не Мтс
        ('мАгАзИн 1000', 'МАгАзИн'),  # Первая буква большая, остальные не меняются
        ('PayPal 2500', 'PayPal'),  # CamelCase должен сохраниться
        ('IKEA 3000', 'IKEA'),  # Все заглавные должны остаться
        ('spotify 150', 'Spotify'),  # Первая буква должна стать заглавной
        ('яндекс.такси 450', 'Яндекс.такси'),  # Точка не должна мешать
    ]
    
    print("Testing case handling in descriptions:\n")
    print("-" * 60)
    
    for text, expected_description in test_cases:
        result = await parse_expense_message(text, use_ai=False)
        if result:
            actual_description = result['description']
            status = "OK" if actual_description == expected_description else "FAIL"
            print(f"{status} '{text}' -> '{actual_description}' (expected: '{expected_description}')")
            if actual_description != expected_description:
                print(f"   Full result: {result}")
        else:
            print(f"FAIL '{text}' -> Parse error")
    
    print("-" * 60)

if __name__ == "__main__":
    asyncio.run(test_case_sensitive())