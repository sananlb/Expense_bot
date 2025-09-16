#!/usr/bin/env python
"""
Полная миграция данных из SQLite в PostgreSQL
"""
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal

# Django setup
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import transaction
from bot.models import TelegramUser, Category, Expense, RecurringPayment, UserSubscription

def migrate_all():
    # Подключение к SQLite
    conn = sqlite3.connect('/tmp/expense_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=== Начинаем полную миграцию данных ===\n")

    # 1. ПОЛЬЗОВАТЕЛИ
    print("1. Миграция пользователей...")
    cursor.execute("SELECT * FROM bot_telegramuser")
    users = cursor.fetchall()
    user_map = {}  # Маппинг telegram_id -> TelegramUser

    for row in users:
        try:
            # Создаем Django user
            django_user, _ = User.objects.get_or_create(
                username=f"telegram_{row['telegram_id']}",
                defaults={'is_active': True}
            )

            # Создаем TelegramUser
            tg_user, created = TelegramUser.objects.update_or_create(
                telegram_id=row['telegram_id'],
                defaults={
                    'user': django_user,
                    'username': row['username'] or '',
                    'first_name': row['first_name'] or '',
                    'last_name': row['last_name'] or '',
                    'is_premium': bool(row['is_premium']),
                    'trial_used': bool(row['trial_used']),
                    'created_at': datetime.fromisoformat(row['created_at'].replace(' ', 'T')) if row['created_at'] else datetime.now(),
                    'timezone': row['timezone'] or 'Europe/Moscow',
                    'language_code': row['language_code'] or 'ru',
                    'subscription_expiry': datetime.fromisoformat(row['subscription_expiry'].replace(' ', 'T')) if row['subscription_expiry'] else None,
                    'reminder_enabled': bool(row['reminder_enabled']) if row['reminder_enabled'] is not None else True,
                    'reminder_time': row['reminder_time'] or '21:00',
                    'daily_limit': Decimal(str(row['daily_limit'])) if row['daily_limit'] else None,
                    'monthly_limit': Decimal(str(row['monthly_limit'])) if row['monthly_limit'] else None,
                }
            )
            user_map[row['telegram_id']] = tg_user
            action = "Создан" if created else "Обновлен"
            print(f"  {action} пользователь: {row['username'] or row['telegram_id']}")
        except Exception as e:
            print(f"  ❌ Ошибка с пользователем {row['telegram_id']}: {e}")

    print(f"✅ Мигрировано пользователей: {len(user_map)}\n")

    # 2. КАТЕГОРИИ
    print("2. Миграция категорий...")
    cursor.execute("SELECT * FROM bot_category")
    categories = cursor.fetchall()
    category_map = {}  # Маппинг старый id -> новая Category

    for row in categories:
        try:
            tg_user = user_map.get(row['user_id'])
            if tg_user:
                category, created = Category.objects.update_or_create(
                    name=row['name'],
                    user=tg_user,
                    defaults={
                        'icon': row['icon'] or '',
                        'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                        'order': row['order'] or 0,
                        'created_at': datetime.fromisoformat(row['created_at'].replace(' ', 'T')) if row['created_at'] else datetime.now()
                    }
                )
                category_map[row['id']] = category
                action = "Создана" if created else "Обновлена"
                print(f"  {action} категория: {row['name']} для пользователя {tg_user.username or tg_user.telegram_id}")
        except Exception as e:
            print(f"  ❌ Ошибка с категорией {row['name']}: {e}")

    print(f"✅ Мигрировано категорий: {len(category_map)}\n")

    # 3. РАСХОДЫ
    print("3. Миграция расходов...")
    cursor.execute("SELECT COUNT(*) as total FROM bot_expense")
    total_expenses = cursor.fetchone()['total']
    print(f"  Всего расходов к миграции: {total_expenses}")

    cursor.execute("SELECT * FROM bot_expense ORDER BY created_at")
    expenses = cursor.fetchall()

    migrated_count = 0
    error_count = 0

    with transaction.atomic():
        for i, row in enumerate(expenses, 1):
            try:
                tg_user = user_map.get(row['user_id'])
                category = category_map.get(row['category_id']) if row['category_id'] else None

                if tg_user:
                    expense = Expense.objects.create(
                        user=tg_user,
                        amount=Decimal(str(row['amount'])),
                        category=category,
                        description=row['description'] or '',
                        date=datetime.fromisoformat(row['date'].replace(' ', 'T')) if row['date'] else datetime.now(),
                        created_at=datetime.fromisoformat(row['created_at'].replace(' ', 'T')) if row['created_at'] else datetime.now(),
                        is_recurring=bool(row['is_recurring']) if row['is_recurring'] is not None else False,
                        payment_method=row['payment_method'] or 'cash',
                        notes=row['notes'],
                        is_deleted=bool(row['is_deleted']) if row['is_deleted'] is not None else False,
                    )
                    migrated_count += 1

                    if i % 100 == 0:
                        print(f"  Обработано {i}/{total_expenses} расходов...")
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Показываем только первые 5 ошибок
                    print(f"  ❌ Ошибка с расходом #{i}: {e}")

    print(f"✅ Мигрировано расходов: {migrated_count} из {total_expenses}")
    if error_count > 0:
        print(f"⚠️  Ошибок при миграции: {error_count}\n")
    else:
        print()

    # 4. РЕГУЛЯРНЫЕ ПЛАТЕЖИ
    print("4. Миграция регулярных платежей...")
    cursor.execute("SELECT * FROM bot_recurringpayment")
    recurring = cursor.fetchall()

    recurring_count = 0
    for row in recurring:
        try:
            tg_user = user_map.get(row['user_id'])
            category = category_map.get(row['category_id']) if row['category_id'] else None

            if tg_user:
                RecurringPayment.objects.create(
                    user=tg_user,
                    amount=Decimal(str(row['amount'])),
                    category=category,
                    description=row['description'] or '',
                    frequency=row['frequency'] or 'monthly',
                    next_payment_date=datetime.fromisoformat(row['next_payment_date'].replace(' ', 'T')).date() if row['next_payment_date'] else None,
                    is_active=bool(row['is_active']) if row['is_active'] is not None else True,
                    created_at=datetime.fromisoformat(row['created_at'].replace(' ', 'T')) if row['created_at'] else datetime.now(),
                    payment_day=row['payment_day'] or 1,
                    reminder_enabled=bool(row['reminder_enabled']) if row['reminder_enabled'] is not None else True,
                    auto_create_expense=bool(row['auto_create_expense']) if row['auto_create_expense'] is not None else False
                )
                recurring_count += 1
                print(f"  Создан регулярный платеж: {row['description']}")
        except Exception as e:
            print(f"  ❌ Ошибка с регулярным платежом: {e}")

    print(f"✅ Мигрировано регулярных платежей: {recurring_count}\n")

    # 5. ПОДПИСКИ
    print("5. Миграция подписок...")
    cursor.execute("SELECT * FROM bot_usersubscription")
    subscriptions = cursor.fetchall()

    subscription_count = 0
    for row in subscriptions:
        try:
            tg_user = user_map.get(row['user_id'])
            if tg_user:
                UserSubscription.objects.create(
                    user=tg_user,
                    plan_type=row['plan_type'] or 'free',
                    start_date=datetime.fromisoformat(row['start_date'].replace(' ', 'T')) if row['start_date'] else datetime.now(),
                    end_date=datetime.fromisoformat(row['end_date'].replace(' ', 'T')) if row['end_date'] else None,
                    is_active=bool(row['is_active']) if row['is_active'] is not None else True,
                    payment_provider=row['payment_provider'] or '',
                    payment_id=row['payment_id'] or '',
                    amount=Decimal(str(row['amount'])) if row['amount'] else Decimal('0'),
                    currency=row['currency'] or 'RUB',
                    auto_renew=bool(row['auto_renew']) if row['auto_renew'] is not None else False,
                )
                subscription_count += 1
        except Exception as e:
            print(f"  ❌ Ошибка с подпиской: {e}")

    print(f"✅ Мигрировано подписок: {subscription_count}\n")

    conn.close()

    # ИТОГОВАЯ СТАТИСТИКА
    print("=" * 50)
    print("🎉 МИГРАЦИЯ ЗАВЕРШЕНА!")
    print("=" * 50)
    print(f"📊 Итоговая статистика в PostgreSQL:")
    print(f"  • Пользователи: {TelegramUser.objects.count()}")
    print(f"  • Категории: {Category.objects.count()}")
    print(f"  • Расходы: {Expense.objects.count()}")
    print(f"  • Регулярные платежи: {RecurringPayment.objects.count()}")
    print(f"  • Подписки: {UserSubscription.objects.count()}")

    # Проверяем конкретных пользователей
    print("\n📋 Детали по пользователям:")
    for tg_user in TelegramUser.objects.all()[:5]:  # Показываем первых 5
        expense_count = Expense.objects.filter(user=tg_user).count()
        category_count = Category.objects.filter(user=tg_user).count()
        print(f"  • {tg_user.username or tg_user.telegram_id}: {expense_count} расходов, {category_count} категорий")

if __name__ == "__main__":
    try:
        migrate_all()
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)