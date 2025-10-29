#!/usr/bin/env python
"""
ПОЛНАЯ МИГРАЦИЯ ВСЕХ ДАННЫХ ИЗ SQLITE В POSTGRESQL
"""
import sqlite3
from datetime import datetime, date, time as datetime_time
from decimal import Decimal

print("=" * 50)
print("ПОЛНАЯ МИГРАЦИЯ ВСЕХ ДАННЫХ")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем что есть в базе
cursor.execute("SELECT COUNT(*) FROM users_profile")
total_profiles = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM expenses_expense")
total_expenses = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM expenses_category")
total_categories = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM households")
total_households = cursor.fetchone()[0]

print(f"\nДанные в SQLite для миграции:")
print(f"  Профилей: {total_profiles}")
print(f"  Домохозяйств: {total_households}")
print(f"  Категорий: {total_categories}")
print(f"  Расходов: {total_expenses}")

# Импортируем модели Django
from expenses.models import Profile, Household, ExpenseCategory, Expense, RecurringPayment, UserSettings

# ОЧИСТКА СУЩЕСТВУЮЩИХ ДАННЫХ
print("\n1. Очищаем существующие данные в PostgreSQL...")
Expense.objects.all().delete()
ExpenseCategory.objects.all().delete()
RecurringPayment.objects.all().delete()
UserSettings.objects.all().delete()
Profile.objects.all().delete()
Household.objects.all().delete()
print("  ✓ База очищена")

# МИГРАЦИЯ ДОМОХОЗЯЙСТВ
print("\n2. Мигрируем домохозяйства...")
cursor.execute("SELECT * FROM households")
households = cursor.fetchall()
household_map = {}

for row in households:
    household = Household.objects.create(
        id=row['id'],
        name=row['name'] or f"Household {row['id']}",
        is_active=bool(row['is_active']) if row['is_active'] is not None else True,
        max_members=row['max_members'] or 5,
        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now()
    )
    household_map[row['id']] = household
    print(f"  + Домохозяйство: {household.name} (ID={household.id})")

print(f"  Итого домохозяйств: {len(household_map)}")

# МИГРАЦИЯ ПРОФИЛЕЙ
print("\n3. Мигрируем профили пользователей...")
cursor.execute("SELECT * FROM users_profile")
profiles = cursor.fetchall()
profile_map = {}

for row in profiles:
    # Получаем домохозяйство если есть
    household = household_map.get(row['household_id']) if row['household_id'] else None

    profile = Profile.objects.create(
        id=row['id'],
        telegram_id=row['telegram_id'],
        language_code=row['language_code'] or 'ru',
        timezone=row['timezone'] or 'Europe/Moscow',
        currency=row['currency'] or 'RUB',
        is_active=bool(row['is_active']) if row['is_active'] is not None else True,
        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
        is_beta_tester=bool(row['is_beta_tester']) if row['is_beta_tester'] else False,
        household=household,
        referral_code=row['referral_code'],
        last_activity=datetime.fromisoformat(row['last_activity']) if row['last_activity'] else None,
    )
    profile_map[row['id']] = profile

    household_info = f", домохозяйство={household.name}" if household else ""
    print(f"  + Профиль: {row['telegram_id']} (ID={row['id']}{household_info})")

print(f"  Итого профилей: {len(profile_map)}")

# МИГРАЦИЯ НАСТРОЕК ПОЛЬЗОВАТЕЛЕЙ
print("\n4. Мигрируем настройки пользователей...")
cursor.execute("SELECT * FROM users_settings")
settings_rows = cursor.fetchall()

for row in settings_rows:
    profile = profile_map.get(row['profile_id'])
    if profile:
        settings = UserSettings.objects.create(
            profile=profile,
            view_scope=row['view_scope'] if 'view_scope' in row.keys() else 'personal',
            notifications_enabled=bool(row['notifications_enabled']) if 'notifications_enabled' in row.keys() else True,
        )
        print(f"  + Настройки для профиля {profile.telegram_id}: view_scope={settings.view_scope}")

print(f"  Итого настроек: {len(settings_rows)}")

# МИГРАЦИЯ КАТЕГОРИЙ
print("\n5. Мигрируем категории...")
cursor.execute("SELECT * FROM expenses_category")
categories = cursor.fetchall()
category_map = {}

for row in categories:
    profile = profile_map.get(row['profile_id'])
    if not profile:
        continue

    category = ExpenseCategory.objects.create(
        id=row['id'],
        profile=profile,
        name=row['name'],
        name_ru=row['name_ru'] or row['name'],
        name_en=row['name_en'],
        icon=row['icon'] or '💰',
        is_active=bool(row['is_active']) if row['is_active'] is not None else True,
        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
    )
    category_map[row['id']] = category

print(f"  Итого категорий: {len(category_map)}")

# МИГРАЦИЯ РАСХОДОВ
print("\n6. Мигрируем расходы...")
cursor.execute("SELECT * FROM expenses_expense ORDER BY created_at")
expenses = cursor.fetchall()

migrated = 0
for row in expenses:
    profile = profile_map.get(row['profile_id'])
    if not profile:
        continue

    category = category_map.get(row['category_id']) if row['category_id'] else None

    # Парсим дату и время
    expense_date = date.fromisoformat(row['expense_date']) if row['expense_date'] else date.today()
    expense_time = datetime_time.fromisoformat(row['expense_time']) if row['expense_time'] else datetime.now().time()

    expense = Expense.objects.create(
        profile=profile,
        amount=Decimal(str(row['amount'])),
        category=category,
        description=row['description'] or '',
        expense_date=expense_date,
        expense_time=expense_time,
        currency=row['currency'] or 'RUB',
        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
        payment_method=row['payment_method'] if row['payment_method'] else 'cash',
        is_deleted=bool(row['is_deleted']) if row['is_deleted'] else False,
        ai_categorized=bool(row['ai_categorized']) if row['ai_categorized'] else False,
        ai_confidence=Decimal(str(row['ai_confidence'])) if row['ai_confidence'] else None,
    )
    migrated += 1

    if migrated % 20 == 0:
        print(f"  Мигрировано {migrated} расходов...")

print(f"  Итого расходов: {migrated}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n7. Мигрируем регулярные платежи...")
cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring_rows = cursor.fetchall()

for row in recurring_rows:
    profile = profile_map.get(row['profile_id'])
    if not profile:
        continue

    category = category_map.get(row['category_id']) if row['category_id'] else None

    RecurringPayment.objects.create(
        profile=profile,
        amount=Decimal(str(row['amount'])),
        expense_category=category,
        description=row['description'] or '',
        operation_type='expense',
        period_type=row['frequency'] if row['frequency'] else 'monthly',
        start_date=date.fromisoformat(row['start_date']) if row['start_date'] else date.today(),
        next_payment_date=date.fromisoformat(row['next_payment_date']) if row['next_payment_date'] else None,
        is_active=bool(row['is_active']) if row['is_active'] is not None else True,
        payment_day=row['payment_day'] or 1,
    )

print(f"  Итого регулярных платежей: {len(recurring_rows)}")

conn.close()

# ФИНАЛЬНАЯ ПРОВЕРКА
print("\n" + "=" * 50)
print("ПРОВЕРКА РЕЗУЛЬТАТОВ МИГРАЦИИ")
print("=" * 50)

print(f"\nМигрировано в PostgreSQL:")
print(f"  Домохозяйств: {Household.objects.count()}")
print(f"  Профилей: {Profile.objects.count()}")
print(f"  Настроек: {UserSettings.objects.count()}")
print(f"  Категорий: {ExpenseCategory.objects.count()}")
print(f"  Расходов: {Expense.objects.count()}")
print(f"  Регулярных платежей: {RecurringPayment.objects.count()}")

# Проверяем пользователя 881292737
print("\n" + "=" * 50)
print("ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ 881292737")
print("=" * 50)

try:
    profile = Profile.objects.get(telegram_id=881292737)
    expenses = Expense.objects.filter(profile=profile)
    categories = ExpenseCategory.objects.filter(profile=profile)

    print(f"✓ Профиль найден:")
    print(f"  ID: {profile.id}")
    print(f"  Домохозяйство: {profile.household.name if profile.household else 'НЕТ'}")
    print(f"  Категорий: {categories.count()}")
    print(f"  Расходов: {expenses.count()}")

    if expenses.exists():
        total = sum(e.amount for e in expenses)
        print(f"  Общая сумма: {total:.2f} руб")

        # Показываем последние 5 расходов
        print(f"\n  Последние 5 расходов:")
        for e in expenses.order_by('-expense_date', '-expense_time')[:5]:
            cat_name = e.category.name if e.category else 'Без категории'
            print(f"    {e.expense_date}: {e.amount:.2f} - {cat_name} - {e.description[:30]}")

    # Проверяем настройки
    try:
        settings = UserSettings.objects.get(profile=profile)
        print(f"\n  Настройки:")
        print(f"    view_scope: {settings.view_scope}")
    except UserSettings.DoesNotExist:
        print(f"\n  ⚠ Настройки не найдены")

except Profile.DoesNotExist:
    print("❌ Профиль 881292737 НЕ НАЙДЕН!")

print("\n✅ МИГРАЦИЯ ЗАВЕРШЕНА!")
print("Перезапустите бота: docker-compose restart bot")