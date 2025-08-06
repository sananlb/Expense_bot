#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест: когда именно подключается AI
"""

import os
import sys
import django
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Проверим логику условий для AI

print("=" * 80)
print("АНАЛИЗ: Когда подключается AI")
print("=" * 80)

print("\nПроблема в коде expense_parser.py:")
print("-" * 40)
print("""
# Строка 304:
category = category or 'Прочие расходы'  # <-- Всегда заполняет категорию!

# Строка 316:
if not category:  # <-- Это условие НИКОГДА не выполнится!
    should_use_ai = True
""")

print("\nЭто означает, что AI подключается ТОЛЬКО когда:")
print("1. Категория найдена по ключевым словам")
print("2. НО её нет среди категорий пользователя")
print("")
print("AI НЕ подключается когда:")
print("❌ Слово вообще не найдено в ключевых словах")
print("   (хотя логически именно тогда он нужен больше всего!)")

print("\n" + "=" * 80)
print("РЕКОМЕНДАЦИЯ ДЛЯ ИСПРАВЛЕНИЯ:")
print("=" * 80)

print("""
Изменить логику в expense_parser.py:

# Строка 304 - НЕ заполнять category автоматически:
result = {
    'amount': float(amount),
    'description': description or 'Расход',
    'category': category,  # <-- Оставить None если не найдено
    'currency': currency,
    'confidence': 0.5 if category else 0.2
}

# Строка 316 - условие будет работать правильно:
if not category:
    should_use_ai = True  # <-- Теперь будет срабатывать!

# В конце функции добавить:
if not result['category']:
    result['category'] = 'Прочие расходы'  # <-- Fallback после AI
""")