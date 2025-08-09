#!/bin/bash

# Скрипт для настройки nginx на сервере
# Запускать на сервере после git pull

echo "Настройка nginx для ExpenseBot..."

# Копируем конфигурацию nginx
sudo cp ~/expense_bot/nginx/expensebot.conf /etc/nginx/sites-available/expensebot

# Создаем символическую ссылку
sudo ln -sf /etc/nginx/sites-available/expensebot /etc/nginx/sites-enabled/

# Удаляем дефолтный сайт если есть
sudo rm -f /etc/nginx/sites-enabled/default

# Проверяем конфигурацию
echo "Проверка конфигурации nginx..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "Конфигурация корректна. Перезагружаем nginx..."
    sudo systemctl reload nginx
    echo "✅ Nginx настроен успешно!"
    echo "Админка доступна по адресу: http://expensebot.duckdns.org/admin/"
else
    echo "❌ Ошибка в конфигурации nginx!"
    exit 1
fi