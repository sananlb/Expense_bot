import sqlite3
from datetime import datetime, date, time
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, Expense, RecurringPayment

print("=" * 50)
print("МИГРАЦИЯ ДАННЫХ ИЗ SQLITE В POSTGRESQL")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем что есть в базе (используем правильные имена таблиц)
cursor.execute("SELECT COUNT(*) as cnt FROM users_profile")
users_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM expenses_expense")
expenses_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM expenses_category")
categories_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM expenses_recurring_payment")
recurring_count = cursor.fetchone()['cnt']

print(f"\nДанные в SQLite:")
print(f"  Профилей: {users_count}")
print(f"  Категорий: {categories_count}")
print(f"  Расходов: {expenses_count}")
print(f"  Регулярных платежей: {recurring_count}")

if users_count == 0:
    print("\nБаза данных SQLite пуста!")
    exit()

# МИГРАЦИЯ ПРОФИЛЕЙ
print("\n1. Мигрируем профили пользователей...")
cursor.execute("SELECT * FROM users_profile")
profiles = cursor.fetchall()
profile_map = {}  # id -> Profile

for row in profiles:
    try:
        # Создаем или обновляем Profile
        profile, created = Profile.objects.update_or_create(
            telegram_id=row['telegram_id'],
            defaults={
                'language_code': row['language_code'] or 'ru',
                'timezone': row['timezone'] or 'Europe/Moscow',
                'currency': row['currency'] or 'RUB',
                'is_active': bool(row['is_active']),
                'created_at': datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                'updated_at': datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
                'is_beta_tester': bool(row['is_beta_tester']) if row['is_beta_tester'] else False,
                'beta_access_key': row['beta_access_key'],
                'referral_code': row['referral_code'],
                'last_activity': datetime.fromisoformat(row['last_activity']) if row['last_activity'] else None,
                'accepted_privacy': bool(row['accepted_privacy']) if row['accepted_privacy'] else False,
                'accepted_offer': bool(row['accepted_offer']) if row['accepted_offer'] else False,
            }
        )
        profile_map[row['id']] = profile

        if created:
            print(f"  + Создан профиль: {row['telegram_id']}")
        else:
            print(f"  ~ Обновлен профиль: {row['telegram_id']}")

    except Exception as e:
        print(f"  ! Ошибка с профилем {row['telegram_id']}: {str(e)[:50]}")

print(f"  Итого профилей: {len(profile_map)}")

# МИГРАЦИЯ КАТЕГОРИЙ
print("\n2. Мигрируем категории...")
cursor.execute("SELECT * FROM expenses_category")
categories = cursor.fetchall()
category_map = {}  # id -> ExpenseCategory

for row in categories:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            print(f"  ! Профиль не найден для категории {row['name']}")
            continue

        # Используем emoji вместо icon если есть
        emoji = row['icon'] if row['icon'] else ''

        category, created = ExpenseCategory.objects.update_or_create(
            name=row['name'],
            profile=profile,
            defaults={
                'emoji': emoji,
                'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                'created_at': datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
                'updated_at': datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now(),
            }
        )
        category_map[row['id']] = category

        if created:
            print(f"  + Создана категория: {row['name']}")

    except Exception as e:
        print(f"  ! Ошибка с категорией {row['name']}: {str(e)[:50]}")

print(f"  Итого категорий: {len(category_map)}")

# МИГРАЦИЯ РАСХОДОВ
print("\n3. Мигрируем расходы...")
cursor.execute("SELECT * FROM expenses_expense ORDER BY created_at")
expenses = cursor.fetchall()

migrated = 0
errors = 0

for i, row in enumerate(expenses, 1):
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            errors += 1
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим дату и время
        expense_date = date.today()
        if row['expense_date']:
            try:
                expense_date = date.fromisoformat(row['expense_date'])
            except:
                expense_date = date.today()

        expense_time = None
        if row['expense_time']:
            try:
                expense_time = time.fromisoformat(row['expense_time'])
            except:
                pass

        created_at = datetime.now()
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'])
            except:
                created_at = datetime.now()

        # Создаем расход
        expense = Expense.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            category=category,
            description=row['description'] or '',
            expense_date=expense_date,
            expense_time=expense_time,
            created_at=created_at,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else created_at,
            payment_method=row['payment_method'] if row['payment_method'] else 'cash',
            is_deleted=bool(row['is_deleted']) if row['is_deleted'] else False,
            ai_categorized=bool(row['ai_categorized']) if row['ai_categorized'] else False,
            ai_confidence=Decimal(str(row['ai_confidence'])) if row['ai_confidence'] else None,
        )
        migrated += 1

        if migrated % 20 == 0:
            print(f"  Обработано {migrated} расходов...")

    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ! Ошибка с расходом #{i}: {str(e)[:80]}")

print(f"  Мигрировано расходов: {migrated}")
if errors > 0:
    print(f"  Ошибок: {errors}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n4. Мигрируем регулярные платежи...")
cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring = cursor.fetchall()

recurring_migrated = 0
for row in recurring:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим дату следующего платежа
        next_payment = None
        if row['next_payment_date']:
            try:
                next_payment = date.fromisoformat(row['next_payment_date'])
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
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
        )
        recurring_migrated += 1
        print(f"  + {row['description'] or 'Без описания'}")

    except Exception as e:
        print(f"  ! Ошибка: {str(e)[:80]}")

print(f"  Итого регулярных платежей: {recurring_migrated}")

conn.close()

# ФИНАЛЬНАЯ СТАТИСТИКА
print("\n" + "=" * 50)
print("МИГРАЦИЯ ЗАВЕРШЕНА!")
print("=" * 50)
print("\nИтоговая статистика в PostgreSQL:")
print(f"  Профилей: {Profile.objects.count()}")
print(f"  Категорий: {ExpenseCategory.objects.count()}")
print(f"  Расходов: {Expense.objects.count()}")
print(f"  Регулярных платежей: {RecurringPayment.objects.count()}")

# Показываем данные по каждому пользователю
print("\nДетали по пользователям:")
for profile in Profile.objects.all():
    expenses = Expense.objects.filter(profile=profile).count()
    categories = ExpenseCategory.objects.filter(profile=profile).count()
    recurring = RecurringPayment.objects.filter(profile=profile).count()
    total = sum(e.amount for e in Expense.objects.filter(profile=profile))
    print(f"  {profile.telegram_id}: {expenses} расходов на {total:.2f}, {categories} категорий, {recurring} регулярных")

print("\nГотово! Перезапустите бота командой: docker-compose restart bot")