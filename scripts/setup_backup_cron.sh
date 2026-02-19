#!/bin/bash
# =============================================================================
# Установка cron-задачи для автоматического бекапа БД на Google Drive
# Идемпотентный — не дублирует строку при повторном запуске
# =============================================================================

SCRIPT_PATH="/home/batman/expense_bot/scripts/backup_to_gdrive.sh"
LOG_PATH="/home/batman/backups/backup.log"
CRON_LINE="58 23 * * * TZ=Europe/Moscow ${SCRIPT_PATH} >> ${LOG_PATH} 2>&1"
CRON_MARKER="backup_to_gdrive.sh"

echo "=== Установка cron-задачи для бекапа БД ==="

# Создать директорию для логов
mkdir -p "$(dirname "$LOG_PATH")"

# Проверить что скрипт существует
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Скрипт не найден: ${SCRIPT_PATH}"
    echo "   Сначала задеплойте скрипт на сервер"
    exit 1
fi

# Сделать скрипт исполняемым
chmod +x "$SCRIPT_PATH"

# Проверить, есть ли уже задача в crontab
if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
    echo "⚠️  Cron-задача уже установлена:"
    crontab -l | grep "$CRON_MARKER"
    echo ""
    echo "Для переустановки сначала удалите старую:"
    echo "  crontab -l | grep -v '${CRON_MARKER}' | crontab -"
    exit 0
fi

# Добавить задачу в crontab
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo "✅ Cron-задача установлена:"
echo "   ${CRON_LINE}"
echo ""
echo "Проверка: crontab -l"
echo "Логи: tail -f ${LOG_PATH}"
echo ""
echo "Для тестового запуска:"
echo "   bash ${SCRIPT_PATH}"
