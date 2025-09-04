#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест категоризации
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

from bot.utils.expense_categorizer import categorize_expense, categorize_expense_smart
from expenses.models import Profile, ExpenseCategory

# Тестовые случаи
test_cases = [
    "капучино, пицца",
    "кофе, пицца",
    "капучино",
    "пицца",
    "кофе",
    "вода",
    "чебурек",
]

print("="*50)
print("ТЕСТ КАТЕГОРИЗАЦИИ")
print("="*50)

print("\n=== Тест без профиля (статические правила) ===")
for text in test_cases:
    category, confidence, corrected = categorize_expense(text)
    print(f"'{text}' -> {category} (уверенность: {confidence:.2%})")

print("\n=== Тест с профилем пользователя ===")
# Получаем тестового пользователя
try:
    profile = Profile.objects.get(telegram_id=881292737)  # Ваш ID
    print(f"Используем профиль: {profile.telegram_id}")
    
    # Показываем категории пользователя
    categories = ExpenseCategory.objects.filter(profile=profile)
    print(f"Категории пользователя: {', '.join([c.name for c in categories])}")
    
    for text in test_cases:
        category, confidence, corrected = categorize_expense_smart(text, profile)
        print(f"'{text}' -> {category} (уверенность: {confidence:.2%})")
        
except Profile.DoesNotExist:
    print("Профиль не найден")

print("\n" + "="*50)