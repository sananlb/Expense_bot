#!/bin/bash

# Docker deployment script for Expense Bot

set -e

echo "=== Expense Bot Docker Deployment ==="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

echo "1. Building Docker images..."
docker-compose build

echo "2. Starting database and Redis services..."
docker-compose up -d db redis

echo "3. Waiting for services to be ready..."
sleep 10

echo "4. Running database migrations..."
docker-compose run --rm bot python manage.py migrate

echo "5. Creating superuser (if needed)..."
docker-compose run --rm bot python manage.py createsuperuser || echo "Superuser creation skipped"

echo "6. Starting all services..."
docker-compose up -d

echo "7. Checking service status..."
docker-compose ps

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Services running:"
echo "- Bot: expense_bot_app"
echo "- Database: expense_bot_db"
echo "- Redis: expense_bot_redis"
echo "- Celery: expense_bot_celery"
echo "- Celery Beat: expense_bot_celery_beat"
echo "- Web Admin: http://localhost:8000/admin"
echo ""
echo "To view logs: docker-compose logs -f [service_name]"
echo "To stop: docker-compose down"
echo "To restart: docker-compose restart"