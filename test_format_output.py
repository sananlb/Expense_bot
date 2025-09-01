#!/usr/bin/env python
"""
Тестирование форматирования вывода списка трат
"""
import asyncio
import os
import sys
from datetime import datetime, date, timedelta

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

import django
django.setup()

from bot.services.expense_functions import ExpenseFunctions
from bot.services.google_ai_service import GoogleAIService

TEST_USER_ID = 881292737  # пользователь с тратами

async def test_expenses_list_formatting():
    """Тестируем форматирование списка трат"""
    
    print("="*60)
    print("ТЕСТИРУЕМ ФОРМАТИРОВАНИЕ СПИСКА ТРАТ ЗА МЕСЯЦ")
    print("="*60)
    
    # 1. Сначала получаем данные через функцию
    result = await ExpenseFunctions.get_expenses_list(
        TEST_USER_ID,
        start_date="2025-08-01",
        end_date="2025-08-31"
    )
    
    print("\n1. СЫРЫЕ ДАННЫЕ ОТ ФУНКЦИИ:")
    print("-"*40)
    print(f"Успешно: {result.get('success')}")
    print(f"Период: {result.get('start_date')} - {result.get('end_date')}")
    print(f"Количество трат: {result.get('count')}")
    print(f"Общая сумма: {result.get('total')}")
    print(f"Первые 3 траты:")
    for exp in result.get('expenses', [])[:3]:
        print(f"  - {exp}")
    
    # 2. Теперь форматируем как в нашем коде
    print("\n2. ФОРМАТИРОВАННЫЙ ВЫВОД (наш код):")
    print("-"*40)
    
    # Эмулируем код из google_ai_service.py
    func_name = 'get_expenses_list'
    
    if result.get('success'):
        if func_name == 'get_expenses_list':
            expenses = result.get('expenses', [])
            total = result.get('total', 0)
            count = result.get('count', len(expenses))
            
            if expenses:
                response_text = f"Найдено {count} трат на сумму {total:,.0f} руб.\n"
                response_text += f"Период: с {result.get('start_date', '')} по {result.get('end_date', '')}\n\n"
                
                for exp in expenses[:50]:  # Показываем первые 50
                    date = exp.get('date', '')
                    time = exp.get('time', '')
                    desc = exp.get('description', '')
                    amount = exp.get('amount', 0)
                    
                    time_str = f" {time}" if time else ""
                    response_text += f"• {date}{time_str}: {desc} - {amount:,.0f} руб.\n"
                
                if count > 50:
                    response_text += f"\n... и еще {count - 50} трат"
                
                print(response_text)
            else:
                print("Траты за указанный период не найдены.")
    
    # 3. Тестируем с разным количеством трат
    print("\n3. ЭМУЛЯЦИЯ БОЛЬШОГО СПИСКА (60 трат):")
    print("-"*40)
    
    # Создаем тестовые данные
    test_result = {
        'success': True,
        'start_date': '2025-08-01',
        'end_date': '2025-08-31',
        'count': 60,
        'total': 157890.50,
        'expenses': []
    }
    
    # Генерируем тестовые траты
    for i in range(60):
        day = (i % 30) + 1
        test_result['expenses'].append({
            'date': f'2025-08-{day:02d}',
            'time': f'{10 + (i % 14):02d}:{(i*7) % 60:02d}',
            'amount': 500 + (i * 137) % 3000,
            'description': f'Тестовая трата №{i+1}'
        })
    
    # Форматируем
    expenses = test_result.get('expenses', [])
    total = test_result.get('total', 0)
    count = test_result.get('count', len(expenses))
    
    response_text = f"Найдено {count} трат на сумму {total:,.0f} руб.\n"
    response_text += f"Период: с {test_result.get('start_date', '')} по {test_result.get('end_date', '')}\n\n"
    
    shown_count = 0
    for exp in expenses[:50]:  # Показываем первые 50
        date = exp.get('date', '')
        time = exp.get('time', '')
        desc = exp.get('description', '')
        amount = exp.get('amount', 0)
        
        time_str = f" {time}" if time else ""
        response_text += f"• {date}{time_str}: {desc} - {amount:,.0f} руб.\n"
        shown_count += 1
    
    if count > 50:
        response_text += f"\n... и еще {count - 50} трат"
    
    # Показываем только часть вывода
    lines = response_text.split('\n')
    for line in lines[:10]:  # Первые 10 строк
        print(line)
    print("...")
    for line in lines[-5:]:  # Последние 5 строк
        print(line)
    
    print(f"\nВсего строк в выводе: {len(lines)}")
    print(f"Показано трат: {shown_count} из {count}")

async def test_other_formats():
    """Тестируем форматирование других функций"""
    
    print("\n" + "="*60)
    print("ПРИМЕРЫ ФОРМАТИРОВАНИЯ ДРУГИХ ФУНКЦИЙ")
    print("="*60)
    
    # 1. get_max_expense_day
    print("\n1. ДЕНЬ С МАКСИМАЛЬНЫМИ ТРАТАМИ:")
    print("-"*40)
    
    result = {
        'date': '2025-08-17',
        'total': 5333.0,
        'count': 3,
        'details': [
            {'time': '10:00', 'description': 'Продукты', 'amount': 1500.0, 'category': 'Еда'},
            {'time': '14:30', 'description': 'Бензин', 'amount': 2333.0, 'category': 'Транспорт'},
            {'time': '19:00', 'description': 'Кафе', 'amount': 1500.0, 'category': 'Еда'},
        ]
    }
    
    date = result.get('date', '')
    total = result.get('total', 0)
    count = result.get('count', 0)
    details = result.get('details', [])
    
    response_text = f"День с максимальными тратами: {date}\n"
    response_text += f"Всего: {total:,.0f} руб. ({count} трат)\n\n"
    
    if details:
        response_text += "Детали:\n"
        for exp in details[:20]:
            time = exp.get('time', '')
            desc = exp.get('description', '')
            amount = exp.get('amount', 0)
            category = exp.get('category', '')
            response_text += f"• {time}: {desc} - {amount:,.0f} руб. [{category}]\n"
    
    print(response_text)
    
    # 2. get_category_statistics
    print("\n2. СТАТИСТИКА ПО КАТЕГОРИЯМ:")
    print("-"*40)
    
    result = {
        'total': 150000.0,
        'categories': [
            {'name': 'Еда', 'total': 50000.0, 'count': 150, 'percentage': 33.3},
            {'name': 'Транспорт', 'total': 30000.0, 'count': 45, 'percentage': 20.0},
            {'name': 'Развлечения', 'total': 25000.0, 'count': 30, 'percentage': 16.7},
            {'name': 'Дом', 'total': 20000.0, 'count': 5, 'percentage': 13.3},
            {'name': 'Здоровье', 'total': 15000.0, 'count': 10, 'percentage': 10.0},
        ]
    }
    
    categories = result.get('categories', [])
    total = result.get('total', 0)
    
    response_text = f"Статистика по категориям (всего: {total:,.0f} руб.)\n\n"
    
    for cat in categories[:10]:
        name = cat.get('name', '')
        cat_total = cat.get('total', 0)
        count = cat.get('count', 0)
        percent = cat.get('percentage', 0)
        response_text += f"• {name}: {cat_total:,.0f} руб. ({count} шт., {percent:.1f}%)\n"
    
    print(response_text)
    
    # 3. get_daily_totals
    print("\n3. ТРАТЫ ПО ДНЯМ:")
    print("-"*40)
    
    result = {
        'total': 50000.0,
        'average': 1666.67,
        'daily_totals': {
            '2025-08-26': 3500.0,
            '2025-08-25': 2100.0,
            '2025-08-24': 0,
            '2025-08-23': 4500.0,
            '2025-08-22': 1800.0,
            '2025-08-21': 0,
            '2025-08-20': 3200.0,
        }
    }
    
    daily = result.get('daily_totals', {})
    total = result.get('total', 0)
    average = result.get('average', 0)
    
    response_text = f"Траты по дням (всего: {total:,.0f} руб., среднее: {average:,.0f} руб./день)\n\n"
    
    dates = sorted(daily.keys(), reverse=True)[:10]
    for date in dates:
        amount = daily[date]
        if amount > 0:
            response_text += f"• {date}: {amount:,.0f} руб.\n"
    
    print(response_text)

async def main():
    await test_expenses_list_formatting()
    await test_other_formats()

if __name__ == "__main__":
    asyncio.run(main())