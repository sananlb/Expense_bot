#!/bin/bash
# Скрипт проверки здоровья Expense Bot

# Переменные
SERVICE_NAME="expense-bot"
PROJECT_DIR="/home/deploy/expense_bot"
TELEGRAM_WEBHOOK_URL=""  # Опционально: URL для отправки уведомлений

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Счетчики проблем
WARNINGS=0
ERRORS=0

# Функции для вывода
log_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((ERRORS++))
}

echo "======================================"
echo "  Expense Bot Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"
echo ""

# 1. Проверка системных ресурсов
echo "1. Системные ресурсы:"

# Проверка CPU
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
CPU_INT=${CPU_USAGE%.*}
if [ "$CPU_INT" -gt 80 ]; then
    log_warn "Высокая загрузка CPU: ${CPU_USAGE}%"
else
    log_ok "Загрузка CPU: ${CPU_USAGE}%"
fi

# Проверка памяти
MEM_TOTAL=$(free -m | awk 'NR==2{print $2}')
MEM_USED=$(free -m | awk 'NR==2{print $3}')
MEM_PERCENT=$((MEM_USED * 100 / MEM_TOTAL))
if [ "$MEM_PERCENT" -gt 80 ]; then
    log_warn "Высокое использование памяти: ${MEM_PERCENT}% (${MEM_USED}MB / ${MEM_TOTAL}MB)"
else
    log_ok "Использование памяти: ${MEM_PERCENT}% (${MEM_USED}MB / ${MEM_TOTAL}MB)"
fi

# Проверка диска
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    log_error "Критическое использование диска: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -gt 60 ]; then
    log_warn "Высокое использование диска: ${DISK_USAGE}%"
else
    log_ok "Использование диска: ${DISK_USAGE}%"
fi

echo ""

# 2. Проверка сервисов
echo "2. Статус сервисов:"

# PostgreSQL
if systemctl is-active --quiet postgresql; then
    log_ok "PostgreSQL активен"
    # Проверка подключения к БД
    if sudo -u postgres psql -d expense_bot -c "SELECT 1;" &>/dev/null; then
        log_ok "Подключение к БД expense_bot успешно"
    else
        log_error "Не удается подключиться к БД expense_bot"
    fi
else
    log_error "PostgreSQL не запущен"
fi

# Redis
if systemctl is-active --quiet redis-server; then
    log_ok "Redis активен"
    # Проверка подключения к Redis
    if redis-cli ping &>/dev/null; then
        log_ok "Redis отвечает на запросы"
    else
        log_error "Redis не отвечает"
    fi
else
    log_error "Redis не запущен"
fi

# Expense Bot
if systemctl is-active --quiet $SERVICE_NAME; then
    log_ok "Expense Bot активен"
    # Проверка времени работы
    UPTIME=$(systemctl show -p ActiveEnterTimestamp $SERVICE_NAME | cut -d'=' -f2)
    echo "    Запущен: $UPTIME"
else
    log_error "Expense Bot не запущен"
fi

echo ""

# 3. Проверка логов на ошибки
echo "3. Анализ логов:"

# Проверка последних ошибок в логах бота
ERROR_COUNT=$(sudo journalctl -u $SERVICE_NAME --since "1 hour ago" | grep -c "ERROR" || true)
if [ "$ERROR_COUNT" -gt 10 ]; then
    log_error "Обнаружено $ERROR_COUNT ошибок за последний час"
elif [ "$ERROR_COUNT" -gt 0 ]; then
    log_warn "Обнаружено $ERROR_COUNT ошибок за последний час"
else
    log_ok "Ошибок в логах за последний час не обнаружено"
fi

# Проверка критических ошибок
CRITICAL_COUNT=$(sudo journalctl -u $SERVICE_NAME --since "1 hour ago" | grep -c "CRITICAL" || true)
if [ "$CRITICAL_COUNT" -gt 0 ]; then
    log_error "Обнаружено $CRITICAL_COUNT критических ошибок!"
fi

echo ""

# 4. Проверка файловой системы проекта
echo "4. Файловая система:"

# Проверка наличия важных файлов
if [ -f "$PROJECT_DIR/.env" ]; then
    log_ok "Файл .env существует"
else
    log_error "Файл .env не найден!"
fi

if [ -f "$PROJECT_DIR/manage.py" ]; then
    log_ok "manage.py найден"
else
    log_error "manage.py не найден!"
fi

# Проверка прав на директории
if [ -w "$PROJECT_DIR/logs" ] 2>/dev/null; then
    log_ok "Директория logs доступна для записи"
else
    log_warn "Директория logs недоступна для записи"
fi

echo ""

# 5. Проверка сетевых подключений
echo "5. Сетевые подключения:"

# Проверка количества подключений к PostgreSQL
PG_CONNECTIONS=$(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'expense_bot';" 2>/dev/null || echo "0")
log_ok "Активных подключений к БД: $PG_CONNECTIONS"

# Проверка доступности Telegram API
if curl -s --max-time 5 https://api.telegram.org >/dev/null; then
    log_ok "Telegram API доступен"
else
    log_error "Telegram API недоступен"
fi

echo ""

# Итоговый отчет
echo "======================================"
echo "  Результаты проверки:"
echo "======================================"
if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}✅ Система работает нормально${NC}"
    EXIT_CODE=0
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Обнаружены предупреждения: $WARNINGS${NC}"
    EXIT_CODE=1
else
    echo -e "${RED}❌ Обнаружены ошибки: $ERRORS, предупреждения: $WARNINGS${NC}"
    EXIT_CODE=2
fi

# Отправка уведомления (если настроено)
if [ ! -z "$TELEGRAM_WEBHOOK_URL" ] && [ "$ERRORS" -gt 0 ]; then
    MESSAGE="🚨 Expense Bot Health Check Alert!\nErrors: $ERRORS\nWarnings: $WARNINGS\nTime: $(date)"
    curl -s -X POST "$TELEGRAM_WEBHOOK_URL" -d "text=$MESSAGE" >/dev/null
fi

exit $EXIT_CODE