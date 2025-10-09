#!/bin/bash

# Полное обновление сервера включая Docker контейнеры и лендинг
# Использование: bash scripts/full_update.sh

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
echo -e "${YELLOW}[1/8] 🛑 Останавливаю Docker контейнеры...${NC}"
docker-compose down
echo -e "${GREEN}✓ Контейнеры остановлены${NC}"
echo ""

# Шаг 2: Очистка Docker
echo -e "${YELLOW}[2/8] 🧹 Очищаю Docker систему...${NC}"
docker system prune -af --volumes=false
echo -e "${GREEN}✓ Docker очищен${NC}"
echo ""

# Шаг 3: Получение изменений из Git
echo -e "${YELLOW}[3/8] 📥 Получаю последние изменения из Git...${NC}"
git fetch --all
git reset --hard origin/master
git pull origin master
echo -e "${GREEN}✓ Код обновлен из репозитория${NC}"
echo ""

# Шаг 4: Обновление лендинга ПЕРЕД сборкой Docker
echo -e "${YELLOW}[4/8] 🌐 Обновляю лендинг страницу...${NC}"
# Делаем скрипт исполняемым если нужно
chmod +x scripts/update_landing.sh
# Запускаем обновление лендинга
bash scripts/update_landing.sh
echo -e "${GREEN}✓ Лендинг обновлен${NC}"
echo ""

# Шаг 5: Пересборка Docker образов
echo -e "${YELLOW}[5/8] 🔨 Пересобираю Docker образы...${NC}"
docker-compose build --no-cache
echo -e "${GREEN}✓ Docker образы пересобраны${NC}"
echo ""

# Шаг 6: Запуск новых контейнеров
echo -e "${YELLOW}[6/8] 🚀 Запускаю новые контейнеры...${NC}"
docker-compose up -d --force-recreate
echo -e "${GREEN}✓ Контейнеры запущены${NC}"
echo ""

# Шаг 7: Проверка статуса
echo -e "${YELLOW}[7/8] 📊 Проверяю статус контейнеров...${NC}"
docker-compose ps
echo ""

# Шаг 8: Ожидание готовности контейнеров
echo -e "${YELLOW}[8/10] ⏳ Жду готовности контейнеров...${NC}"
echo -e "${YELLOW}  Даю контейнерам 10 секунд на инициализацию...${NC}"
sleep 10
echo -e "${GREEN}✓ Контейнеры готовы${NC}"
echo ""

# Шаг 9: Установка webhook
echo -e "${YELLOW}[9/10] 🔗 Устанавливаю Telegram webhook...${NC}"

# Делаем скрипт исполняемым
chmod +x scripts/set_webhook.sh

# Запускаем установку webhook
if bash scripts/set_webhook.sh; then
    echo -e "${GREEN}✓ Webhook установлен${NC}"
else
    echo -e "${YELLOW}⚠️ Проблема с установкой webhook${NC}"
    echo -e "${YELLOW}  Попробуйте вручную: bash ~/fix_webhook_force.sh${NC}"
fi
echo ""

# Шаг 10: Финальная проверка
echo -e "${YELLOW}[10/10] 🔍 Выполняю финальные проверки...${NC}"

# Проверка что контейнеры запущены
RUNNING_CONTAINERS=$(docker-compose ps | grep "Up" | wc -l)
EXPECTED_CONTAINERS=5  # web, app, celery, celery_beat, redis

if [ $RUNNING_CONTAINERS -ge $EXPECTED_CONTAINERS ]; then
    echo -e "${GREEN}✓ Все основные контейнеры запущены ($RUNNING_CONTAINERS)${NC}"
else
    echo -e "${YELLOW}⚠️ Запущено контейнеров: $RUNNING_CONTAINERS из $EXPECTED_CONTAINERS ожидаемых${NC}"
fi

# Проверка доступности сайтов
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
echo -e "   docker-compose logs -f app"
echo -e "   docker-compose logs -f web"
echo ""