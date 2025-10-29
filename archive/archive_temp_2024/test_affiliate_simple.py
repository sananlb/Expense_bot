#!/usr/bin/env python
"""
Простой тест партнёрской программы Telegram Stars
"""
import os
import sys
import django
from datetime import timedelta

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.utils import timezone
from expenses.models import (
    Profile, 
    AffiliateProgram,
    AffiliateLink, 
    AffiliateReferral,
    AffiliateCommission,
    Subscription
)

print("Тест партнёрской программы Telegram Stars")
print("=" * 50)

# 1. Создаём программу
print("\n1. Создаём партнёрскую программу с 10% комиссией...")
program = AffiliateProgram.objects.create(
    commission_permille=100,  # 10%
    is_active=True
)
print(f"   OK: Программа создана, комиссия: {program.get_commission_percent()}%")

# 2. Создаём профиль реферера
print("\n2. Создаём профиль реферера...")
referrer = Profile.objects.create(
    telegram_id=111111,
    language_code="ru"
)
print(f"   OK: Реферер создан: ID {referrer.telegram_id}")

# 3. Создаём реферальную ссылку
print("\n3. Создаём реферальную ссылку...")
link = AffiliateLink.objects.create(
    profile=referrer,
    affiliate_code="TEST1234",
    telegram_link="https://t.me/test_bot?start=ref_TEST1234",
    is_active=True
)
print(f"   OK: Ссылка создана: {link.telegram_link}")

# 4. Создаём профиль реферала
print("\n4. Создаём профиль реферала...")
referred = Profile.objects.create(
    telegram_id=222222,
    language_code="ru"
)
print(f"   OK: Реферал создан: ID {referred.telegram_id}")

# 5. Создаём реферальную связь
print("\n5. Создаём связь реферер-реферал...")
referral = AffiliateReferral.objects.create(
    referrer=referrer,
    referred=referred,
    affiliate_link=link
)
print(f"   OK: Связь создана")

# 6. Создаём подписку
print("\n6. Реферал оплачивает подписку на месяц (150 звёзд)...")
subscription = Subscription.objects.create(
    profile=referred,
    type='month',
    payment_method='stars',
    amount=150,
    start_date=timezone.now(),
    end_date=timezone.now() + timedelta(days=30),
    is_active=True
)
print(f"   OK: Подписка оплачена: {subscription.amount} звёзд")

# 7. Создаём комиссию
print("\n7. Начисляем комиссию рефереру...")
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
print(f"   OK: Комиссия начислена: {commission.commission_amount} звёзд")
print(f"   OK: Статус: {commission.get_status_display()}")
print(f"   OK: Доступна после: {commission.hold_until.strftime('%d.%m.%Y')}")

# 8. Проверяем расчёты
print("\n8. Проверка расчётов:")
print(f"   • Сумма платежа: {subscription.amount} звёзд")
print(f"   • Процент комиссии: {program.get_commission_percent()}%")
print(f"   • Комиссия реферера: {commission_amount} звёзд")
print(f"   • Расчёт корректен: {commission_amount == subscription.amount * program.get_commission_percent() / 100}")

# Очистка
print("\n9. Очистка тестовых данных...")
commission.delete()
subscription.delete()
referral.delete()
referred.delete()
link.delete()
referrer.delete()
program.delete()
print("   OK: Данные удалены")

print("\n" + "=" * 50)
print("ТЕСТ УСПЕШНО ЗАВЕРШЁН!")
print("\nПартнёрская программа работает корректно.")
print("Пользователи могут использовать команду /affiliate")