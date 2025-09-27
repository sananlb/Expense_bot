#!/bin/bash
# Простой скрипт резервного копирования expense_bot
# Запускать на основном сервере (80.66.87.178)

set -e

# Конфигурация
PROJECT_PATH="/home/batman/expense_bot"
RESERVE_SERVER="45.95.2.84"
RESERVE_USER="root"
BACKUP_DIR="/root/expense_bot_backups"

echo "================================================"
echo "Резервное копирование ExpenseBot → ${RESERVE_SERVER}"
echo "Время: $(date)"
echo "================================================"

# 1. Создание SQL дампа (всегда сохраняем последний)
echo "→ Создание дампа PostgreSQL..."
cd $PROJECT_PATH
docker exec expense_bot_db pg_dump -U batman expense_bot > expense_bot_latest.sql
echo "  ✓ Дамп создан"

# 2. Архивирование проекта (перезаписываем latest)
echo "→ Архивирование проекта..."
cd $(dirname $PROJECT_PATH)
tar -czf expense_bot_latest.tar.gz \
  expense_bot/ \
  --exclude='expense_bot/venv' \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/**/*.pyc' \
  --exclude='expense_bot/logs/*.log' \
  --exclude='expense_bot/staticfiles/*' \
  --exclude='expense_bot/.git'
echo "  ✓ Архив создан"

# 3. Копирование на резервный сервер
echo "→ Копирование на ${RESERVE_SERVER}..."
ssh ${RESERVE_USER}@${RESERVE_SERVER} "mkdir -p ${BACKUP_DIR}"
scp expense_bot_latest.tar.gz ${RESERVE_USER}@${RESERVE_SERVER}:${BACKUP_DIR}/
scp expense_bot/expense_bot_latest.sql ${RESERVE_USER}@${RESERVE_SERVER}:${BACKUP_DIR}/
echo "  ✓ Файлы скопированы в ${BACKUP_DIR}"

# 4. Очистка
rm expense_bot_latest.tar.gz
rm expense_bot/expense_bot_latest.sql

echo ""
echo "================================================"
echo "✓ Резервная копия создана успешно!"
echo "================================================"
echo ""
echo "На резервном сервере доступны команды:"
echo "  bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest"
echo "  bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db"
echo "  bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --start"
echo "  bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db --start"