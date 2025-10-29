import sqlite3
from datetime import datetime, date, time as datetime_time
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, Expense, RecurringPayment

print("=" * 50)
print("ПОЛНАЯ МИГРАЦИЯ ДАННЫХ ИЗ SQLITE В POSTGRESQL")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем что есть в базе
cursor.execute("SELECT COUNT(*) as cnt FROM users_profile")
users_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM expenses_expense")
expenses_count = cursor.fetchone()['cnt']
cursor.execute("SELECT COUNT(*) as cnt FROM expenses_category")
categories_count = cursor.fetchone()['cnt']

print(f"\nДанные в SQLite:")
print(f"  Профилей: {users_count}")
print(f"  Категорий: {categories_count}")
print(f"  Расходов: {expenses_count}")

# СОЗДАЕМ МАППИНГ ПРОФИЛЕЙ (уже созданы в предыдущем запуске)
print("\n1. Получаем профили...")
cursor.execute("SELECT id, telegram_id FROM users_profile")
profile_rows = cursor.fetchall()
profile_map = {}

for row in profile_rows:
    try:
        profile = Profile.objects.get(telegram_id=row['telegram_id'])
        profile_map[row['id']] = profile
        print(f"  ✓ Найден профиль: {row['telegram_id']}")
    except Profile.DoesNotExist:
        print(f"  ✗ Профиль не найден: {row['telegram_id']}")

print(f"Всего профилей для маппинга: {len(profile_map)}")

# МИГРАЦИЯ КАТЕГОРИЙ
print("\n2. Мигрируем категории...")
cursor.execute("SELECT * FROM expenses_category")
categories = cursor.fetchall()
category_map = {}

for row in categories:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            print(f"  ! Профиль id={row['profile_id']} не найден")
            continue

        # Создаем категорию с правильными полями
        category, created = ExpenseCategory.objects.update_or_create(
            profile=profile,
            name=row['name'],
            defaults={
                'name_ru': row['name_ru'] or row['name'],
                'name_en': row['name_en'],
                'icon': row['icon'] or '💰',
                'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                'original_language': row['original_language'] or 'ru',
                'is_translatable': bool(row['is_translatable']) if row['is_translatable'] is not None else True,
            }
        )
        category_map[row['id']] = category

        if created:
            print(f"  + Создана категория: {row['name']}")
        else:
            print(f"  ~ Обновлена категория: {row['name']}")

    except Exception as e:
        print(f"  ! Ошибка с категорией {row['name']}: {e}")

print(f"Итого категорий: {len(category_map)}")

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

        # Парсим дату
        expense_date = date.today()
        if row['expense_date']:
            try:
                expense_date = date.fromisoformat(row['expense_date'])
            except:
                expense_date = date.today()

        # Парсим время
        expense_time = datetime.now().time()
        if row['expense_time']:
            try:
                expense_time = datetime_time.fromisoformat(row['expense_time'])
            except:
                expense_time = datetime.now().time()

        # Создаем расход
        expense = Expense.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            category=category,
            description=row['description'] or '',
            expense_date=expense_date,
            expense_time=expense_time,
            currency=row['currency'] or 'RUB',
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
            print(f"  ! Ошибка с расходом #{i}: {e}")

print(f"Мигрировано расходов: {migrated} из {len(expenses)}")
if errors > 0:
    print(f"Ошибок: {errors}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n4. Мигрируем регулярные платежи...")
cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring_rows = cursor.fetchall()

recurring_count = 0
for row in recurring_rows:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            print(f"  ! Профиль id={row['profile_id']} не найден")
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим дату следующего платежа
        next_payment_date = None
        if row['next_payment_date']:
            try:
                next_payment_date = date.fromisoformat(row['next_payment_date'])
            except:
                pass

        RecurringPayment.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            category=category,
            description=row['description'] or 'Регулярный платеж',
            frequency=row['frequency'] or 'monthly',
            next_payment_date=next_payment_date,
            is_active=bool(row['is_active']) if row['is_active'] is not None else True,
            payment_day=row['payment_day'] or 1,
            reminder_enabled=bool(row['reminder_enabled']) if row['reminder_enabled'] is not None else True,
        )
        recurring_count += 1
        print(f"  + Создан регулярный платеж: {row['description'] or 'Без описания'}")

    except Exception as e:
        print(f"  ! Ошибка с регулярным платежом: {e}")

print(f"Итого регулярных платежей: {recurring_count}")

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

# Детали по пользователям
print("\nДетали по пользователям:")
for profile in Profile.objects.all():
    expenses = Expense.objects.filter(profile=profile)
    expense_count = expenses.count()
    total_amount = sum(e.amount for e in expenses) if expense_count > 0 else 0
    categories = ExpenseCategory.objects.filter(profile=profile).count()
    recurring = RecurringPayment.objects.filter(profile=profile).count()

    if expense_count > 0 or categories > 0:
        print(f"  {profile.telegram_id}:")
        print(f"    - Расходов: {expense_count} на сумму {total_amount:.2f}")
        print(f"    - Категорий: {categories}")
        print(f"    - Регулярных платежей: {recurring}")

print("\n✅ Готово! Перезапустите бота: docker-compose restart bot")