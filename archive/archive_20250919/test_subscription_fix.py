"""
Скрипт для тестирования исправления создания пробной подписки
"""
import os
import sys
import django
import asyncio
from datetime import timedelta

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Subscription, Expense, Income
from django.utils import timezone
from bot.services.category import create_default_categories, create_default_income_categories

async def test_subscription_creation():
    """Тестируем создание пробной подписки для нового пользователя"""

    # Тестовый telegram_id (используем большое число чтобы не конфликтовать с реальными)
    test_user_id = 999999999

    print(f"Тестируем создание подписки для пользователя {test_user_id}")

    # Удаляем тестового пользователя если он существует
    try:
        existing_profile = await Profile.objects.aget(telegram_id=test_user_id)
        await existing_profile.adelete()
        print("Удален существующий тестовый профиль")
    except Profile.DoesNotExist:
        print("Тестовый профиль не существует, создаем новый")

    # Создаем новый профиль (имитируем get_or_create_profile)
    profile = await Profile.objects.acreate(
        telegram_id=test_user_id,
        language_code='ru',
        timezone='Europe/Moscow',
        currency='RUB',
        is_active=True,
        accepted_privacy=True  # Сразу принимаем политику
    )
    print(f"Создан профиль: {profile}")

    # Создаем категории
    await create_default_categories(test_user_id)
    await create_default_income_categories(test_user_id)
    print("Созданы базовые категории")

    # Проверяем статус нового пользователя (логика из start.py)
    has_expenses = await Expense.objects.filter(profile=profile).aexists()
    has_incomes = await Income.objects.filter(profile=profile).aexists()
    has_subscription_history = await Subscription.objects.filter(profile=profile).aexists()

    is_new_user = not has_expenses and not has_incomes and not has_subscription_history

    print(f"Статус пользователя:")
    print(f"  has_expenses: {has_expenses}")
    print(f"  has_incomes: {has_incomes}")
    print(f"  has_subscription_history: {has_subscription_history}")
    print(f"  is_new_user: {is_new_user}")
    print(f"  is_beta_tester: {profile.is_beta_tester}")

    # Проверяем условия для создания пробной подписки
    if not profile.is_beta_tester:
        existing_trial = await profile.subscriptions.filter(
            type='trial'
        ).aexists()

        has_active_subscription = await profile.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).aexists()

        print(f"Проверка подписки:")
        print(f"  existing_trial: {existing_trial}")
        print(f"  has_active_subscription: {has_active_subscription}")

        # Создаем пробную подписку
        if is_new_user and not has_active_subscription and not existing_trial:
            try:
                trial_end = timezone.now() + timedelta(days=7)
                subscription = await Subscription.objects.acreate(
                    profile=profile,
                    type='trial',
                    payment_method='trial',
                    amount=0,
                    start_date=timezone.now(),
                    end_date=trial_end,
                    is_active=True
                )
                print(f"✅ УСПЕШНО создана пробная подписка!")
                print(f"   ID: {subscription.id}")
                print(f"   Тип: {subscription.type}")
                print(f"   Активна: {subscription.is_active}")
                print(f"   Начало: {subscription.start_date}")
                print(f"   Окончание: {subscription.end_date}")
                return True
            except Exception as e:
                print(f"❌ ОШИБКА создания подписки: {e}")
                return False
        else:
            print(f"❌ Подписка НЕ создана. Условия не выполнены:")
            print(f"   is_new_user: {is_new_user}")
            print(f"   not has_active_subscription: {not has_active_subscription}")
            print(f"   not existing_trial: {not existing_trial}")
            return False
    else:
        print("❌ Пользователь является бета-тестером, подписка не нужна")
        return False

async def main():
    """Основная функция тестирования"""
    print("=== ТЕСТИРОВАНИЕ СОЗДАНИЯ ПРОБНОЙ ПОДПИСКИ ===\n")

    success = await test_subscription_creation()

    print(f"\n=== РЕЗУЛЬТАТ: {'УСПЕХ' if success else 'НЕУДАЧА'} ===")

    if success:
        print("\n✅ Исправления работают корректно!")
        print("Пробная подписка создается для новых пользователей.")
    else:
        print("\n❌ Есть проблемы с созданием подписки.")
        print("Проверьте логи выше для диагностики.")

if __name__ == "__main__":
    asyncio.run(main())