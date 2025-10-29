#!/bin/bash
# Script to update optimized landing page on server
# Run this on the server: bash update_landing_optimized.sh

set -e  # Exit on error

echo "🚀 Updating optimized landing page..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Pull latest changes
echo -e "${BLUE}Step 1: Pulling latest changes from Git...${NC}"
cd /home/batman/expense_bot
git pull origin master

# Step 2: Copy landing files to web directory
echo -e "${BLUE}Step 2: Copying landing files (including WebP)...${NC}"
sudo cp -rf landing/* /var/www/coins-bot/

# Step 3: Set correct permissions
echo -e "${BLUE}Step 3: Setting permissions...${NC}"
sudo chown -R www-data:www-data /var/www/coins-bot/

# Step 4: Backup current Nginx config
echo -e "${BLUE}Step 4: Backing up Nginx config...${NC}"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
sudo cp /etc/nginx/sites-available/coins-bot /etc/nginx/sites-available/coins-bot.backup_$BACKUP_DATE
echo "Backup saved: coins-bot.backup_$BACKUP_DATE"

# Step 5: Update Nginx configuration
echo -e "${BLUE}Step 5: Updating Nginx configuration...${NC}"
sudo cp /home/batman/expense_bot/deploy/nginx/landing-cache.conf /etc/nginx/sites-available/coins-bot

# Step 6: Test Nginx configuration
echo -e "${BLUE}Step 6: Testing Nginx configuration...${NC}"
sudo nginx -t

# Step 7: Reload Nginx
echo -e "${BLUE}Step 7: Reloading Nginx...${NC}"
sudo systemctl reload nginx

# Step 8: Check Nginx status
echo -e "${BLUE}Step 8: Checking Nginx status...${NC}"
sudo systemctl status nginx --no-pager | head -10

# Done!
echo ""
echo -e "${GREEN}✅ Landing page updated successfully!${NC}"
echo ""
echo "📊 Optimizations applied:"
echo "  - WebP images (88% size reduction)"
echo "  - Gzip compression enabled"
echo "  - Long-term caching for static assets"
echo "  - Security headers configured"
echo ""
echo "🧪 Test the results:"
echo "  1. Open: https://www.coins-bot.ru"
echo "  2. Check PageSpeed: https://pagespeed.web.dev/"
echo "  3. Verify WebP: curl -I https://www.coins-bot.ru/Coins%20logo.webp"
echo ""
echo "📋 View logs:"
echo "  sudo tail -f /var/log/nginx/coins-bot_error.log"
echo ""
echo "🔄 Rollback if needed:"
echo "  sudo cp /etc/nginx/sites-available/coins-bot.backup_$BACKUP_DATE /etc/nginx/sites-available/coins-bot"
echo "  sudo nginx -t && sudo systemctl reload nginx"
echo ""
