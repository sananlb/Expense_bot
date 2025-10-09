#!/bin/bash
# Надежная установка webhook с retry механизмом и проверкой DNS
# Использование: bash scripts/set_webhook.sh

set -e

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         🔗 УСТАНОВКА TELEGRAM WEBHOOK                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Получаем BOT_TOKEN из .env
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    exit 1
fi

BOT_TOKEN=$(grep '^BOT_TOKEN=' .env | cut -d '=' -f2 | tr -d ' "' | tr -d "'" )
WEBHOOK_URL=$(grep '^WEBHOOK_URL=' .env | cut -d '=' -f2 | tr -d ' "' | tr -d "'" )

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}❌ BOT_TOKEN не найден в .env${NC}"
    exit 1
fi

if [ -z "$WEBHOOK_URL" ]; then
    echo -e "${RED}❌ WEBHOOK_URL не найден в .env${NC}"
    exit 1
fi

# Извлекаем домен из URL
DOMAIN=$(echo "$WEBHOOK_URL" | sed 's|https://||' | sed 's|http://||')

echo -e "${YELLOW}📌 Конфигурация:${NC}"
echo -e "   Домен: ${BLUE}$DOMAIN${NC}"
echo -e "   Webhook URL: ${BLUE}$WEBHOOK_URL/webhook/${NC}"
echo ""

# Функция проверки DNS
check_dns() {
    echo -e "${YELLOW}🔍 Проверяю DNS резолюцию...${NC}"

    # Пробуем 5 раз с интервалом 2 секунды
    for i in {1..5}; do
        if nslookup "$DOMAIN" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ DNS резолвится успешно${NC}"
            return 0
        fi

        if [ $i -lt 5 ]; then
            echo -e "${YELLOW}  Попытка $i/5: DNS не резолвится, жду 2 сек...${NC}"
            sleep 2
        fi
    done

    echo -e "${YELLOW}⚠️ DNS не резолвится после 5 попыток${NC}"
    echo -e "${YELLOW}  Пробую использовать IP вместо домена...${NC}"
    return 1
}

# Функция удаления webhook
delete_webhook() {
    echo -e "${YELLOW}🗑️  Удаляю старый webhook...${NC}"

    RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook")

    if echo "$RESPONSE" | grep -q '"ok":true'; then
        echo -e "${GREEN}✓ Webhook удален${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️ Не удалось удалить webhook: $RESPONSE${NC}"
        return 1
    fi
}

# Функция установки webhook
set_webhook() {
    local url="$1"
    echo -e "${YELLOW}🔗 Устанавливаю webhook: ${BLUE}$url${NC}"

    # Пробуем 3 раза с интервалом 3 секунды
    for i in {1..3}; do
        RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${url}/webhook/&allowed_updates=[\"message\",\"callback_query\",\"pre_checkout_query\"]")

        if echo "$RESPONSE" | grep -q '"ok":true'; then
            echo -e "${GREEN}✓ Webhook установлен успешно!${NC}"
            return 0
        fi

        if [ $i -lt 3 ]; then
            echo -e "${YELLOW}  Попытка $i/3: ошибка, жду 3 сек...${NC}"
            echo -e "${YELLOW}  Ответ: $RESPONSE${NC}"
            sleep 3
        fi
    done

    echo -e "${RED}❌ Не удалось установить webhook после 3 попыток${NC}"
    return 1
}

# Функция проверки webhook
check_webhook() {
    echo -e "${YELLOW}🔍 Проверяю статус webhook...${NC}"

    RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")

    # Извлекаем URL
    CURRENT_URL=$(echo "$RESPONSE" | grep -o '"url":"[^"]*"' | cut -d '"' -f4)
    PENDING_COUNT=$(echo "$RESPONSE" | grep -o '"pending_update_count":[0-9]*' | cut -d ':' -f2)

    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         📊 СТАТУС WEBHOOK                                ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo -e "${GREEN}✓ Текущий URL:${NC} ${BLUE}$CURRENT_URL${NC}"
    echo -e "${GREEN}✓ Pending updates:${NC} ${BLUE}$PENDING_COUNT${NC}"

    if [ -n "$CURRENT_URL" ]; then
        echo -e "${GREEN}✓ Webhook установлен!${NC}"
        return 0
    else
        echo -e "${RED}❌ Webhook НЕ установлен!${NC}"
        return 1
    fi
}

# Основной процесс
main() {
    # Шаг 1: Удаляем старый webhook
    delete_webhook
    sleep 2

    # Шаг 2: Проверяем DNS
    if check_dns; then
        # DNS работает - используем домен
        set_webhook "$WEBHOOK_URL"
    else
        # DNS не работает - пробуем использовать IP
        echo -e "${YELLOW}⚠️ Пытаюсь установить webhook по IP адресу...${NC}"

        # Получаем IP сервера
        SERVER_IP=$(hostname -I | awk '{print $1}')

        if [ -z "$SERVER_IP" ]; then
            echo -e "${RED}❌ Не удалось определить IP сервера${NC}"
            exit 1
        fi

        echo -e "${YELLOW}  IP сервера: $SERVER_IP${NC}"

        # Пробуем установить webhook по IP
        if ! set_webhook "https://$SERVER_IP"; then
            echo -e "${RED}❌ КРИТИЧЕСКАЯ ОШИБКА: не удалось установить webhook${NC}"
            exit 1
        fi
    fi

    # Шаг 3: Проверяем результат
    echo ""
    check_webhook

    # Шаг 4: Финальное сообщение
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         ✅ WEBHOOK УСТАНОВЛЕН УСПЕШНО!                   ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}💡 Что дальше:${NC}"
    echo -e "   1. Проверьте бота в Telegram: @showmecoinbot"
    echo -e "   2. Мониторинг логов: ${BLUE}docker-compose logs -f app${NC}"
    echo ""
}

# Запуск
main
