import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Subscription

# Удаляем последнюю созданную подписку
profile = Profile.objects.filter(telegram_id=881292737).first()
if profile:
    # Удаляем самую новую подписку
    last_sub = profile.subscriptions.all().order_by('-created_at').first()
    if last_sub:
        print(f"Удаляем подписку ID: {last_sub.id}, создана: {last_sub.created_at}")
        last_sub.delete()
        print("Удалено!")
    
    # Показываем оставшиеся
    print(f"\nОсталось подписок: {profile.subscriptions.count()}")
    for sub in profile.subscriptions.all():
        print(f"  ID: {sub.id}, до {sub.end_date}")
