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
echo -e "${YELLOW}ℹ️  Обновляется только контейнер бота (app)${NC}"
echo -e "${YELLOW}ℹ️  Веб, Celery, Redis и лендинг не затрагиваются${NC}"
echo ""

# Шаг 1: Остановка контейнера бота
echo -e "${YELLOW}[1/7] 🛑 Останавливаю контейнер бота...${NC}"
docker-compose stop app
echo -e "${GREEN}✓ Контейнер app остановлен${NC}"
echo ""

# Шаг 2: Удаление старого образа бота
echo -e "${YELLOW}[2/7] 🧹 Удаляю старый образ бота...${NC}"
OLD_IMAGE=$(docker images -q 'expense_bot-app' 2>/dev/null || true)
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

# Шаг 4: Пересборка образа бота
echo -e "${YELLOW}[4/7] 🔨 Пересобираю образ бота...${NC}"
docker-compose build --no-cache app
echo -e "${GREEN}✓ Образ app пересобран${NC}"
echo ""

# Шаг 5: Запуск контейнера бота
echo -e "${YELLOW}[5/7] 🚀 Запускаю контейнер бота...${NC}"
docker-compose up -d --force-recreate app
echo -e "${GREEN}✓ Контейнер app запущен${NC}"
echo ""

# Шаг 6: Проверка статуса
echo -e "${YELLOW}[6/7] 📊 Проверяю статус контейнера...${NC}"
docker-compose ps app
echo ""

# Ожидание готовности контейнера
echo -e "${YELLOW}  ⏳ Жду готовности контейнера (5 секунд)...${NC}"
sleep 5
echo -e "${GREEN}✓ Контейнер готов${NC}"
echo ""

# Шаг 7: Установка webhook
echo -e "${YELLOW}[7/7] 🔗 Устанавливаю Telegram webhook...${NC}"

# Делаем скрипт исполняемым
chmod +x scripts/set_webhook.sh

# Запускаем установку webhook (не падаем при ошибке)
set +e
if bash scripts/set_webhook.sh; then
    echo -e "${GREEN}✓ Webhook установлен${NC}"
else
    echo -e "${YELLOW}⚠️ Проблема с установкой webhook${NC}"
    echo -e "${YELLOW}  Попробуйте вручную: bash ~/fix_webhook_force.sh${NC}"
fi
set -e
echo ""

# Финальная проверка
echo -e "${YELLOW}🔍 Проверяю логи контейнера app...${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
docker-compose logs app --tail 20
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         ✅ ОБНОВЛЕНИЕ БОТА ЗАВЕРШЕНО!                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📌 Обновлено:${NC}"
echo -e "   ✓ Контейнер бота (app)"
echo -e "   ✓ Webhook Telegram"
echo ""
echo -e "${YELLOW}ℹ️  НЕ обновлялось:${NC}"
echo -e "   • Веб-панель (web)"
echo -e "   • Celery воркеры (celery, celery_beat)"
echo -e "   • Redis"
echo -e "   • Лендинг"
echo ""
echo -e "${GREEN}🤖 Проверьте бота: @showmecoinbot${NC}"
echo ""
echo -e "${YELLOW}💡 Для полного обновления используйте:${NC}"
echo -e "   bash scripts/full_update.sh"
echo ""
