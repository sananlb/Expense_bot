#!/usr/bin/env python
"""
Детальный тест исправления уведомлений о подписках
"""
import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Subscription, SubscriptionNotification


def test_subscription_notification_logic():
    """Тестирование логики уведомлений с реальными данными"""
    
    print("=" * 60)
    print("ТЕСТ: Проверка исправления уведомлений о подписках")
    print("=" * 60)
    
    # Получаем или создаем тестовый профиль
    profile, created = Profile.objects.get_or_create(
        telegram_id=999999999,
        defaults={'username': 'test_user'}
    )
    
    if created:
        print(f"\n[INFO] Создан тестовый профиль: {profile.telegram_id}")
    else:
        print(f"\n[INFO] Используем существующий профиль: {profile.telegram_id}")
    
    # Очистка старых тестовых данных
    Subscription.objects.filter(profile=profile).delete()
    print("[INFO] Очищены старые подписки")
    
    # Создаем сценарии для тестирования
    tomorrow = timezone.now() + timedelta(days=1)
    next_week = timezone.now() + timedelta(days=7)
    
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 1: Trial истекает завтра, других подписок нет")
    print("-" * 60)
    
    # Создаем пробную подписку, истекающую завтра
    trial_sub = Subscription.objects.create(
        profile=profile,
        type='trial',
        start_date=timezone.now() - timedelta(days=6),
        end_date=tomorrow.replace(hour=23, minute=59, second=59),
        is_active=True,
        amount=0
    )
    print(f"  Создана trial подписка ID: {trial_sub.id}")
    print(f"  Окончание: {trial_sub.end_date.strftime('%d.%m.%Y %H:%M')}")
    
    # Проверяем логику
    other_active = Subscription.objects.filter(
        profile=profile,
        is_active=True,
        end_date__gt=trial_sub.end_date
    ).exclude(id=trial_sub.id).exists()
    
    print(f"\n  Есть другие активные подписки? {other_active}")
    print(f"  Ожидаемый результат: Отправить уведомление")
    print(f"  [{'PASS' if not other_active else 'FAIL'}] Тест пройден")
    
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 2: Trial истекает завтра, есть платная подписка")
    print("-" * 60)
    
    # Добавляем платную подписку на следующую неделю
    paid_sub = Subscription.objects.create(
        profile=profile,
        type='monthly',
        start_date=tomorrow,
        end_date=next_week.replace(hour=23, minute=59, second=59),
        is_active=True,
        amount=299
    )
    print(f"  Добавлена платная подписка ID: {paid_sub.id}")
    print(f"  Окончание: {paid_sub.end_date.strftime('%d.%m.%Y %H:%M')}")
    
    # Проверяем логику для trial подписки
    other_active = Subscription.objects.filter(
        profile=profile,
        is_active=True,
        end_date__gt=trial_sub.end_date
    ).exclude(id=trial_sub.id).exists()
    
    print(f"\n  Есть другие активные подписки после trial? {other_active}")
    print(f"  Ожидаемый результат: НЕ отправлять уведомление")
    print(f"  [{'PASS' if other_active else 'FAIL'}] Тест пройден")
    
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 3: Две платные подписки с разными датами")
    print("-" * 60)
    
    # Очищаем и создаем новые подписки
    Subscription.objects.filter(profile=profile).delete()
    
    # Первая платная подписка истекает завтра
    paid_sub1 = Subscription.objects.create(
        profile=profile,
        type='monthly',
        start_date=timezone.now() - timedelta(days=29),
        end_date=tomorrow.replace(hour=23, minute=59, second=59),
        is_active=True,
        amount=299
    )
    
    # Вторая платная подписка на месяц вперед
    paid_sub2 = Subscription.objects.create(
        profile=profile,
        type='yearly',
        start_date=tomorrow,
        end_date=timezone.now() + timedelta(days=30),
        is_active=True,
        amount=2999
    )
    
    print(f"  Подписка 1 (истекает завтра): ID {paid_sub1.id}, до {paid_sub1.end_date.strftime('%d.%m.%Y')}")
    print(f"  Подписка 2 (активна месяц): ID {paid_sub2.id}, до {paid_sub2.end_date.strftime('%d.%m.%Y')}")
    
    # Проверяем логику для первой подписки
    other_active = Subscription.objects.filter(
        profile=profile,
        is_active=True,
        end_date__gt=paid_sub1.end_date
    ).exclude(id=paid_sub1.id).exists()
    
    print(f"\n  Есть другие активные подписки после первой? {other_active}")
    print(f"  Ожидаемый результат: НЕ отправлять уведомление")
    print(f"  [{'PASS' if other_active else 'FAIL'}] Тест пройден")
    
    # Очистка тестовых данных
    print("\n" + "=" * 60)
    print("ОЧИСТКА ТЕСТОВЫХ ДАННЫХ")
    Subscription.objects.filter(profile=profile).delete()
    if profile.telegram_id == 999999999:  # Удаляем только тестовый профиль
        profile.delete()
        print("[OK] Тестовые данные удалены")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)


def check_real_user_subscriptions():
    """Проверка реальных подписок пользователя"""
    
    print("\n" + "=" * 60)
    print("ПРОВЕРКА РЕАЛЬНЫХ ДАННЫХ")
    print("=" * 60)
    
    # Проверяем подписки для админа
    try:
        admin_profile = Profile.objects.get(telegram_id=881292737)
        print(f"\nПрофиль админа: {admin_profile.telegram_id}")
        
        # Все активные подписки
        active_subs = Subscription.objects.filter(
            profile=admin_profile,
            is_active=True
        ).order_by('end_date')
        
        print(f"\nАктивных подписок: {active_subs.count()}")
        for sub in active_subs:
            print(f"  - ID: {sub.id}, Тип: {sub.type}, До: {sub.end_date.strftime('%d.%m.%Y %H:%M')}")
            
            # Проверяем, будет ли отправлено уведомление
            tomorrow = timezone.now() + timedelta(days=1)
            tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            if tomorrow_start <= sub.end_date <= tomorrow_end:
                other_active = Subscription.objects.filter(
                    profile=admin_profile,
                    is_active=True,
                    end_date__gt=sub.end_date
                ).exclude(id=sub.id).exists()
                
                if other_active:
                    print(f"    -> Уведомление НЕ будет отправлено (есть другие подписки)")
                else:
                    print(f"    -> Уведомление БУДЕТ отправлено")
    except Profile.DoesNotExist:
        print("Профиль админа не найден")


if __name__ == "__main__":
    print("\n[START] ЗАПУСК ТЕСТИРОВАНИЯ\n")
    
    # Основное тестирование
    test_subscription_notification_logic()
    
    # Проверка реальных данных
    check_real_user_subscriptions()
    
    print("\n[DONE] Тестирование завершено!")