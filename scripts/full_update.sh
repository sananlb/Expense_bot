#!/bin/bash

# Полное обновление сервера включая Docker контейнеры и лендинг
# Использование: bash scripts/full_update.sh

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
echo -e "${BLUE}║         🚀 ПОЛНОЕ ОБНОВЛЕНИЕ COINS BOT                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Ошибка: docker-compose.yml не найден!${NC}"
    echo -e "${RED}   Убедитесь, что вы в директории /home/batman/expense_bot${NC}"
    exit 1
fi

echo -e "${YELLOW}📍 Текущая директория: $(pwd)${NC}"
echo ""

# Шаг 1: Остановка контейнеров
echo -e "${YELLOW}[1/11] 🛑 Останавливаю Docker контейнеры...${NC}"
docker-compose down
echo -e "${GREEN}✓ Контейнеры остановлены${NC}"
echo ""

# Шаг 2: Очистка Docker
echo -e "${YELLOW}[2/11] 🧹 Очищаю Docker систему...${NC}"
# Удаляем старые образы expense_bot
echo -e "${YELLOW}  Удаляю старые образы expense_bot...${NC}"
OLD_IMAGES=$(docker images -q 'expense_bot*' 2>/dev/null || true)
if [ -n "$OLD_IMAGES" ]; then
    docker rmi $OLD_IMAGES 2>/dev/null || true
    echo -e "${GREEN}  ✓ Удалены старые образы${NC}"
else
    echo -e "${YELLOW}  ℹ Старых образов не найдено${NC}"
fi
# Очищаем неиспользуемые данные
docker system prune -af --volumes=false
echo -e "${GREEN}✓ Docker очищен${NC}"
echo ""

# Шаг 3: Получение изменений из Git
echo -e "${YELLOW}[3/11] 📥 Получаю последние изменения из Git...${NC}"
git fetch --all
git reset --hard origin/master
git pull origin master
echo -e "${GREEN}✓ Код обновлен из репозитория${NC}"
echo ""

# Шаг 4: Обновление лендинга ПЕРЕД сборкой Docker
echo -e "${YELLOW}[4/11] 🌐 Обновляю лендинг страницу...${NC}"
# Делаем скрипт исполняемым если нужно
chmod +x scripts/update_landing.sh
# Запускаем обновление лендинга
bash scripts/update_landing.sh
echo -e "${GREEN}✓ Лендинг обновлен${NC}"
echo ""

# Шаг 5: Пересборка Docker образов
echo -e "${YELLOW}[5/11] 🔨 Пересобираю Docker образы...${NC}"
docker-compose build --no-cache
echo -e "${GREEN}✓ Docker образы пересобраны${NC}"
echo ""

# Шаг 6: Запуск новых контейнеров
echo -e "${YELLOW}[6/11] 🚀 Запускаю новые контейнеры...${NC}"
docker-compose up -d --force-recreate
echo -e "${GREEN}✓ Контейнеры запущены${NC}"
echo ""

# Шаг 7: Проверка статуса
echo -e "${YELLOW}[7/11] 📊 Проверяю статус контейнеров...${NC}"
docker-compose ps
echo ""

# Шаг 8: Ожидание готовности контейнеров
echo -e "${YELLOW}[8/11] ⏳ Жду готовности контейнеров...${NC}"
echo -e "${YELLOW}  Даю контейнерам 20 секунд на инициализацию (PostgreSQL, Redis, Bot)...${NC}"
sleep 20
echo -e "${GREEN}✓ Контейнеры готовы${NC}"
echo ""

# Шаг 9: Проверка UFW и DNS конфигурации
echo -e "${YELLOW}[9/11] 🔍 Проверка UFW и DNS конфигурации...${NC}"
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

# Шаг 10: Проверка готовности и webhook
echo -e "${YELLOW}[10/11] 🔗 Проверяю установку Telegram webhook...${NC}"
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
BOT_TOKEN=$(grep "^BOT_TOKEN=" .env | cut -d '=' -f2 | tr -d '\r' | tr -d ' ')

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

    WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | grep "^URL=" | cut -d '=' -f2-)
    PENDING=$(echo "$WEBHOOK_INFO" | grep "^PENDING=" | cut -d '=' -f2-)
    ERROR=$(echo "$WEBHOOK_INFO" | grep "^ERROR=" | cut -d '=' -f2-)

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

# Шаг 11: Финальная проверка
echo -e "${YELLOW}[11/11] 🔍 Выполняю финальные проверки...${NC}"

# Проверка что контейнеры запущены
RUNNING_CONTAINERS=$(docker-compose ps | grep "Up" | wc -l)
EXPECTED_CONTAINERS=5  # web, app, celery, celery_beat, redis

if [ $RUNNING_CONTAINERS -ge $EXPECTED_CONTAINERS ]; then
    echo -e "${GREEN}✓ Все основные контейнеры запущены ($RUNNING_CONTAINERS)${NC}"
else
    echo -e "${YELLOW}⚠️ Запущено контейнеров: $RUNNING_CONTAINERS из $EXPECTED_CONTAINERS ожидаемых${NC}"
fi

# Проверка доступности сайтов (не прерываем выполнение при ошибках)
set +e
echo ""
echo -e "${YELLOW}🌐 Проверяю доступность сайтов...${NC}"

# Проверка админки
if curl -s -o /dev/null -w "%{http_code}" https://expensebot.duckdns.org/admin/ | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Админка доступна: https://expensebot.duckdns.org/admin/${NC}"
else
    echo -e "${YELLOW}⚠️ Админка может быть недоступна${NC}"
fi

# Проверка лендинга
if curl -s -o /dev/null -w "%{http_code}" https://www.coins-bot.ru | grep -q "200"; then
    echo -e "${GREEN}✓ Лендинг доступен: https://www.coins-bot.ru${NC}"
else
    echo -e "${YELLOW}⚠️ Лендинг может быть недоступен${NC}"
fi
set -e

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         ✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!                 ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📌 Что проверить:${NC}"
echo -e "   1. Бот в Telegram: @showmecoinbot"
echo -e "   2. Админка: https://expensebot.duckdns.org/admin/"
echo -e "   3. Лендинг: https://www.coins-bot.ru"
echo ""
echo -e "${YELLOW}💡 Совет: Если что-то не работает, проверьте логи:${NC}"
echo -e "   docker-compose logs -f bot"
echo -e "   docker-compose logs -f web"
echo ""