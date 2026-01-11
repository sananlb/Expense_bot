"""
Тест сравнения периодов в search_expenses
"""
import os
import sys
import django
import asyncio

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


async def test_search_with_comparison():
    """
    Тестирование search_expenses с сравнением периодов
    """
    user_id = 881292737

    print("=" * 80)
    print("ТЕСТ: search_expenses с сравнением периодов")
    print("=" * 80)

    test_cases = [
        {
            'query': 'Родственники',
            'period': 'last_month',
            'description': 'Поиск "Родственники" за прошлый месяц'
        },
        {
            'query': 'Подарки',
            'period': 'ноябрь',
            'description': 'Поиск "Подарки" за ноябрь'
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        query = test_case['query']
        period = test_case['period']
        description = test_case['description']

        print(f"\n{'=' * 80}")
        print(f"ТЕСТ {i}: {description}")
        print('=' * 80)

        # Вызываем функцию
        result = await ExpenseFunctions.search_expenses(
            user_id=user_id,
            query=query,
            period=period
        )

        if not result.get('success'):
            print(f"❌ Ошибка: {result.get('message')}")
            continue

        # Выводим результаты
        print("\n📊 Результат функции:")
        print(f"  query: {result.get('query')}")
        print(f"  period: {period}")
        print(f"  start_date: {result.get('start_date')}")
        print(f"  end_date: {result.get('end_date')}")
        print(f"  count: {result.get('count')}")
        print(f"  total: {result.get('total'):,.0f} ₽")

        # Проверяем сравнение
        comparison = result.get('previous_comparison')
        if comparison:
            print("\n📈 Сравнение с предыдущим периодом:")
            print(f"  previous_period: {comparison['previous_period']['start']} — {comparison['previous_period']['end']}")
            print(f"  previous_count: {comparison['previous_count']}")
            print(f"  previous_total: {comparison['previous_total']:,.0f} ₽")
            print(f"  difference: {comparison['difference']:,.0f} ₽")
            print(f"  percent_change: {comparison['percent_change']}%")
            print(f"  trend: {comparison['trend']}")
        else:
            print("\n📊 Сравнение: не доступно (нет данных в предыдущем периоде)")

        # Форматированный вывод
        formatted = format_function_result('search_expenses', result)
        print("\n💬 Форматированный вывод:")
        print("─" * 80)
        # Убираем HTML теги для читаемости
        import re
        clean_text = re.sub(r'<[^>]+>', '', formatted)
        print(clean_text)
        print("─" * 80)

    print(f"\n{'=' * 80}")
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(test_search_with_comparison())
