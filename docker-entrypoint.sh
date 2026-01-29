#!/bin/bash
set -e

echo "Starting Expense Bot container..."

# Wait for PostgreSQL to be ready
if [ "$DB_HOST" ]; then
    echo "Waiting for PostgreSQL..."
    while ! pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-expense_user}" -d "${DB_NAME:-expense_bot}"; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 2
    done
    echo "PostgreSQL is ready!"
fi

# Wait for Redis to be ready (simplified - just wait a bit)
if [ "$REDIS_HOST" ]; then
    echo "Waiting for Redis to start..."
    sleep 5
    echo "Proceeding with startup..."
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Create superuser if it doesn't exist
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ] && [ "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput || echo "Superuser already exists or creation failed"
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create necessary directories
mkdir -p logs media

# Execute the main command
echo "Starting application..."
exec "$@"