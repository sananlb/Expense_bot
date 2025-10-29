import sqlite3
from datetime import datetime, date, time as datetime_time
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, Expense, RecurringPayment

print("=" * 50)
print("МИГРАЦИЯ РАСХОДОВ И РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем структуру таблицы expenses_expense
print("\nСтруктура таблицы expenses_expense:")
cursor.execute("PRAGMA table_info(expenses_expense)")
columns = cursor.fetchall()
column_names = []
for col in columns:
    column_names.append(col['name'])
    print(f"  {col['name']} ({col['type']})")

print(f"\nВсего колонок: {len(column_names)}")

# Получаем одну запись для анализа
cursor.execute("SELECT * FROM expenses_expense LIMIT 1")
sample_expense = cursor.fetchone()
if sample_expense:
    print("\nПример записи расхода:")
    for col in column_names[:15]:  # Первые 15 полей
        try:
            value = sample_expense[col]
            print(f"  {col}: {value}")
        except:
            print(f"  {col}: <error accessing>")

# СОЗДАЕМ МАППИНГИ
print("\n" + "=" * 50)
print("ПОДГОТОВКА МАППИНГОВ")
print("=" * 50)

# Маппинг профилей
cursor.execute("SELECT id, telegram_id FROM users_profile")
profile_rows = cursor.fetchall()
profile_map = {}

for row in profile_rows:
    try:
        profile = Profile.objects.get(telegram_id=row['telegram_id'])
        profile_map[row['id']] = profile
    except Profile.DoesNotExist:
        pass

print(f"Профилей для маппинга: {len(profile_map)}")

# Маппинг категорий
cursor.execute("SELECT id, name, profile_id FROM expenses_category")
category_rows = cursor.fetchall()
category_map = {}

for row in category_rows:
    try:
        profile = profile_map.get(row['profile_id'])
        if profile:
            category = ExpenseCategory.objects.get(
                profile=profile,
                name=row['name']
            )
            category_map[row['id']] = category
    except ExpenseCategory.DoesNotExist:
        pass

print(f"Категорий для маппинга: {len(category_map)}")

# МИГРАЦИЯ РАСХОДОВ
print("\n" + "=" * 50)
print("МИГРАЦИЯ РАСХОДОВ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_expense ORDER BY created_at")
expenses = cursor.fetchall()

migrated = 0
errors = 0

for i, expense_row in enumerate(expenses, 1):
    try:
        # Используем dict() для конвертации sqlite3.Row в словарь
        row = dict(expense_row)

        profile = profile_map.get(row.get('profile_id'))
        if not profile:
            errors += 1
            if errors <= 3:
                print(f"  ! Профиль id={row.get('profile_id')} не найден")
            continue

        category = category_map.get(row.get('category_id')) if row.get('category_id') else None

        # Парсим дату
        expense_date = date.today()
        if row.get('expense_date'):
            try:
                expense_date = date.fromisoformat(row['expense_date'])
            except:
                expense_date = date.today()

        # Парсим время
        expense_time = datetime.now().time()
        if row.get('expense_time'):
            try:
                expense_time = datetime_time.fromisoformat(row['expense_time'])
            except:
                expense_time = datetime.now().time()

        # Создаем расход с минимальными обязательными полями
        expense_data = {
            'profile': profile,
            'amount': Decimal(str(row.get('amount', 0))),
            'description': row.get('description', ''),
            'expense_date': expense_date,
            'expense_time': expense_time,
        }

        # Добавляем опциональные поля если они есть
        if category:
            expense_data['category'] = category

        if row.get('currency'):
            expense_data['currency'] = row['currency']

        if row.get('payment_method'):
            expense_data['payment_method'] = row['payment_method']

        if row.get('is_deleted') is not None:
            expense_data['is_deleted'] = bool(row['is_deleted'])

        if row.get('ai_categorized') is not None:
            expense_data['ai_categorized'] = bool(row['ai_categorized'])

        if row.get('ai_confidence') is not None:
            expense_data['ai_confidence'] = Decimal(str(row['ai_confidence']))

        expense = Expense.objects.create(**expense_data)
        migrated += 1

        if migrated % 20 == 0:
            print(f"  Мигрировано {migrated} расходов...")

    except Exception as e:
        errors += 1
        if errors <= 5:
            print(f"  ! Ошибка с расходом #{i}: {e}")
            import traceback
            if errors == 1:
                traceback.print_exc()

print(f"\nИтого мигрировано расходов: {migrated} из {len(expenses)}")
if errors > 0:
    print(f"Ошибок: {errors}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n" + "=" * 50)
print("МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring_rows = cursor.fetchall()

recurring_count = 0
for recurring_row in recurring_rows:
    try:
        row = dict(recurring_row)

        profile = profile_map.get(row.get('profile_id'))
        if not profile:
            print(f"  ! Профиль id={row.get('profile_id')} не найден")
            continue

        category = category_map.get(row.get('category_id')) if row.get('category_id') else None

        # Парсим дату следующего платежа
        next_payment_date = None
        if row.get('next_payment_date'):
            try:
                next_payment_date = date.fromisoformat(row['next_payment_date'])
            except:
                pass

        recurring_data = {
            'profile': profile,
            'amount': Decimal(str(row.get('amount', 0))),
            'description': row.get('description', 'Регулярный платеж'),
            'frequency': row.get('frequency', 'monthly'),
        }

        if category:
            recurring_data['category'] = category

        if next_payment_date:
            recurring_data['next_payment_date'] = next_payment_date

        if row.get('is_active') is not None:
            recurring_data['is_active'] = bool(row['is_active'])

        if row.get('payment_day'):
            recurring_data['payment_day'] = row['payment_day']

        if row.get('reminder_enabled') is not None:
            recurring_data['reminder_enabled'] = bool(row['reminder_enabled'])

        RecurringPayment.objects.create(**recurring_data)
        recurring_count += 1
        print(f"  + Создан регулярный платеж: {row.get('description', 'Без описания')}")

    except Exception as e:
        print(f"  ! Ошибка с регулярным платежом: {e}")

print(f"\nИтого регулярных платежей: {recurring_count}")

conn.close()

# ФИНАЛЬНАЯ СТАТИСТИКА
print("\n" + "=" * 50)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 50)
print(f"Профилей: {Profile.objects.count()}")
print(f"Категорий: {ExpenseCategory.objects.count()}")
print(f"Расходов: {Expense.objects.count()}")
print(f"Регулярных платежей: {RecurringPayment.objects.count()}")

print("\nДетали по пользователям:")
for profile in Profile.objects.all():
    expenses = Expense.objects.filter(profile=profile)
    expense_count = expenses.count()
    if expense_count > 0:
        total_amount = sum(e.amount for e in expenses)
        categories = ExpenseCategory.objects.filter(profile=profile).count()
        print(f"  {profile.telegram_id}: {expense_count} расходов на {total_amount:.2f}, {categories} категорий")

print("\n✅ Готово! Перезапустите бота: docker-compose restart bot")