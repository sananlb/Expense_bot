
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
-- Пользователь: Profile ID 12, Household ID 1
-- Трат: 62
-- Категорий: 25
-- View scope: household
