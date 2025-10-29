#!/usr/bin/env python3
"""
Тест для проверки как AI интерпретирует временные периоды
"""
import sys
import os
import django
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

def test_time_periods_interpretation():
    """Проверяем как различные временные выражения обрабатываются в системе"""

    today = date.today()
    print(f"Сегодня: {today}")
    print("=" * 50)

    # Случай 1: "прошлый месяц" в промпте для search_expenses
    # Согласно промпту, AI должен преобразовать его в конкретные даты
    print("\n1. Запрос: 'сколько я потратил на кофе в прошлом месяце'")
    print("Согласно промпту в prompt_builder.py:")
    print("AI должен вызвать: search_expenses(query='кофе', start_date='2025-08-01', end_date='2025-08-31')")
    print("(если сегодня сентябрь 2025)")

    # Случай 2: "на прошлой неделе" для get_max_single_expense
    print("\n2. Запрос: 'какая моя самая большая трата на прошлой неделе'")
    print("Текущая реализация после нашего исправления:")
    print("AI передает period='week' -> преобразуется в period_days=7")
    print(f"Это означает период с {today - timedelta(days=7)} по {today}")
    print("НО 'прошлая неделя' != 'последние 7 дней'!")

    # Случай 3: Что на самом деле означает "прошлая неделя"
    print("\n3. Правильная интерпретация 'прошлая неделя':")
    current_weekday = today.weekday()  # 0 = понедельник
    start_of_this_week = today - timedelta(days=current_weekday)
    end_of_last_week = start_of_this_week - timedelta(days=1)
    start_of_last_week = end_of_last_week - timedelta(days=6)
    print(f"Прошлая неделя: с {start_of_last_week} по {end_of_last_week}")

    # Случай 4: Проверяем compare_periods
    print("\n4. Функция compare_periods имеет специальную логику:")
    print("period='last_week' обрабатывается правильно:")
    print("p2_end = p1_start - timedelta(days=1)")
    print("p2_start = p2_end - timedelta(days=6)")

    # Случай 5: analytics_query
    print("\n5. analytics_query поддерживает только:")
    print("period=['today', 'yesterday', 'week', 'month', 'year']")
    print("где 'week' = текущая неделя с понедельника")
    print("НЕТ поддержки 'last_week', 'last_month'")

    print("\n" + "=" * 50)
    print("\nВЫВОДЫ:")
    print("1. Для search_expenses: AI должен сам вычислить даты прошлого месяца")
    print("2. Для get_max_single_expense: 'week' интерпретируется как последние 7 дней")
    print("3. compare_periods: есть правильная обработка 'last_week'")
    print("4. analytics_query: не поддерживает 'прошлый' период")
    print("\nПРОБЛЕМА: Нет единообразной обработки 'прошлый месяц/неделя'")

if __name__ == "__main__":
    test_time_periods_interpretation()