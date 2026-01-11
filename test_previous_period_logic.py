"""
Тест логики определения предыдущего периода для месяцев разной длины
"""
import os
import sys
from datetime import date, timedelta

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Копируем функцию для тестирования
def _get_previous_period(start_date: date, end_date: date, period: str) -> tuple:
    """
    Определяет предыдущий период на основе текущего периода.

    Для месяцев возвращает предыдущий календарный месяц (полный).
    Для других периодов - период такой же длины перед текущим.
    """
    period_lower = period.lower() if period else ''

    # Список названий месяцев на разных языках
    month_names = {
        'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
        'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    }

    # Проверяем, является ли период месяцем
    is_month_period = (
        # Явно указан месяц по названию
        period_lower in month_names or
        # Период типа "month" или "last_month"
        period_lower in ('month', 'this_month', 'last_month') or
        # Начинается с 1-го числа месяца И это не год/сезон/числовой период
        (start_date.day == 1 and
         period_lower not in ('year', 'this_year', 'last_year',
                              'зима', 'весна', 'лето', 'осень',
                              'winter', 'spring', 'summer', 'autumn', 'fall',
                              'зимой', 'весной', 'летом', 'осенью') and
         not period_lower.isdigit())  # И это не числовой период типа "30"
    )

    if is_month_period:
        # Для месяцев используем календарную логику
        # Последний день предыдущего месяца
        prev_end_date = start_date - timedelta(days=1)
        # Первый день предыдущего месяца
        prev_start_date = prev_end_date.replace(day=1)
        return prev_start_date, prev_end_date
    else:
        # Для других периодов (год, сезон, неделя, кастомные даты) - берем период такой же длины
        period_days = (end_date - start_date).days + 1
        prev_start_date = start_date - timedelta(days=period_days)
        prev_end_date = end_date - timedelta(days=period_days)
        return prev_start_date, prev_end_date


def test_previous_period_logic():
    """
    Тестируем определение предыдущего периода
    """
    print("=" * 80)
    print("ТЕСТ: Определение предыдущего периода для месяцев разной длины")
    print("=" * 80)

    test_cases = [
        {
            'name': 'Март 2025 (31 день)',
            'current_start': date(2025, 3, 1),
            'current_end': date(2025, 3, 31),
            'expected_prev_start': date(2025, 2, 1),
            'expected_prev_end': date(2025, 2, 28),
            'period': 'март'
        },
        {
            'name': 'Февраль 2025 (28 дней)',
            'current_start': date(2025, 2, 1),
            'current_end': date(2025, 2, 28),
            'expected_prev_start': date(2025, 1, 1),
            'expected_prev_end': date(2025, 1, 31),
            'period': 'февраль'
        },
        {
            'name': 'Январь 2025 (31 день)',
            'current_start': date(2025, 1, 1),
            'current_end': date(2025, 1, 31),
            'expected_prev_start': date(2024, 12, 1),
            'expected_prev_end': date(2024, 12, 31),
            'period': 'январь'
        },
        {
            'name': 'Декабрь 2025 (31 день)',
            'current_start': date(2025, 12, 1),
            'current_end': date(2025, 12, 31),
            'expected_prev_start': date(2025, 11, 1),
            'expected_prev_end': date(2025, 11, 30),
            'period': 'декабрь'
        },
        {
            'name': 'Апрель 2025 (30 дней)',
            'current_start': date(2025, 4, 1),
            'current_end': date(2025, 4, 30),
            'expected_prev_start': date(2025, 3, 1),
            'expected_prev_end': date(2025, 3, 31),
            'period': 'апрель'
        },
        {
            'name': 'Февраль 2024 високосный (29 дней)',
            'current_start': date(2024, 2, 1),
            'current_end': date(2024, 2, 29),
            'expected_prev_start': date(2024, 1, 1),
            'expected_prev_end': date(2024, 1, 31),
            'period': 'февраль'
        },
        {
            'name': 'Неделя (не месяц)',
            'current_start': date(2025, 1, 6),  # Понедельник
            'current_end': date(2025, 1, 12),   # Воскресенье
            'expected_prev_start': date(2024, 12, 30),  # 7 дней назад
            'expected_prev_end': date(2025, 1, 5),
            'period': 'week'
        },
        {
            'name': 'Год 2025 (365 дней)',
            'current_start': date(2025, 1, 1),
            'current_end': date(2025, 12, 31),
            'expected_prev_start': date(2024, 1, 2),  # 365 дней назад (2024 был високосным - 366 дней)
            'expected_prev_end': date(2024, 12, 31),
            'period': 'year'
        },
        {
            'name': 'Лето 2025 (сезон начинается с 1 июня)',
            'current_start': date(2025, 6, 1),
            'current_end': date(2025, 8, 31),
            'expected_prev_start': date(2025, 3, 1),  # 92 дня назад (март-май)
            'expected_prev_end': date(2025, 5, 31),
            'period': 'лето'
        },
        {
            'name': 'Зима 2024-2025 (начинается с 1 декабря)',
            'current_start': date(2024, 12, 1),
            'current_end': date(2025, 2, 28),
            'expected_prev_start': date(2024, 9, 2),  # 90 дней назад
            'expected_prev_end': date(2024, 11, 30),
            'period': 'зима'
        },
        {
            'name': 'Числовой период "30" (30 дней)',
            'current_start': date(2025, 1, 15),
            'current_end': date(2025, 2, 13),
            'expected_prev_start': date(2024, 12, 16),  # 30 дней назад
            'expected_prev_end': date(2025, 1, 14),
            'period': '30'
        },
    ]

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"ТЕСТ {i}: {test['name']}")
        print('=' * 80)

        current_start = test['current_start']
        current_end = test['current_end']
        current_days = (current_end - current_start).days + 1

        print(f"📅 Текущий период: {current_start} — {current_end} ({current_days} дней)")

        # Вызываем функцию
        prev_start, prev_end = _get_previous_period(
            current_start,
            current_end,
            test['period']
        )

        prev_days = (prev_end - prev_start).days + 1

        print(f"📅 Предыдущий период: {prev_start} — {prev_end} ({prev_days} дней)")

        # Проверяем ожидаемый результат
        expected_start = test['expected_prev_start']
        expected_end = test['expected_prev_end']

        print(f"🎯 Ожидается: {expected_start} — {expected_end}")

        if prev_start == expected_start and prev_end == expected_end:
            print("✅ PASSED")
        else:
            print("❌ FAILED")
            print(f"   Получено:  {prev_start} — {prev_end}")
            print(f"   Ожидалось: {expected_start} — {expected_end}")
            all_passed = False

        # Дополнительная информация - реальная логика определения
        period_lower = test['period'].lower()
        month_names = {
            'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
            'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        }
        is_month_period = (
            period_lower in month_names or
            period_lower in ('month', 'this_month', 'last_month') or
            (current_start.day == 1 and
             period_lower not in ('year', 'this_year', 'last_year',
                                  'зима', 'весна', 'лето', 'осень',
                                  'winter', 'spring', 'summer', 'autumn', 'fall',
                                  'зимой', 'весной', 'летом', 'осенью') and
             not period_lower.isdigit())
        )
        print(f"ℹ️  Распознано как месяц: {'Да' if is_month_period else 'Нет'}")

    print(f"\n{'=' * 80}")
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
    print('=' * 80)

    # Демонстрация проблемы старой логики
    print(f"\n{'=' * 80}")
    print("ДЕМОНСТРАЦИЯ ПРОБЛЕМЫ СТАРОЙ ЛОГИКИ")
    print('=' * 80)

    print("\n🔴 Старая логика (по количеству дней):")
    print("   Март 2025 (31 день) → Предыдущий период: 31 день назад")

    march_start = date(2025, 3, 1)
    march_end = date(2025, 3, 31)
    march_days = 31

    old_prev_end = march_start - timedelta(days=1)  # 28 февраля
    old_prev_start = old_prev_end - timedelta(days=march_days - 1)  # 31 день назад

    print(f"   Получится: {old_prev_start} — {old_prev_end}")
    print(f"   ❌ Это НЕ февраль! Это конец января + весь февраль")

    print("\n✅ Новая логика (календарный месяц):")
    print("   Март 2025 → Февраль 2025")
    feb_start = date(2025, 2, 1)
    feb_end = date(2025, 2, 28)
    print(f"   Получится: {feb_start} — {feb_end}")
    print(f"   ✅ Правильный полный календарный месяц (28 дней)")


if __name__ == '__main__':
    test_previous_period_logic()
