#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: обработка сообщения чатом
"""

import os
import sys
import django
import asyncio
import io
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.routers.chat import get_simple_response

async def test():
    user_id = 881292737
    
    test_cases = [
        "Огурец",
        "Привет",
        "Что умеешь?",
        "Сколько я потратил сегодня?",
        "А вчера?",
        "Покажи траты за месяц"
    ]
    
    print("=" * 80)
    print("ТЕСТ ПРОСТЫХ ОТВЕТОВ ЧАТА")
    print("=" * 80)
    
    for text in test_cases:
        print(f"\n📝 Сообщение: '{text}'")
        print("-" * 40)
        
        response = await get_simple_response(text, user_id)
        print(f"🤖 Ответ: {response}")

if __name__ == "__main__":
    asyncio.run(test())