#!/usr/bin/env python3
"""
Простое решение для проверки миграции данных пользователя 881292737
"""
import sqlite3
import json

def create_user_specific_export():
    """Экспорт только данных пользователя 881292737 для отладки"""

    conn = sqlite3.connect('/mnt/c/Users/_batman_/Desktop/expense_bot/expense_bot.db')
    cursor = conn.cursor()

    print("СОЗДАНИЕ ЭКСПОРТА ДЛЯ ПОЛЬЗОВАТЕЛЯ 881292737")
    print("=" * 60)

    # Получаем данные пользователя
    cursor.execute('SELECT * FROM users_profile WHERE telegram_id = 881292737')
    profile_row = cursor.fetchone()

    if not profile_row:
        print("ОШИБКА: Пользователь не найден!")
        return

    cursor.execute('PRAGMA table_info(users_profile)')
    profile_cols = [col[1] for col in cursor.fetchall()]
    profile_data = dict(zip(profile_cols, profile_row))

    profile_id = profile_data['id']
    household_id = profile_data['household_id']

    print(f"Profile ID: {profile_id}")
    print(f"Telegram ID: {profile_data['telegram_id']}")
    print(f"Household ID: {household_id}")

    export_data = {
        'profile': profile_data,
        'expenses': [],
        'categories': [],
        'settings': {},
        'household': {},
        'subscriptions': [],
        'summary': {}
    }

    # Экспорт трат
    cursor.execute('SELECT * FROM expenses_expense WHERE profile_id = ?', (profile_id,))
    expenses = cursor.fetchall()
    cursor.execute('PRAGMA table_info(expenses_expense)')
    expense_cols = [col[1] for col in cursor.fetchall()]

    for expense in expenses:
        export_data['expenses'].append(dict(zip(expense_cols, expense)))

    print(f"Трат найдено: {len(export_data['expenses'])}")

    # Экспорт категорий пользователя
    cursor.execute('SELECT * FROM expenses_category WHERE profile_id = ?', (profile_id,))
    categories = cursor.fetchall()
    cursor.execute('PRAGMA table_info(expenses_category)')
    category_cols = [col[1] for col in cursor.fetchall()]

    for category in categories:
        export_data['categories'].append(dict(zip(category_cols, category)))

    print(f"Категорий найдено: {len(export_data['categories'])}")

    # Экспорт настроек
    cursor.execute('SELECT * FROM users_settings WHERE profile_id = ?', (profile_id,))
    settings = cursor.fetchone()
    if settings:
        cursor.execute('PRAGMA table_info(users_settings)')
        settings_cols = [col[1] for col in cursor.fetchall()]
        export_data['settings'] = dict(zip(settings_cols, settings))
        print(f"View scope: {export_data['settings'].get('view_scope', 'НЕТ')}")

    # Экспорт домохозяйства если есть
    if household_id:
        cursor.execute('SELECT * FROM households WHERE id = ?', (household_id,))
        household = cursor.fetchone()
        if household:
            cursor.execute('PRAGMA table_info(households)')
            household_cols = [col[1] for col in cursor.fetchall()]
            export_data['household'] = dict(zip(household_cols, household))
            print(f"Домохозяйство: {export_data['household'].get('name', 'Без имени')}")

    # Экспорт подписок
    cursor.execute('SELECT * FROM subscriptions WHERE profile_id = ?', (profile_id,))
    subscriptions = cursor.fetchall()
    cursor.execute('PRAGMA table_info(subscriptions)')
    sub_cols = [col[1] for col in cursor.fetchall()]

    for sub in subscriptions:
        export_data['subscriptions'].append(dict(zip(sub_cols, sub)))

    print(f"Подписок найдено: {len(export_data['subscriptions'])}")

    # Создаем сводку
    export_data['summary'] = {
        'total_expenses': len(export_data['expenses']),
        'total_categories': len(export_data['categories']),
        'has_household': bool(household_id),
        'view_scope': export_data['settings'].get('view_scope', 'personal'),
        'recent_expenses': []
    }

    # Последние 10 трат для проверки
    cursor.execute('''
        SELECT e.id, e.amount, e.description, e.expense_date, e.created_at, c.name as category_name
        FROM expenses_expense e
        LEFT JOIN expenses_category c ON e.category_id = c.id
        WHERE e.profile_id = ?
        ORDER BY e.created_at DESC
        LIMIT 10
    ''', (profile_id,))

    recent = cursor.fetchall()
    for exp in recent:
        export_data['summary']['recent_expenses'].append({
            'id': exp[0],
            'amount': exp[1],
            'description': exp[2],
            'date': exp[3],
            'created': exp[4],
            'category': exp[5]
        })

    # Сохраняем экспорт
    filename = 'user_881292737_debug_export.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nЭкспорт сохранен в: {filename}")

    # Создаем SQL команды для проверки PostgreSQL
    sql_commands = f"""
-- КОМАНДЫ ДЛЯ ПРОВЕРКИ PostgreSQL
-- Выполните эти команды на сервере:

-- 1. Проверить наличие пользователя
SELECT id, telegram_id, household_id FROM users_profile WHERE telegram_id = 881292737;

-- 2. Проверить количество трат
SELECT COUNT(*) as expense_count FROM expenses_expense
WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);

-- 3. Проверить настройки пользователя
SELECT view_scope FROM users_settings
WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);

-- 4. Проверить домохозяйство если есть
SELECT h.* FROM households h
JOIN users_profile p ON h.id = p.household_id
WHERE p.telegram_id = 881292737;

-- 5. Проверить последние траты
SELECT e.id, e.amount, e.description, e.expense_date, c.name as category_name
FROM expenses_expense e
LEFT JOIN expenses_category c ON e.category_id = c.id
WHERE e.profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737)
ORDER BY e.created_at DESC
LIMIT 10;

-- 6. Проверить sequences
SELECT last_value FROM users_profile_id_seq;
SELECT last_value FROM expenses_expense_id_seq;
SELECT last_value FROM expenses_category_id_seq;

-- ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ ИЗ SQLite:
-- Пользователь: Profile ID {profile_id}, Household ID {household_id}
-- Трат: {len(export_data['expenses'])}
-- Категорий: {len(export_data['categories'])}
-- View scope: {export_data['summary']['view_scope']}
"""

    with open('postgresql_check_commands.sql', 'w', encoding='utf-8') as f:
        f.write(sql_commands)

    print("SQL команды сохранены в: postgresql_check_commands.sql")

    conn.close()

    return export_data

def create_minimal_fixture():
    """Создание минимального fixture только для пользователя 881292737"""

    conn = sqlite3.connect('/mnt/c/Users/_batman_/Desktop/expense_bot/expense_bot.db')
    cursor = conn.cursor()

    fixtures = []

    # Profile
    cursor.execute('SELECT * FROM users_profile WHERE telegram_id = 881292737')
    profile = cursor.fetchone()
    cursor.execute('PRAGMA table_info(users_profile)')
    profile_cols = [col[1] for col in cursor.fetchall()]
    profile_data = dict(zip(profile_cols, profile))

    profile_id = profile_data['id']

    fixture = {
        "model": "expenses.profile",
        "pk": profile_id,
        "fields": {
            "telegram_id": profile_data['telegram_id'],
            "language_code": profile_data['language_code'] or 'ru',
            "timezone": profile_data['timezone'] or 'UTC',
            "currency": profile_data['currency'] or 'RUB',
            "is_active": bool(profile_data['is_active']),
            "created_at": profile_data['created_at'],
            "updated_at": profile_data['updated_at'],
            "household": profile_data['household_id']
        }
    }
    fixtures.append(fixture)

    # Household если есть
    if profile_data['household_id']:
        cursor.execute('SELECT * FROM households WHERE id = ?', (profile_data['household_id'],))
        household = cursor.fetchone()
        if household:
            cursor.execute('PRAGMA table_info(households)')
            household_cols = [col[1] for col in cursor.fetchall()]
            household_data = dict(zip(household_cols, household))

            fixture = {
                "model": "expenses.household",
                "pk": household_data['id'],
                "fields": {
                    "created_at": household_data['created_at'],
                    "name": household_data['name'],
                    "creator": household_data['creator_id'],
                    "is_active": bool(household_data['is_active']),
                    "max_members": household_data['max_members'] or 5
                }
            }
            fixtures.append(fixture)

    # Categories
    cursor.execute('SELECT * FROM expenses_category WHERE profile_id = ?', (profile_id,))
    categories = cursor.fetchall()
    cursor.execute('PRAGMA table_info(expenses_category)')
    category_cols = [col[1] for col in cursor.fetchall()]

    for cat in categories:
        cat_data = dict(zip(category_cols, cat))
        fixture = {
            "model": "expenses.expensecategory",
            "pk": cat_data['id'],
            "fields": {
                "profile": cat_data['profile_id'],
                "name": cat_data['name'],
                "icon": cat_data['icon'] or '💰',
                "is_active": bool(cat_data['is_active']),
                "created_at": cat_data['created_at'],
                "updated_at": cat_data['updated_at']
            }
        }
        fixtures.append(fixture)

    # Expenses
    cursor.execute('SELECT * FROM expenses_expense WHERE profile_id = ?', (profile_id,))
    expenses = cursor.fetchall()
    cursor.execute('PRAGMA table_info(expenses_expense)')
    expense_cols = [col[1] for col in cursor.fetchall()]

    for exp in expenses:
        exp_data = dict(zip(expense_cols, exp))
        fixture = {
            "model": "expenses.expense",
            "pk": exp_data['id'],
            "fields": {
                "profile": exp_data['profile_id'],
                "category": exp_data['category_id'],
                "amount": str(exp_data['amount']),
                "currency": exp_data['currency'] or 'RUB',
                "description": exp_data['description'] or '',
                "expense_date": exp_data['expense_date'],
                "expense_time": exp_data['expense_time'],
                "ai_categorized": bool(exp_data['ai_categorized']),
                "created_at": exp_data['created_at'],
                "updated_at": exp_data['updated_at'],
                "cashback_excluded": bool(exp_data['cashback_excluded']),
                "cashback_amount": str(exp_data['cashback_amount'] or 0)
            }
        }
        fixtures.append(fixture)

    # Settings
    cursor.execute('SELECT * FROM users_settings WHERE profile_id = ?', (profile_id,))
    settings = cursor.fetchone()
    if settings:
        cursor.execute('PRAGMA table_info(users_settings)')
        settings_cols = [col[1] for col in cursor.fetchall()]
        settings_data = dict(zip(settings_cols, settings))

        fixture = {
            "model": "expenses.usersettings",
            "pk": settings_data['id'],
            "fields": {
                "profile": settings_data['profile_id'],
                "budget_alerts_enabled": bool(settings_data['budget_alerts_enabled']),
                "cashback_enabled": bool(settings_data['cashback_enabled']),
                "view_scope": settings_data['view_scope'] or 'personal',
                "created_at": settings_data['created_at'],
                "updated_at": settings_data['updated_at']
            }
        }
        fixtures.append(fixture)

    filename = 'user_881292737_minimal_fixture.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, indent=2, ensure_ascii=False, default=str)

    print(f"Минимальный fixture создан: {filename}")
    print(f"Объектов в fixture: {len(fixtures)}")

    conn.close()

    return filename

if __name__ == "__main__":
    # Создаем детальный экспорт для анализа
    export_data = create_user_specific_export()

    # Создаем минимальный fixture для тестирования
    fixture_file = create_minimal_fixture()

    print("\n" + "="*60)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("="*60)
    print("Файлы созданы:")
    print("1. user_881292737_debug_export.json - детальный анализ")
    print("2. user_881292737_minimal_fixture.json - для тестирования")
    print("3. postgresql_check_commands.sql - команды проверки")
    print()
    print("СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Проверьте данные в PostgreSQL командами из .sql файла")
    print("2. Если данных нет - загрузите minimal fixture")
    print("3. Проверьте работу бота")