#!/usr/bin/env python
"""
Тестирование функции учета доходов как премиум-функции
"""

import os
import django
import asyncio
from decimal import Decimal

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Subscription
from bot.services.subscription import check_subscription
from bot.utils.expense_parser import detect_income_intent
from django.utils import timezone
from datetime import timedelta


async def test_income_detection():
    """Тест определения доходов"""
    print("\n=== Тест определения доходов ===")

    test_messages = [
        "+5000",
        "зарплата 100000",
        "+30000 премия",
        "кофе 200",  # Не доход
        "такси 500",  # Не доход
        "плюс 10000",
        "долг вернули +15000"
    ]

    for msg in test_messages:
        is_income = detect_income_intent(msg)
        print(f"'{msg}' -> Доход: {is_income}")


async def test_subscription_check():
    """Тест проверки подписки для доходов"""
    print("\n=== Тест проверки подписки ===")

    # Создаем тестового пользователя без подписки
    test_user_id = 999999999

    try:
        # Удаляем старого пользователя если есть
        try:
            old_profile = await Profile.objects.aget(telegram_id=test_user_id)
            await old_profile.adelete()
        except Profile.DoesNotExist:
            pass

        # Создаем нового пользователя без подписки
        profile = await Profile.objects.acreate(
            telegram_id=test_user_id
        )

        # Проверяем что у пользователя нет подписки
        has_subscription = await check_subscription(test_user_id)
        print(f"Пользователь без подписки: has_subscription = {has_subscription}")
        assert has_subscription == False, "У нового пользователя не должно быть подписки"

        # Добавляем активную подписку
        subscription = await Subscription.objects.acreate(
            profile=profile,
            type='monthly',
            is_active=True,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30)
        )

        # Проверяем что теперь есть подписка
        has_subscription = await check_subscription(test_user_id)
        print(f"Пользователь с подпиской: has_subscription = {has_subscription}")
        assert has_subscription == True, "У пользователя с активной подпиской должен быть доступ"

        # Деактивируем подписку
        subscription.is_active = False
        await subscription.asave()

        # Проверяем что подписки больше нет
        has_subscription = await check_subscription(test_user_id)
        print(f"Пользователь с неактивной подпиской: has_subscription = {has_subscription}")
        assert has_subscription == False, "У пользователя с неактивной подпиской не должно быть доступа"

        print("\n[OK] Все тесты проверки подписки пройдены успешно!")

    finally:
        # Очистка тестовых данных
        try:
            profile = await Profile.objects.aget(telegram_id=test_user_id)
            await profile.adelete()
        except Profile.DoesNotExist:
            pass


async def test_premium_income_message():
    """Тест сообщения о премиум-функции"""
    print("\n=== Тест сообщения о необходимости подписки ===")

    expected_message = """[X] <b>Учет доходов — премиум функция</b>

Функция учета доходов доступна только по подписке.

С подпиской вы получите:
• Полный учет доходов и расходов
• Голосовой ввод трат
• PDF отчеты
• Семейный бюджет
• Кешбэк менеджер
• Расширенная аналитика

Оформите подписку, чтобы вести полноценный учет финансов!"""

    print("Ожидаемое сообщение при попытке ввода дохода без подписки:")
    print("-" * 50)
    print(expected_message)
    print("-" * 50)


async def main():
    """Главная функция тестирования"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ФУНКЦИИ УЧЕТА ДОХОДОВ КАК ПРЕМИУМ-ФУНКЦИИ")
    print("=" * 60)

    await test_income_detection()
    await test_subscription_check()
    await test_premium_income_message()

    print("\n" + "=" * 60)
    print("[OK] ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())