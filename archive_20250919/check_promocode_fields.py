#!/usr/bin/env python3
import os
import sys
import django

# Добавляем путь к проекту
sys.path.insert(0, '/Users/aleksejnalbantov/Desktop/expense_bot')

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import PromoCode

print("\n" + "="*60)
print("ПРОВЕРКА ПОЛЕЙ МОДЕЛИ PromoCode")
print("="*60)

# Проверяем поля модели
fields = PromoCode._meta.get_fields()

for field in fields:
    if hasattr(field, 'name'):
        print(f"\nПоле: {field.name}")
        if hasattr(field, 'choices') and field.choices:
            print(f"  Тип: {field.__class__.__name__}")
            print(f"  Варианты выбора:")
            for value, label in field.choices:
                print(f"    - {value}: {label}")
        elif field.name == 'applicable_subscription_types':
            print(f"  Тип: {field.__class__.__name__}")
            print(f"  Max length: {field.max_length}")
            print(f"  Default: {field.default}")
            print(f"  Verbose name: {field.verbose_name}")
            print(f"  Help text: {field.help_text}")

# Проверяем существующие промокоды
print("\n" + "="*60)
print("СУЩЕСТВУЮЩИЕ ПРОМОКОДЫ")
print("="*60)

promocodes = PromoCode.objects.all()
if promocodes.exists():
    for promo in promocodes:
        print(f"\nПромокод: {promo.code}")
        print(f"  Тип скидки: {promo.discount_type}")
        print(f"  Значение: {promo.discount_value}")
        print(f"  Применимо к: {promo.applicable_subscription_types}")
        print(f"  Активен: {promo.is_active}")
else:
    print("\nПромокодов нет в базе данных")

print("\n" + "="*60)