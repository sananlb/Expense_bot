import sqlite3
from datetime import datetime
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, Expense, RecurringPayment

print("=" * 50)
print("МИГРАЦИЯ ДАННЫХ ИЗ SQLITE В POSTGRESQL")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем что есть в базе
cursor.execute("SELECT COUNT(*) as cnt FROM bot_telegramuser")
users_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM bot_expense")
expenses_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM bot_category")
categories_count = cursor.fetchone()['cnt']

print(f"\nДанные в SQLite:")
print(f"  Пользователей: {users_count}")
print(f"  Категорий: {categories_count}")
print(f"  Расходов: {expenses_count}")

if users_count == 0:
    print("\nБаза данных SQLite пуста!")
    exit()

# МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ
print("\n1. Мигрируем пользователей...")
cursor.execute("SELECT * FROM bot_telegramuser")
users = cursor.fetchall()
user_map = {}

for row in users:
    try:
        # Создаем Profile
        profile, created = Profile.objects.update_or_create(
            telegram_id=row['telegram_id'],
            defaults={
                'language_code': row['language_code'] or 'ru',
                'timezone': row['timezone'] or 'Europe/Moscow',
                'is_active': True,
            }
        )
        user_map[row['telegram_id']] = profile

        if created:
            print(f"  + Создан: {row['username'] or row['telegram_id']}")
        else:
            print(f"  ~ Обновлен: {row['username'] or row['telegram_id']}")

    except Exception as e:
        print(f"  ! Ошибка с пользователем {row['telegram_id']}: {str(e)[:50]}")

print(f"  Итого пользователей: {len(user_map)}")

# МИГРАЦИЯ КАТЕГОРИЙ
print("\n2. Мигрируем категории...")
cursor.execute("SELECT * FROM bot_category")
categories = cursor.fetchall()
category_map = {}

for row in categories:
    try:
        profile = user_map.get(row['user_id'])
        if not profile:
            continue

        category, created = ExpenseCategory.objects.update_or_create(
            name=row['name'],
            profile=profile,
            defaults={
                'emoji': row['icon'] or '',
                'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                'order': row['order'] or 0,
            }
        )
        category_map[row['id']] = category

        if created:
            print(f"  + {row['name']}")

    except Exception as e:
        print(f"  ! Ошибка с категорией {row['name']}: {str(e)[:50]}")

print(f"  Итого категорий: {len(category_map)}")

# МИГРАЦИЯ РАСХОДОВ
print("\n3. Мигрируем расходы...")
cursor.execute("SELECT * FROM bot_expense ORDER BY created_at")
expenses = cursor.fetchall()

migrated = 0
errors = 0

for i, row in enumerate(expenses, 1):
    try:
        profile = user_map.get(row['user_id'])
        if not profile:
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим даты
        expense_date = datetime.now()
        if row['date']:
            try:
                expense_date = datetime.fromisoformat(row['date'].replace(' ', 'T'))
            except:
                expense_date = datetime.now()

        created_at = datetime.now()
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'].replace(' ', 'T'))
            except:
                created_at = datetime.now()

        expense = Expense.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            category=category,
            description=row['description'] or '',
            date=expense_date,
            created_at=created_at,
            payment_method=row['payment_method'] or 'cash',
            is_deleted=bool(row['is_deleted']) if row['is_deleted'] else False,
        )
        migrated += 1

        if migrated % 100 == 0:
            print(f"  Обработано {migrated} расходов...")

    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ! Ошибка с расходом #{i}: {str(e)[:50]}")

print(f"  Мигрировано расходов: {migrated}")
if errors > 0:
    print(f"  Ошибок: {errors}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n4. Мигрируем регулярные платежи...")
cursor.execute("SELECT * FROM bot_recurringpayment")
recurring = cursor.fetchall()

recurring_count = 0
for row in recurring:
    try:
        profile = user_map.get(row['user_id'])
        if not profile:
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим дату следующего платежа
        next_payment = None
        if row['next_payment_date']:
            try:
                next_payment = datetime.fromisoformat(row['next_payment_date'].replace(' ', 'T')).date()
            except:
                pass

        RecurringPayment.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            category=category,
            description=row['description'] or '',
            frequency=row['frequency'] or 'monthly',
            next_payment_date=next_payment,
            is_active=bool(row['is_active']) if row['is_active'] is not None else True,
            payment_day=row['payment_day'] or 1,
            reminder_enabled=bool(row['reminder_enabled']) if row['reminder_enabled'] is not None else True,
        )
        recurring_count += 1
        print(f"  + {row['description'] or 'Без описания'}")

    except Exception as e:
        print(f"  ! Ошибка: {str(e)[:50]}")

print(f"  Итого регулярных платежей: {recurring_count}")

conn.close()

# ФИНАЛЬНАЯ СТАТИСТИКА
print("\n" + "=" * 50)
print("МИГРАЦИЯ ЗАВЕРШЕНА!")
print("=" * 50)
print("\nИтоговая статистика в PostgreSQL:")
print(f"  Пользователей: {Profile.objects.count()}")
print(f"  Категорий: {ExpenseCategory.objects.count()}")
print(f"  Расходов: {Expense.objects.count()}")
print(f"  Регулярных платежей: {RecurringPayment.objects.count()}")

# Показываем данные по каждому пользователю
print("\nДетали по пользователям:")
for profile in Profile.objects.all()[:5]:  # Первые 5 пользователей
    expenses = Expense.objects.filter(profile=profile).count()
    categories = ExpenseCategory.objects.filter(profile=profile).count()
    recurring = RecurringPayment.objects.filter(profile=profile).count()
    print(f"  {profile.telegram_id}: {expenses} расходов, {categories} категорий, {recurring} регулярных")

print("\nГотово! Перезапустите бота командой: docker-compose restart bot")