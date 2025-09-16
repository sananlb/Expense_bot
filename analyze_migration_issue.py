#!/usr/bin/env python3
"""
Анализ проблем миграции SQLite -> PostgreSQL для пользователя 881292737
"""
import sqlite3
import json
from datetime import datetime
from collections import defaultdict

def analyze_sqlite_database():
    """Полный анализ SQLite базы для выявления проблем миграции"""

    conn = sqlite3.connect('/mnt/c/Users/_batman_/Desktop/expense_bot/expense_bot.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("АНАЛИЗ ПРОБЛЕМ МИГРАЦИИ SQLite -> PostgreSQL")
    print("=" * 80)

    # 1. Анализ пользователя 881292737
    print("\n1. АНАЛИЗ ПОЛЬЗОВАТЕЛЯ 881292737")
    print("-" * 40)

    cursor.execute('SELECT * FROM users_profile WHERE telegram_id = 881292737')
    profile = cursor.fetchone()

    if profile:
        cursor.execute('PRAGMA table_info(users_profile)')
        profile_cols = [col[1] for col in cursor.fetchall()]

        print("Профиль найден:")
        profile_data = dict(zip(profile_cols, profile))
        for key, value in profile_data.items():
            print(f"  {key}: {value}")

        profile_id = profile[0]

        # Проверяем траты
        cursor.execute('SELECT COUNT(*) FROM expenses_expense WHERE profile_id = ?', (profile_id,))
        expense_count = cursor.fetchone()[0]
        print(f"\nВсего трат для profile_id {profile_id}: {expense_count}")

        # Анализ дат трат
        cursor.execute('''
            SELECT
                expense_date,
                COUNT(*) as count,
                MIN(created_at) as first_created,
                MAX(created_at) as last_created
            FROM expenses_expense
            WHERE profile_id = ?
            GROUP BY expense_date
            ORDER BY expense_date DESC
            LIMIT 10
        ''', (profile_id,))

        recent_dates = cursor.fetchall()
        print("\nПоследние даты трат:")
        for date_info in recent_dates:
            print(f"  {date_info[0]}: {date_info[1]} трат (создано: {date_info[2]} - {date_info[3]})")

        # Проверяем категории
        cursor.execute('''
            SELECT DISTINCT c.id, c.name, c.profile_id, COUNT(e.id) as usage_count
            FROM expenses_category c
            LEFT JOIN expenses_expense e ON c.id = e.category_id
            WHERE e.profile_id = ?
            GROUP BY c.id, c.name, c.profile_id
            ORDER BY usage_count DESC
        ''', (profile_id,))

        categories = cursor.fetchall()
        print(f"\nИспользуемые категории ({len(categories)}):")
        for cat in categories:
            print(f"  ID {cat[0]}: {cat[1]} (Profile ID: {cat[2]}, использований: {cat[3]})")

    else:
        print("ОШИБКА: Пользователь 881292737 не найден!")
        return

    # 2. Анализ всех пользователей
    print("\n\n2. АНАЛИЗ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ")
    print("-" * 40)

    cursor.execute('''
        SELECT
            p.id, p.telegram_id, p.is_active, p.household_id,
            COUNT(e.id) as expense_count,
            COUNT(c.id) as category_count,
            COUNT(s.id) as subscription_count
        FROM users_profile p
        LEFT JOIN expenses_expense e ON p.id = e.profile_id
        LEFT JOIN expenses_category c ON p.id = c.profile_id
        LEFT JOIN subscriptions s ON p.id = s.profile_id
        GROUP BY p.id, p.telegram_id, p.is_active, p.household_id
        ORDER BY expense_count DESC
    ''')

    all_profiles = cursor.fetchall()
    print("Все профили:")
    for profile in all_profiles:
        print(f"  Profile ID {profile[0]}: Telegram {profile[1]} (активен: {profile[2]}, домохозяйство: {profile[3]}) - {profile[4]} трат, {profile[5]} категорий, {profile[6]} подписок")

    # 3. Анализ структуры базы данных
    print("\n\n3. АНАЛИЗ СТРУКТУРЫ БАЗЫ ДАННЫХ")
    print("-" * 40)

    # Проверяем внешние ключи
    print("Внешние ключи в expenses_expense:")
    cursor.execute('PRAGMA foreign_key_list(expenses_expense)')
    fks = cursor.fetchall()
    for fk in fks:
        print(f"  {fk}")

    # Проверяем наличие orphaned records
    print("\nПроверка orphaned записей:")

    # Orphaned expenses (траты без профиля)
    cursor.execute('''
        SELECT COUNT(*)
        FROM expenses_expense e
        LEFT JOIN users_profile p ON e.profile_id = p.id
        WHERE p.id IS NULL
    ''')
    orphaned_expenses = cursor.fetchone()[0]
    print(f"  Траты без профиля: {orphaned_expenses}")

    # Orphaned expenses (траты без категории или с несуществующей категорией)
    cursor.execute('''
        SELECT COUNT(*)
        FROM expenses_expense e
        LEFT JOIN expenses_category c ON e.category_id = c.id
        WHERE e.category_id IS NOT NULL AND c.id IS NULL
    ''')
    orphaned_expense_categories = cursor.fetchone()[0]
    print(f"  Траты с несуществующими категориями: {orphaned_expense_categories}")

    # Categories без профиля
    cursor.execute('''
        SELECT COUNT(*)
        FROM expenses_category c
        LEFT JOIN users_profile p ON c.profile_id = p.id
        WHERE p.id IS NULL
    ''')
    orphaned_categories = cursor.fetchone()[0]
    print(f"  Категории без профиля: {orphaned_categories}")

    # 4. Анализ format данных
    print("\n\n4. АНАЛИЗ ФОРМАТОВ ДАННЫХ")
    print("-" * 40)

    # Проверяем форматы дат и времени
    cursor.execute('''
        SELECT
            expense_date, expense_time, created_at, updated_at
        FROM expenses_expense
        WHERE profile_id = ?
        ORDER BY created_at DESC
        LIMIT 5
    ''', (profile_id,))

    sample_expenses = cursor.fetchall()
    print("Образцы форматов дат для пользователя 881292737:")
    for exp in sample_expenses:
        print(f"  expense_date: {exp[0]} (тип: {type(exp[0])})")
        print(f"  expense_time: {exp[1]} (тип: {type(exp[1])})")
        print(f"  created_at: {exp[2]} (тип: {type(exp[2])})")
        print(f"  updated_at: {exp[3]} (тип: {type(exp[3])})")
        print("  ---")

    # 5. Проверка дублирования ID
    print("\n\n5. ПРОВЕРКА ДУБЛИРОВАНИЯ ID")
    print("-" * 40)

    tables_to_check = ['users_profile', 'expenses_expense', 'expenses_category', 'subscriptions']

    for table in tables_to_check:
        cursor.execute(f'SELECT MAX(id), COUNT(*) FROM {table}')
        max_id, count = cursor.fetchone()
        print(f"  {table}: MAX(id)={max_id}, COUNT(*)={count}")

        # Проверяем на дубли ID
        cursor.execute(f'SELECT id, COUNT(*) FROM {table} GROUP BY id HAVING COUNT(*) > 1')
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"    ВНИМАНИЕ: Найдены дублирующиеся ID: {duplicates}")
        else:
            print(f"    OK: Дублирующихся ID нет")

    # 6. Генерация команд для проверки PostgreSQL
    print("\n\n6. КОМАНДЫ ДЛЯ ПРОВЕРКИ PostgreSQL")
    print("-" * 40)

    print("Выполните эти команды на сервере PostgreSQL:")
    print()
    print("-- Проверить наличие пользователя 881292737 в PostgreSQL")
    print("SELECT * FROM users_profile WHERE telegram_id = 881292737;")
    print()
    print("-- Проверить количество трат для этого пользователя")
    print("SELECT COUNT(*) FROM expenses_expense WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);")
    print()
    print("-- Проверить категории пользователя")
    print("SELECT * FROM expenses_category WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);")
    print()
    print("-- Проверить последние траты")
    print("""SELECT e.*, c.name as category_name
FROM expenses_expense e
LEFT JOIN expenses_category c ON e.category_id = c.id
WHERE e.profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737)
ORDER BY e.created_at DESC
LIMIT 10;""")
    print()
    print("-- Проверить sequence значения")
    print("SELECT last_value FROM users_profile_id_seq;")
    print("SELECT last_value FROM expenses_expense_id_seq;")
    print("SELECT last_value FROM expenses_category_id_seq;")

    # 7. Экспорт данных пользователя 881292737
    print("\n\n7. ЭКСПОРТ ДАННЫХ ПОЛЬЗОВАТЕЛЯ 881292737")
    print("-" * 40)

    export_data = {
        'profile': profile_data,
        'expenses': [],
        'categories': [],
        'subscriptions': [],
        'settings': [],
        'household': None
    }

    # Экспорт трат
    cursor.execute('''
        SELECT * FROM expenses_expense
        WHERE profile_id = ?
        ORDER BY created_at
    ''', (profile_id,))

    cursor.execute('PRAGMA table_info(expenses_expense)')
    expense_cols = [col[1] for col in cursor.fetchall()]

    for expense in cursor.fetchall():
        export_data['expenses'].append(dict(zip(expense_cols, expense)))

    # Экспорт категорий
    cursor.execute('''
        SELECT * FROM expenses_category
        WHERE profile_id = ?
        ORDER BY id
    ''', (profile_id,))

    cursor.execute('PRAGMA table_info(expenses_category)')
    category_cols = [col[1] for col in cursor.fetchall()]

    for category in cursor.fetchall():
        export_data['categories'].append(dict(zip(category_cols, category)))

    # Экспорт подписок
    cursor.execute('''
        SELECT * FROM subscriptions
        WHERE profile_id = ?
        ORDER BY created_at
    ''', (profile_id,))

    if cursor.fetchall():
        cursor.execute('PRAGMA table_info(subscriptions)')
        subs_cols = [col[1] for col in cursor.fetchall()]

        cursor.execute('SELECT * FROM subscriptions WHERE profile_id = ?', (profile_id,))
        for subscription in cursor.fetchall():
            export_data['subscriptions'].append(dict(zip(subs_cols, subscription)))

    # Экспорт настроек
    cursor.execute('''
        SELECT * FROM users_settings
        WHERE profile_id = ?
    ''', (profile_id,))

    settings = cursor.fetchone()
    if settings:
        cursor.execute('PRAGMA table_info(users_settings)')
        settings_cols = [col[1] for col in cursor.fetchall()]
        export_data['settings'] = dict(zip(settings_cols, settings))

    # Экспорт домохозяйства
    if profile_data['household_id']:
        cursor.execute('''
            SELECT * FROM households
            WHERE id = ?
        ''', (profile_data['household_id'],))

        household = cursor.fetchone()
        if household:
            cursor.execute('PRAGMA table_info(households)')
            household_cols = [col[1] for col in cursor.fetchall()]
            export_data['household'] = dict(zip(household_cols, household))

    # Сохраняем экспорт
    export_filename = f'user_881292737_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(export_filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"Данные пользователя экспортированы в файл: {export_filename}")
    print(f"  - Профиль: 1 запись")
    print(f"  - Траты: {len(export_data['expenses'])} записей")
    print(f"  - Категории: {len(export_data['categories'])} записей")
    print(f"  - Подписки: {len(export_data['subscriptions'])} записей")
    print(f"  - Настройки: {'есть' if export_data['settings'] else 'нет'}")
    print(f"  - Домохозяйство: {'есть' if export_data['household'] else 'нет'}")

    # 8. Анализ возможных причин проблемы
    print("\n\n8. ВОЗМОЖНЫЕ ПРИЧИНЫ ПРОБЛЕМЫ МИГРАЦИИ")
    print("-" * 40)

    potential_issues = []

    # Проверяем ID sequences
    cursor.execute('SELECT MAX(id) FROM users_profile')
    max_profile_id = cursor.fetchone()[0]
    cursor.execute('SELECT MAX(id) FROM expenses_expense')
    max_expense_id = cursor.fetchone()[0]
    cursor.execute('SELECT MAX(id) FROM expenses_category')
    max_category_id = cursor.fetchone()[0]

    print(f"Максимальные ID в SQLite:")
    print(f"  users_profile: {max_profile_id}")
    print(f"  expenses_expense: {max_expense_id}")
    print(f"  expenses_category: {max_category_id}")

    if orphaned_expenses > 0:
        potential_issues.append("Найдены траты без связанного профиля")

    if orphaned_expense_categories > 0:
        potential_issues.append("Найдены траты с несуществующими категориями")

    if orphaned_categories > 0:
        potential_issues.append("Найдены категории без связанного профиля")

    # Проверяем уникальность telegram_id
    cursor.execute('SELECT telegram_id, COUNT(*) FROM users_profile GROUP BY telegram_id HAVING COUNT(*) > 1')
    duplicate_telegram_ids = cursor.fetchall()
    if duplicate_telegram_ids:
        potential_issues.append(f"Найдены дублирующиеся telegram_id: {duplicate_telegram_ids}")

    if potential_issues:
        print("\nВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
        for i, issue in enumerate(potential_issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\nСТРУКТУРНЫЕ ПРОБЛЕМЫ НЕ НАЙДЕНЫ")

    # 9. Рекомендации по исправлению
    print("\n\n9. РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("-" * 40)

    print("1. ПРОВЕРИТЬ PostgreSQL:")
    print("   - Убедиться что все данные мигрированы")
    print("   - Проверить sequence значения")
    print("   - Проверить foreign key constraints")
    print()
    print("2. АЛЬТЕРНАТИВНЫЕ МЕТОДЫ МИГРАЦИИ:")
    print("   - Использовать Django dumpdata/loaddata")
    print("   - Использовать pgloader")
    print("   - Создать custom migration script")
    print()
    print("3. ПРОВЕРИТЬ ЛОГИКУ БОТА:")
    print("   - Возможно проблема в фильтрах данных")
    print("   - Проверить view_scope настройки")
    print("   - Проверить household_id влияние")

    conn.close()

    return export_filename, export_data

if __name__ == "__main__":
    export_filename, export_data = analyze_sqlite_database()

    print(f"\n\nАНАЛИЗ ЗАВЕРШЕН")
    print(f"Экспорт сохранен в файл: {export_filename}")