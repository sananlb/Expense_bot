#!/bin/bash
# Скрипт создания резервных копий БД для Expense Bot

# Конфигурация
BACKUP_DIR="/home/deploy/expense_bot/backups"
DB_NAME="expense_bot"
DB_USER="expense_user"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/expense_bot_backup_$TIMESTAMP.sql"
KEEP_DAYS=7  # Хранить бэкапы за последние 7 дней

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Функция логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Создаем директорию для бэкапов если её нет
if [ ! -d "$BACKUP_DIR" ]; then
    log "Создание директории для бэкапов: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Проверяем наличие pg_dump
if ! command -v pg_dump &> /dev/null; then
    error "pg_dump не найден. Установите PostgreSQL client tools."
    exit 1
fi

# Создание бэкапа
log "Начало создания резервной копии БД: $DB_NAME"

# Используем .pgpass для авторизации или переменные окружения
export PGPASSWORD="${DB_PASSWORD:-}"

# Создаем дамп
if pg_dump -h localhost -U "$DB_USER" -d "$DB_NAME" -f "$BACKUP_FILE" 2>/dev/null; then
    # Сжимаем бэкап
    log "Сжатие резервной копии..."
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    # Проверяем размер
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✅ Резервная копия создана успешно: $BACKUP_FILE (размер: $SIZE)"
    
    # Создаем симлинк на последний бэкап
    ln -sf "$BACKUP_FILE" "$BACKUP_DIR/latest_backup.sql.gz"
else
    error "Ошибка создания резервной копии!"
    exit 1
fi

# Очистка старых бэкапов
log "Очистка бэкапов старше $KEEP_DAYS дней..."
find "$BACKUP_DIR" -name "expense_bot_backup_*.sql.gz" -type f -mtime +$KEEP_DAYS -delete

# Показываем список бэкапов
echo -e "\n${YELLOW}Текущие резервные копии:${NC}"
ls -lh "$BACKUP_DIR"/expense_bot_backup_*.sql.gz 2>/dev/null | tail -10

# Показываем использование диска
echo -e "\n${YELLOW}Использование диска директорией бэкапов:${NC}"
du -sh "$BACKUP_DIR"

# Дополнительно: отправка бэкапа в облако (раскомментируйте если нужно)
# if command -v rclone &> /dev/null; then
#     log "Отправка бэкапа в облако..."
#     rclone copy "$BACKUP_FILE" remote:expense-bot-backups/
# fi

log "Процесс резервного копирования завершён!"