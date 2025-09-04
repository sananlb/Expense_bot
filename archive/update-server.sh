#!/bin/bash

# Скрипт обновления ExpenseBot на сервере
# Использование: ./update-server.sh

set -e

echo "🚀 Updating ExpenseBot..."

cd /home/batman/expense_bot

# Останавливаем контейнеры
docker-compose down

# Получаем обновления
git fetch --all
git reset --hard origin/master
git pull origin master

# Настраиваем nginx если нужно
if [ -f nginx/expensebot.conf ]; then
    echo "Configuring nginx..."
    sudo cp nginx/expensebot.conf /etc/nginx/sites-available/expensebot
    sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
fi

# Пересобираем и запускаем контейнеры
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Очищаем старые образы
docker image prune -f

echo "✅ Update completed!"
echo "Admin panel: http://expensebot.duckdns.org/admin/"