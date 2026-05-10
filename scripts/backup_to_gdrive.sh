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

# --- Retry-обёртка для rclone (экспоненциальный backoff: 30s, 60s, 120s) ---
# Возвращает 0 при успехе, 1 при исчерпании попыток. stdout сохраняется.
# Не использует error_exit и не падает по set -e (вызывающий код решает что делать).
rclone_with_retry() {
    local max_attempts=3
    local delays=(30 60 120)
    local attempt=1
    local rc=0
    while [ "$attempt" -le "$max_attempts" ]; do
        if rclone "$@" 2>/tmp/rclone_err.$$; then
            rm -f /tmp/rclone_err.$$
            return 0
        fi
        rc=$?
        log "WARNING: rclone $1 неудача (попытка ${attempt}/${max_attempts}, exit=${rc})"
        if [ "$attempt" -lt "$max_attempts" ]; then
            sleep "${delays[$((attempt - 1))]}"
        fi
        attempt=$((attempt + 1))
    done
    log "ERROR: rclone $1 не удался после ${max_attempts} попыток. Stderr:"
    [ -f /tmp/rclone_err.$$ ] && sed 's/^/  /' /tmp/rclone_err.$$ | head -10 | while IFS= read -r line; do log "$line"; done
    rm -f /tmp/rclone_err.$$
    return 1
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

# --- Шаг 3: Загрузка на Google Drive (с retry) ---
log "Загрузка на Google Drive..."
if ! rclone_with_retry copy "$BACKUP_FILE" "$GDRIVE_REMOTE"; then
    error_exit "Загрузка на Google Drive не удалась после ретраев"
fi
log "Загружено на Google Drive"

# --- Шаг 4: Ротация на Google Drive (NON-FATAL: бэкап уже залит) ---
# Дамп уже на Google Drive, поэтому сбой ротации (например, Google API quota)
# не должен помечать весь бэкап как неуспешный — только warning.
log "Ротация на Google Drive (макс: ${MAX_GDRIVE_BACKUPS})..."
ROTATION_OK=true
GDRIVE_FILES=""
if GDRIVE_FILES_RAW=$(rclone_with_retry lsf "$GDRIVE_REMOTE" --include "$BACKUP_MASK"); then
    GDRIVE_FILES=$(echo "$GDRIVE_FILES_RAW" | sort)
else
    ROTATION_OK=false
    log "WARNING: не удалось получить список файлов на Google Drive — пропускаю ротацию"
fi
GDRIVE_COUNT=$(echo "$GDRIVE_FILES" | grep -c . || true)

if [ "$ROTATION_OK" = "true" ] && [ "$GDRIVE_COUNT" -gt "$MAX_GDRIVE_BACKUPS" ]; then
    DELETE_COUNT=$((GDRIVE_COUNT - MAX_GDRIVE_BACKUPS))
    DELETE_FILES=$(echo "$GDRIVE_FILES" | head -n "$DELETE_COUNT")
    log "Удаление ${DELETE_COUNT} старых бекапов с Google Drive..."
    while IFS= read -r file; do
        if rclone_with_retry deletefile "${GDRIVE_REMOTE}/${file}"; then
            log "  Удалён: ${file}"
        else
            log "  WARNING: не удалось удалить ${file} (продолжаем)"
            ROTATION_OK=false
        fi
    done <<< "$DELETE_FILES"
fi
log "На Google Drive: ${GDRIVE_COUNT} бекапов"

if [ "$ROTATION_OK" != "true" ]; then
    send_telegram "⚠️ <b>Бекап БД залит, но ротация на Google Drive не удалась</b>%0A%0AВремя: $(date '+%d.%m.%Y %H:%M:%S')%0AДействие: проверь Google Drive API quota / rclone логи"
fi

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
GDRIVE_COUNT_FINAL=$(rclone lsf "$GDRIVE_REMOTE" --include "$BACKUP_MASK" 2>/dev/null | grep -c . || true)

MESSAGE="✅ <b>Бекап БД выполнен</b>%0A"
MESSAGE+="📅 $(date '+%d.%m.%Y %H:%M:%S')%0A"
MESSAGE+="📦 Размер: ${BACKUP_SIZE}%0A"
MESSAGE+="☁️ Google Drive: ${GDRIVE_COUNT_FINAL}/${MAX_GDRIVE_BACKUPS} бекапов%0A"
MESSAGE+="⏱ Время: ${DURATION} сек"

send_telegram "$MESSAGE" "true"
log "Бекап завершён успешно за ${DURATION} сек"
