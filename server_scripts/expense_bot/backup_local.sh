#!/bin/bash
# Скрипт создания локальной резервной копии expense_bot
# Запускать на основном сервере (80.66.87.178)

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
echo "  ✓ Дамп создан: $BACKUP_DIR/expense_bot_latest.sql"

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
echo "  ✓ Архив создан: $BACKUP_DIR/expense_bot_latest.tar.gz"

# 3. Показать размеры файлов
echo ""
echo "→ Созданные файлы:"
ls -lh $BACKUP_DIR/expense_bot_latest.*

echo ""
echo "================================================"
echo "✓ Резервная копия создана!"
echo "================================================"
echo ""
echo "Для копирования на резервный сервер выполните с ВАШЕГО компьютера:"
echo ""
echo "1. Скачать файлы:"
echo "   scp batman@80.66.87.178:$BACKUP_DIR/expense_bot_latest.tar.gz ."
echo "   scp batman@80.66.87.178:$BACKUP_DIR/expense_bot_latest.sql ."
echo ""
echo "2. Загрузить на резервный сервер:"
echo "   scp expense_bot_latest.tar.gz root@45.95.2.84:/root/expense_bot_backups/"
echo "   scp expense_bot_latest.sql root@45.95.2.84:/root/expense_bot_backups/"
echo ""
echo "Или одной командой через ваш компьютер:"
echo "   scp batman@80.66.87.178:$BACKUP_DIR/expense_bot_latest.* ./ && \\"
echo "   scp expense_bot_latest.* root@45.95.2.84:/root/expense_bot_backups/"