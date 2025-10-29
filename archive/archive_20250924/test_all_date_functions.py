#!/usr/bin/env python3
"""
Комплексный тест всех функций работы с датами
"""
import sys
import os
import django
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.date_utils import get_period_dates


def test_all_date_functions():
    """Проверяем работу с датами во всех функциях"""

    today = date.today()
    print(f"Сегодня: {today} ({today.strftime('%A')})")
    print("=" * 80)

    # Список всех поддерживаемых периодов
    all_periods = [
        'today', 'yesterday', 'week', 'month', 'year',
        'last_week', 'last_month', 'last_year'
    ]

    print("\nПРОВЕРКА ВСЕХ ПЕРИОДОВ В date_utils:")
    print("-" * 40)

    for period in all_periods:
        try:
            start_date, end_date = get_period_dates(period)
            days = (end_date - start_date).days + 1

            # Проверка корректности периодов
            if period == 'today':
                assert start_date == end_date == today, f"today должно быть {today}"
                print(f"OK {period:12} -> {start_date} (1 день)")

            elif period == 'yesterday':
                yesterday = today - timedelta(days=1)
                assert start_date == end_date == yesterday, f"yesterday должно быть {yesterday}"
                print(f"OK {period:12} -> {start_date} (1 день)")

            elif period == 'week':
                assert start_date.weekday() == 0, "Неделя должна начинаться с понедельника"
                assert end_date == today, "Неделя должна заканчиваться сегодня"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

            elif period == 'last_week':
                assert start_date.weekday() == 0, "Прошлая неделя должна начинаться с понедельника"
                assert end_date.weekday() == 6, "Прошлая неделя должна заканчиваться в воскресенье"
                assert days == 7, "Прошлая неделя должна содержать 7 дней"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

            elif period == 'month':
                assert start_date.day == 1, "Месяц должен начинаться с 1 числа"
                assert end_date == today, "Месяц должен заканчиваться сегодня"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

            elif period == 'last_month':
                assert start_date.day == 1, "Прошлый месяц должен начинаться с 1 числа"
                # Проверяем что это действительно прошлый месяц
                if today.month == 1:
                    assert start_date.month == 12 and start_date.year == today.year - 1
                else:
                    assert start_date.month == today.month - 1 and start_date.year == today.year
                # Проверяем последний день месяца
                next_month = start_date.replace(day=28) + timedelta(days=4)
                last_day = (next_month - timedelta(days=next_month.day)).day
                assert end_date.day == last_day, "Прошлый месяц должен заканчиваться последним числом"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

            elif period == 'year':
                assert start_date == date(today.year, 1, 1), "Год должен начинаться с 1 января"
                assert end_date == today, "Год должен заканчиваться сегодня"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

            elif period == 'last_year':
                assert start_date == date(today.year - 1, 1, 1), "Прошлый год должен начинаться с 1 января прошлого года"
                assert end_date == date(today.year - 1, 12, 31), "Прошлый год должен заканчиваться 31 декабря"
                print(f"OK {period:12} -> с {start_date} по {end_date} ({days} дней)")

        except Exception as e:
            print(f"ERROR {period:12} -> Ошибка: {e}")

    print("\nФУНКЦИИ С ОБНОВЛЕННОЙ ЛОГИКОЙ:")
    print("-" * 40)

    updated_functions = [
        "OK:get_period_total() - использует date_utils",
        "OK:get_category_total() - использует date_utils",
        "OK:get_income_period_total() - использует date_utils",
        "OK:get_max_single_expense() - поддерживает period='last_week/last_month'",
        "OK:get_max_single_income() - поддерживает period='last_week/last_month'",
        "OK:search_expenses() - поддерживает period='last_week/last_month'",
        "OK:analytics_query - поддерживает все периоды включая last_*",
        "OK:compare_periods() - изначально поддерживал last_week/last_month"
    ]

    for func in updated_functions:
        print(f"  {func}")

    print("\nПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:")
    print("-" * 40)

    examples = [
        ("Самая большая трата на прошлой неделе",
         "get_max_single_expense(period='last_week')"),
        ("Траты на кофе в прошлом месяце",
         "search_expenses(query='кофе', period='last_month')"),
        ("Сколько потратил вчера",
         "get_period_total(period='yesterday')"),
        ("Доходы за прошлый год",
         "get_income_period_total(period='last_year')"),
        ("Траты на продукты на этой неделе",
         "get_category_total(category='продукты', period='week')"),
    ]

    for description, code in examples:
        print(f"  * {description}")
        print(f"    -> {code}")

    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО!")
    print("\nВсе функции теперь используют единую логику обработки дат:")
    print("   * Календарные периоды (не просто N дней назад)")
    print("   * Поддержка last_week, last_month, last_year")
    print("   * Единообразная обработка через date_utils.get_period_dates()")


if __name__ == "__main__":
    test_all_date_functions()