#!/usr/bin/env python
"""
Тестирование форматирования списка трат в стиле дневника
"""
import asyncio
import os
import sys
from datetime import datetime, date, timedelta
from types import SimpleNamespace

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

import django
django.setup()

from bot.utils.expense_formatter import format_expenses_diary_style

def test_diary_formatting():
    """Тестируем форматирование в стиле дневника"""
    
    print("="*60)
    print("ТЕСТ ФОРМАТИРОВАНИЯ В СТИЛЕ ДНЕВНИКА")
    print("="*60)
    
    # Создаем тестовые данные
    expenses = []
    today = date.today()
    
    # Траты за сегодня
    for i in range(3):
        exp = SimpleNamespace()
        exp.expense_date = today
        exp.expense_time = datetime.strptime(f"{14+i}:{30+i*10}", '%H:%M').time()
        exp.created_at = datetime.now()
        exp.description = ["Кофе в кафе", "Продукты в магазине", "Такси"][i]
        exp.amount = [320, 1250, 450][i]
        exp.currency = 'RUB'
        expenses.append(exp)
    
    # Траты за вчера
    yesterday = today - timedelta(days=1)
    for i in range(2):
        exp = SimpleNamespace()
        exp.expense_date = yesterday
        exp.expense_time = datetime.strptime(f"{10+i*2}:{15+i*20}", '%H:%M').time()
        exp.created_at = datetime.now()
        exp.description = ["Завтрак", "Обед"][i]
        exp.amount = [280, 650][i]
        exp.currency = 'RUB'
        expenses.append(exp)
    
    # Траты за позавчера
    day_before = today - timedelta(days=2)
    for i in range(2):
        exp = SimpleNamespace()
        exp.expense_date = day_before
        exp.expense_time = datetime.strptime(f"{19+i}:00", '%H:%M').time()
        exp.created_at = datetime.now()
        exp.description = ["Ужин", "Десерт"][i]
        exp.amount = [1200, 250][i]
        exp.currency = 'RUB'
        expenses.append(exp)
    
    # Форматируем
    result = format_expenses_diary_style(expenses, today=today, max_expenses=50)
    
    print("\nРезультат форматирования:")
    print("-"*40)
    print(result)
    
    # Теперь протестируем с большим количеством трат
    print("\n" + "="*60)
    print("ТЕСТ С БОЛЬШИМ КОЛИЧЕСТВОМ ТРАТ")
    print("="*60)
    
    # Создаем 60 трат
    many_expenses = []
    for day_offset in range(10):
        current_date = today - timedelta(days=day_offset)
        for i in range(6):
            exp = SimpleNamespace()
            exp.expense_date = current_date
            exp.expense_time = datetime.strptime(f"{9+i*2}:{i*10}", '%H:%M').time()
            exp.created_at = datetime.now()
            exp.description = f"Трата #{day_offset*6 + i + 1}"
            exp.amount = 100 + (day_offset * 6 + i) * 50
            exp.currency = 'RUB'
            many_expenses.append(exp)
    
    # Форматируем с ограничением
    result = format_expenses_diary_style(many_expenses, today=today, max_expenses=20)
    
    print("\nРезультат с ограничением (первые 500 символов):")
    print("-"*40)
    print(result[:500] + "...")

if __name__ == "__main__":
    test_diary_formatting()