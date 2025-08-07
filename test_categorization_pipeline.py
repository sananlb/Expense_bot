#!/usr/bin/env python
"""Тест полного пайплайна категоризации"""
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from bot.services.ai_selector import get_service
from expenses.models import ExpenseCategory

async def test_categorization():
    """Тестируем категоризацию через AI"""
    
    # Получаем список категорий
    categories = ['Продукты', 'Транспорт', 'Развлечения', 'Здоровье', 
                  'Образование', 'Рестораны', 'Покупки', 'Услуги', 'Другое']
    
    print("=" * 50)
    print("Testing AI categorization pipeline")
    print("=" * 50)
    
    # Получаем сервис
    print("\n1. Getting AI service...")
    service = get_service('categorization')
    print(f"   Service: {type(service).__name__}")
    
    # Тестовые данные
    test_cases = [
        ("Шахматы 1990", 1990.0, "RUB"),
        ("Яндекс такси домой", 350.0, "RUB"),
        ("Пятерочка продукты", 1200.0, "RUB")
    ]
    
    for text, amount, currency in test_cases:
        print(f"\n2. Testing: '{text}' ({amount} {currency})")
        
        try:
            result = await service.categorize_expense(
                text=text,
                amount=amount,
                currency=currency,
                categories=categories,
                user_context={'user_id': 'test', 'telegram_id': 'test'}
            )
            
            if result:
                print(f"   [OK] Category: {result['category']}")
                print(f"   [OK] Confidence: {result['confidence']}")
                print(f"   [OK] Reasoning: {result.get('reasoning', 'N/A')[:100]}")
            else:
                print(f"   [FAIL] Failed to categorize")
                
        except asyncio.TimeoutError:
            print(f"   [FAIL] TIMEOUT!")
        except Exception as e:
            print(f"   [FAIL] ERROR: {type(e).__name__}: {str(e)[:100]}")
    
    print("\n" + "=" * 50)
    print("Test completed")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_categorization())