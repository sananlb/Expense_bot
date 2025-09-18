#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования обработки кешбека с обновленным алгоритмом
"""

import os
import sys
import django
import asyncio
import logging
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

from bot.services.cashback_free_text import process_cashback_free_text, looks_like_cashback_free_text

async def test_cashback():
    """Тестирование обработки кешбека"""
    
    # ID пользователя Alexey Nalbantov
    user_id = 881292737
    
    # Тестовые сообщения
    test_messages = [
        "Кешбек 6 процентов, категория подарки, втб",
        "кешбек 5 процентов на категорию подарки тинькофф",
        "добавь кешбек 10% на категорию gifts втб",
        "кешбек 3.5 процента категория рестораны сбер",
        "кешбек 7% на категорию супермаркеты альфа",
    ]
    
    print("=" * 60)
    print("Тестирование обработки кешбека")
    print("=" * 60)
    
    for msg in test_messages:
        print(f"\nТестовое сообщение: '{msg}'")
        print("-" * 40)
        
        # Проверка детекции
        if looks_like_cashback_free_text(msg):
            print("[OK] Сообщение распознано как кешбек")
            
            # Обработка
            success, response = await process_cashback_free_text(user_id, msg)
            
            if success:
                # Убираем эмодзи для вывода в консоль Windows
                response_clean = ''.join(c for c in response if ord(c) < 128 or c.isalpha() or c in ' \n\t')
                print(f"[SUCCESS] {response_clean}")
            else:
                response_clean = ''.join(c for c in response if ord(c) < 128 or c.isalpha() or c in ' \n\t')
                print(f"[ERROR] {response_clean}")
        else:
            print("[SKIP] Сообщение не распознано как кешбек")
    
    print("\n" + "=" * 60)
    print("Тестирование завершено")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_cashback())