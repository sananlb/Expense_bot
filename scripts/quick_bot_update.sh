#!/bin/bash

# Быстрое обновление только контейнера бота (без лендинга, веб, celery, redis)
# Использование: bash scripts/quick_bot_update.sh

# Строгий режим: останавливаем выполнение при любой ошибке
set -euo pipefail

# Обработчик ошибок
trap 'echo -e "${RED}❌ Ошибка на строке $LINENO. Обновление прервано!${NC}"; exit 1' ERR

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      ⚡ БЫСТРОЕ ОБНОВЛЕНИЕ БОТА (ТОЛЬКО APP)             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Ошибка: docker-compose.yml не найден!${NC}"
    echo -e "${RED}   Убедитесь, что вы в директории /home/batman/expense_bot${NC}"
    exit 1
fi

echo -e "${YELLOW}📍 Текущая директория: $(pwd)${NC}"
echo -e "${YELLOW}ℹ️  Обновляется только контейнер бота (bot)${NC}"
echo -e "${YELLOW}ℹ️  Веб, Celery, Redis и лендинг не затрагиваются${NC}"
echo ""

# Контейнер бота использует host-local DNS из docker-compose.yml.
DNS_CACHE_IP="${DOCKER_DNS_CACHE_IP:-10.255.255.53}"
echo -e "${YELLOW}🌐 Проверяю локальный DNS-кэш для Docker...${NC}"
if ! command -v dig >/dev/null 2>&1 || \
   ! dig +short +time=2 +tries=1 "@${DNS_CACHE_IP}" api.telegram.org A | grep -q .; then
    echo -e "${YELLOW}  DNS-кэш недоступен, запускаю настройку...${NC}"
    sudo bash scripts/setup_local_dns_cache.sh
fi
echo -e "${GREEN}✓ Локальный DNS-кэш доступен на ${DNS_CACHE_IP}${NC}"
echo ""

# Шаг 1: Остановка и удаление контейнера бота
echo -e "${YELLOW}[1/7] 🛑 Останавливаю и удаляю контейнер бота...${NC}"
docker-compose stop bot
docker-compose rm -f bot
echo -e "${GREEN}✓ Контейнер bot остановлен и удален${NC}"
echo ""

# Шаг 2: Удаление старого образа бота
echo -e "${YELLOW}[2/7] 🧹 Удаляю старый образ бота...${NC}"
# Пробуем оба варианта имени образа (с дефисом и подчеркиванием)
OLD_IMAGE=$(docker images -q 'expense_bot_app' 2>/dev/null || true)
if [ -z "$OLD_IMAGE" ]; then
    OLD_IMAGE=$(docker images -q 'expense_bot-app' 2>/dev/null || true)
fi
if [ -n "$OLD_IMAGE" ]; then
    docker rmi $OLD_IMAGE 2>/dev/null || true
    echo -e "${GREEN}  ✓ Удален старый образ app${NC}"
else
    echo -e "${YELLOW}  ℹ Старого образа не найдено${NC}"
fi
echo -e "${GREEN}✓ Образ очищен${NC}"
echo ""

# Шаг 3: Получение изменений из Git
echo -e "${YELLOW}[3/7] 📥 Получаю последние изменения из Git...${NC}"
git fetch --all
git reset --hard origin/master
git pull origin master
echo -e "${GREEN}✓ Код обновлен из репозитория${NC}"
echo ""

# Проверка безопасности портов (ПОСЛЕ git pull — проверяем код, который будет задеплоен)
echo -e "${YELLOW}🔒 Проверяю безопасность портов в docker-compose файлах...${NC}"
UNSAFE_PORTS=""
for COMPOSE_FILE in docker-compose.yml docker-compose.override.yml; do
    if [ -f "$COMPOSE_FILE" ]; then
        # Ловим все форматы port-маппинга без 127.0.0.1:
        #   - "8000:8000"         (quoted, без bind)
        #   - "0.0.0.0:8000:8000" (quoted, явный 0.0.0.0)
        #   - 8000:8000           (unquoted)
        #   - "${VAR}:8000"       (с переменными)
        # Требуем наличие ":" (port mapping), чтобы не ловить dns записи вроде "- 8.8.8.8"
        FILE_UNSAFE=$(grep -E '^[[:space:]]*-[[:space:]]*("|'"'"')?[0-9$]' "$COMPOSE_FILE" | grep ':' | grep -v '127\.0\.0\.1' || true)
        if [ -n "$FILE_UNSAFE" ]; then
            UNSAFE_PORTS="${UNSAFE_PORTS}${COMPOSE_FILE}:\n${FILE_UNSAFE}\n"
        fi
    fi
done
if [ -n "$UNSAFE_PORTS" ]; then
    echo -e "${RED}❌ ВНИМАНИЕ: Обнаружены порты без привязки к 127.0.0.1!${NC}"
    echo -e "${RED}   Это позволяет обходить Nginx и получать прямой доступ к сервисам.${NC}"
    echo -e "$UNSAFE_PORTS" | sed 's/^/   /'
    echo -e "${RED}   Исправьте: замените порты на '\"127.0.0.1:PORT:PORT\"'${NC}"
    echo -e "${RED}   Сборка прервана для безопасности.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Порты безопасно привязаны к 127.0.0.1${NC}"
echo ""

# Шаг 4: Пересборка образа бота
echo -e "${YELLOW}[4/7] 🔨 Пересобираю образ бота...${NC}"
docker-compose build --no-cache bot
echo -e "${GREEN}✓ Образ bot пересобран${NC}"
echo ""

# Шаг 5: Запуск контейнера бота
echo -e "${YELLOW}[5/9] 🚀 Запускаю контейнер бота...${NC}"
docker-compose up -d bot
echo -e "${GREEN}✓ Контейнер bot запущен${NC}"
echo ""

# Шаг 6: Проверка статуса
echo -e "${YELLOW}[6/9] 📊 Проверяю статус контейнера...${NC}"
docker-compose ps bot
echo ""

# Шаг 7: Ожидание готовности контейнера (увеличено до 20 секунд как в full_update.sh)
echo -e "${YELLOW}[7/9] ⏳ Жду готовности контейнера...${NC}"
echo -e "${YELLOW}  Даю контейнеру 20 секунд на инициализацию (PostgreSQL, Redis, Bot)...${NC}"
sleep 20

# Проверяем что контейнер действительно запущен
set +e
CONTAINER_STATUS=$(docker-compose ps -q bot | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null || echo "unknown")
if [ "$CONTAINER_STATUS" = "running" ]; then
    echo -e "${GREEN}✓ Контейнер bot работает${NC}"
else
    echo -e "${RED}⚠️ Контейнер в статусе: $CONTAINER_STATUS${NC}"
    echo -e "${YELLOW}  Проверьте логи: docker-compose logs bot${NC}"
fi
set -e
echo ""

# Шаг 8: Проверка UFW и DNS конфигурации (добавлено из full_update.sh)
echo -e "${YELLOW}[8/9] 🔍 Проверка UFW и DNS конфигурации...${NC}"
set +e

# Проверяем наличие UFW
if command -v ufw >/dev/null 2>&1; then
    echo -e "${YELLOW}  Проверяю правила UFW для DNS...${NC}"

    # Проверяем правила для порта 53 (DNS)
    DNS_OUT_RULE=$(sudo ufw status | grep "53/udp" | grep "ALLOW OUT" || true)
    DNS_IN_RULE=$(sudo ufw status | grep "53/tcp" | grep "ALLOW IN" || true)

    if [ -z "$DNS_OUT_RULE" ]; then
        echo -e "${YELLOW}  ⚠️ Нет правила UFW для исходящего DNS (53/udp)${NC}"
        echo -e "${YELLOW}  Добавляю правило...${NC}"
        sudo ufw allow out 53/udp comment 'DNS queries' >/dev/null 2>&1 || true
        echo -e "${GREEN}  ✓ Правило для исходящего DNS добавлено${NC}"
    else
        echo -e "${GREEN}  ✓ UFW правило для исходящего DNS есть${NC}"
    fi

    if [ -z "$DNS_IN_RULE" ]; then
        echo -e "${YELLOW}  ⚠️ Нет правила UFW для входящего DNS (53/tcp)${NC}"
        echo -e "${YELLOW}  Добавляю правило...${NC}"
        sudo ufw allow in 53/tcp comment 'DNS responses' >/dev/null 2>&1 || true
        echo -e "${GREEN}  ✓ Правило для входящего DNS добавлено${NC}"
    else
        echo -e "${GREEN}  ✓ UFW правило для входящего DNS есть${NC}"
    fi
else
    echo -e "${YELLOW}  ℹ UFW не установлен или не используется${NC}"
fi

# Проверяем резолв домена
echo -e "${YELLOW}  Проверяю резолв домена expensebot.duckdns.org...${NC}"
if nslookup expensebot.duckdns.org >/dev/null 2>&1 || host expensebot.duckdns.org >/dev/null 2>&1; then
    RESOLVED_IP=$(nslookup expensebot.duckdns.org | grep -A1 "Name:" | tail -1 | awk '{print $2}' || echo "unknown")
    echo -e "${GREEN}  ✓ Домен резолвится: $RESOLVED_IP${NC}"
    USE_DOMAIN=true
else
    echo -e "${YELLOW}  ⚠️ Домен не резолвится! Будет использоваться IP адрес${NC}"
    echo -e "${YELLOW}  Возможные причины: UFW блокирует DNS, проблемы с DuckDNS${NC}"
    USE_DOMAIN=false
fi

set -e
echo -e "${GREEN}✓ Проверка DNS/UFW завершена${NC}"
echo ""

# Шаг 9: Проверка готовности и webhook (добавлено из full_update.sh)
echo -e "${YELLOW}[9/9] 🔗 Проверяю установку Telegram webhook...${NC}"
set +e

# Ждем еще 10 секунд чтобы бот успел установить webhook
echo -e "${YELLOW}  Даю боту 10 секунд на установку webhook...${NC}"
sleep 10

# Проверяем что эндпоинт доступен изнутри
echo -e "${YELLOW}  Проверяю эндпоинт /webhook/ изнутри контейнера...${NC}"
ENDPOINT_CHECK=$(docker exec expense_bot_app curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/webhook/ 2>/dev/null || echo "000")

if [ "$ENDPOINT_CHECK" = "405" ]; then
    echo -e "${GREEN}  ✓ Эндпоинт /webhook/ доступен (405 = ожидает POST)${NC}"
else
    echo -e "${YELLOW}  ⚠️ Эндпоинт /webhook/ вернул код: $ENDPOINT_CHECK${NC}"
fi

# Проверяем статус webhook через Telegram API
echo -e "${YELLOW}  Проверяю статус webhook в Telegram...${NC}"
BOT_TOKEN=$(sed -n 's/^BOT_TOKEN=//p' .env | head -n 1 | tr -d '\r' | tr -d ' ')

if [ -n "$BOT_TOKEN" ]; then
    WEBHOOK_INFO=$(docker exec expense_bot_app python -c "
import os
import requests
token = '$BOT_TOKEN'
try:
    r = requests.get(f'https://api.telegram.org/bot{token}/getWebhookInfo', timeout=5)
    result = r.json().get('result', {})
    url = result.get('url', '')
    pending = result.get('pending_update_count', 0)
    error = result.get('last_error_message', '')
    print(f'URL={url}')
    print(f'PENDING={pending}')
    print(f'ERROR={error}')
except Exception as e:
    print(f'ERROR=Failed to check: {e}')
" 2>/dev/null || echo "ERROR=Failed to execute check")

    WEBHOOK_URL=$(printf '%s\n' "$WEBHOOK_INFO" | sed -n 's/^URL=//p' | head -n 1)
    PENDING=$(printf '%s\n' "$WEBHOOK_INFO" | sed -n 's/^PENDING=//p' | head -n 1)
    ERROR=$(printf '%s\n' "$WEBHOOK_INFO" | sed -n 's/^ERROR=//p' | head -n 1)

    if [ -n "$WEBHOOK_URL" ] && [ "$WEBHOOK_URL" != "None" ]; then
        echo -e "${GREEN}  ✅ Webhook установлен: $WEBHOOK_URL${NC}"
        [ "$PENDING" != "0" ] && echo -e "${YELLOW}  ⚠️ Pending updates: $PENDING${NC}"
    else
        echo -e "${YELLOW}  ⚠️ Webhook не установлен или не настроен${NC}"
        [ -n "$ERROR" ] && [ "$ERROR" != "None" ] && echo -e "${YELLOW}  Последняя ошибка: $ERROR${NC}"
        echo -e "${YELLOW}  💡 Бот может работать, но webhook нужно проверить${NC}"
    fi
else
    echo -e "${RED}  ❌ Не найден BOT_TOKEN в .env${NC}"
fi

# Проверяем логи бота на наличие ошибок webhook
echo -e "${YELLOW}  Проверяю логи бота на ошибки webhook...${NC}"
WEBHOOK_ERRORS=$(docker logs expense_bot_app 2>&1 | grep -i "webhook" | grep -i "error\|failed" | tail -3 || true)
if [ -n "$WEBHOOK_ERRORS" ]; then
    echo -e "${YELLOW}  ⚠️ Обнаружены ошибки в логах:${NC}"
    echo "$WEBHOOK_ERRORS" | sed 's/^/     /'
else
    echo -e "${GREEN}  ✓ Ошибок webhook в логах не обнаружено${NC}"
fi

set -e
echo ""

# Финальная проверка
echo -e "${YELLOW}🔍 Проверяю логи контейнера bot...${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
# Не прерываем выполнение если логи недоступны
set +e
docker-compose logs --tail=20 bot
set -e
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         ✅ ОБНОВЛЕНИЕ БОТА ЗАВЕРШЕНО!                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📌 Обновлено:${NC}"
echo -e "   ✓ Контейнер бота (bot)"
echo -e "   ✓ Webhook Telegram"
echo ""
echo -e "${YELLOW}ℹ️  НЕ обновлялось:${NC}"
echo -e "   • Веб-панель (web)"
echo -e "   • Celery воркеры (celery, celery-beat)"
echo -e "   • Redis"
echo -e "   • Лендинг"
echo ""
echo -e "${GREEN}🤖 Проверьте бота: @showmecoinbot${NC}"
echo ""
echo -e "${YELLOW}💡 Для полного обновления используйте:${NC}"
echo -e "   bash scripts/full_update.sh"
echo ""
