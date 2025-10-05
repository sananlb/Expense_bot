#!/bin/bash

# Скрипт проверки состояния системы после деплоя
# Запускать на сервере после обновления кода

set -e

echo "=================================="
echo "Проверка состояния системы"
echo "=================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки
check_component() {
    local name="$1"
    local command="$2"

    echo -n "Проверка $name... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        return 1
    fi
}

# Счетчик ошибок
ERRORS=0

# 1. Проверка контейнеров Docker
echo "=== 1. Docker контейнеры ==="
if docker ps | grep -q "expense_bot"; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep expense_bot
    echo ""
else
    echo -e "${RED}Контейнеры не запущены!${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 2. Проверка базы данных
echo "=== 2. База данных PostgreSQL ==="
if docker exec expense_bot_db pg_isready -U expense_user > /dev/null 2>&1; then
    echo -e "${GREEN}PostgreSQL: OK${NC}"

    # Проверка количества пользователей
    USER_COUNT=$(docker exec expense_bot_db psql -U expense_user -d expense_bot -t -c "SELECT COUNT(*) FROM users_profile;" 2>/dev/null | tr -d ' ')
    echo "Пользователей в БД: $USER_COUNT"
else
    echo -e "${RED}PostgreSQL: FAILED${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 3. Проверка Redis
echo "=== 3. Redis ==="
if docker exec expense_bot_redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}Redis: OK${NC}"

    # Информация о памяти
    REDIS_MEMORY=$(docker exec expense_bot_redis redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    echo "Использование памяти: $REDIS_MEMORY"
else
    echo -e "${RED}Redis: FAILED${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 4. Проверка Telegram Bot API
echo "=== 4. Telegram Bot API ==="
TOKEN=$(docker exec expense_bot_app printenv BOT_TOKEN 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
    RESPONSE=$(curl -s "https://api.telegram.org/bot$TOKEN/getMe")
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        BOT_USERNAME=$(echo "$RESPONSE" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}Telegram API: OK${NC}"
        echo "Bot username: @$BOT_USERNAME"
    else
        echo -e "${RED}Telegram API: FAILED${NC}"
        echo "Response: $RESPONSE"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}BOT_TOKEN не найден${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 5. Проверка Webhook
echo "=== 5. Telegram Webhook ==="
if [ -n "$TOKEN" ]; then
    WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo")

    WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    PENDING_UPDATES=$(echo "$WEBHOOK_INFO" | grep -o '"pending_update_count":[0-9]*' | cut -d: -f2)
    LAST_ERROR=$(echo "$WEBHOOK_INFO" | grep -o '"last_error_message":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$WEBHOOK_URL" ]; then
        echo -e "${RED}⚠️  КРИТИЧЕСКАЯ ПРОБЛЕМА: Webhook URL пустой!${NC}"
        echo "Бот НЕ получает обновления от Telegram!"
        echo ""
        echo "Запустите: bash ~/fix_webhook_force.sh"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}Webhook URL: $WEBHOOK_URL${NC}"

        if [ -n "$PENDING_UPDATES" ] && [ "$PENDING_UPDATES" -gt 0 ]; then
            if [ "$PENDING_UPDATES" -gt 10 ]; then
                echo -e "${YELLOW}⚠️  WARNING: $PENDING_UPDATES необработанных обновлений${NC}"
            else
                echo "Pending updates: $PENDING_UPDATES"
            fi
        else
            echo "Pending updates: 0"
        fi

        if [ -n "$LAST_ERROR" ]; then
            echo -e "${YELLOW}Last error: $LAST_ERROR${NC}"
        fi
    fi
else
    echo -e "${RED}Не удалось проверить webhook (нет токена)${NC}"
fi
echo ""

# 6. Проверка Celery
echo "=== 6. Celery Workers ==="
CELERY_STATUS=$(docker exec expense_bot_celery celery -A expense_bot inspect active 2>/dev/null || echo "")
if echo "$CELERY_STATUS" | grep -q "celery@"; then
    echo -e "${GREEN}Celery workers: OK${NC}"
    docker exec expense_bot_celery celery -A expense_bot inspect stats 2>/dev/null | grep -E "(celery@|pool:)"
else
    echo -e "${RED}Celery workers: FAILED${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 7. Проверка доступности webhook URL снаружи
echo "=== 7. Доступность webhook endpoint ==="
if [ -n "$WEBHOOK_URL" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X HEAD "$WEBHOOK_URL" || echo "000")
    if [ "$HTTP_CODE" = "405" ] || [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}Webhook endpoint доступен (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}Webhook endpoint недоступен (HTTP $HTTP_CODE)${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# 8. Проверка логов на ошибки
echo "=== 8. Последние ошибки в логах ==="
ERROR_COUNT=$(docker logs expense_bot_app --since 1h 2>&1 | grep -c "ERROR" || echo "0")
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Найдено $ERROR_COUNT ошибок за последний час${NC}"
    echo "Последние 5 ошибок:"
    docker logs expense_bot_app --since 1h 2>&1 | grep "ERROR" | tail -5
else
    echo -e "${GREEN}Ошибок не найдено${NC}"
fi
echo ""

# 9. Проверка дискового пространства
echo "=== 9. Дисковое пространство ==="
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
DISK_AVAILABLE=$(df -h / | awk 'NR==2 {print $4}')

if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}Использование диска: ${DISK_USAGE}% (доступно: $DISK_AVAILABLE)${NC}"
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${YELLOW}Использование диска: ${DISK_USAGE}% (доступно: $DISK_AVAILABLE)${NC}"
else
    echo -e "${RED}⚠️  КРИТИЧЕСКОЕ: Использование диска ${DISK_USAGE}% (доступно: $DISK_AVAILABLE)${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Итоговый результат
echo "=================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Все проверки пройдены успешно!${NC}"
    exit 0
else
    echo -e "${RED}❌ Обнаружено проблем: $ERRORS${NC}"
    echo ""
    echo "Рекомендации:"
    echo "1. Проверьте логи: docker logs expense_bot_app --tail 100"
    echo "2. Проверьте статус контейнеров: docker ps -a"
    echo "3. Перезапустите проблемные контейнеры: docker restart <container_name>"
    exit 1
fi
