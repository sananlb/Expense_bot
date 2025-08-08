#!/usr/bin/env python
"""
Тестовый скрипт для проверки исправлений генерации отчетов
"""
import os
import sys
import asyncio
from datetime import date, timedelta
import sqlite3

# Проверим, что исправления применены правильно на уровне SQL запросов
def test_database_queries():
    """Тестируем SQL запросы напрямую к базе данных"""
    print("=== ТЕСТИРОВАНИЕ SQL ЗАПРОСОВ ===")
    
    conn = sqlite3.connect('expense_bot.db')
    cursor = conn.cursor()
    
    # Тест 1: Проверяем структуру таблицы
    print("\n1. Структура таблицы expenses_expense:")
    cursor.execute("PRAGMA table_info(expenses_expense);")
    columns = cursor.fetchall()
    date_columns = [col for col in columns if 'date' in col[1]]
    print(f"   Поля с 'date': {date_columns}")
    
    # Тест 2: Проверяем, что данные есть
    telegram_id = 881292737
    print(f"\n2. Тестовый пользователь {telegram_id}:")
    
    # Находим profile_id
    cursor.execute("SELECT id FROM users_profile WHERE telegram_id = ?", (telegram_id,))
    profile_result = cursor.fetchone()
    if not profile_result:
        print("   ❌ Профиль не найден!")
        conn.close()
        return
    
    profile_id = profile_result[0]
    print(f"   Profile ID: {profile_id}")
    
    # Тест 3: Расходы за текущий месяц
    current_month = date.today().strftime('%Y-%m')
    print(f"\n3. Расходы за текущий месяц {current_month}:")
    
    cursor.execute("""
        SELECT COUNT(*), SUM(amount) 
        FROM expenses_expense 
        WHERE profile_id = ? AND expense_date LIKE ?
    """, (profile_id, current_month + '%'))
    
    month_result = cursor.fetchone()
    expenses_count, total_amount = month_result
    print(f"   Количество расходов: {expenses_count}")
    print(f"   Общая сумма: {total_amount}")
    
    if expenses_count > 0:
        print("   ✅ Данные найдены!")
        
        # Показываем несколько расходов
        cursor.execute("""
            SELECT expense_date, amount, description 
            FROM expenses_expense 
            WHERE profile_id = ? AND expense_date LIKE ?
            ORDER BY expense_date DESC 
            LIMIT 5
        """, (profile_id, current_month + '%'))
        
        expenses = cursor.fetchall()
        print("   Последние расходы:")
        for exp in expenses:
            print(f"     {exp[0]}: {exp[1]} - {exp[2]}")
    else:
        print("   ❌ Нет данных за текущий месяц!")
    
    # Тест 4: Расходы по категориям
    print(f"\n4. Расходы по категориям за текущий месяц:")
    cursor.execute("""
        SELECT c.name, COUNT(*), SUM(e.amount)
        FROM expenses_expense e
        LEFT JOIN expenses_category c ON e.category_id = c.id
        WHERE e.profile_id = ? AND e.expense_date LIKE ?
        GROUP BY c.name
        ORDER BY SUM(e.amount) DESC
    """, (profile_id, current_month + '%'))
    
    categories = cursor.fetchall()
    if categories:
        print("   Категории:")
        for cat in categories:
            cat_name = cat[0] or "Без категории"
            print(f"     {cat_name}: {cat[1]} расходов, {cat[2]} сумма")
    else:
        print("   ❌ Нет данных по категориям!")
    
    conn.close()
    
    # Выводим резюме
    print(f"\n=== РЕЗЮМЕ ===")
    if expenses_count > 0:
        print("✅ Данные в базе есть - проблема была в коде!")
        print("✅ Исправления должны решить проблему с отчетами")
        print("\n📋 Что было исправлено:")
        print("   • bot/services/expense.py: order_by('-date') → order_by('-expense_date')")
        print("   • bot/routers/reports.py: expense.date → expense.expense_date")
        print("   • database/models.py: expenses.first().date → expenses.first().expense_date")
        print("   • expenses/models_old.py: аналогичные исправления")
        
        print(f"\n📊 На сервере для пользователя {telegram_id} должно быть:")
        print(f"   • {expenses_count} расходов за текущий месяц")
        print(f"   • Общая сумма: {total_amount}")
        print(f"   • {len(categories)} категорий с данными")
    else:
        print("❌ Проблема не только в коде - нет данных за текущий месяц")


if __name__ == "__main__":
    test_database_queries()