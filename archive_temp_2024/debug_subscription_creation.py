"""
Скрипт для отладки создания подписок
Запускать: python debug_subscription_creation.py
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Subscription
from django.utils import timezone

def check_subscriptions():
    # Сначала покажем все профили
    print("Все профили в базе:")
    for p in Profile.objects.all().order_by('-created_at')[:10]:
        print(f"  ID: {p.id}, Telegram ID: {p.telegram_id}, Beta: {p.is_beta_tester}, Created: {p.created_at}")
    
    # Получаем ваш профиль (администратора)
    profile = Profile.objects.filter(telegram_id=881292737).first()
    if not profile:
        # Попробуем найти по beta_tester или последний созданный
        profile = Profile.objects.filter(is_beta_tester=True).first()
        if not profile:
            profile = Profile.objects.all().order_by('-created_at').first()
        if not profile:
            print("Профиль не найден вообще")
            return
    
    print(f"Профиль: {profile}")
    print(f"Beta tester: {profile.is_beta_tester}")
    
    # Все подписки
    subs = profile.subscriptions.all().order_by('-created_at')
    print(f"\nВсего подписок: {subs.count()}")
    
    for sub in subs:
        print(f"\nПодписка ID: {sub.id}")
        print(f"  Тип: {sub.type}")
        print(f"  Метод оплаты: {sub.payment_method}")
        print(f"  Активна: {sub.is_active}")
        print(f"  Начало: {sub.start_date}")
        print(f"  Конец: {sub.end_date}")
        print(f"  Создана: {sub.created_at}")
        print(f"  Обновлена: {sub.updated_at}")
        
    # Активные подписки
    active_subs = profile.subscriptions.filter(
        is_active=True,
        end_date__gt=timezone.now()
    )
    print(f"\nАктивных подписок: {active_subs.count()}")

if __name__ == "__main__":
    check_subscriptions()
