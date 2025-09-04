# Expense Bot Docker Deployment Guide

## Prerequisites

- Docker and Docker Compose installed
- Domain name (optional, for production with SSL)
- SSL certificates (optional, for HTTPS)

## Quick Start

### 1. Clone the repository
```bash
git clone <repository-url>
cd expense_bot
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your configuration
nano .env
```

### 3. Deploy with Docker

#### Development deployment (without nginx):
```bash
# Make scripts executable
chmod +x deploy/*.sh

# Deploy
./deploy/docker-deploy.sh
```

#### Production deployment (with nginx):
```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration

### Required Environment Variables

- `BOT_TOKEN` - Your Telegram bot token from @BotFather
- `SECRET_KEY` - Django secret key (generate a strong one)
- `DB_PASSWORD` - PostgreSQL password
- `REDIS_PASSWORD` - Redis password

### Optional Configuration

- AI Services (OpenAI, Google AI, Gemini)
- Currency API settings
- Voice recognition settings
- Webhook configuration

## Management Commands

Use the management script for common operations:

```bash
# Start services
./deploy/docker-manage.sh start

# Stop services
./deploy/docker-manage.sh stop

# View logs
./deploy/docker-manage.sh logs
./deploy/docker-manage.sh logs bot  # Specific service

# Run migrations
./deploy/docker-manage.sh migrate

# Create superuser
./deploy/docker-manage.sh createsuperuser

# Database backup
./deploy/docker-manage.sh backup

# Open shell
./deploy/docker-manage.sh shell
```

## Services

The deployment includes:

1. **Bot** - Main Telegram bot application
2. **PostgreSQL** - Database server
3. **Redis** - Cache and message broker
4. **Celery** - Async task worker
5. **Celery Beat** - Scheduled tasks
6. **Web** - Django admin panel (optional)
7. **Nginx** - Reverse proxy (production only)

## Volumes

- `postgres_data` - Database files
- `redis_data` - Redis persistence
- `static_volume` - Static files
- `media_volume` - User uploads
- `./logs` - Application logs

## Ports

- Development:
  - 8000 - Django admin panel
  
- Production (with nginx):
  - 80 - HTTP (redirects to HTTPS)
  - 443 - HTTPS

## SSL Configuration

For production with HTTPS:

1. Obtain SSL certificates (e.g., using Let's Encrypt)
2. Update nginx configuration with your domain
3. Mount certificates in docker-compose.prod.yml

## Monitoring

### Check service status:
```bash
docker-compose ps
```

### View logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f bot
```

### Health checks:
- Database: `pg_isready` 
- Redis: `redis-cli ping`
- Web: `http://localhost/health`

## Backup and Restore

### Backup database:
```bash
./deploy/docker-manage.sh backup
```

### Restore database:
```bash
./deploy/docker-manage.sh restore backup_20240101_120000.sql
```

## Troubleshooting

### Bot not starting
- Check logs: `docker-compose logs bot`
- Verify BOT_TOKEN is correct
- Ensure database is running

### Database connection errors
- Check if PostgreSQL is healthy: `docker-compose ps`
- Verify database credentials in .env

### Redis connection errors
- Check Redis password in .env
- Ensure Redis is running

### Permission errors
- Set correct permissions: `chmod -R 755 logs media`
- Check docker user permissions

## Updates

To update the application:

```bash
# Pull latest changes
git pull

# Rebuild and restart
./deploy/docker-manage.sh update
```

## Security Recommendations

1. Use strong passwords for all services
2. Keep SECRET_KEY secret and unique
3. Enable firewall (allow only necessary ports)
4. Use HTTPS in production
5. Regularly update Docker images
6. Monitor logs for suspicious activity
7. Backup database regularly

## Support

For issues and questions:
- Check logs first: `docker-compose logs -f`
- Review environment variables in .env
- Ensure all services are running: `docker-compose ps`