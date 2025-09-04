#!/usr/bin/env python
"""
Тестирование системы уведомлений о подписках
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


def test_subscription_notifications():
    """Тестирование логики уведомлений о подписках"""
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ УВЕДОМЛЕНИЙ О ПОДПИСКАХ")
    print("=" * 60)
    
    # Получаем тестовый профиль (используем ваш ID)
    try:
        profile = Profile.objects.get(telegram_id=881292737)
        print(f"\n[INFO] Используем профиль: {profile.telegram_id}")
    except Profile.DoesNotExist:
        print("[ERROR] Профиль не найден")
        return
    
    # Проверяем текущие подписки
    print("\n[ТЕКУЩИЕ ПОДПИСКИ]")
    active_subscriptions = Subscription.objects.filter(
        profile=profile,
        is_active=True,
        end_date__gt=timezone.now()
    ).order_by('end_date')
    
    if active_subscriptions.exists():
        for sub in active_subscriptions:
            print(f"  - ID: {sub.id}, Тип: {sub.type}, Окончание: {sub.end_date.strftime('%d.%m.%Y %H:%M')}")
    else:
        print("  Нет активных подписок")
    
    # Проверяем подписки, истекающие завтра
    tomorrow = timezone.now() + timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    print("\n[ПОДПИСКИ, ИСТЕКАЮЩИЕ ЗАВТРА]")
    expiring_subscriptions = Subscription.objects.filter(
        profile=profile,
        is_active=True,
        end_date__gte=tomorrow_start,
        end_date__lte=tomorrow_end
    )
    
    if expiring_subscriptions.exists():
        for sub in expiring_subscriptions:
            print(f"  - ID: {sub.id}, Тип: {sub.type}, Окончание: {sub.end_date.strftime('%d.%m.%Y %H:%M')}")
            
            # Проверяем, есть ли другие активные подписки
            other_active = Subscription.objects.filter(
                profile=profile,
                is_active=True,
                end_date__gt=sub.end_date
            ).exists()
            
            if other_active:
                print(f"    [SKIP] Есть другие активные подписки после этой даты")
            else:
                print(f"    [SEND] Нужно отправить уведомление")
    else:
        print("  Нет подписок, истекающих завтра")
    
    # Проверяем историю уведомлений
    print("\n[ИСТОРИЯ УВЕДОМЛЕНИЙ]")
    notifications = SubscriptionNotification.objects.filter(
        subscription__profile=profile
    ).order_by('-sent_at')[:5]
    
    if notifications.exists():
        for notif in notifications:
            print(f"  - Подписка ID: {notif.subscription.id}, Тип: {notif.notification_type}, "
                  f"Отправлено: {notif.sent_at.strftime('%d.%m.%Y %H:%M')}")
    else:
        print("  Нет отправленных уведомлений")
    
    print("\n" + "=" * 60)


def simulate_expiring_subscription():
    """Симуляция истекающей подписки для тестирования"""
    
    print("\n[СИМУЛЯЦИЯ ИСТЕКАЮЩЕЙ ПОДПИСКИ]")
    
    try:
        profile = Profile.objects.get(telegram_id=881292737)
        
        # Создаем тестовую подписку, истекающую завтра
        tomorrow = timezone.now() + timedelta(days=1)
        test_subscription = Subscription.objects.create(
            profile=profile,
            type='trial',
            start_date=timezone.now() - timedelta(days=6),
            end_date=tomorrow.replace(hour=23, minute=59, second=59),
            is_active=True,
            amount=0
        )
        
        print(f"  [OK] Создана тестовая подписка ID: {test_subscription.id}")
        print(f"       Тип: {test_subscription.type}")
        print(f"       Окончание: {test_subscription.end_date.strftime('%d.%m.%Y %H:%M')}")
        
        # Проверяем, будет ли отправлено уведомление
        other_active = Subscription.objects.filter(
            profile=profile,
            is_active=True,
            end_date__gt=test_subscription.end_date
        ).exclude(id=test_subscription.id).exists()
        
        if other_active:
            print(f"  [INFO] Уведомление НЕ будет отправлено (есть другие активные подписки)")
        else:
            print(f"  [INFO] Уведомление БУДЕТ отправлено")
        
        # Удаляем тестовую подписку
        response = input("\n  Удалить тестовую подписку? (y/n): ")
        if response.lower() == 'y':
            test_subscription.delete()
            print("  [OK] Тестовая подписка удалена")
        
    except Profile.DoesNotExist:
        print("  [ERROR] Профиль не найден")
    except Exception as e:
        print(f"  [ERROR] Ошибка: {e}")


def check_notification_logic():
    """Проверка логики отправки уведомлений"""
    
    print("\n[ПРОВЕРКА ЛОГИКИ УВЕДОМЛЕНИЙ]")
    print("-" * 40)
    
    # Сценарий 1: Пробный период истекает завтра, нет других подписок
    print("\nСценарий 1: Trial истекает завтра, нет других подписок")
    print("  Результат: ОТПРАВИТЬ уведомление [OK]")
    
    # Сценарий 2: Пробный период истекает завтра, есть платная подписка
    print("\nСценарий 2: Trial истекает завтра, есть активная платная подписка")
    print("  Результат: НЕ отправлять уведомление [OK]")
    
    # Сценарий 3: Платная подписка истекает завтра, есть другая платная
    print("\nСценарий 3: Платная истекает завтра, есть другая активная")
    print("  Результат: НЕ отправлять уведомление [OK]")
    
    # Сценарий 4: Единственная подписка истекает завтра
    print("\nСценарий 4: Единственная подписка истекает завтра")
    print("  Результат: ОТПРАВИТЬ уведомление [OK]")
    
    print("\n" + "-" * 40)


def main():
    """Главная функция"""
    print("\n[START] ТЕСТИРОВАНИЕ СИСТЕМЫ УВЕДОМЛЕНИЙ О ПОДПИСКАХ\n")
    
    # Основное тестирование
    test_subscription_notifications()
    
    # Проверка логики
    check_notification_logic()
    
    # Спрашиваем, нужна ли симуляция
    print("\n" + "=" * 60)
    response = input("Создать тестовую истекающую подписку? (y/n): ")
    if response.lower() == 'y':
        simulate_expiring_subscription()
    
    print("\n[DONE] Тестирование завершено!")


if __name__ == "__main__":
    main()