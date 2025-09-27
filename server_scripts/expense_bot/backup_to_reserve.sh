#!/bin/bash
# Скрипт создания резервной копии expense_bot
# Запускать на основном сервере (80.66.87.178)
# Копирование происходит через локальный компьютер

set -e

# Конфигурация
PROJECT_PATH="/home/batman/expense_bot"
BACKUP_DIR="/home/batman/backups"

echo "================================================"
echo "Создание резервной копии ExpenseBot"
echo "Время: $(date)"
echo "================================================"

# Создание директории для бэкапов
mkdir -p $BACKUP_DIR

# 1. Создание SQL дампа
echo "→ Создание дампа PostgreSQL..."
cd $PROJECT_PATH
docker exec expense_bot_db pg_dump -U batman expense_bot > $BACKUP_DIR/expense_bot_latest.sql
echo "  ✓ Дамп создан: expense_bot_latest.sql"

# 2. Архивирование проекта
echo "→ Архивирование проекта..."
cd $(dirname $PROJECT_PATH)
tar -czf $BACKUP_DIR/expense_bot_latest.tar.gz \
  expense_bot/ \
  --exclude='expense_bot/venv' \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/**/*.pyc' \
  --exclude='expense_bot/logs/*.log' \
  --exclude='expense_bot/staticfiles/*' \
  --exclude='expense_bot/.git'
echo "  ✓ Архив создан: expense_bot_latest.tar.gz"

# 3. Показать размеры файлов
echo ""
echo "→ Созданные файлы:"
ls -lh $BACKUP_DIR/expense_bot_latest.* | awk '{print "  " $9 " (" $5 ")"}'

echo ""
echo "================================================"
echo "✓ Резервная копия создана в $BACKUP_DIR"
echo "================================================"
echo ""
echo "ШАГ 2: На ВАШЕМ ЛОКАЛЬНОМ компьютере (Windows PowerShell):"
echo ""
echo "# Создать временную папку и скачать файлы:"
echo "mkdir C:\temp\expense_backup"
echo "cd C:\temp\expense_backup"
echo "scp batman@80.66.87.178:$BACKUP_DIR/expense_bot_latest.* ./"
echo ""
echo "# Загрузить на резервный сервер:"
echo "scp expense_bot_latest.* root@45.95.2.84:/root/expense_bot_backups/"
echo ""
echo "ШАГ 3: На РЕЗЕРВНОМ сервере (45.95.2.84):"
echo ""
echo "# Развернуть проект (выберите нужную команду):"
echo "bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest                    # Только код"
echo "bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db       # Код + БД"
echo "bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db --start # Полное развертывание"