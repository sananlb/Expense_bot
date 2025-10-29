# Анализ проблемы миграции SQLite → PostgreSQL

## Проблема
Пользователь с `telegram_id = 881292737` имеет 62 траты в SQLite базе, но после миграции в PostgreSQL бот показывает 0 трат.

## Результаты анализа

### Данные в SQLite базе
- **Profile ID**: 12
- **Telegram ID**: 881292737
- **Household ID**: 1 (состоит в домохозяйстве "Family2")
- **Количество трат**: 62
- **Количество категорий**: 25
- **View scope**: household
- **Подписок**: 3

### Структура данных
```sql
-- Пользователь
Profile ID: 12, telegram_id: 881292737, household_id: 1

-- Домохозяйство
Household ID: 1, name: "Family2", creator_id: 12, участников: 2

-- Участники домохозяйства:
- Profile ID 12 (881292737): 62 траты
- Profile ID 24 (7967547829): 1 трата

-- Настройки пользователя
view_scope: "household" - показывает траты всего домохозяйства
```

## Возможные причины проблемы

### 1. Неполная миграция данных
- Данные пользователя не мигрированы в PostgreSQL
- Нарушена связь `household_id`
- Не мигрированы настройки пользователя (`view_scope`)

### 2. Проблемы с ID последовательностями (sequences)
- PostgreSQL sequences могут иметь неправильные значения
- При вставке новых записей возможны конфликты ID

### 3. Логика отображения в боте
- При `view_scope = "household"` бот показывает траты всего домохозяйства
- Если в PostgreSQL нет связи с домохозяйством - результат будет пустым

## Решения

### Решение 1: Проверка PostgreSQL
Выполните команды из файла `postgresql_check_commands.sql`:

```sql
-- Проверить наличие пользователя
SELECT id, telegram_id, household_id FROM users_profile WHERE telegram_id = 881292737;

-- Проверить количество трат
SELECT COUNT(*) FROM expenses_expense
WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);

-- Проверить настройки
SELECT view_scope FROM users_settings
WHERE profile_id = (SELECT id FROM users_profile WHERE telegram_id = 881292737);
```

**Ожидаемые результаты:**
- Пользователь найден с `household_id = 1`
- Количество трат: 62
- View scope: "household"

### Решение 2: Полная миграция через Django fixtures
Используйте файл `complete_migration_fixtures_*.json` и скрипт `load_fixtures_*.sh`:

```bash
# На сервере
./load_fixtures_20250916_012234.sh
```

### Решение 3: Тестовая миграция одного пользователя
Используйте минимальный fixture `user_881292737_minimal_fixture.json`:

```bash
# На сервере
python manage.py loaddata user_881292737_minimal_fixture.json
```

### Решение 4: Ручное создание записей
Если предыдущие методы не работают:

```sql
-- Создать пользователя
INSERT INTO users_profile (id, telegram_id, household_id, ...) VALUES (12, 881292737, 1, ...);

-- Создать домохозяйство
INSERT INTO households (id, name, creator_id, ...) VALUES (1, 'Family2', 12, ...);

-- Создать настройки
INSERT INTO users_settings (profile_id, view_scope, ...) VALUES (12, 'household', ...);
```

## Альтернативные методы миграции

### 1. pgloader
```bash
# Установка pgloader
apt-get install pgloader

# Миграция
pgloader sqlite:///path/to/expense_bot.db postgresql://user:pass@host/db
```

### 2. Django dumpdata/loaddata
```bash
# Создание dump из SQLite
python manage.py dumpdata --database=sqlite > sqlite_dump.json

# Загрузка в PostgreSQL
python manage.py loaddata sqlite_dump.json
```

### 3. Пользовательский migration script
```python
# В Django management command
from expenses.models import *

# Миграция данных с проверкой целостности
```

## Важные моменты

### 1. Домохозяйства
- Пользователь 881292737 состоит в домохозяйстве
- При `view_scope = "household"` показываются траты всех участников
- Критически важно сохранить связь `household_id`

### 2. ID последовательности
- Максимальные ID в SQLite:
  - users_profile: 26
  - expenses_expense: 145
  - expenses_category: 173
- PostgreSQL sequences должны иметь такие же значения

### 3. Целостность данных
- Все foreign key связи должны быть сохранены
- Особое внимание к связям profile ↔ household ↔ expenses

## Следующие шаги

1. **Проверить PostgreSQL** командами из `postgresql_check_commands.sql`
2. **Если данных нет** - выполнить полную миграцию через fixtures
3. **Если данные есть но неполные** - выполнить дополнительную миграцию
4. **Проверить работу бота** с пользователем 881292737
5. **Проверить sequences** PostgreSQL и при необходимости обновить

## Файлы для работы

- `postgresql_check_commands.sql` - команды проверки PostgreSQL
- `complete_migration_fixtures_*.json` - полная миграция всех данных
- `load_fixtures_*.sh` - скрипт загрузки
- `user_881292737_minimal_fixture.json` - минимальный набор для тестирования
- `user_881292737_debug_export.json` - детальный анализ данных пользователя

## Заключение

Проблема скорее всего связана с неполной миграцией данных, особенно:
- Отсутствие пользователя 881292737 в PostgreSQL
- Нарушенная связь с домохозяйством
- Отсутствие настройки `view_scope = "household"`

Рекомендуется начать с проверки PostgreSQL и при необходимости выполнить полную миграцию через Django fixtures.