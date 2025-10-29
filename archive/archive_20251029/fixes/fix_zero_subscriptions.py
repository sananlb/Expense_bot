#!/usr/bin/env python3
"""
Скрипт для исправления подписок с нулевой суммой
"""
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, '/Users/aleksejnalbantov/Desktop/expense_bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Subscription

SUBSCRIPTION_PRICES = {
    'month': 150,
    'six_months': 600,
}

print("\n" + "="*60)
print("ИСПРАВЛЕНИЕ ПОДПИСОК С НУЛЕВОЙ СУММОЙ")
print("="*60)

# Получаем все подписки с нулевой суммой
zero_subs = Subscription.objects.filter(
    payment_method='stars',
    amount=0
)

print(f"\nНайдено подписок с нулевой суммой: {zero_subs.count()}")

fixed_count = 0
for sub in zero_subs:
    # Определяем правильную сумму по типу подписки
    if sub.type in SUBSCRIPTION_PRICES:
        correct_amount = SUBSCRIPTION_PRICES[sub.type]
        print(f"\nИсправляем подписку #{sub.id}:")
        print(f"  Пользователь: {sub.profile.telegram_id}")
        print(f"  Тип: {sub.type}")
        print(f"  Было: {sub.amount} Stars")
        print(f"  Стало: {correct_amount} Stars")
        
        sub.amount = correct_amount
        sub.save()
        fixed_count += 1

print("\n" + "="*60)
print("РЕЗУЛЬТАТЫ:")
print("="*60)
print(f"✅ Исправлено подписок: {fixed_count}")
print("\n✅ Исправление завершено!")
print("="*60)
