#!/bin/bash
# Скрипт для быстрого переключения webhook при смене серверов
# Использовать после изменения IP в DuckDNS

BOT_TOKEN="8239680156:AAGe68TEXVcJzbcGaNA3YJGSb4lvpna349U"
WEBHOOK_URL="https://expensebot.duckdns.org/webhook/"

echo "========================================="
echo "   ExpenseBot Webhook Переключатель"
echo "========================================="
echo ""
echo "1. Удаляем старый webhook..."
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"
echo ""

echo "2. Ждем 3 секунды..."
sleep 3

echo "3. Устанавливаем новый webhook..."
result=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"${WEBHOOK_URL}\", \"drop_pending_updates\": true}")
echo "$result" | grep -o '"ok":[^,]*'

echo ""
echo "4. Проверяем результат..."
info=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
echo "   URL: $(echo "$info" | grep -oP '"url":"[^"]*"' | cut -d'"' -f4)"
echo "   IP:  $(echo "$info" | grep -oP '"ip_address":"[^"]*"' | cut -d'"' -f4)"

echo ""
echo "========================================="
echo "⚠️  ВАЖНО: Telegram кеширует DNS!"
echo "   Если IP не обновился, подождите 5-15 минут"
echo "   и запустите скрипт снова."
echo "========================================="