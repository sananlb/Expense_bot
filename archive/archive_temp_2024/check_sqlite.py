import sqlite3

print("=" * 50)
print("ПРОВЕРКА СТРУКТУРЫ SQLITE БАЗЫ ДАННЫХ")
print("=" * 50)

# Подключаемся к SQLite
conn = sqlite3.connect('/tmp/expense_bot.db')
cursor = conn.cursor()

# Получаем список всех таблиц
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("\nТаблицы в базе данных:")
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name}: {count} записей")

# Проверяем структуру таблиц с пользователями
print("\n" + "=" * 50)
print("СТРУКТУРА ТАБЛИЦ")
print("=" * 50)

# Ищем таблицы связанные с пользователями
user_tables = [t[0] for t in tables if 'user' in t[0].lower() or 'profile' in t[0].lower()]
if user_tables:
    print("\nТаблицы с пользователями:")
    for table_name in user_tables:
        print(f"\n{table_name}:")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")

# Ищем таблицы с расходами
expense_tables = [t[0] for t in tables if 'expense' in t[0].lower()]
if expense_tables:
    print("\nТаблицы с расходами:")
    for table_name in expense_tables:
        print(f"\n{table_name}:")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns[:5]:  # Показываем первые 5 колонок
            print(f"  {col[1]} ({col[2]})")

# Ищем таблицы с категориями
category_tables = [t[0] for t in tables if 'category' in t[0].lower()]
if category_tables:
    print("\nТаблицы с категориями:")
    for table_name in category_tables:
        print(f"\n{table_name}:")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns[:5]:  # Показываем первые 5 колонок
            print(f"  {col[1]} ({col[2]})")

conn.close()

print("\nИспользуйте найденные имена таблиц для миграции!")