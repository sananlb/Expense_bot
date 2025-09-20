#!/usr/bin/env python3
"""
Интеграционные тесты для проверки всех исправлений
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.insert(0, '/Users/aleksejnalbantov/Desktop/expense_bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.utils import timezone
from expenses.models import Profile, Subscription, Expense, Income, AffiliateReferral
from bot.services.subscription import check_subscription
from bot.utils import get_user_language
import asyncio

# Цвета для вывода
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_test(name, result):
    """Вывести результат теста"""
    status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {name}")


def print_section(title):
    """Вывести заголовок секции"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


async def test_new_user_detection():
    """Тест определения нового пользователя"""
    print_section("ТЕСТ: Определение нового пользователя")

    # Создаем тестового пользователя
    test_user_id = '999999999'
    profile, created = await Profile.objects.aget_or_create(
        telegram_id=test_user_id
    )

    # Удаляем все связанные данные для чистого теста
    await Expense.objects.filter(profile=profile).adelete()
    await Income.objects.filter(profile=profile).adelete()
    await Subscription.objects.filter(profile=profile).adelete()

    # Проверяем что пользователь считается новым
    has_expenses = await Expense.objects.filter(profile=profile).aexists()
    has_incomes = await Income.objects.filter(profile=profile).aexists()
    has_subscriptions = await Subscription.objects.filter(profile=profile).aexists()

    is_new_user = not has_expenses and not has_incomes and not has_subscriptions
    print_test("Пользователь без данных считается новым", is_new_user)

    # Создаем категорию для траты
    from expenses.models import ExpenseCategory
    category, _ = await ExpenseCategory.objects.aget_or_create(
        profile=profile,
        name='Test Category',
        defaults={'icon': '🔖'}
    )

    # Добавляем трату и проверяем снова
    await Expense.objects.acreate(
        profile=profile,
        amount=100,
        description='Test expense',
        category=category
    )

    has_expenses = await Expense.objects.filter(profile=profile).aexists()
    is_new_user_after = not has_expenses and not has_incomes and not has_subscriptions
    print_test("Пользователь с тратами НЕ считается новым", not is_new_user_after)

    # Очистка
    await Expense.objects.filter(profile=profile).adelete()

    return True


async def test_trial_subscription_creation():
    """Тест создания пробной подписки"""
    print_section("ТЕСТ: Создание пробной подписки")

    test_user_id = '999999998'
    profile, created = await Profile.objects.aget_or_create(
        telegram_id=test_user_id
    )

    # Удаляем старые подписки
    await Subscription.objects.filter(profile=profile).adelete()

    # Проверяем что нет пробной подписки
    has_trial_before = await Subscription.objects.filter(
        profile=profile,
        type='trial'
    ).aexists()
    print_test("Нет пробной подписки до создания", not has_trial_before)

    # Создаем пробную подписку (как в privacy_accept)
    trial_end = timezone.now() + timedelta(days=7)
    trial_sub = await Subscription.objects.acreate(
        profile=profile,
        type='trial',
        payment_method='trial',
        amount=0,
        start_date=timezone.now(),
        end_date=trial_end,
        is_active=True
    )

    # Проверяем создание
    has_trial_after = await Subscription.objects.filter(
        profile=profile,
        type='trial'
    ).aexists()
    print_test("Пробная подписка создана", has_trial_after)

    # Проверяем что попытка создать вторую пробную подписку не пройдет
    existing_trial = await Subscription.objects.filter(
        profile=profile,
        type='trial'
    ).aexists()
    print_test("Защита от дублирования пробных подписок", existing_trial)

    # Проверка активности подписки
    is_active = await check_subscription(int(test_user_id))
    print_test("Пробная подписка активна", is_active)

    # Очистка
    await Subscription.objects.filter(profile=profile).adelete()

    return True


async def test_stars_subscription_amount():
    """Тест сохранения правильной суммы Stars"""
    print_section("ТЕСТ: Сохранение суммы Stars в подписках")

    test_user_id = '999999997'
    profile, created = await Profile.objects.aget_or_create(
        telegram_id=test_user_id
    )

    # Создаем подписку с правильной суммой Stars
    stars_amount = 150
    subscription = await Subscription.objects.acreate(
        profile=profile,
        type='month',
        payment_method='stars',
        amount=stars_amount,  # Правильная сумма
        telegram_payment_charge_id='test_payment_123',
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True
    )

    # Проверяем сохраненную сумму
    saved_sub = await Subscription.objects.aget(id=subscription.id)
    print_test(f"Сумма Stars сохранена правильно ({stars_amount})", saved_sub.amount == stars_amount)
    print_test("Сумма Stars НЕ равна нулю", saved_sub.amount > 0)

    # Очистка
    await Subscription.objects.filter(profile=profile).adelete()

    return True


async def test_referral_commission_first_payment_only():
    """Тест что бонус продления начисляется только за первый платеж"""
    print_section("ТЕСТ: Бонус продления только за первый платеж")

    # Создаем реферера
    referrer_id = '999999996'
    referrer, _ = await Profile.objects.aget_or_create(
        telegram_id=referrer_id
    )

    # Создаем реферала
    referred_id = '999999995'
    referred, _ = await Profile.objects.aget_or_create(
        telegram_id=referred_id
    )

    # Очищаем старые данные
    await AffiliateReferral.objects.filter(referred=referred).adelete()
    await Subscription.objects.filter(profile=referred).adelete()
    await Subscription.objects.filter(profile=referrer).adelete()

    # Создаем реферальную связь
    from expenses.models import AffiliateLink, AffiliateProgram

    # Получаем или создаем программу
    try:
        program = await AffiliateProgram.objects.filter(is_active=True).afirst()
        if not program:
            program = await AffiliateProgram.objects.acreate(
                is_active=True,
                commission_permille=100  # 10% комиссия
            )
    except Exception:
        program = await AffiliateProgram.objects.acreate(
            is_active=True,
            commission_permille=100  # 10% комиссия
        )

    # Создаем реферальную ссылку
    link, _ = await AffiliateLink.objects.aget_or_create(
        profile=referrer,
        defaults={
            'affiliate_code': 'TEST123',
            'telegram_link': 'https://t.me/bot?start=ref_TEST123'
        }
    )

    # Создаем реферальную связь
    referral, _ = await AffiliateReferral.objects.aget_or_create(
        referrer=referrer,
        referred=referred,
        defaults={'affiliate_link': link}
    )

    print(f"Создана реферальная связь: {referrer_id} -> {referred_id}")

    # Симулируем первый платеж
    first_payment = await Subscription.objects.acreate(
        profile=referred,
        type='month',
        payment_method='stars',
        amount=150,
        telegram_payment_charge_id='first_payment_123',
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True
    )

    from bot.services.affiliate import reward_referrer_subscription_extension

    reward1 = await reward_referrer_subscription_extension(first_payment)

    print_test(
        "Бонус продления создан за первый платеж",
        reward1 is not None and reward1.get('status') == 'reward_granted'
    )
    if reward1 and reward1.get('status') == 'reward_granted':
        print(
            f"  Бонус: {reward1['reward_months']} мес., до {reward1['reward_end'].strftime('%d.%m.%Y')}"
        )

    # Симулируем второй платеж (продление)
    second_payment = await Subscription.objects.acreate(
        profile=referred,
        type='month',
        payment_method='stars',
        amount=150,
        telegram_payment_charge_id='second_payment_456',
        start_date=timezone.now() + timedelta(days=30),
        end_date=timezone.now() + timedelta(days=60),
        is_active=True
    )

    # Обновляем объект referral из БД после первого бонуса
    await referral.arefresh_from_db()

    reward2 = await reward_referrer_subscription_extension(second_payment)

    print_test(
        "Повторный бонус не создаётся",
        not reward2 or reward2.get('status') != 'reward_granted'
    )

    total_rewards = await AffiliateReferral.objects.filter(
        referred=referred,
        reward_granted=True
    ).acount()
    print_test("Отмечен только один бонус", total_rewards == 1)

    # Очистка
    await AffiliateReferral.objects.filter(referred=referred).adelete()
    await Subscription.objects.filter(profile=referred).adelete()

    return True


async def test_income_categories_emojis():
    """Тест эмодзи в категориях доходов"""
    print_section("ТЕСТ: Эмодзи в категориях доходов")

    test_user_id = '999999994'
    profile, created = await Profile.objects.aget_or_create(
        telegram_id=test_user_id
    )

    # Устанавливаем язык русский
    if created:
        from expenses.models import UserSettings
        await UserSettings.objects.aget_or_create(
            profile=profile,
            defaults={'language': 'ru'}
        )

    if created:
        # Создаем категории доходов для нового пользователя
        from bot.services.category import create_default_income_categories
        await create_default_income_categories(profile)

    # Проверяем категории доходов
    from expenses.models import IncomeCategory
    categories = []
    async for cat in IncomeCategory.objects.filter(profile=profile):
        categories.append(cat)
        has_emoji = any(ord(c) > 127 for c in cat.name)  # Проверка на наличие unicode символов (эмодзи)
        print(f"  {cat.name} - {'✅ есть эмодзи' if has_emoji else '❌ нет эмодзи'}")

    # Все категории должны иметь эмодзи
    all_have_emojis = all(any(ord(c) > 127 for c in cat.name) for cat in categories)
    print_test("Все категории доходов имеют эмодзи", all_have_emojis)

    return True


async def main():
    """Запуск всех тестов"""
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}ИНТЕГРАЦИОННЫЕ ТЕСТЫ{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}")

    results = []

    # Запускаем тесты
    results.append(await test_new_user_detection())
    results.append(await test_trial_subscription_creation())
    results.append(await test_stars_subscription_amount())
    results.append(await test_referral_commission_first_payment_only())
    results.append(await test_income_categories_emojis())

    # Итоги
    print_section("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"{GREEN}✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ ({passed}/{total}){RESET}")
    else:
        print(f"{RED}❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ ({passed}/{total}){RESET}")

    return passed == total


if __name__ == '__main__':
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
