#!/usr/bin/env python
"""
Тестирование функционала исключения кешбека
"""
import os
import sys
import django
import asyncio
from decimal import Decimal
from datetime import date, datetime
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, Expense, Cashback
from bot.services.cashback import calculate_potential_cashback


async def test_cashback_exclusion():
    """Тестирование исключения кешбека для конкретной траты"""
    
    # Используем тестового пользователя
    TEST_USER_ID = 123456789
    
    try:
        # Создаем или получаем профиль
        profile, _ = await Profile.objects.aget_or_create(
            telegram_id=TEST_USER_ID,
            defaults={'currency': 'RUB'}
        )
        print(f"✅ Профиль создан/получен: {profile}")
        
        # Создаем категорию
        category, _ = await ExpenseCategory.objects.aget_or_create(
            profile=profile,
            name="Тест категория",
            defaults={'icon': '🧪'}
        )
        print(f"✅ Категория создана: {category}")
        
        # Создаем кешбек для категории
        current_month = datetime.now().month
        cashback, _ = await Cashback.objects.aget_or_create(
            profile=profile,
            category=category,
            bank_name="Тестовый банк",
            month=current_month,
            defaults={'cashback_percent': Decimal('5.0')}
        )
        print(f"✅ Кешбек создан: {cashback.cashback_percent}% для {category.name}")
        
        # Создаем две траты
        expense1 = await Expense.objects.acreate(
            profile=profile,
            category=category,
            amount=Decimal('1000'),
            description="Тестовая трата 1",
            expense_date=date.today(),
            cashback_excluded=False  # С кешбеком
        )
        print(f"✅ Трата 1 создана: {expense1.amount} руб (кешбек включен)")
        
        expense2 = await Expense.objects.acreate(
            profile=profile,
            category=category,
            amount=Decimal('2000'),
            description="Тестовая трата 2",
            expense_date=date.today(),
            cashback_excluded=True  # БЕЗ кешбека
        )
        print(f"✅ Трата 2 создана: {expense2.amount} руб (кешбек ИСКЛЮЧЕН)")
        
        # Рассчитываем общий кешбек
        start_date = date.today().replace(day=1)
        end_date = date.today()
        
        total_cashback = await calculate_potential_cashback(
            user_id=TEST_USER_ID,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"\n📊 Результаты расчета:")
        print(f"   Трата 1: {expense1.amount} руб × 5% = {expense1.amount * Decimal('0.05')} руб кешбека")
        print(f"   Трата 2: {expense2.amount} руб × 0% = 0 руб (исключена)")
        print(f"   Итого кешбек: {total_cashback} руб")
        
        # Проверяем, что кешбек считается только для первой траты
        expected_cashback = expense1.amount * Decimal('0.05')  # 1000 * 0.05 = 50
        
        if total_cashback == expected_cashback:
            print(f"\n✅ ТЕСТ ПРОЙДЕН! Кешбек правильно исключен для траты 2")
            print(f"   Ожидалось: {expected_cashback} руб")
            print(f"   Получено: {total_cashback} руб")
        else:
            print(f"\n❌ ТЕСТ ПРОВАЛЕН!")
            print(f"   Ожидалось: {expected_cashback} руб")
            print(f"   Получено: {total_cashback} руб")
        
        # Тестируем изменение флага
        print(f"\n🔄 Тестируем изменение флага исключения...")
        expense2.cashback_excluded = False
        await expense2.asave()
        
        total_cashback_after = await calculate_potential_cashback(
            user_id=TEST_USER_ID,
            start_date=start_date,
            end_date=end_date
        )
        
        expected_cashback_after = (expense1.amount + expense2.amount) * Decimal('0.05')  # 3000 * 0.05 = 150
        
        if total_cashback_after == expected_cashback_after:
            print(f"✅ Флаг успешно изменен, кешбек пересчитан")
            print(f"   Теперь кешбек: {total_cashback_after} руб")
        else:
            print(f"❌ Ошибка при изменении флага")
            print(f"   Ожидалось: {expected_cashback_after} руб")
            print(f"   Получено: {total_cashback_after} руб")
        
        # Очищаем тестовые данные
        print(f"\n🧹 Очищаем тестовые данные...")
        await Expense.objects.filter(profile=profile).adelete()
        await Cashback.objects.filter(profile=profile).adelete()
        await ExpenseCategory.objects.filter(profile=profile).adelete()
        await Profile.objects.filter(telegram_id=TEST_USER_ID).adelete()
        print(f"✅ Тестовые данные удалены")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("Тестирование функционала исключения кешбека")
    print("=" * 60)
    asyncio.run(test_cashback_exclusion())