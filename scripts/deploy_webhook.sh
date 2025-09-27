#!/bin/bash

# ExpenseBot Webhook Deployment Script
# Usage: ./deploy_webhook.sh [domain]
# Example: ./deploy_webhook.sh expensebot.duckdns.org

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOMAIN=${1:-""}
PROJECT_DIR="/home/batman/expense_bot"
NGINX_SITES="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"

# Function to print colored messages
print_msg() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    print_error "Please run with sudo: sudo $0 $@"
    exit 1
fi

# Check domain parameter
if [ -z "$DOMAIN" ]; then
    print_error "Domain name required!"
    echo "Usage: $0 DOMAIN_NAME"
    echo "Example: $0 expensebot.duckdns.org"
    exit 1
fi

print_msg "Starting webhook deployment for domain: $DOMAIN"

# Step 1: Backup current .env
if [ -f "$PROJECT_DIR/.env" ]; then
    BACKUP_FILE="$PROJECT_DIR/.env.backup_$(date +%Y%m%d_%H%M%S)"
    cp "$PROJECT_DIR/.env" "$BACKUP_FILE"
    print_msg "Backed up .env to $BACKUP_FILE"
fi

# Step 2: Check required environment variables
print_msg "Checking environment configuration..."
if ! grep -q "BOT_TOKEN=" "$PROJECT_DIR/.env"; then
    print_error "BOT_TOKEN not found in .env file!"
    exit 1
fi

# Step 3: Update .env for webhook mode
print_msg "Updating .env for webhook mode..."
if grep -q "^BOT_MODE=" "$PROJECT_DIR/.env"; then
    sed -i "s/^BOT_MODE=.*/BOT_MODE=webhook/" "$PROJECT_DIR/.env"
else
    echo "BOT_MODE=webhook" >> "$PROJECT_DIR/.env"
fi

if grep -q "^WEBHOOK_URL=" "$PROJECT_DIR/.env"; then
    sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=https://$DOMAIN|" "$PROJECT_DIR/.env"
else
    echo "WEBHOOK_URL=https://$DOMAIN" >> "$PROJECT_DIR/.env"
fi

# Update Redis URLs with password
if grep -q "^REDIS_URL=" "$PROJECT_DIR/.env"; then
    if ! grep -q "redis://:" "$PROJECT_DIR/.env"; then
        print_warning "Updating Redis URL to include password..."
        REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$PROJECT_DIR/.env" | cut -d'=' -f2)
        if [ -n "$REDIS_PASSWORD" ]; then
            sed -i "s|^REDIS_URL=.*|REDIS_URL=redis://:$REDIS_PASSWORD@redis:6379/0|" "$PROJECT_DIR/.env"
            sed -i "s|^CELERY_BROKER_URL=.*|CELERY_BROKER_URL=redis://:$REDIS_PASSWORD@redis:6379/0|" "$PROJECT_DIR/.env"
            sed -i "s|^CELERY_RESULT_BACKEND=.*|CELERY_RESULT_BACKEND=redis://:$REDIS_PASSWORD@redis:6379/0|" "$PROJECT_DIR/.env"
        fi
    fi
fi

# Fix multiline SENTRY_DSN if present
if grep -q "^SENTRY_DSN=" "$PROJECT_DIR/.env"; then
    print_msg "Checking SENTRY_DSN configuration..."
    # Remove any line breaks in SENTRY_DSN
    sed -i ':a;N;$!ba;s/SENTRY_DSN=[^\n]*\n[[:space:]]\+/SENTRY_DSN=/g' "$PROJECT_DIR/.env"
fi

# Step 4: Install Nginx if not installed
if ! command -v nginx &> /dev/null; then
    print_msg "Installing Nginx..."
    apt-get update
    apt-get install -y nginx certbot python3-certbot-nginx
else
    print_msg "Nginx already installed"
fi

# Step 5: Setup Nginx configuration
print_msg "Setting up Nginx configuration..."
NGINX_CONFIG="$NGINX_SITES/expensebot"
cp "$PROJECT_DIR/nginx/webhook-config.conf" "$NGINX_CONFIG"
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" "$NGINX_CONFIG"

# Create symlink if not exists
if [ ! -L "$NGINX_ENABLED/expensebot" ]; then
    ln -s "$NGINX_CONFIG" "$NGINX_ENABLED/expensebot"
    print_msg "Created Nginx symlink"
fi

# Step 6: Test Nginx configuration
print_msg "Testing Nginx configuration..."
nginx -t
if [ $? -ne 0 ]; then
    print_error "Nginx configuration test failed!"
    exit 1
fi

# Step 7: Setup SSL with Let's Encrypt
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    print_msg "Setting up SSL certificate with Let's Encrypt..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@$DOMAIN --redirect
else
    print_msg "SSL certificate already exists"
fi

# Step 8: Restart Nginx
print_msg "Restarting Nginx..."
systemctl restart nginx

# Step 9: Rebuild and restart Docker containers
print_msg "Rebuilding Docker containers..."
cd "$PROJECT_DIR"
docker-compose down
docker-compose build --no-cache bot
docker-compose up -d

# Wait for containers to start
print_msg "Waiting for containers to start..."
sleep 10

# Step 10: Check container status
print_msg "Checking container status..."
docker-compose ps

# Step 11: Check webhook registration
print_msg "Checking webhook registration with Telegram..."
BOT_TOKEN=$(grep "^BOT_TOKEN=" "$PROJECT_DIR/.env" | cut -d'=' -f2)
if [ -n "$BOT_TOKEN" ]; then
    WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo")
    echo "$WEBHOOK_INFO" | python3 -m json.tool

    if echo "$WEBHOOK_INFO" | grep -q "\"url\": \"https://$DOMAIN/webhook/"; then
        print_msg "✅ Webhook successfully registered!"
    else
        print_warning "Webhook might not be registered correctly. Check the output above."
    fi
fi

# Step 12: Show logs
print_msg "Showing bot logs (press Ctrl+C to stop)..."
docker-compose logs -f --tail=50 bot