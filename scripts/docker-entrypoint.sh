#!/bin/bash
set -e

echo "Starting Expense Bot container..."

# Ждем PostgreSQL
echo "Waiting for PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "PostgreSQL is ready!"

# Ждем Redis
echo "Waiting for Redis to start..."
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 1
done
echo "Proceeding with startup..."

# Выполняем миграции
echo "Running database migrations..."
python manage.py migrate --noinput

# Собираем статику
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Проверяем и настраиваем nginx на хосте (если есть доступ)
if [ -f /host/nginx/expensebot.conf ] && [ -d /host/nginx-sites ]; then
    echo "Updating nginx configuration on host..."
    cp /host/nginx/expensebot.conf /host/nginx-sites/expensebot || true
fi

# Запускаем приложение
echo "Starting application..."
exec "$@"