# Схема базы данных ExpenseBot

## Обзор

База данных ExpenseBot спроектирована для хранения информации о пользователях, их расходах, категориях, кешбэках и настройках. Используется PostgreSQL в продакшене и SQLite для разработки.

## Диаграмма ER

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ users_profile   │    │expenses_category│    │expenses_expense │
│                 │    │                 │    │                 │
│ ├─ id (PK)      │◄──┤ ├─ id (PK)      │◄──┤ ├─ id (PK)      │
│ ├─ telegram_id  │   │ ├─ profile_id   │   │ ├─ profile_id   │
│ ├─ username     │   │ ├─ name         │   │ ├─ category_id  │
│ ├─ first_name   │   │ ├─ icon         │   │ ├─ amount       │
│ ├─ last_name    │   │ ├─ is_active    │   │ ├─ description  │
│ ├─ language_code│   │ ├─ created_at   │   │ ├─ expense_date │
│ ├─ timezone     │   │ └─ updated_at   │   │ ├─ expense_time │
│ ├─ currency     │   └─────────────────┘   │ ├─ receipt_photo│
│ ├─ is_active    │                         │ ├─ ai_categorized│
│ ├─ created_at   │   ┌─────────────────┐   │ ├─ ai_confidence│
│ └─ updated_at   │   │expenses_cashback│   │ ├─ created_at   │
└─────────────────┘   │                 │   │ └─ updated_at   │
         │             │ ├─ id (PK)      │   └─────────────────┘
         │             │ ├─ profile_id   │
         │             │ ├─ category_id  │
         │             │ ├─ bank_name    │
         └─────────────┤ ├─ cashback_%   │
                       │ ├─ month        │
                       │ ├─ limit_amount │
                       │ ├─ created_at   │
                       │ └─ updated_at   │
                       └─────────────────┘
                                │
       ┌─────────────────┐      │
       │ users_settings  │      │
       │                 │      │
       │ ├─ id (PK)      │      │
       │ ├─ profile_id   │──────┘
       │ ├─ daily_reminder_enabled
       │ ├─ daily_reminder_time
       │ ├─ weekly_summary_enabled
       │ ├─ monthly_summary_enabled
       │ ├─ budget_alerts_enabled
       │ ├─ created_at   │
       │ └─ updated_at   │
       └─────────────────┘
```

## Таблицы

### 1. users_profile

Основная таблица пользователей системы.

```sql
CREATE TABLE users_profile (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(2) DEFAULT 'ru',
    timezone VARCHAR(50) DEFAULT 'UTC',
    currency VARCHAR(3) DEFAULT 'RUB',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE UNIQUE INDEX idx_users_profile_telegram_id ON users_profile(telegram_id);
CREATE INDEX idx_users_profile_active ON users_profile(is_active);
CREATE INDEX idx_users_profile_created ON users_profile(created_at);
```

**Поля:**
- `id` - Внутренний ID пользователя
- `telegram_id` - ID пользователя в Telegram (уникальный)
- `username` - Имя пользователя в Telegram (@username)
- `first_name` - Имя пользователя
- `last_name` - Фамилия пользователя
- `language_code` - Код языка (ru/en)
- `timezone` - Часовой пояс пользователя
- `currency` - Основная валюта (RUB, USD, EUR)
- `is_active` - Статус активности

### 2. expenses_category

Категории расходов для каждого пользователя.

```sql
CREATE TABLE expenses_category (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(10) DEFAULT '💰',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_profile_category UNIQUE(profile_id, name)
);

-- Индексы
CREATE INDEX idx_expenses_category_profile ON expenses_category(profile_id);
CREATE INDEX idx_expenses_category_active ON expenses_category(profile_id, is_active);
```

**Поля:**
- `id` - ID категории
- `profile_id` - Ссылка на пользователя
- `name` - Название категории
- `icon` - Эмодзи иконка категории
- `is_active` - Активность категории

**Базовые категории** (создаются автоматически при регистрации):
```sql
INSERT INTO expenses_category (profile_id, name, icon) VALUES
    (:profile_id, 'Супермаркеты', '🛒'),
    (:profile_id, 'Другие продукты', '🫑'),
    (:profile_id, 'Рестораны и кафе', '🍽️'),
    (:profile_id, 'АЗС', '⛽'),
    (:profile_id, 'Такси', '🚕'),
    (:profile_id, 'Общественный транспорт', '🚌'),
    (:profile_id, 'Автомобиль', '🚗'),
    (:profile_id, 'Жилье', '🏠'),
    (:profile_id, 'Аптеки', '💊'),
    (:profile_id, 'Медицина', '🏥'),
    (:profile_id, 'Спорт', '🏃'),
    (:profile_id, 'Спортивные товары', '🏀'),
    (:profile_id, 'Одежда и обувь', '👔'),
    (:profile_id, 'Цветы', '🌹'),
    (:profile_id, 'Развлечения', '🎭'),
    (:profile_id, 'Образование', '📚'),
    (:profile_id, 'Подарки', '🎁'),
    (:profile_id, 'Путешествия', '✈️'),
    (:profile_id, 'Связь и интернет', '📱'),
    (:profile_id, 'Прочее', '💰');
```

### 3. expenses_expense

Основная таблица расходов.

```sql
CREATE TABLE expenses_expense (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES expenses_category(id) ON DELETE SET NULL,
    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),
    description TEXT,
    expense_date DATE DEFAULT CURRENT_DATE,
    expense_time TIME DEFAULT CURRENT_TIME,
    receipt_photo VARCHAR(255),
    ai_categorized BOOLEAN DEFAULT FALSE,
    ai_confidence DECIMAL(3,2) CHECK (ai_confidence >= 0 AND ai_confidence <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для оптимизации запросов
CREATE INDEX idx_expenses_expense_profile ON expenses_expense(profile_id);
CREATE INDEX idx_expenses_expense_category ON expenses_expense(category_id);
CREATE INDEX idx_expenses_expense_date ON expenses_expense(expense_date);
CREATE INDEX idx_expenses_expense_profile_date ON expenses_expense(profile_id, expense_date);
CREATE INDEX idx_expenses_expense_profile_category ON expenses_expense(profile_id, category_id);
CREATE INDEX idx_expenses_expense_amount ON expenses_expense(amount);

-- Составной индекс для аналитики
CREATE INDEX idx_expenses_expense_analytics ON expenses_expense(profile_id, expense_date, category_id, amount);
```

**Поля:**
- `id` - ID расхода
- `profile_id` - Ссылка на пользователя
- `category_id` - Ссылка на категорию (может быть NULL)
- `amount` - Сумма расхода
- `description` - Описание расхода
- `expense_date` - Дата расхода
- `expense_time` - Время расхода
- `receipt_photo` - Путь к фото чека
- `ai_categorized` - Категория определена ИИ
- `ai_confidence` - Уверенность ИИ (0.0-1.0)

### 4. expenses_cashback

Информация о кешбэках по категориям.

```sql
CREATE TABLE expenses_cashback (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES expenses_category(id) ON DELETE CASCADE,
    bank_name VARCHAR(100) NOT NULL,
    cashback_percent DECIMAL(4,2) NOT NULL CHECK (cashback_percent >= 0 AND cashback_percent <= 100),
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    limit_amount DECIMAL(12,2) CHECK (limit_amount >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_profile_category_bank_month UNIQUE(profile_id, category_id, bank_name, month)
);

-- Индексы
CREATE INDEX idx_expenses_cashback_profile ON expenses_cashback(profile_id);
CREATE INDEX idx_expenses_cashback_month ON expenses_cashback(profile_id, month);
CREATE INDEX idx_expenses_cashback_category ON expenses_cashback(profile_id, category_id);
```

**Поля:**
- `id` - ID кешбэка
- `profile_id` - Ссылка на пользователя
- `category_id` - Ссылка на категорию
- `bank_name` - Название банка
- `cashback_percent` - Процент кешбэка (0.00-100.00)
- `month` - Месяц действия (1-12)
- `limit_amount` - Лимит кешбэка в рублях

### 5. users_settings

Настройки пользователей.

```sql
CREATE TABLE users_settings (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) ON DELETE CASCADE UNIQUE,
    daily_reminder_enabled BOOLEAN DEFAULT TRUE,
    daily_reminder_time TIME DEFAULT '20:00:00',
    weekly_summary_enabled BOOLEAN DEFAULT TRUE,
    monthly_summary_enabled BOOLEAN DEFAULT TRUE,
    budget_alerts_enabled BOOLEAN DEFAULT TRUE,
    preferred_language VARCHAR(2) DEFAULT 'ru',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE UNIQUE INDEX idx_users_settings_profile ON users_settings(profile_id);
CREATE INDEX idx_users_settings_reminders ON users_settings(daily_reminder_enabled, daily_reminder_time);
```

**Поля:**
- `profile_id` - Ссылка на пользователя (один к одному)
- `daily_reminder_enabled` - Включены ли ежедневные напоминания
- `daily_reminder_time` - Время ежедневного напоминания
- `weekly_summary_enabled` - Включены ли еженедельные сводки
- `monthly_summary_enabled` - Включены ли месячные сводки
- `budget_alerts_enabled` - Включены ли уведомления о бюджете

### 6. expenses_budget (будущая функциональность)

Бюджеты по категориям.

```sql
CREATE TABLE expenses_budget (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES expenses_category(id) ON DELETE CASCADE,
    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),
    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('daily', 'weekly', 'monthly')),
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_expenses_budget_profile ON expenses_budget(profile_id);
CREATE INDEX idx_expenses_budget_category ON expenses_budget(profile_id, category_id);
CREATE INDEX idx_expenses_budget_period ON expenses_budget(start_date, end_date, is_active);
```

## Функции и процедуры

### 1. Создание базовых категорий
```sql
CREATE OR REPLACE FUNCTION create_default_categories(user_profile_id INTEGER)
RETURNS VOID AS $$
DECLARE
    categories_data RECORD;
BEGIN
    FOR categories_data IN 
        SELECT unnest(ARRAY['Супермаркеты', 'Другие продукты', 'Рестораны и кафе', 'АЗС', 'Такси', 'Общественный транспорт', 'Автомобиль', 'Жилье', 'Аптеки', 'Медицина', 'Спорт', 'Спортивные товары', 'Одежда и обувь', 'Цветы', 'Развлечения', 'Образование', 'Подарки', 'Путешествия', 'Связь и интернет', 'Прочее']) as name,
               unnest(ARRAY['🛒', '🫑', '🍽️', '⛽', '🚕', '🚌', '🚗', '🏠', '💊', '🏥', '🏃', '🏀', '👔', '🌹', '🎭', '📚', '🎁', '✈️', '📱', '💰']) as icon
    LOOP
        INSERT INTO expenses_category (profile_id, name, icon)
        VALUES (user_profile_id, categories_data.name, categories_data.icon)
        ON CONFLICT (profile_id, name) DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### 2. Расчет кешбэка
```sql
CREATE OR REPLACE FUNCTION calculate_cashback(
    user_profile_id INTEGER,
    category_id INTEGER,
    amount DECIMAL,
    expense_month INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    cashback_info RECORD;
    spent_this_month DECIMAL;
    available_limit DECIMAL;
    cashback_amount DECIMAL := 0;
BEGIN
    -- Получаем информацию о кешбэке
    SELECT * INTO cashback_info
    FROM expenses_cashback
    WHERE profile_id = user_profile_id
      AND category_id = category_id
      AND month = expense_month
    ORDER BY cashback_percent DESC
    LIMIT 1;
    
    IF NOT FOUND THEN
        RETURN 0;
    END IF;
    
    -- Рассчитываем потраченную сумму в этом месяце по категории
    SELECT COALESCE(SUM(amount), 0) INTO spent_this_month
    FROM expenses_expense
    WHERE profile_id = user_profile_id
      AND category_id = category_id
      AND EXTRACT(MONTH FROM expense_date) = expense_month
      AND EXTRACT(YEAR FROM expense_date) = EXTRACT(YEAR FROM CURRENT_DATE);
    
    -- Рассчитываем доступный лимит
    IF cashback_info.limit_amount IS NOT NULL THEN
        available_limit := cashback_info.limit_amount - spent_this_month;
        IF available_limit <= 0 THEN
            RETURN 0;
        END IF;
        
        -- Применяем кешбэк только в пределах лимита
        IF amount > available_limit THEN
            cashback_amount := available_limit * cashback_info.cashback_percent / 100;
        ELSE
            cashback_amount := amount * cashback_info.cashback_percent / 100;
        END IF;
    ELSE
        -- Нет лимита
        cashback_amount := amount * cashback_info.cashback_percent / 100;
    END IF;
    
    RETURN cashback_amount;
END;
$$ LANGUAGE plpgsql;
```

### 3. Обновление временных меток
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяем триггер ко всем таблицам
CREATE TRIGGER update_users_profile_updated_at BEFORE UPDATE ON users_profile FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expenses_category_updated_at BEFORE UPDATE ON expenses_category FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expenses_expense_updated_at BEFORE UPDATE ON expenses_expense FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_expenses_cashback_updated_at BEFORE UPDATE ON expenses_cashback FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_settings_updated_at BEFORE UPDATE ON users_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Представления (Views)

### 1. Сводка по категориям за текущий месяц
```sql
CREATE VIEW current_month_summary AS
SELECT 
    p.id as profile_id,
    p.telegram_id,
    c.id as category_id,
    c.name as category_name,
    c.icon as category_icon,
    COUNT(e.id) as expenses_count,
    COALESCE(SUM(e.amount), 0) as total_amount,
    COALESCE(AVG(e.amount), 0) as average_amount
FROM users_profile p
LEFT JOIN expenses_category c ON c.profile_id = p.id AND c.is_active = TRUE
LEFT JOIN expenses_expense e ON e.category_id = c.id 
    AND EXTRACT(YEAR FROM e.expense_date) = EXTRACT(YEAR FROM CURRENT_DATE)
    AND EXTRACT(MONTH FROM e.expense_date) = EXTRACT(MONTH FROM CURRENT_DATE)
WHERE p.is_active = TRUE
GROUP BY p.id, p.telegram_id, c.id, c.name, c.icon
ORDER BY total_amount DESC;
```

### 2. Потенциальные кешбэки за месяц
```sql
CREATE VIEW monthly_cashback_potential AS
SELECT 
    p.id as profile_id,
    p.telegram_id,
    EXTRACT(MONTH FROM e.expense_date) as month,
    EXTRACT(YEAR FROM e.expense_date) as year,
    c.name as category_name,
    cb.bank_name,
    cb.cashback_percent,
    cb.limit_amount,
    SUM(e.amount) as spent_amount,
    CASE 
        WHEN cb.limit_amount IS NOT NULL AND SUM(e.amount) > cb.limit_amount 
        THEN cb.limit_amount * cb.cashback_percent / 100
        ELSE SUM(e.amount) * cb.cashback_percent / 100
    END as potential_cashback
FROM users_profile p
JOIN expenses_expense e ON e.profile_id = p.id
JOIN expenses_category c ON c.id = e.category_id
JOIN expenses_cashback cb ON cb.profile_id = p.id 
    AND cb.category_id = c.id 
    AND cb.month = EXTRACT(MONTH FROM e.expense_date)
WHERE p.is_active = TRUE
GROUP BY p.id, p.telegram_id, EXTRACT(MONTH FROM e.expense_date), EXTRACT(YEAR FROM e.expense_date), 
         c.name, cb.bank_name, cb.cashback_percent, cb.limit_amount
ORDER BY potential_cashback DESC;
```

## Миграции Django

### Начальная миграция
```python
# expenses/migrations/0001_initial.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    
    operations = [
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('telegram_id', models.BigIntegerField(unique=True)),
                ('username', models.CharField(max_length=255, null=True, blank=True)),
                ('first_name', models.CharField(max_length=255, null=True, blank=True)),
                ('last_name', models.CharField(max_length=255, null=True, blank=True)),
                ('language_code', models.CharField(max_length=2, default='ru')),
                ('timezone', models.CharField(max_length=50, default='UTC')),
                ('currency', models.CharField(max_length=3, default='RUB')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'users_profile',
            },
        ),
        # ... остальные модели
    ]
```

## Резервное копирование

### Скрипт ежедневного бэкапа
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/var/backups/expensebot"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="expensebot"
DB_USER="expensebot_user"

# Создаем бэкап
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Удаляем старые бэкапы (старше 30 дней)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

### Восстановление из бэкапа
```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1
DB_NAME="expensebot"
DB_USER="expensebot_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

# Останавливаем приложение
systemctl stop expensebot-bot
systemctl stop expensebot-web

# Восстанавливаем БД
dropdb -U $DB_USER $DB_NAME
createdb -U $DB_USER $DB_NAME
gunzip -c $BACKUP_FILE | psql -U $DB_USER $DB_NAME

# Запускаем приложение
systemctl start expensebot-web
systemctl start expensebot-bot

echo "Restore completed from: $BACKUP_FILE"
```

## Оптимизация производительности

### Рекомендуемые настройки PostgreSQL
```sql
-- postgresql.conf
shared_buffers = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
random_page_cost = 1.1
```

### Полезные запросы для мониторинга
```sql
-- Самые медленные запросы
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Размер таблиц
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY tablename, attname;

-- Использование индексов
SELECT 
    indexrelname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```