#!/usr/bin/env python
"""Тест изолированного Google AI сервиса"""
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

from bot.services.google_ai_service_isolated import GoogleAIService

async def test_isolated_service():
    """Тестируем изолированный сервис"""
    
    print("=" * 50)
    print("Testing Isolated Google AI Service")
    print("=" * 50)
    
    # Создаем сервис
    print("\n1. Creating service...")
    service = GoogleAIService()
    print("   Service created successfully")
    
    # Тестовые данные
    categories = ['Продукты', 'Транспорт', 'Развлечения', 'Здоровье', 
                  'Образование', 'Рестораны', 'Покупки', 'Услуги', 'Другое']
    
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
                categories=categories
            )
            
            if result:
                print(f"   [OK] Category: {result['category']}")
                print(f"   [OK] Confidence: {result['confidence']}")
                print(f"   [OK] Reasoning: {result.get('reasoning', 'N/A')[:100]}")
            else:
                print(f"   [FAIL] Failed to categorize")
                
        except Exception as e:
            print(f"   [FAIL] ERROR: {type(e).__name__}: {str(e)[:100]}")
    
    print("\n" + "=" * 50)
    print("Test completed")
    print("=" * 50)

if __name__ == "__main__":
    # Для Windows - устанавливаем spawn метод
    import multiprocessing as mp
    mp.set_start_method('spawn', force=True)
    
    asyncio.run(test_isolated_service())