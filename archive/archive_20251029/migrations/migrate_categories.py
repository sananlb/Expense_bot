import sqlite3
from datetime import datetime, date, time
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, Expense, RecurringPayment

print("=" * 50)
print("МИГРАЦИЯ КАТЕГОРИЙ И РАСХОДОВ")
print("=" * 50)

# Сначала проверим какие поля есть у ExpenseCategory
print("\nПоля модели ExpenseCategory:")
for field in ExpenseCategory._meta.fields:
    print(f"  {field.name} ({field.get_internal_type()})")

print("\nПоля модели Expense:")
for field in Expense._meta.fields[:10]:  # Первые 10 полей
    print(f"  {field.name} ({field.get_internal_type()})")

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Получаем маппинг профилей
cursor.execute("SELECT id, telegram_id FROM users_profile")
profile_rows = cursor.fetchall()
profile_map = {}
for row in profile_rows:
    try:
        profile = Profile.objects.get(telegram_id=row['telegram_id'])
        profile_map[row['id']] = profile
        print(f"Найден профиль: {row['telegram_id']}")
    except Profile.DoesNotExist:
        print(f"Профиль не найден: {row['telegram_id']}")

print(f"\nВсего профилей для маппинга: {len(profile_map)}")

# МИГРАЦИЯ КАТЕГОРИЙ - пытаемся определить правильные поля
print("\n" + "=" * 50)
print("МИГРАЦИЯ КАТЕГОРИЙ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_category")
categories = cursor.fetchall()
category_map = {}

for row in categories:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            print(f"  ! Профиль {row['profile_id']} не найден для категории {row['name']}")
            continue

        # Пробуем создать категорию с минимальными полями
        try:
            # Вариант 1: name и profile
            category = ExpenseCategory.objects.create(
                name=row['name'],
                profile=profile
            )
            category_map[row['id']] = category
            print(f"  + Создана категория: {row['name']}")
        except Exception as e1:
            # Вариант 2: title и profile
            try:
                category = ExpenseCategory.objects.create(
                    title=row['name'],
                    profile=profile
                )
                category_map[row['id']] = category
                print(f"  + Создана категория: {row['name']}")
            except Exception as e2:
                print(f"  ! Не удалось создать категорию {row['name']}")
                print(f"    Ошибка 1: {str(e1)[:50]}")
                print(f"    Ошибка 2: {str(e2)[:50]}")

    except Exception as e:
        print(f"  ! Общая ошибка с категорией {row['name']}: {str(e)[:80]}")

print(f"\nИтого категорий создано: {len(category_map)}")

# МИГРАЦИЯ РАСХОДОВ
print("\n" + "=" * 50)
print("МИГРАЦИЯ РАСХОДОВ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_expense ORDER BY created_at")
expenses = cursor.fetchall()

migrated = 0
errors = 0

for i, row in enumerate(expenses, 1):
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            errors += 1
            if errors <= 3:
                print(f"  ! Профиль {row['profile_id']} не найден для расхода #{i}")
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        # Парсим даты
        expense_date = date.today()
        if row['expense_date']:
            try:
                expense_date = date.fromisoformat(row['expense_date'])
            except:
                expense_date = date.today()

        # Создаем расход с минимальными полями
        expense = Expense.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            description=row['description'] or '',
            expense_date=expense_date
        )

        # Пытаемся добавить категорию
        if category:
            expense.category = category
            expense.save()

        migrated += 1

        if migrated % 20 == 0:
            print(f"  Мигрировано {migrated} расходов...")

    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ! Ошибка с расходом #{i}: {str(e)[:100]}")

print(f"\nВсего мигрировано расходов: {migrated}")
print(f"Ошибок: {errors}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n" + "=" * 50)
print("МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring_rows = cursor.fetchall()

recurring_count = 0
for row in recurring_rows:
    try:
        profile = profile_map.get(row['profile_id'])
        if not profile:
            print(f"  ! Профиль {row['profile_id']} не найден")
            continue

        category = category_map.get(row['category_id']) if row['category_id'] else None

        RecurringPayment.objects.create(
            profile=profile,
            amount=Decimal(str(row['amount'])),
            description=row['description'] or 'Регулярный платеж',
            frequency=row['frequency'] or 'monthly'
        )
        recurring_count += 1
        print(f"  + Создан регулярный платеж: {row['description'] or 'Без описания'}")

    except Exception as e:
        print(f"  ! Ошибка с регулярным платежом: {str(e)[:100]}")

print(f"\nВсего регулярных платежей: {recurring_count}")

conn.close()

# ИТОГОВАЯ СТАТИСТИКА
print("\n" + "=" * 50)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 50)
print(f"Профилей в БД: {Profile.objects.count()}")
print(f"Категорий в БД: {ExpenseCategory.objects.count()}")
print(f"Расходов в БД: {Expense.objects.count()}")
print(f"Регулярных платежей в БД: {RecurringPayment.objects.count()}")

print("\nДетали по профилям:")
for profile in Profile.objects.all():
    expenses = Expense.objects.filter(profile=profile).count()
    categories = ExpenseCategory.objects.filter(profile=profile).count()
    print(f"  {profile.telegram_id}: {expenses} расходов, {categories} категорий")