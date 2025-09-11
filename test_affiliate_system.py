#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки реферальной системы
"""

import os
import sys
import django

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, AffiliateLink, AffiliateReferral, AffiliateCommission, AffiliateProgram
from django.utils import timezone
from decimal import Decimal


def check_affiliate_system(user1_id: int, user2_id: int):
    """
    Проверяет состояние реферальной системы для двух пользователей
    
    Args:
        user1_id: ID первого пользователя (реферер)
        user2_id: ID второго пользователя (реферал)
    """
    print(f"\n{'='*60}")
    print("ПРОВЕРКА РЕФЕРАЛЬНОЙ СИСТЕМЫ")
    print(f"{'='*60}\n")
    
    # Проверяем профили
    try:
        user1 = Profile.objects.get(telegram_id=user1_id)
        print(f"✅ Пользователь 1 найден: ID={user1_id}, Username={user1.username}")
    except Profile.DoesNotExist:
        print(f"❌ Пользователь 1 с ID {user1_id} не найден!")
        return
    
    try:
        user2 = Profile.objects.get(telegram_id=user2_id)
        print(f"✅ Пользователь 2 найден: ID={user2_id}, Username={user2.username}")
    except Profile.DoesNotExist:
        print(f"❌ Пользователь 2 с ID {user2_id} не найден!")
        return
    
    print(f"\n{'-'*60}")
    print("ПРОВЕРКА РЕФЕРАЛЬНЫХ ПРОГРАММ")
    print(f"{'-'*60}")
    
    # Проверяем активную программу
    active_programs = AffiliateProgram.objects.filter(is_active=True)
    if active_programs.exists():
        for program in active_programs:
            print(f"✅ Активная программа: комиссия {program.commission_permille/10}%, ID={program.id}")
    else:
        print("❌ Нет активных реферальных программ!")
    
    print(f"\n{'-'*60}")
    print("ПРОВЕРКА РЕФЕРАЛЬНЫХ ССЫЛОК")
    print(f"{'-'*60}")
    
    # Проверяем реферальную ссылку пользователя 1
    try:
        link1 = AffiliateLink.objects.get(profile=user1)
        print(f"✅ Реферальная ссылка пользователя 1:")
        print(f"   Код: {link1.affiliate_code}")
        print(f"   Ссылка: {link1.telegram_link}")
        print(f"   Клики: {link1.clicks}")
        print(f"   Конверсии: {link1.conversions}")
        print(f"   Заработано: {link1.total_earned} ⭐")
        print(f"   Активна: {'Да' if link1.is_active else 'Нет'}")
    except AffiliateLink.DoesNotExist:
        print("❌ У пользователя 1 нет реферальной ссылки!")
        link1 = None
    
    print(f"\n{'-'*60}")
    print("ПРОВЕРКА РЕФЕРАЛЬНЫХ СВЯЗЕЙ")
    print(f"{'-'*60}")
    
    # Проверяем связь между пользователями (новая система)
    try:
        referral = AffiliateReferral.objects.get(
            referrer=user1,
            referred=user2
        )
        print(f"✅ Реферальная связь найдена:")
        print(f"   Реферер: {referral.referrer.telegram_id} ({referral.referrer.username})")
        print(f"   Реферал: {referral.referred.telegram_id} ({referral.referred.username})")
        print(f"   Дата регистрации: {referral.created_at}")
        print(f"   Первый платеж: {referral.first_payment_at or 'Нет'}")
        print(f"   Всего платежей: {referral.total_payments}")
        print(f"   Всего потрачено: {referral.total_spent} ⭐")
        if referral.affiliate_link:
            print(f"   Использованная ссылка: {referral.affiliate_link.affiliate_code}")
    except AffiliateReferral.DoesNotExist:
        print(f"❌ Нет реферальной связи между пользователями (новая система)!")
        referral = None
    
    # Проверяем старую систему
    if user2.referrer:
        print(f"\n✅ Связь через старую систему:")
        print(f"   Реферер пользователя 2: {user2.referrer.telegram_id} ({user2.referrer.username})")
    else:
        print(f"\n❌ У пользователя 2 нет реферера в старой системе")
    
    print(f"\n{'-'*60}")
    print("ПРОВЕРКА КОМИССИЙ")
    print(f"{'-'*60}")
    
    # Проверяем комиссии
    commissions = AffiliateCommission.objects.filter(
        referrer=user1,
        referred=user2
    ).order_by('-created_at')
    
    if commissions.exists():
        print(f"✅ Найдено комиссий: {commissions.count()}")
        for i, commission in enumerate(commissions[:5], 1):
            print(f"\n   Комиссия #{i}:")
            print(f"   - Сумма платежа: {commission.payment_amount} ⭐")
            print(f"   - Сумма комиссии: {commission.commission_amount} ⭐")
            print(f"   - Ставка: {commission.commission_rate/10}%")
            print(f"   - Статус: {commission.status}")
            if commission.hold_until:
                print(f"   - Холд до: {commission.hold_until}")
            print(f"   - Дата: {commission.created_at}")
    else:
        print("❌ Нет начисленных комиссий между этими пользователями!")
    
    # Проверяем все комиссии реферера
    all_commissions = AffiliateCommission.objects.filter(referrer=user1)
    if all_commissions.exists():
        total_earned = sum(c.commission_amount for c in all_commissions)
        print(f"\n📊 Всего комиссий у реферера: {all_commissions.count()}")
        print(f"   Общая сумма: {total_earned} ⭐")
        
        # По статусам
        for status in ['pending', 'hold', 'paid', 'cancelled', 'refunded']:
            count = all_commissions.filter(status=status).count()
            if count > 0:
                amount = sum(c.commission_amount for c in all_commissions.filter(status=status))
                print(f"   - {status}: {count} шт. на сумму {amount} ⭐")
    
    print(f"\n{'-'*60}")
    print("ПРОВЕРКА ПОДПИСОК")
    print(f"{'-'*60}")
    
    # Проверяем подписки пользователя 2
    subscriptions = user2.subscriptions.all().order_by('-created_at')
    if subscriptions.exists():
        print(f"✅ Подписки пользователя 2: {subscriptions.count()} шт.")
        for sub in subscriptions[:3]:
            print(f"   - {sub.type}, {sub.amount} ⭐, метод: {sub.payment_method}, активна: {'Да' if sub.is_active else 'Нет'}")
    else:
        print("❌ У пользователя 2 нет подписок")
    
    print(f"\n{'='*60}")
    print("ДИАГНОСТИКА ПРОБЛЕМ")
    print(f"{'='*60}\n")
    
    problems = []
    
    if not active_programs.exists():
        problems.append("Нет активной реферальной программы - создайте через /affiliate или автоматически при первой оплате")
    
    if not link1:
        problems.append("У реферера нет реферальной ссылки - создайте через /affiliate")
    
    if not referral:
        problems.append("Нет связи между пользователями - пользователь 2 должен перейти по реферальной ссылке при регистрации")
    
    if referral and referral.total_payments == 0:
        problems.append("Пользователь 2 еще не делал платежей после регистрации по реферальной ссылке")
    
    if problems:
        print("⚠️ Обнаруженные проблемы:")
        for i, problem in enumerate(problems, 1):
            print(f"   {i}. {problem}")
    else:
        print("✅ Проблем не обнаружено! Система должна работать корректно.")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Запрашиваем ID пользователей
    try:
        user1_id = int(input("Введите ID пользователя 1 (реферер): "))
        user2_id = int(input("Введите ID пользователя 2 (реферал): "))
        
        check_affiliate_system(user1_id, user2_id)
    except ValueError:
        print("Ошибка: введите корректные числовые ID пользователей")
    except KeyboardInterrupt:
        print("\n\nОтменено пользователем")
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()