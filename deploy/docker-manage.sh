#!/bin/bash

# Management script for Docker deployment

set -e

case "$1" in
    start)
        echo "Starting Expense Bot services..."
        docker-compose up -d
        docker-compose ps
        ;;
    
    stop)
        echo "Stopping Expense Bot services..."
        docker-compose down
        ;;
    
    restart)
        echo "Restarting Expense Bot services..."
        docker-compose restart
        docker-compose ps
        ;;
    
    logs)
        if [ -z "$2" ]; then
            docker-compose logs -f
        else
            docker-compose logs -f "$2"
        fi
        ;;
    
    shell)
        echo "Opening shell in bot container..."
        docker-compose exec bot bash
        ;;
    
    dbshell)
        echo "Opening PostgreSQL shell..."
        docker-compose exec db psql -U "${DB_USER:-expense_user}" "${DB_NAME:-expense_bot}"
        ;;
    
    migrate)
        echo "Running database migrations..."
        docker-compose run --rm bot python manage.py migrate
        ;;
    
    makemigrations)
        echo "Creating new migrations..."
        docker-compose run --rm bot python manage.py makemigrations
        ;;
    
    createsuperuser)
        echo "Creating Django superuser..."
        docker-compose run --rm bot python manage.py createsuperuser
        ;;
    
    collectstatic)
        echo "Collecting static files..."
        docker-compose run --rm bot python manage.py collectstatic --noinput
        ;;
    
    backup)
        echo "Creating database backup..."
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        docker-compose exec -T db pg_dump -U "${DB_USER:-expense_user}" "${DB_NAME:-expense_bot}" > "backup_${TIMESTAMP}.sql"
        echo "Backup saved to: backup_${TIMESTAMP}.sql"
        ;;
    
    restore)
        if [ -z "$2" ]; then
            echo "Usage: $0 restore <backup_file.sql>"
            exit 1
        fi
        echo "Restoring database from $2..."
        docker-compose exec -T db psql -U "${DB_USER:-expense_user}" "${DB_NAME:-expense_bot}" < "$2"
        echo "Database restored successfully"
        ;;
    
    update)
        echo "Updating Expense Bot..."
        git pull
        docker-compose build
        docker-compose up -d
        docker-compose run --rm bot python manage.py migrate
        docker-compose run --rm bot python manage.py collectstatic --noinput
        docker-compose restart
        echo "Update complete!"
        ;;
    
    status)
        docker-compose ps
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|logs|shell|dbshell|migrate|makemigrations|createsuperuser|collectstatic|backup|restore|update|status}"
        echo ""
        echo "Commands:"
        echo "  start            - Start all services"
        echo "  stop             - Stop all services"
        echo "  restart          - Restart all services"
        echo "  logs [service]   - View logs (optionally for specific service)"
        echo "  shell            - Open bash shell in bot container"
        echo "  dbshell          - Open PostgreSQL shell"
        echo "  migrate          - Run database migrations"
        echo "  makemigrations   - Create new migrations"
        echo "  createsuperuser  - Create Django admin user"
        echo "  collectstatic    - Collect static files"
        echo "  backup           - Create database backup"
        echo "  restore <file>   - Restore database from backup"
        echo "  update           - Update and restart the application"
        echo "  status           - Show service status"
        exit 1
        ;;
esac