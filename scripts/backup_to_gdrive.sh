#!/bin/bash
# =============================================================================
# Автоматический бекап БД expense_bot на Google Drive
# Запуск: cron ежедневно в 23:58 МСК
# =============================================================================

set -euo pipefail

# --- Конфигурация ---
export TZ="Europe/Moscow"
BACKUP_DIR="/home/batman/backups"
PROJECT_DIR="/home/batman/expense_bot"
ENV_FILE="${PROJECT_DIR}/.env"
LOCK_FILE="/tmp/backup_to_gdrive.lock"
GDRIVE_REMOTE="gdrive:coins_bot_backup/expense-bot-backups"
BACKUP_MASK="expense_bot_*.dump"
MAX_GDRIVE_BACKUPS=30
MAX_LOCAL_BACKUPS=3
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/expense_bot_${TIMESTAMP}.dump"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
START_TIME=$(date +%s)

# --- Загрузка переменных из .env ---
get_env_var() {
    local key="$1"
    grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'"
}

BOT_TOKEN=$(get_env_var "MONITORING_BOT_TOKEN")
ADMIN_ID=$(get_env_var "ADMIN_TELEGRAM_ID")

# Fallback на основной токен если MONITORING_BOT_TOKEN не задан
if [ -z "$BOT_TOKEN" ]; then
    BOT_TOKEN=$(get_env_var "BOT_TOKEN")
fi

# --- Функции ---
send_telegram() {
    local message="$1"
    local disable_notification="${2:-false}"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${ADMIN_ID}" \
        -d "text=${message}" \
        -d "parse_mode=HTML" \
        -d "disable_notification=${disable_notification}" \
        > /dev/null 2>&1 || true
}

log() {
    echo "${LOG_PREFIX} $1"
}

error_exit() {
    local message="$1"
    log "ERROR: ${message}"
    send_telegram "❌ <b>Ошибка бекапа БД</b>%0A%0AШаг: ${message}%0AВремя: $(date '+%d.%m.%Y %H:%M:%S')"
    exit 1
}

# --- Trap для неожиданных ошибок ---
trap 'error_exit "Неожиданная ошибка на строке ${LINENO}"' ERR

# --- Защита от параллельного запуска (flock) ---
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    log "Бекап уже выполняется, выход"
    exit 0
fi

# --- Проверки ---
if [ ! -f "$ENV_FILE" ]; then
    error_exit "Файл .env не найден: ${ENV_FILE}"
fi

if [ -z "$BOT_TOKEN" ] || [ -z "$ADMIN_ID" ]; then
    log "WARNING: Telegram уведомления недоступны (BOT_TOKEN или ADMIN_ID не заданы)"
fi

if ! command -v rclone &> /dev/null; then
    error_exit "rclone не установлен"
fi

if ! docker ps --format '{{.Names}}' | grep -q "expense_bot_db"; then
    error_exit "Контейнер expense_bot_db не запущен"
fi

# --- Создание директории ---
mkdir -p "$BACKUP_DIR"

# --- Шаг 1: Создание дампа БД ---
log "Создание дампа БД..."
if ! docker exec expense_bot_db pg_dump -Fc -U expense_user expense_bot > "$BACKUP_FILE" 2>/dev/null; then
    error_exit "pg_dump не удался"
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Дамп создан: ${BACKUP_FILE} (${BACKUP_SIZE})"

# --- Шаг 2: Валидация дампа ---
log "Валидация дампа..."
if ! docker exec -i expense_bot_db pg_restore --list < "$BACKUP_FILE" > /dev/null 2>&1; then
    error_exit "Дамп не прошёл валидацию (pg_restore --list)"
fi
log "Дамп валиден"

# --- Шаг 3: Загрузка на Google Drive ---
log "Загрузка на Google Drive..."
if ! rclone copy "$BACKUP_FILE" "$GDRIVE_REMOTE" 2>/dev/null; then
    error_exit "Загрузка на Google Drive не удалась"
fi
log "Загружено на Google Drive"

# --- Шаг 4: Ротация на Google Drive (оставить последние MAX_GDRIVE_BACKUPS) ---
log "Ротация на Google Drive (макс: ${MAX_GDRIVE_BACKUPS})..."
GDRIVE_FILES=$(rclone lsf "$GDRIVE_REMOTE" --include "$BACKUP_MASK" | sort)
GDRIVE_COUNT=$(echo "$GDRIVE_FILES" | grep -c . || true)

if [ "$GDRIVE_COUNT" -gt "$MAX_GDRIVE_BACKUPS" ]; then
    DELETE_COUNT=$((GDRIVE_COUNT - MAX_GDRIVE_BACKUPS))
    DELETE_FILES=$(echo "$GDRIVE_FILES" | head -n "$DELETE_COUNT")
    log "Удаление ${DELETE_COUNT} старых бекапов с Google Drive..."
    while IFS= read -r file; do
        rclone deletefile "${GDRIVE_REMOTE}/${file}" 2>/dev/null || true
        log "  Удалён: ${file}"
    done <<< "$DELETE_FILES"
fi
log "На Google Drive: ${GDRIVE_COUNT} бекапов"

# --- Шаг 5: Ротация локальная (оставить последние MAX_LOCAL_BACKUPS) ---
log "Ротация локальных бекапов (макс: ${MAX_LOCAL_BACKUPS})..."
LOCAL_FILES=$(ls -1t "${BACKUP_DIR}"/${BACKUP_MASK} 2>/dev/null || true)
LOCAL_COUNT=$(echo "$LOCAL_FILES" | grep -c . || true)

if [ "$LOCAL_COUNT" -gt "$MAX_LOCAL_BACKUPS" ]; then
    echo "$LOCAL_FILES" | tail -n +$((MAX_LOCAL_BACKUPS + 1)) | while IFS= read -r file; do
        rm -f "$file"
        log "  Удалён локально: $(basename "$file")"
    done
fi

# --- Шаг 6: Уведомление об успехе ---
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
GDRIVE_COUNT_FINAL=$(rclone lsf "$GDRIVE_REMOTE" --include "$BACKUP_MASK" | grep -c . || true)

MESSAGE="✅ <b>Бекап БД выполнен</b>%0A"
MESSAGE+="📅 $(date '+%d.%m.%Y %H:%M:%S')%0A"
MESSAGE+="📦 Размер: ${BACKUP_SIZE}%0A"
MESSAGE+="☁️ Google Drive: ${GDRIVE_COUNT_FINAL}/${MAX_GDRIVE_BACKUPS} бекапов%0A"
MESSAGE+="⏱ Время: ${DURATION} сек"

send_telegram "$MESSAGE" "true"
log "Бекап завершён успешно за ${DURATION} сек"
