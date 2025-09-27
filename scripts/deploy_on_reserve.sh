#!/bin/bash
# Скрипт для развертывания expense_bot на резервном сервере
# Запускать на резервном сервере (45.95.2.84)

set -e

# Проверка аргументов
if [ -z "$1" ]; then
    echo "Использование: $0 <timestamp>"
    echo "Пример: $0 20241227_143022"
    exit 1
fi

TIMESTAMP=$1
BACKUP_DIR="/root"
PROJECT_DIR="/root/expense_bot"

echo "=========================================="
echo "Развертывание ExpenseBot из резервной копии"
echo "Timestamp: ${TIMESTAMP}"
echo "=========================================="

# 1. Проверка наличия файлов
echo "1. Проверка файлов резервной копии..."
if [ ! -f "${BACKUP_DIR}/expense_bot_full_${TIMESTAMP}.tar.gz" ]; then
    echo "   ✗ Файл не найден: expense_bot_full_${TIMESTAMP}.tar.gz"
    exit 1
fi
if [ ! -f "${BACKUP_DIR}/expense_bot_backup_${TIMESTAMP}.sql" ]; then
    echo "   ✗ Файл не найден: expense_bot_backup_${TIMESTAMP}.sql"
    exit 1
fi
echo "   ✓ Файлы найдены"

# 2. Остановка существующих контейнеров (если есть)
echo "2. Остановка существующих контейнеров..."
if [ -d "$PROJECT_DIR" ]; then
    cd $PROJECT_DIR
    docker-compose down 2>/dev/null || true
    cd $BACKUP_DIR
    # Архивирование старой версии
    mv $PROJECT_DIR ${PROJECT_DIR}_old_$(date +%Y%m%d_%H%M%S)
fi
echo "   ✓ Контейнеры остановлены"

# 3. Распаковка архива
echo "3. Распаковка проекта..."
cd $BACKUP_DIR
tar -xzf expense_bot_full_${TIMESTAMP}.tar.gz
echo "   ✓ Проект распакован"

# 4. Переход в директорию проекта
echo "4. Настройка проекта..."
cd $PROJECT_DIR

# 5. Проверка .env файла
if [ ! -f ".env" ]; then
    echo "   ⚠ ВНИМАНИЕ: Файл .env не найден!"
    echo "   Необходимо создать .env файл с правильными настройками"
    echo "   Скопируйте его с основного сервера или используйте .env.example"
    exit 1
fi

# 6. Создание необходимых директорий
mkdir -p logs media staticfiles
echo "   ✓ Директории созданы"

# 7. Сборка Docker образов
echo "5. Сборка Docker образов..."
docker-compose build --no-cache
echo "   ✓ Образы собраны"

# 8. Запуск базы данных
echo "6. Запуск PostgreSQL..."
docker-compose up -d db
echo "   Ожидание запуска БД (15 сек)..."
sleep 15

# 9. Восстановление данных
echo "7. Восстановление базы данных..."
# Создание базы если не существует
docker exec expense_bot_db psql -U batman -c "CREATE DATABASE expense_bot;" 2>/dev/null || true
# Восстановление дампа
docker exec -i expense_bot_db psql -U batman expense_bot < ${BACKUP_DIR}/expense_bot_backup_${TIMESTAMP}.sql
echo "   ✓ База данных восстановлена"

# 10. Запуск Redis
echo "8. Запуск Redis..."
docker-compose up -d redis
sleep 5

# 11. Запуск остальных сервисов
echo "9. Запуск всех сервисов..."
docker-compose up -d
echo "   ✓ Все сервисы запущены"

# 12. Проверка статуса
echo ""
echo "10. Проверка статуса контейнеров:"
docker-compose ps

echo ""
echo "=========================================="
echo "Развертывание завершено успешно!"
echo "=========================================="
echo ""
echo "Важные шаги после развертывания:"
echo "1. Проверить логи: docker-compose logs -f bot"
echo "2. Обновить webhook Telegram (если нужно)"
echo "3. Проверить работу бота"
echo "4. Настроить nginx/SSL (если требуется)"
echo ""
echo "Для переключения на этот сервер:"
echo "- Измените DNS записи на IP: 45.95.2.84"
echo "- Или обновите webhook в Telegram на новый IP"