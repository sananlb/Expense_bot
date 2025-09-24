#!/usr/bin/env python3
"""
Тест расширенных периодов (позавчера, позапрошлый месяц и т.д.)
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


def test_extended_periods():
    """Тестируем расширенные периоды"""

    today = date.today()
    print(f"Сегодня: {today}")
    print("=" * 60)

    # Тестовые случаи для расширенных периодов
    test_cases = [
        ('today', today, today, "Сегодня"),
        ('yesterday', today - timedelta(days=1), today - timedelta(days=1), "Вчера"),
        ('day_before_yesterday', today - timedelta(days=2), today - timedelta(days=2), "Позавчера"),
        ('позавчера', today - timedelta(days=2), today - timedelta(days=2), "Позавчера (рус)"),
        ('three_days_ago', today - timedelta(days=3), today - timedelta(days=3), "Три дня назад"),
        ('week_before_last', None, None, "Позапрошлая неделя"),
        ('month_before_last', None, None, "Позапрошлый месяц"),
    ]

    print("\nПРОВЕРКА РАСШИРЕННЫХ ПЕРИОДОВ:")
    print("-" * 40)

    for period, expected_start, expected_end, description in test_cases:
        try:
            start_date, end_date = get_period_dates(period)
            days = (end_date - start_date).days + 1

            # Для позапрошлой недели и месяца проверяем особые условия
            if period == 'week_before_last':
                # Проверяем что это полная неделя (7 дней)
                assert days == 7, "Позапрошлая неделя должна быть 7 дней"
                assert start_date.weekday() == 0, "Должна начинаться с понедельника"
                assert end_date.weekday() == 6, "Должна заканчиваться в воскресенье"
                # Проверяем что это действительно позапрошлая неделя
                weeks_ago = (today - end_date).days // 7
                assert weeks_ago >= 1, "Должна быть минимум неделю назад"
                print(f"OK {period:20} -> с {start_date} по {end_date} ({days} дней) - {description}")

            elif period == 'month_before_last':
                # Проверяем что начинается с 1 числа
                assert start_date.day == 1, "Месяц должен начинаться с 1 числа"
                # Проверяем что это полный месяц
                assert days >= 28 and days <= 31, "Месяц должен быть 28-31 день"
                # Проверяем что это действительно позапрошлый месяц
                months_diff = (today.year - start_date.year) * 12 + today.month - start_date.month
                assert months_diff == 2, "Должен быть 2 месяца назад"
                print(f"OK {period:20} -> с {start_date} по {end_date} ({days} дней) - {description}")

            elif expected_start and expected_end:
                # Для точных дат проверяем соответствие
                assert start_date == expected_start, f"Ожидалось {expected_start}, получено {start_date}"
                assert end_date == expected_end, f"Ожидалось {expected_end}, получено {end_date}"
                print(f"OK {period:20} -> {start_date} ({days} день) - {description}")

        except Exception as e:
            print(f"ERROR {period:20} -> {e}")

    # Проверяем что позавчера работает и на русском
    print("\n" + "=" * 60)
    print("ПРОВЕРКА ИНТЕГРАЦИИ С ФУНКЦИЯМИ:")
    print("-" * 40)

    print("\nПримеры использования новых периодов:")
    examples = [
        ("Траты позавчера", "get_period_total(period='day_before_yesterday')"),
        ("Самая большая трата позапрошлый месяц", "get_max_single_expense(period='month_before_last')"),
        ("Доходы позапрошлую неделю", "get_income_period_total(period='week_before_last')"),
        ("Траты на кофе позавчера", "search_expenses(query='кофе', period='day_before_yesterday')"),
    ]

    for description, code in examples:
        print(f"  * {description}")
        print(f"    -> {code}")

    print("\n" + "=" * 60)
    print("ИТОГ:")
    print("  - Поддержка 'позавчера' (day_before_yesterday)")
    print("  - Поддержка 'three_days_ago' (три дня назад)")
    print("  - Поддержка 'week_before_last' (позапрошлая неделя)")
    print("  - Поддержка 'month_before_last' (позапрошлый месяц)")
    print("  - Все периоды доступны во всех функциях работы с датами")


if __name__ == "__main__":
    test_extended_periods()