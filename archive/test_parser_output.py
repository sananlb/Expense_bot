#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест парсера для "капучино, пицца"
"""

import os
import sys
import django
import io
import asyncio

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message
from expenses.models import Profile

async def test_parser():
    """Тестируем, что возвращает парсер"""
    user_id = 881292737
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except:
        profile = None
    
    test_inputs = [
        "капучино, пицца 500",
        "кафе 300",
        "пицца 400",
        "кофе 200",
    ]
    
    print("=" * 60)
    print("ТЕСТ ПАРСЕРА")
    print("=" * 60)
    
    for text in test_inputs:
        print(f"\nВход: '{text}'")
        result = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=False)
        
        if result:
            print(f"  Сумма: {result['amount']}")
            print(f"  Описание: {result['description']}")
            print(f"  Категория: {result['category']}")
            print(f"  Уверенность: {result['confidence']}")
            print(f"  Валюта: {result['currency']}")
        else:
            print("  ❌ Не удалось распарсить")
    
    print("\n" + "=" * 60)

# Запускаем тест
asyncio.run(test_parser())