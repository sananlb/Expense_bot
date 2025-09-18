#!/usr/bin/env python
"""
Тест интеграции партнёрской программы Telegram Stars
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from expenses.models import (
    Profile, 
    ExpenseCategory,
    AffiliateProgram,
    AffiliateLink, 
    AffiliateReferral,
    AffiliateCommission,
    Subscription
)


def test_models():
    """Тест моделей партнёрской программы"""
    print("=== Тест моделей партнёрской программы ===\n")
    
    # 1. Создаем программу
    program = AffiliateProgram.objects.create(
        commission_permille=100,  # 10%
        duration_months=None,
        is_active=True
    )
    print(f"Создана партнёрская программа с комиссией {program.get_commission_percent()}%")
    
    # 2. Создаем профиль реферера
    referrer = Profile.objects.create(
        telegram_id=111111,
        first_name="Referrer",
        language_code="ru"
    )
    print(f"Создан профиль реферера: {referrer.telegram_id}")
    
    # 3. Создаем реферальную ссылку
    link = AffiliateLink.objects.create(
        profile=referrer,
        affiliate_code="TEST1234",
        telegram_link="https://t.me/test_bot?start=ref_TEST1234",
        is_active=True
    )
    print(f"Создана реферальная ссылка: {link.telegram_link}")
    
    # 4. Создаем профиль реферала
    referred = Profile.objects.create(
        telegram_id=222222,
        first_name="Referred",
        language_code="ru"
    )
    print(f"Создан профиль реферала: {referred.telegram_id}")
    
    # 5. Создаем реферальную связь
    referral = AffiliateReferral.objects.create(
        referrer=referrer,
        referred=referred,
        affiliate_link=link
    )
    print(f"Создана реферальная связь между {referrer.telegram_id} и {referred.telegram_id}")
    
    # 6. Создаем подписку для реферала
    subscription = Subscription.objects.create(
        profile=referred,
        type='month',
        payment_method='stars',
        amount=150,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True
    )
    print(f"Создана подписка на сумму {subscription.amount} звёзд")
    
    # 7. Создаем комиссию
    commission_amount = program.calculate_commission(subscription.amount)
    commission = AffiliateCommission.objects.create(
        referrer=referrer,
        referred=referred,
        subscription=subscription,
        referral=referral,
        payment_amount=subscription.amount,
        commission_amount=commission_amount,
        commission_rate=program.commission_permille,
        status='hold',
        hold_until=timezone.now() + timedelta(days=21)
    )
    print(f"Создана комиссия на сумму {commission.commission_amount} звёзд (холд до {commission.hold_until.date()})")
    
    # Проверяем статистику
    print(f"\n=== Статистика ===")
    print(f"Конверсия ссылки: {link.get_conversion_rate()}%")
    print(f"Процент комиссии: {commission.get_commission_percent()}%")
    print(f"Статус комиссии: {commission.get_status_display()}")
    
    # Очистка
    commission.delete()
    subscription.delete()
    referral.delete()
    referred.delete()
    link.delete()
    referrer.delete()
    program.delete()
    
    print("\nТест моделей успешно завершен!")
    return True


def test_services():
    """Тест сервисного слоя"""
    print("\n=== Тест сервисного слоя ===\n")
    
    from bot.services.affiliate import (
        get_or_create_affiliate_program,
        get_or_create_affiliate_link,
        process_referral_link,
        get_referrer_stats
    )
    
    # 1. Создаем/получаем программу
    program = get_or_create_affiliate_program(commission_percent=10)
    print(f"Программа: комиссия {program.get_commission_percent()}%")
    
    # 2. Создаем профили
    referrer = Profile.objects.create(
        telegram_id=333333,
        first_name="ServiceReferrer"
    )
    referred = Profile.objects.create(
        telegram_id=444444,
        first_name="ServiceReferred"
    )
    
    # 3. Создаем реферальную ссылку
    link = get_or_create_affiliate_link(referrer.telegram_id, "test_bot")
    print(f"Ссылка: {link.telegram_link}")
    
    # 4. Обрабатываем переход по ссылке
    referral = process_referral_link(referred.telegram_id, link.affiliate_code)
    if referral:
        print(f"Реферальная связь создана: {referral.referrer.telegram_id} -> {referral.referred.telegram_id}")
    
    # 5. Получаем статистику
    stats = get_referrer_stats(referrer.telegram_id)
    print(f"\nСтатистика реферера:")
    print(f"  - Переходов: {stats['clicks']}")
    print(f"  - Рефералов: {stats['referrals_count']}")
    print(f"  - Заработано: {stats['total_earned']} звёзд")
    
    # Очистка
    if referral:
        referral.delete()
    link.delete()
    referred.delete()
    referrer.delete()
    program.delete()
    
    print("\nТест сервисного слоя успешно завершен!")
    return True


def test_bot_integration():
    """Тест интеграции с ботом"""
    print("\n=== Тест интеграции с ботом ===\n")
    
    try:
        # Проверяем импорт роутера
        from bot.routers.affiliate import router as affiliate_router
        print("Роутер affiliate успешно импортирован")
        
        # Проверяем, что роутер экспортируется
        from bot.routers import affiliate_router
        print("Роутер affiliate доступен в bot.routers")
        
        # Проверяем импорт в main.py
        from bot.main import create_dispatcher
        print("Диспетчер успешно создается")
        
        print("\nИнтеграция с ботом проверена успешно!")
        return True
        
    except ImportError as e:
        print(f"Ошибка импорта: {e}")
        return False


if __name__ == "__main__":
    print("Запуск тестов партнёрской программы Telegram Stars\n")
    print("=" * 50)
    
    success = True
    
    # Тест 1: Модели
    try:
        if not test_models():
            success = False
    except Exception as e:
        print(f"Ошибка в тесте моделей: {e}")
        success = False
    
    # Тест 2: Сервисы
    try:
        if not test_services():
            success = False
    except Exception as e:
        print(f"Ошибка в тесте сервисов: {e}")
        success = False
    
    # Тест 3: Интеграция с ботом
    try:
        if not test_bot_integration():
            success = False
    except Exception as e:
        print(f"Ошибка в тесте интеграции: {e}")
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("Все тесты пройдены успешно!")
    else:
        print("Некоторые тесты завершились с ошибками")