#!/bin/bash

# Скрипт для создания systemd сервиса, который автоматически настраивает nginx
# Запустить один раз на сервере после первого git clone

echo "Creating systemd service for automatic nginx configuration..."

# Создаем systemd сервис
sudo tee /etc/systemd/system/expense-bot-nginx.service > /dev/null <<EOF
[Unit]
Description=Configure nginx for ExpenseBot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c '\
    if [ -f /home/batman/expense_bot/nginx/expensebot.conf ]; then \
        cp /home/batman/expense_bot/nginx/expensebot.conf /etc/nginx/sites-available/expensebot; \
        ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/; \
        rm -f /etc/nginx/sites-enabled/default; \
        nginx -t && systemctl reload nginx; \
    fi'

[Install]
WantedBy=multi-user.target
EOF

# Создаем path watcher для автоматического запуска при изменении файла
sudo tee /etc/systemd/system/expense-bot-nginx.path > /dev/null <<EOF
[Unit]
Description=Watch for ExpenseBot nginx config changes
After=docker.service

[Path]
PathModified=/home/batman/expense_bot/nginx/expensebot.conf
Unit=expense-bot-nginx.service

[Install]
WantedBy=multi-user.target
EOF

# Активируем сервисы
sudo systemctl daemon-reload
sudo systemctl enable expense-bot-nginx.path
sudo systemctl start expense-bot-nginx.path
sudo systemctl enable expense-bot-nginx.service

# Запускаем сервис первый раз
sudo systemctl start expense-bot-nginx.service

echo "✅ Systemd service created and enabled"
echo "Nginx will be automatically configured when docker-compose restarts"