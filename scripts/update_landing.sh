#!/bin/bash

# Скрипт автоматического обновления лендинга на сервере
# Копирует файлы из git репозитория в директорию веб-сервера

LANDING_SOURCE="/home/batman/expense_bot/landing"
LANDING_DEST="/var/www/coins-bot"
BACKUP_DIR="/var/www/backups/coins-bot"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Начинаю обновление лендинга coins-bot.ru${NC}"

# Проверяем существование исходной папки
if [ ! -d "$LANDING_SOURCE" ]; then
    echo -e "${RED}❌ Ошибка: Папка с лендингом не найдена: $LANDING_SOURCE${NC}"
    exit 1
fi

# Создаем папку для бэкапов если её нет
sudo mkdir -p "$BACKUP_DIR"

# Создаем резервную копию
BACKUP_NAME="coins-bot.backup.$(date +%Y%m%d_%H%M%S)"
echo -e "${YELLOW}📦 Создаю резервную копию в $BACKUP_DIR/$BACKUP_NAME${NC}"
sudo cp -r "$LANDING_DEST" "$BACKUP_DIR/$BACKUP_NAME"

# Копируем новые файлы
echo -e "${YELLOW}📋 Копирую файлы из Git в веб-директорию${NC}"
# Используем rsync для более надежного копирования или cp с флагами
if command -v rsync &> /dev/null; then
    sudo rsync -av --delete "$LANDING_SOURCE/" "$LANDING_DEST/"
else
    sudo cp -rf "$LANDING_SOURCE"/* "$LANDING_DEST/"
    # Явно копируем папку demos если она существует
    if [ -d "$LANDING_SOURCE/demos" ]; then
        echo -e "${YELLOW}📹 Копирую видео демонстрации${NC}"
        sudo cp -f "$LANDING_SOURCE/demos/"*.mp4 "$LANDING_DEST/demos/" 2>/dev/null || true
    fi
fi

# Устанавливаем правильные права доступа
echo -e "${YELLOW}🔐 Устанавливаю права доступа${NC}"
sudo chown -R www-data:www-data "$LANDING_DEST"
sudo chmod -R 755 "$LANDING_DEST"

# Перезагружаем nginx для сброса кеша
echo -e "${YELLOW}🔄 Перезагружаю конфигурацию nginx${NC}"
sudo nginx -s reload

# Очищаем старые бэкапы (оставляем только последние 5)
echo -e "${YELLOW}🗑️ Очищаю старые резервные копии (оставляю последние 5)${NC}"
cd "$BACKUP_DIR" && ls -t | tail -n +6 | xargs -r sudo rm -rf

echo -e "${GREEN}✅ Лендинг успешно обновлен!${NC}"
echo -e "${GREEN}🌐 Проверьте: https://www.coins-bot.ru${NC}"