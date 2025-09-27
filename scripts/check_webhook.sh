#!/bin/bash

# Script to check webhook status and troubleshoot issues
# Usage: ./check_webhook.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    print_error ".env file not found!"
    exit 1
fi

print_section "Environment Check"

# Check BOT_TOKEN
if [ -z "$BOT_TOKEN" ]; then
    print_error "BOT_TOKEN not set in .env!"
    exit 1
else
    print_msg "BOT_TOKEN is set"
fi

# Check BOT_MODE
if [ "$BOT_MODE" = "webhook" ]; then
    print_msg "Bot mode: WEBHOOK ✅"
else
    print_warning "Bot mode: $BOT_MODE (should be 'webhook' for production)"
fi

# Check WEBHOOK_URL
if [ -z "$WEBHOOK_URL" ]; then
    print_error "WEBHOOK_URL not set in .env!"
else
    print_msg "Webhook URL: $WEBHOOK_URL"
fi

print_section "Docker Containers Status"
docker-compose ps

print_section "Bot Container Logs (last 20 lines)"
docker-compose logs --tail=20 bot

print_section "Telegram Webhook Info"
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo")
echo "$WEBHOOK_INFO" | python3 -m json.tool

# Parse webhook info
if echo "$WEBHOOK_INFO" | grep -q '"ok": true'; then
    URL=$(echo "$WEBHOOK_INFO" | grep -o '"url": "[^"]*' | cut -d'"' -f4)
    PENDING_COUNT=$(echo "$WEBHOOK_INFO" | grep -o '"pending_update_count": [0-9]*' | cut -d: -f2 | tr -d ' ')
    LAST_ERROR=$(echo "$WEBHOOK_INFO" | grep -o '"last_error_message": "[^"]*' | cut -d'"' -f4)

    if [ -n "$URL" ]; then
        print_msg "Webhook URL registered: $URL"

        if [ "$PENDING_COUNT" -gt 0 ]; then
            print_warning "Pending updates: $PENDING_COUNT"
        fi

        if [ -n "$LAST_ERROR" ]; then
            print_error "Last error: $LAST_ERROR"
        fi
    else
        print_warning "No webhook URL registered"
    fi
else
    print_error "Failed to get webhook info from Telegram"
fi

print_section "Network Connectivity Tests"

# Test DNS
print_msg "Testing DNS resolution..."
if nslookup api.telegram.org > /dev/null 2>&1; then
    print_msg "DNS resolution: OK ✅"
else
    print_error "DNS resolution failed!"
fi

# Test connection to Telegram API
print_msg "Testing connection to Telegram API..."
if curl -s -o /dev/null -w "%{http_code}" "https://api.telegram.org/bot$BOT_TOKEN/getMe" | grep -q "200"; then
    print_msg "Telegram API connection: OK ✅"
else
    print_error "Cannot connect to Telegram API!"
fi

# Test local webhook endpoint
if [ -n "$WEBHOOK_URL" ]; then
    print_msg "Testing local webhook endpoint..."
    DOMAIN=$(echo "$WEBHOOK_URL" | sed 's|https://||' | sed 's|/.*||')

    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8001/health" 2>/dev/null | grep -q "200\|404"; then
        print_msg "Local webhook server: Running ✅"
    else
        print_error "Local webhook server not responding!"
    fi
fi

print_section "Nginx Status"
if systemctl is-active --quiet nginx; then
    print_msg "Nginx: Active ✅"

    # Check Nginx configuration
    if nginx -t 2>/dev/null; then
        print_msg "Nginx configuration: Valid ✅"
    else
        print_error "Nginx configuration has errors!"
    fi
else
    print_warning "Nginx is not running"
fi

print_section "Redis Connection"
# Test Redis from container
if docker exec expense_bot_redis redis-cli -a "${REDIS_PASSWORD:-redis_password}" ping 2>/dev/null | grep -q "PONG"; then
    print_msg "Redis: Connected ✅"
else
    print_warning "Redis connection issue (might be auth problem)"
fi

print_section "Summary"
echo -e "${BLUE}----------------------------------------${NC}"

# Final status
if [ "$BOT_MODE" = "webhook" ] && [ -n "$URL" ] && [ -z "$LAST_ERROR" ]; then
    echo -e "${GREEN}✅ Webhook is configured and working!${NC}"
else
    echo -e "${YELLOW}⚠️  Some issues detected. Review the output above.${NC}"

    if [ "$BOT_MODE" != "webhook" ]; then
        echo "   - Set BOT_MODE=webhook in .env"
    fi

    if [ -z "$URL" ]; then
        echo "   - Webhook URL not registered with Telegram"
    fi

    if [ -n "$LAST_ERROR" ]; then
        echo "   - Fix the webhook error: $LAST_ERROR"
    fi
fi

echo -e "${BLUE}----------------------------------------${NC}"