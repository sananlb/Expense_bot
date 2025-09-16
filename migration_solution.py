#!/usr/bin/env python3
"""
Решение проблемы миграции SQLite -> PostgreSQL
Создание корректных Django fixtures для полной миграции данных
"""
import sqlite3
import json
import os
from datetime import datetime
from collections import defaultdict

def create_django_fixtures():
    """Создание Django fixtures из SQLite базы для корректной миграции"""

    conn = sqlite3.connect('/mnt/c/Users/_batman_/Desktop/expense_bot/expense_bot.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("СОЗДАНИЕ DJANGO FIXTURES ДЛЯ МИГРАЦИИ SQLite -> PostgreSQL")
    print("=" * 80)

    fixtures = []

    # 1. Миграция профилей пользователей
    print("\n1. Экспорт профилей пользователей...")
    cursor.execute('''
        SELECT id, telegram_id, language_code, timezone, currency, is_active,
               created_at, updated_at, beta_access_key, is_beta_tester,
               referral_code, last_activity, household_id, accepted_privacy,
               accepted_offer, referrer_id
        FROM users_profile
        ORDER BY id
    ''')

    profiles = cursor.fetchall()
    for profile in profiles:
        fixture = {
            "model": "expenses.profile",
            "pk": profile[0],
            "fields": {
                "telegram_id": profile[1],
                "language_code": profile[2] or 'ru',
                "timezone": profile[3] or 'UTC',
                "currency": profile[4] or 'RUB',
                "is_active": bool(profile[5]),
                "created_at": profile[6],
                "updated_at": profile[7],
                "beta_access_key": profile[8],
                "is_beta_tester": bool(profile[9]),
                "referral_code": profile[10],
                "last_activity": profile[11],
                "household": profile[12],
                "accepted_privacy": bool(profile[13]),
                "accepted_offer": bool(profile[14]),
                "referrer": profile[15]
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(profiles)} профилей")

    # 2. Миграция домохозяйств
    print("\n2. Экспорт домохозяйств...")
    cursor.execute('''
        SELECT id, created_at, name, creator_id, is_active, max_members
        FROM households
        ORDER BY id
    ''')

    households = cursor.fetchall()
    for household in households:
        fixture = {
            "model": "expenses.household",
            "pk": household[0],
            "fields": {
                "created_at": household[1],
                "name": household[2],
                "creator": household[3],
                "is_active": bool(household[4]),
                "max_members": household[5] or 5
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(households)} домохозяйств")

    # 3. Миграция категорий расходов
    print("\n3. Экспорт категорий расходов...")
    cursor.execute('''
        SELECT id, name, icon, is_active, created_at, updated_at, profile_id,
               name_ru, name_en, original_language, is_translatable
        FROM expenses_category
        ORDER BY id
    ''')

    categories = cursor.fetchall()
    for category in categories:
        fixture = {
            "model": "expenses.expensecategory",
            "pk": category[0],
            "fields": {
                "profile": category[6],
                "name": category[1] or 'Без категории',
                "icon": category[2] or '💰',
                "is_active": bool(category[3]),
                "created_at": category[4],
                "updated_at": category[5],
                "name_ru": category[7],
                "name_en": category[8],
                "original_language": category[9] or 'ru',
                "is_translatable": bool(category[10]) if category[10] is not None else True
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(categories)} категорий")

    # 4. Миграция трат
    print("\n4. Экспорт трат...")
    cursor.execute('''
        SELECT id, profile_id, category_id, amount, currency, description,
               expense_date, expense_time, receipt_photo, ai_categorized,
               ai_confidence, created_at, updated_at, cashback_excluded,
               cashback_amount
        FROM expenses_expense
        ORDER BY id
    ''')

    expenses = cursor.fetchall()
    for expense in expenses:
        fixture = {
            "model": "expenses.expense",
            "pk": expense[0],
            "fields": {
                "profile": expense[1],
                "category": expense[2],
                "amount": str(expense[3]),  # Decimal field
                "currency": expense[4] or 'RUB',
                "description": expense[5] or '',
                "expense_date": expense[6],
                "expense_time": expense[7],
                "receipt_photo": expense[8] or '',
                "ai_categorized": bool(expense[9]),
                "ai_confidence": str(expense[10]) if expense[10] is not None else None,
                "created_at": expense[11],
                "updated_at": expense[12],
                "cashback_excluded": bool(expense[13]),
                "cashback_amount": str(expense[14]) if expense[14] is not None else "0.00"
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(expenses)} трат")

    # 5. Миграция настроек пользователей
    print("\n5. Экспорт настроек пользователей...")
    cursor.execute('''
        SELECT id, profile_id, budget_alerts_enabled, cashback_enabled,
               view_scope, created_at, updated_at
        FROM users_settings
        ORDER BY id
    ''')

    settings = cursor.fetchall()
    for setting in settings:
        fixture = {
            "model": "expenses.usersettings",
            "pk": setting[0],
            "fields": {
                "profile": setting[1],
                "budget_alerts_enabled": bool(setting[2]),
                "cashback_enabled": bool(setting[3]),
                "view_scope": setting[4] or 'personal',
                "created_at": setting[5],
                "updated_at": setting[6]
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(settings)} настроек")

    # 6. Миграция подписок
    print("\n6. Экспорт подписок...")
    cursor.execute('''
        SELECT id, profile_id, type, payment_method, amount,
               telegram_payment_charge_id, start_date, end_date,
               is_active, notification_sent, created_at, updated_at
        FROM subscriptions
        ORDER BY id
    ''')

    subscriptions = cursor.fetchall()
    for subscription in subscriptions:
        fixture = {
            "model": "expenses.subscription",
            "pk": subscription[0],
            "fields": {
                "profile": subscription[1],
                "type": subscription[2] or 'month',
                "payment_method": subscription[3] or 'stars',
                "amount": subscription[4] or 0,
                "telegram_payment_charge_id": subscription[5],
                "start_date": subscription[6],
                "end_date": subscription[7],
                "is_active": bool(subscription[8]),
                "notification_sent": bool(subscription[9]),
                "created_at": subscription[10],
                "updated_at": subscription[11]
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(subscriptions)} подписок")

    # 7. Миграция регулярных платежей
    print("\n7. Экспорт регулярных платежей...")
    cursor.execute('''
        SELECT id, profile_id, operation_type, expense_category_id,
               income_category_id, amount, currency, description,
               day_of_month, is_active, last_processed, created_at, updated_at
        FROM expenses_recurring_payment
        ORDER BY id
    ''')

    recurring_payments = cursor.fetchall()
    for payment in recurring_payments:
        fixture = {
            "model": "expenses.recurringpayment",
            "pk": payment[0],
            "fields": {
                "profile": payment[1],
                "operation_type": payment[2] or 'expense',
                "expense_category": payment[3],
                "income_category": payment[4],
                "amount": str(payment[5]),
                "currency": payment[6] or 'RUB',
                "description": payment[7] or '',
                "day_of_month": payment[8],
                "is_active": bool(payment[9]),
                "last_processed": payment[10],
                "created_at": payment[11],
                "updated_at": payment[12]
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(recurring_payments)} регулярных платежей")

    # 8. Миграция ключевых слов категорий
    print("\n8. Экспорт ключевых слов категорий...")
    cursor.execute('''
        SELECT id, category_id, keyword, language, usage_count,
               normalized_weight, created_at
        FROM expenses_category_keyword
        ORDER BY id
    ''')

    keywords = cursor.fetchall()
    for keyword in keywords:
        fixture = {
            "model": "expenses.categorykeyword",
            "pk": keyword[0],
            "fields": {
                "category": keyword[1],
                "keyword": keyword[2],
                "language": keyword[3] or 'ru',
                "usage_count": keyword[4] or 0,
                "normalized_weight": keyword[5] or 1.0,
                "created_at": keyword[6]
            }
        }
        fixtures.append(fixture)

    print(f"   Экспортировано {len(keywords)} ключевых слов")

    # 9. Дополнительные таблицы если они есть
    additional_tables = [
        ('expenses_cashback', 'expenses.cashback'),
        ('family_invites', 'expenses.familyinvite'),
        ('incomes_category', 'expenses.incomecategory'),
        ('incomes_income', 'expenses.income'),
        ('expenses_income_category_keyword', 'expenses.incomecategorykeyword'),
    ]

    for table_name, model_name in additional_tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"\n9. Экспорт {table_name}...")
                cursor.execute(f'SELECT * FROM {table_name} ORDER BY id')
                cursor.execute(f'PRAGMA table_info({table_name})')
                cols = [col[1] for col in cursor.fetchall()]

                cursor.execute(f'SELECT * FROM {table_name} ORDER BY id')
                rows = cursor.fetchall()

                for row in rows:
                    row_data = dict(zip(cols, row))
                    # Удаляем id из fields
                    pk = row_data.pop('id')

                    fixture = {
                        "model": model_name,
                        "pk": pk,
                        "fields": row_data
                    }
                    fixtures.append(fixture)

                print(f"   Экспортировано {len(rows)} записей из {table_name}")
        except sqlite3.OperationalError:
            # Таблица не существует
            continue

    # Сохраняем fixtures
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fixture_filename = f'complete_migration_fixtures_{timestamp}.json'

    with open(fixture_filename, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, indent=2, ensure_ascii=False, default=str)

    conn.close()

    print(f"\n" + "=" * 80)
    print(f"FIXTURES СОЗДАНЫ УСПЕШНО!")
    print(f"Файл: {fixture_filename}")
    print(f"Всего объектов: {len(fixtures)}")
    print("=" * 80)

    # Создаем скрипт для загрузки
    script_content = f'''#!/bin/bash
# Скрипт для загрузки fixtures в PostgreSQL через Django

echo "Загрузка полной миграции данных из SQLite..."

# Останавливаем контейнеры
echo "Остановка контейнеров..."
docker-compose down

# Очищаем PostgreSQL базу (ОСТОРОЖНО!)
echo "Очистка PostgreSQL базы..."
docker-compose run --rm web python manage.py flush --noinput

# Применяем миграции
echo "Применение миграций..."
docker-compose run --rm web python manage.py migrate

# Загружаем fixtures
echo "Загрузка данных..."
docker-compose run --rm web python manage.py loaddata {fixture_filename}

# Проверяем результат
echo "Проверка миграции..."
docker-compose run --rm web python manage.py shell -c "
from expenses.models import Profile, Expense
profile = Profile.objects.filter(telegram_id=881292737).first()
if profile:
    print(f'Пользователь 881292737 найден: Profile ID {{profile.id}}')
    expenses = Expense.objects.filter(profile=profile).count()
    print(f'Количество трат: {{expenses}}')
    print(f'View scope: {{profile.settings.view_scope if hasattr(profile, \"settings\") else \"НЕТ НАСТРОЕК\"}}')
    if profile.household:
        print(f'Домохозяйство: {{profile.household.name}} (ID: {{profile.household.id}})')
        household_expenses = Expense.objects.filter(profile__household=profile.household).count()
        print(f'Всего трат в домохозяйстве: {{household_expenses}}')
else:
    print('ОШИБКА: Пользователь 881292737 не найден!')
"

# Запускаем контейнеры
echo "Запуск контейнеров..."
docker-compose up -d

echo "Миграция завершена!"
'''

    script_filename = f'load_fixtures_{timestamp}.sh'
    with open(script_filename, 'w') as f:
        f.write(script_content)

    os.chmod(script_filename, 0o755)

    print(f"\\nСОЗДАН СКРИПТ ЗАГРУЗКИ: {script_filename}")
    print("\\nДЛЯ ЗАГРУЗКИ НА СЕРВЕРЕ ВЫПОЛНИТЕ:")
    print(f"1. Скопируйте файлы {fixture_filename} и {script_filename} на сервер")
    print(f"2. Выполните: ./{script_filename}")

    return fixture_filename, script_filename

def analyze_specific_user():
    """Дополнительный анализ для пользователя 881292737"""

    conn = sqlite3.connect('/mnt/c/Users/_batman_/Desktop/expense_bot/expense_bot.db')
    cursor = conn.cursor()

    print("\\n" + "=" * 80)
    print("ДЕТАЛЬНЫЙ АНАЛИЗ ПОЛЬЗОВАТЕЛЯ 881292737")
    print("=" * 80)

    # Получаем данные пользователя
    cursor.execute('SELECT * FROM users_profile WHERE telegram_id = 881292737')
    profile = cursor.fetchone()

    if profile:
        profile_id = profile[0]
        household_id = profile[10]  # household_id

        print(f"Profile ID: {profile_id}")
        print(f"Household ID: {household_id}")

        # Проверяем view_scope
        cursor.execute('SELECT view_scope FROM users_settings WHERE profile_id = ?', (profile_id,))
        settings = cursor.fetchone()
        view_scope = settings[0] if settings else 'personal'
        print(f"View Scope: {view_scope}")

        # Личные траты
        cursor.execute('SELECT COUNT(*) FROM expenses_expense WHERE profile_id = ?', (profile_id,))
        personal_expenses = cursor.fetchone()[0]
        print(f"\\nЛичные траты: {personal_expenses}")

        if household_id:
            # Траты домохозяйства
            cursor.execute('''
                SELECT COUNT(*) FROM expenses_expense e
                JOIN users_profile p ON e.profile_id = p.id
                WHERE p.household_id = ?
            ''', (household_id,))
            household_expenses = cursor.fetchone()[0]
            print(f"Траты всего домохозяйства: {household_expenses}")

            # Участники домохозяйства
            cursor.execute('SELECT id, telegram_id FROM users_profile WHERE household_id = ?', (household_id,))
            members = cursor.fetchall()
            print(f"\\nУчастники домохозяйства:")
            for member_id, telegram_id in members:
                cursor.execute('SELECT COUNT(*) FROM expenses_expense WHERE profile_id = ?', (member_id,))
                member_expenses = cursor.fetchone()[0]
                print(f"  {telegram_id}: {member_expenses} трат")

        print(f"\\nВЫВОД:")
        print(f"Если view_scope = 'household', бот должен показывать {household_expenses if household_id else personal_expenses} трат")
        print(f"Если view_scope = 'personal', бот должен показывать {personal_expenses} трат")
        print(f"\\nВ PostgreSQL нужно проверить:")
        print(f"1. Наличие пользователя с telegram_id = 881292737")
        print(f"2. Правильность household_id = {household_id}")
        print(f"3. Настройку view_scope = '{view_scope}'")
        print(f"4. Наличие всех {personal_expenses} личных трат")

    conn.close()

if __name__ == "__main__":
    fixture_file, script_file = create_django_fixtures()
    analyze_specific_user()

    print(f"\\n" + "=" * 80)
    print("МИГРАЦИЯ ГОТОВА К ВЫПОЛНЕНИЮ")
    print("=" * 80)
    print(f"Fixtures файл: {fixture_file}")
    print(f"Скрипт загрузки: {script_file}")
    print("\\nСледующие шаги:")
    print("1. Скопируйте файлы на сервер")
    print("2. Создайте backup текущей PostgreSQL базы")
    print("3. Выполните скрипт загрузки")
    print("4. Проверьте работу бота с пользователем 881292737")