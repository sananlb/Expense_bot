"""
Async тестовый скрипт для проверки get_category_total с сравнением периодов
"""
import os
import sys
import django
import asyncio
from datetime import date

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.expense_functions import ExpenseFunctions
from bot.services.response_formatter import format_function_result


async def test_get_category_total():
    """
    Тестирование функции get_category_total с новым функционалом сравнения
    """
    # Ваш Telegram ID
    user_id = 881292737

    print("=" * 80)
    print("ASYNC ТЕСТ: get_category_total с сравнением периодов")
    print("=" * 80)

    # Тестовые категории и периоды
    test_cases = [
        {
            'category': 'Родственники',
            'period': 'ноябрь',
            'description': 'Ноябрь 2025 (есть траты)'
        },
        {
            'category': 'Подарки',
            'period': 'ноябрь',
            'description': 'Ноябрь 2025 - Подарки'
        },
        {
            'category': 'Родственники',
            'period': 'декабрь',
            'description': 'Декабрь 2025 (нет трат)'
        },
        {
            'category': 'Спорт',
            'period': 'last_month',
            'description': 'Прошлый месяц - Спорт'
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        category = test_case['category']
        period = test_case['period']
        description = test_case['description']

        print(f"\n{'=' * 80}")
        print(f"ТЕСТ {i}/{len(test_cases)}: {description}")
        print('=' * 80)

        # Вызываем функцию
        result = await ExpenseFunctions.get_category_total(
            user_id=user_id,
            category=category,
            period=period
        )

        if not result.get('success'):
            print(f"❌ Ошибка: {result.get('message')}")
            continue

        # Выводим сырые данные
        print("\n📊 Результат функции (JSON):")
        print(f"  success: {result.get('success')}")
        print(f"  category: {result.get('category')}")
        print(f"  period: {result.get('period')}")
        print(f"  start_date: {result.get('start_date')}")
        print(f"  end_date: {result.get('end_date')}")
        print(f"  count: {result.get('count')}")
        print(f"  total: {result.get('total'):,.0f} ₽")
        print(f"  average: {result.get('average'):,.0f} ₽")
        print(f"  currency: {result.get('currency')}")

        # Проверяем сравнение с предыдущим периодом
        comparison = result.get('previous_comparison')
        if comparison:
            print("\n📈 Данные сравнения:")
            print(f"  previous_period:")
            print(f"    start: {comparison['previous_period']['start']}")
            print(f"    end: {comparison['previous_period']['end']}")
            print(f"  previous_count: {comparison['previous_count']}")
            print(f"  previous_total: {comparison['previous_total']:,.0f} ₽")
            print(f"  difference: {comparison['difference']:,.0f} ₽")
            print(f"  percent_change: {comparison['percent_change']}%")
            print(f"  trend: {comparison['trend']}")
        else:
            print("\n📊 previous_comparison: None (нет трат в предыдущем периоде)")

        # Форматированный вывод для пользователя
        formatted = format_function_result('get_category_total', result)
        print("\n💬 ФОРМАТИРОВАННЫЙ ВЫВОД ДЛЯ ПОЛЬЗОВАТЕЛЯ:")
        print("─" * 80)
        print(formatted)
        print("─" * 80)

    print(f"\n{'=' * 80}")
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print('=' * 80)

    # Демонстрация разных сценариев
    print(f"\n{'=' * 80}")
    print("ДЕМОНСТРАЦИЯ СЦЕНАРИЕВ:")
    print('=' * 80)

    scenarios = [
        {
            'title': '1. Траты увеличились',
            'current': 15000,
            'previous': 10000,
            'expected': '+50% больше'
        },
        {
            'title': '2. Траты уменьшились',
            'current': 7500,
            'previous': 10000,
            'expected': '-25% меньше'
        },
        {
            'title': '3. Без изменений',
            'current': 10000,
            'previous': 10000,
            'expected': 'без изменений'
        },
        {
            'title': '4. Не было трат в предыдущем периоде',
            'current': 5000,
            'previous': 0,
            'expected': 'нет сравнения'
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['title']}:")
        print(f"  Текущий период: {scenario['current']:,.0f} ₽")
        print(f"  Предыдущий период: {scenario['previous']:,.0f} ₽")
        print(f"  Ожидаемый результат: {scenario['expected']}")

        if scenario['previous'] > 0:
            diff = scenario['current'] - scenario['previous']
            pct = ((scenario['current'] - scenario['previous']) / scenario['previous']) * 100

            if diff > 0:
                print(f"  ✅ Результат: 📈 На {abs(pct):.1f}% больше (было {scenario['previous']:,.0f} ₽)")
            elif diff < 0:
                print(f"  ✅ Результат: 📉 На {abs(pct):.1f}% меньше (было {scenario['previous']:,.0f} ₽)")
            else:
                print(f"  ✅ Результат: ➡️ Сумма не изменилась ({scenario['previous']:,.0f} ₽)")
        else:
            print(f"  ✅ Результат: ℹ️ Сравнение недоступно (нет трат в предыдущем периоде)")


if __name__ == '__main__':
    asyncio.run(test_get_category_total())
