import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, Category, Expense, RecurringPayment
from decimal import Decimal

data = {
    'users': [],
    'categories': [],
    'expenses': [],
    'recurring': []
}

# Export users
for user in Profile.objects.all():
    data['users'].append({
        'telegram_id': user.telegram_id,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'timezone': user.timezone,
        'language_code': user.language_code,
        'is_active': user.is_active,
    })
    print(f"Exported user: {user.telegram_id}")

# Export categories
for cat in Category.objects.all():
    clean_name = cat.name.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    data['categories'].append({
        'user_telegram_id': cat.profile.telegram_id,
        'name': clean_name,
        'is_active': cat.is_active,
        'order': cat.order,
    })
    print(f"Exported category: {clean_name}")

# Export expenses
count = 0
for exp in Expense.objects.all():
    clean_desc = exp.description.encode('utf-8', 'ignore').decode('utf-8', 'ignore') if exp.description else ''
    data['expenses'].append({
        'user_telegram_id': exp.profile.telegram_id,
        'amount': str(exp.amount),
        'category_name': exp.category.name if exp.category else None,
        'description': clean_desc,
        'date': exp.date.isoformat() if exp.date else None,
        'created_at': exp.created_at.isoformat() if exp.created_at else None,
        'payment_method': exp.payment_method,
        'is_deleted': exp.is_deleted,
    })
    count += 1
    if count % 100 == 0:
        print(f"Exported {count} expenses...")

print(f"Total expenses exported: {count}")

# Export recurring
for rec in RecurringPayment.objects.all():
    clean_desc = rec.description.encode('utf-8', 'ignore').decode('utf-8', 'ignore') if rec.description else ''
    data['recurring'].append({
        'user_telegram_id': rec.profile.telegram_id,
        'amount': str(rec.amount),
        'category_name': rec.category.name if rec.category else None,
        'description': clean_desc,
        'frequency': rec.frequency,
        'next_payment_date': rec.next_payment_date.isoformat() if rec.next_payment_date else None,
        'is_active': rec.is_active,
        'payment_day': rec.payment_day,
    })
    print(f"Exported recurring: {clean_desc}")

# Save to file
with open('data_export.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'\n=== Export Complete ===')
print(f'Users: {len(data["users"])}')
print(f'Categories: {len(data["categories"])}')
print(f'Expenses: {len(data["expenses"])}')
print(f'Recurring: {len(data["recurring"])}')
print(f'Data saved to data_export.json')