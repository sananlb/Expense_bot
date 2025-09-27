#!/bin/bash

# Server Synchronization Script for ExpenseBot
# Синхронизация основного и резервного серверов
# Usage: ./sync_servers.sh [backup|restore|sync]

set -e

# Configuration
PRIMARY_SERVER="80.66.87.178"
BACKUP_SERVER="45.95.2.84"  # Замените на IP резервного сервера
PRIMARY_USER="batman"
BACKUP_USER="batman"
PROJECT_DIR="/home/batman/expense_bot"
BACKUP_DIR="/home/batman/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
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

# Determine which server we're on
CURRENT_IP=$(hostname -I | awk '{print $1}')
if [[ "$CURRENT_IP" == *"$PRIMARY_SERVER"* ]]; then
    SERVER_ROLE="PRIMARY"
    REMOTE_SERVER="$BACKUP_SERVER"
    REMOTE_USER="$BACKUP_USER"
elif [[ "$CURRENT_IP" == *"$BACKUP_SERVER"* ]]; then
    SERVER_ROLE="BACKUP"
    REMOTE_SERVER="$PRIMARY_SERVER"
    REMOTE_USER="$PRIMARY_USER"
else
    SERVER_ROLE="UNKNOWN"
fi

# Main functions

backup_database() {
    print_section "Creating Database Backup"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

    # Create backup directory if not exists
    mkdir -p "$BACKUP_DIR"

    # Create database dump
    print_msg "Creating database dump..."
    docker exec expense_bot_db pg_dump -U expense_user expense_bot > "$BACKUP_FILE"

    # Compress backup
    print_msg "Compressing backup..."
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"

    # Show backup info
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    print_msg "Backup created: $BACKUP_FILE (Size: $BACKUP_SIZE)"

    echo "$BACKUP_FILE"
}

backup_configs() {
    print_section "Backing Up Configuration Files"

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    CONFIG_BACKUP="$BACKUP_DIR/configs_$TIMESTAMP.tar.gz"

    # Create backup directory if not exists
    mkdir -p "$BACKUP_DIR"

    # Archive important config files
    print_msg "Archiving configuration files..."
    tar -czf "$CONFIG_BACKUP" \
        -C "$PROJECT_DIR" \
        .env \
        docker-compose.yml \
        nginx/ \
        2>/dev/null || true

    print_msg "Config backup created: $CONFIG_BACKUP"
    echo "$CONFIG_BACKUP"
}

sync_to_backup_server() {
    print_section "Syncing to Backup Server"

    if [ "$SERVER_ROLE" != "PRIMARY" ]; then
        print_error "This command should be run from the PRIMARY server!"
        exit 1
    fi

    # Create fresh backups
    print_msg "Creating fresh backups..."
    DB_BACKUP=$(backup_database)
    CONFIG_BACKUP=$(backup_configs)

    # Sync code (excluding .env and local files)
    print_section "Syncing Code to Backup Server"
    print_msg "Syncing project files to $REMOTE_USER@$REMOTE_SERVER..."

    rsync -avz --delete \
        --exclude='.env' \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='logs/' \
        --exclude='media/' \
        --exclude='staticfiles/' \
        --exclude='expense_bot.db' \
        --exclude='backups/' \
        "$PROJECT_DIR/" \
        "$REMOTE_USER@$REMOTE_SERVER:$PROJECT_DIR/"

    # Copy database backup
    print_msg "Copying database backup to backup server..."
    scp "$DB_BACKUP" "$REMOTE_USER@$REMOTE_SERVER:$BACKUP_DIR/"

    # Copy config backup
    print_msg "Copying config backup to backup server..."
    scp "$CONFIG_BACKUP" "$REMOTE_USER@$REMOTE_SERVER:$BACKUP_DIR/"

    # Execute restore on backup server
    print_msg "Executing restore on backup server..."
    ssh "$REMOTE_USER@$REMOTE_SERVER" << 'ENDSSH'
        cd /home/batman/expense_bot

        # Find latest backup
        LATEST_DB=$(ls -t /home/batman/backups/db_backup_*.gz | head -1)

        if [ -n "$LATEST_DB" ]; then
            echo "Restoring database from $LATEST_DB..."

            # Stop containers
            docker-compose stop bot celery celery-beat

            # Restore database
            gunzip -c "$LATEST_DB" | docker exec -i expense_bot_db psql -U expense_user expense_bot

            # Start containers
            docker-compose start bot celery celery-beat

            echo "Database restored successfully"
        fi
ENDSSH

    print_msg "✅ Synchronization completed!"
}

restore_from_backup() {
    print_section "Restoring from Backup"

    # Find latest database backup
    LATEST_DB=$(ls -t "$BACKUP_DIR"/db_backup_*.gz 2>/dev/null | head -1)

    if [ -z "$LATEST_DB" ]; then
        print_error "No database backup found in $BACKUP_DIR"
        exit 1
    fi

    print_msg "Found backup: $LATEST_DB"
    read -p "Restore from this backup? (y/n): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop services
        print_msg "Stopping services..."
        docker-compose stop bot celery celery-beat

        # Restore database
        print_msg "Restoring database..."
        gunzip -c "$LATEST_DB" | docker exec -i expense_bot_db psql -U expense_user expense_bot

        # Start services
        print_msg "Starting services..."
        docker-compose start bot celery celery-beat

        print_msg "✅ Restore completed!"
    else
        print_msg "Restore cancelled"
    fi
}

check_sync_status() {
    print_section "Synchronization Status Check"

    print_msg "Current server role: $SERVER_ROLE"
    print_msg "Current server IP: $CURRENT_IP"

    if [ "$SERVER_ROLE" != "UNKNOWN" ]; then
        print_msg "Remote server: $REMOTE_SERVER"

        # Check connection to remote server
        print_msg "Testing connection to remote server..."
        if ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_SERVER" "echo 'Connected'" &>/dev/null; then
            print_msg "✅ Connection to remote server: OK"

            # Compare Docker images versions
            print_section "Docker Images Comparison"
            print_msg "Local images:"
            docker images | grep expense_bot

            print_msg "\nRemote images:"
            ssh "$REMOTE_USER@$REMOTE_SERVER" "docker images | grep expense_bot"

            # Compare .env files (without showing sensitive data)
            print_section "Configuration Comparison"
            print_msg "Local .env variables:"
            grep -E "^[A-Z]" .env | cut -d= -f1 | sort

            print_msg "\nRemote .env variables:"
            ssh "$REMOTE_USER@$REMOTE_SERVER" "cd $PROJECT_DIR && grep -E '^[A-Z]' .env | cut -d= -f1 | sort"

        else
            print_error "❌ Cannot connect to remote server"
        fi
    fi

    # Show backup status
    print_section "Backup Status"
    if [ -d "$BACKUP_DIR" ]; then
        print_msg "Latest backups:"
        ls -lht "$BACKUP_DIR" | head -5
    else
        print_warning "No backup directory found"
    fi
}

setup_auto_sync() {
    print_section "Setting Up Automatic Synchronization"

    if [ "$SERVER_ROLE" != "PRIMARY" ]; then
        print_error "Auto-sync should be configured on the PRIMARY server only!"
        exit 1
    fi

    # Create sync script
    CRON_SCRIPT="/home/$USER/sync_expense_bot.sh"
    cat > "$CRON_SCRIPT" << 'EOF'
#!/bin/bash
cd /home/batman/expense_bot
./scripts/sync_servers.sh sync >> /home/batman/backups/sync.log 2>&1
EOF
    chmod +x "$CRON_SCRIPT"

    # Add to crontab
    print_msg "Adding cron job for automatic sync..."
    (crontab -l 2>/dev/null | grep -v "sync_expense_bot.sh"; echo "0 */6 * * * $CRON_SCRIPT") | crontab -

    print_msg "✅ Auto-sync configured (every 6 hours)"
    print_msg "Check cron jobs with: crontab -l"
}

# Main menu
case "${1:-}" in
    backup)
        backup_database
        backup_configs
        ;;
    restore)
        restore_from_backup
        ;;
    sync)
        sync_to_backup_server
        ;;
    status)
        check_sync_status
        ;;
    auto)
        setup_auto_sync
        ;;
    *)
        echo "ExpenseBot Server Synchronization Tool"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  backup   - Create local backups (database + configs)"
        echo "  restore  - Restore from latest local backup"
        echo "  sync     - Sync primary server to backup server"
        echo "  status   - Check synchronization status"
        echo "  auto     - Setup automatic synchronization (cron)"
        echo ""
        echo "Current server: $SERVER_ROLE ($CURRENT_IP)"
        echo ""
        echo "Examples:"
        echo "  $0 backup   # Create backups"
        echo "  $0 sync     # Sync to backup server (from primary)"
        echo "  $0 status   # Check sync status"
        exit 0
        ;;
esac