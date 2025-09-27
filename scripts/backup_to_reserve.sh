#!/bin/bash
# Скрипт для создания резервной копии expense_bot на резервный сервер
# Запускать на основном сервере (80.66.87.178)

set -e

# Конфигурация
MAIN_SERVER_PATH="/home/batman/expense_bot"
RESERVE_SERVER="45.95.2.84"
RESERVE_USER="root"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "Резервное копирование ExpenseBot"
echo "Время: $(date)"
echo "=========================================="

# 1. Создание дампа базы данных
echo "1. Создание дампа PostgreSQL..."
cd $MAIN_SERVER_PATH
docker exec expense_bot_db pg_dump -U batman expense_bot > expense_bot_backup_${TIMESTAMP}.sql
echo "   ✓ Дамп создан: expense_bot_backup_${TIMESTAMP}.sql"

# 2. Архивирование проекта
echo "2. Архивирование проекта..."
cd /home/batman
tar -czf expense_bot_full_${TIMESTAMP}.tar.gz \
  expense_bot/ \
  --exclude='expense_bot/venv' \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/logs/*.log' \
  --exclude='expense_bot/staticfiles' \
  --exclude='expense_bot/*.pyc'
echo "   ✓ Архив создан: expense_bot_full_${TIMESTAMP}.tar.gz"

# 3. Копирование на резервный сервер
echo "3. Копирование на резервный сервер ${RESERVE_SERVER}..."
scp expense_bot_full_${TIMESTAMP}.tar.gz ${RESERVE_USER}@${RESERVE_SERVER}:/root/
scp expense_bot/expense_bot_backup_${TIMESTAMP}.sql ${RESERVE_USER}@${RESERVE_SERVER}:/root/
echo "   ✓ Файлы скопированы"

# 4. Очистка временных файлов
echo "4. Очистка временных файлов..."
rm expense_bot_full_${TIMESTAMP}.tar.gz
mv expense_bot/expense_bot_backup_${TIMESTAMP}.sql expense_bot/backups/ 2>/dev/null || mkdir -p expense_bot/backups && mv expense_bot/expense_bot_backup_${TIMESTAMP}.sql expense_bot/backups/
echo "   ✓ Временные файлы очищены"

echo ""
echo "=========================================="
echo "Резервное копирование завершено!"
echo "=========================================="
echo ""
echo "Для развертывания на резервном сервере выполните:"
echo "ssh ${RESERVE_USER}@${RESERVE_SERVER}"
echo "bash /root/deploy_expense_bot.sh ${TIMESTAMP}"