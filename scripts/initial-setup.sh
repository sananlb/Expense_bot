#!/bin/bash

# Первоначальная настройка сервера (запустить один раз)
# После этого можно использовать стандартные команды обновления

echo "🔧 Initial server setup for ExpenseBot..."

# Проверяем, что мы на сервере
if [ ! -d /home/batman/expense_bot ]; then
    echo "❌ This script should be run on the server in /home/batman/expense_bot"
    exit 1
fi

cd /home/batman/expense_bot

# 1. Создаем .env из примера если нет
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env from example - please edit it!"
    echo "   nano .env"
    exit 1
fi

# 2. Настраиваем nginx
if [ -f nginx/expensebot.conf ]; then
    echo "Configuring nginx..."
    sudo cp nginx/expensebot.conf /etc/nginx/sites-available/expensebot
    sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx
    echo "✅ Nginx configured"
fi

# 3. Создаем cron задачу для проверки nginx после перезагрузки
(crontab -l 2>/dev/null; echo "@reboot sleep 60 && [ -f /home/batman/expense_bot/nginx/expensebot.conf ] && sudo cp /home/batman/expense_bot/nginx/expensebot.conf /etc/nginx/sites-available/expensebot && sudo systemctl reload nginx") | crontab -

echo "✅ Initial setup completed!"
echo ""
echo "Now you can use standard update commands:"
echo "cd /home/batman/expense_bot && \\"
echo "docker-compose down && \\"
echo "git fetch --all && \\"
echo "git reset --hard origin/master && \\"
echo "git pull origin master && \\"
echo "docker-compose build --no-cache && \\"
echo "docker-compose up -d --force-recreate && \\"
echo "docker image prune -f"
echo ""
echo "Admin panel will be available at:"
echo "http://expensebot.duckdns.org/admin/"