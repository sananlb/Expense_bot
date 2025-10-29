import sqlite3
from datetime import datetime, date
from decimal import Decimal
from expenses.models import Profile, ExpenseCategory, IncomeCategory, RecurringPayment

print("=" * 50)
print("МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ")
print("=" * 50)

# Сначала проверим какие поля есть у RecurringPayment
print("\nПоля модели RecurringPayment:")
for field in RecurringPayment._meta.fields[:20]:  # Первые 20 полей
    print(f"  {field.name} ({field.get_internal_type()})")

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Проверяем структуру таблицы expenses_recurring_payment
print("\nСтруктура таблицы expenses_recurring_payment:")
cursor.execute("PRAGMA table_info(expenses_recurring_payment)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col['name']} ({col['type']})")

# Получаем пример записи
cursor.execute("SELECT * FROM expenses_recurring_payment LIMIT 1")
sample = cursor.fetchone()
if sample:
    print("\nПример записи:")
    row_dict = dict(sample)
    for key, value in list(row_dict.items())[:15]:
        print(f"  {key}: {value}")

# СОЗДАЕМ МАППИНГИ
print("\n" + "=" * 50)

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

# Маппинг категорий расходов
cursor.execute("SELECT id, name, profile_id FROM expenses_category")
category_rows = cursor.fetchall()
expense_category_map = {}

for row in category_rows:
    try:
        profile = profile_map.get(row['profile_id'])
        if profile:
            category = ExpenseCategory.objects.get(
                profile=profile,
                name=row['name']
            )
            expense_category_map[row['id']] = category
    except ExpenseCategory.DoesNotExist:
        pass

print(f"Категорий расходов для маппинга: {len(expense_category_map)}")

# МИГРАЦИЯ РЕГУЛЯРНЫХ ПЛАТЕЖЕЙ
print("\n" + "=" * 50)
print("МИГРАЦИЯ")
print("=" * 50)

cursor.execute("SELECT * FROM expenses_recurring_payment")
recurring_rows = cursor.fetchall()

recurring_count = 0
for recurring_row in recurring_rows:
    try:
        row = dict(recurring_row)
        print(f"\nОбрабатываем регулярный платеж: {row.get('description', 'Без описания')}")

        profile = profile_map.get(row.get('profile_id'))
        if not profile:
            print(f"  ! Профиль id={row.get('profile_id')} не найден")
            continue

        category = expense_category_map.get(row.get('category_id')) if row.get('category_id') else None

        # Базовые обязательные поля для RecurringPayment
        recurring_data = {
            'profile': profile,
            'amount': Decimal(str(row.get('amount', 0))),
            'description': row.get('description', 'Регулярный платеж'),
            'operation_type': 'expense',  # По умолчанию расход
        }

        # Добавляем категорию если есть
        if category:
            recurring_data['expense_category'] = category
            print(f"  Категория: {category.name}")

        # Пытаемся добавить дополнительные поля
        if row.get('period_type'):
            recurring_data['period_type'] = row['period_type']
        elif row.get('frequency'):
            # Конвертируем frequency в period_type если нужно
            freq_map = {
                'monthly': 'monthly',
                'weekly': 'weekly',
                'daily': 'daily'
            }
            recurring_data['period_type'] = freq_map.get(row['frequency'], 'monthly')

        # Даты
        if row.get('start_date'):
            try:
                recurring_data['start_date'] = date.fromisoformat(row['start_date'])
            except:
                recurring_data['start_date'] = date.today()
        else:
            recurring_data['start_date'] = date.today()

        if row.get('end_date'):
            try:
                recurring_data['end_date'] = date.fromisoformat(row['end_date'])
            except:
                pass

        if row.get('next_payment_date'):
            try:
                recurring_data['next_payment_date'] = date.fromisoformat(row['next_payment_date'])
            except:
                pass

        if row.get('is_active') is not None:
            recurring_data['is_active'] = bool(row['is_active'])

        if row.get('payment_day'):
            recurring_data['payment_day'] = int(row['payment_day'])

        if row.get('reminder_enabled') is not None:
            recurring_data['reminder_enabled'] = bool(row['reminder_enabled'])

        print(f"  Создаем с полями: {list(recurring_data.keys())}")

        RecurringPayment.objects.create(**recurring_data)
        recurring_count += 1
        print(f"  ✓ Создан регулярный платеж: {row.get('description', 'Без описания')}")

    except Exception as e:
        print(f"  ! Ошибка: {e}")
        import traceback
        traceback.print_exc()

print(f"\nИтого регулярных платежей создано: {recurring_count}")

conn.close()

# ФИНАЛЬНАЯ СТАТИСТИКА
print("\n" + "=" * 50)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 50)
print(f"Профилей: {Profile.objects.count()}")
print(f"Категорий: {ExpenseCategory.objects.count()}")
print(f"Расходов: {Expense.objects.count()}")
print(f"Регулярных платежей: {RecurringPayment.objects.count()}")

print("\n✅ Миграция завершена!")