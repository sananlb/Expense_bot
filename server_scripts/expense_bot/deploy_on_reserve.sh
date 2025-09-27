#!/bin/bash
# Скрипт развертывания expense_bot на резервном сервере
# Запускать на резервном сервере (45.95.2.84)

set -e

# Конфигурация
BACKUP_DIR="/root/expense_bot_backups"
PROJECT_DIR="/opt/expense_bot"
TIMESTAMP="$1"

# Флаги управления
RESTORE_DB=false
START_SERVICES=false
FORCE_REBUILD=false

# Функция помощи
show_help() {
    echo "Использование: $0 <timestamp|latest> [опции]"
    echo ""
    echo "Опции:"
    echo "  --restore-db     Восстановить базу данных из дампа"
    echo "  --start          Запустить все сервисы после развертывания"
    echo "  --force-rebuild  Принудительно пересобрать Docker образы"
    echo "  --help           Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 latest                    # Только обновить код"
    echo "  $0 latest --restore-db       # Обновить код и БД"
    echo "  $0 latest --start            # Обновить код и запустить"
    echo "  $0 latest --restore-db --start # Полное развертывание"
    exit 0
}

# Парсинг аргументов
if [ -z "$1" ] || [ "$1" == "--help" ]; then
    show_help
fi

shift # Удаляем первый аргумент (timestamp)
while [[ $# -gt 0 ]]; do
    case $1 in
        --restore-db)
            RESTORE_DB=true
            shift
            ;;
        --start)
            START_SERVICES=true
            shift
            ;;
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        *)
            echo "Неизвестная опция: $1"
            show_help
            ;;
    esac
done

echo "================================================"
echo "Развертывание ExpenseBot на резервном сервере"
echo "Версия: ${TIMESTAMP}"
echo "Восстановление БД: ${RESTORE_DB}"
echo "Запуск сервисов: ${START_SERVICES}"
echo "================================================"

# 1. Проверка файлов
echo "→ Проверка резервной копии..."
ARCHIVE_FILE="${BACKUP_DIR}/expense_bot_${TIMESTAMP}.tar.gz"
SQL_FILE="${BACKUP_DIR}/expense_bot_${TIMESTAMP}.sql"

# Если указан latest, используем последние файлы
if [ "$TIMESTAMP" == "latest" ]; then
    ARCHIVE_FILE="${BACKUP_DIR}/expense_bot_latest.tar.gz"
    SQL_FILE="${BACKUP_DIR}/expense_bot_latest.sql"
fi

if [ ! -f "$ARCHIVE_FILE" ]; then
    echo "  ✗ Архив не найден: $ARCHIVE_FILE"
    exit 1
fi
echo "  ✓ Архив найден"

if [ "$RESTORE_DB" == "true" ] && [ ! -f "$SQL_FILE" ]; then
    echo "  ✗ SQL дамп не найден: $SQL_FILE"
    exit 1
fi

# 2. Остановка сервисов (если запущены)
if [ -d "$PROJECT_DIR" ]; then
    echo "→ Остановка существующих контейнеров..."
    cd $PROJECT_DIR
    docker-compose down 2>/dev/null || true
    cd /
fi

# 3. Backup старой версии (если есть)
if [ -d "$PROJECT_DIR" ]; then
    echo "→ Архивирование предыдущей версии..."
    mv $PROJECT_DIR ${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)
    echo "  ✓ Старая версия сохранена"
fi

# 4. Распаковка новой версии
echo "→ Распаковка проекта..."
mkdir -p /opt
cd /opt
tar -xzf $ARCHIVE_FILE
echo "  ✓ Проект распакован в $PROJECT_DIR"

# 5. Проверка .env
cd $PROJECT_DIR
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  ВНИМАНИЕ: Файл .env не найден!"
    echo "   Создайте файл .env с необходимыми переменными:"
    echo "   - BOT_TOKEN"
    echo "   - DB_NAME, DB_USER, DB_PASSWORD"
    echo "   - REDIS_PASSWORD"
    echo "   - ADMIN_TELEGRAM_ID"
    echo ""
    if [ "$START_SERVICES" == "true" ]; then
        echo "Отмена запуска из-за отсутствия .env"
        exit 1
    fi
fi

# 6. Создание директорий
echo "→ Создание необходимых директорий..."
mkdir -p logs media staticfiles
echo "  ✓ Директории созданы"

# 7. Сборка образов (если нужно)
if [ "$START_SERVICES" == "true" ] || [ "$FORCE_REBUILD" == "true" ]; then
    echo "→ Сборка Docker образов..."
    if [ "$FORCE_REBUILD" == "true" ]; then
        docker-compose build --no-cache
    else
        docker-compose build
    fi
    echo "  ✓ Образы готовы"
fi

# 8. Восстановление БД (если указано)
if [ "$RESTORE_DB" == "true" ]; then
    echo "→ Восстановление базы данных..."

    # Запуск только БД
    docker-compose up -d db
    echo "  Ожидание запуска PostgreSQL (10 сек)..."
    sleep 10

    # Создание БД если не существует
    docker exec expense_bot_db psql -U batman -c "CREATE DATABASE expense_bot;" 2>/dev/null || true

    # Восстановление дампа
    docker exec -i expense_bot_db psql -U batman expense_bot < $SQL_FILE
    echo "  ✓ База данных восстановлена"

    # Если не запускаем все сервисы, останавливаем БД
    if [ "$START_SERVICES" != "true" ]; then
        docker-compose stop db
    fi
fi

# 9. Запуск всех сервисов (если указано)
if [ "$START_SERVICES" == "true" ]; then
    echo "→ Запуск всех сервисов..."
    docker-compose up -d
    echo "  ✓ Сервисы запущены"

    echo ""
    echo "→ Проверка статуса:"
    docker-compose ps
fi

echo ""
echo "================================================"
echo "✓ Развертывание завершено!"
echo "================================================"

if [ "$START_SERVICES" != "true" ]; then
    echo ""
    echo "Сервисы НЕ запущены. Для запуска выполните:"
    echo "  cd $PROJECT_DIR && docker-compose up -d"
fi

if [ "$RESTORE_DB" != "true" ]; then
    echo ""
    echo "База данных НЕ восстановлена."
    echo "Используется существующая БД или будет создана новая."
fi

echo ""
echo "Полезные команды:"
echo "  cd $PROJECT_DIR"
echo "  docker-compose ps                    # Статус"
echo "  docker-compose logs -f bot           # Логи бота"
echo "  docker-compose restart bot           # Перезапуск бота"
echo "  docker-compose down                  # Остановить все"