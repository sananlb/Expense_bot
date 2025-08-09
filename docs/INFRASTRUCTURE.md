# Инфраструктура проекта expense_bot

## Production Server
- **IP:** 80.66.87.178
- **Domain:** expensebot.duckdns.org
- **OS:** Ubuntu 22.04.5 LTS
- **Path:** /home/batman/expense_bot
- **Hostname:** vm977127
- **Пользователи:**
  - root (доступ отключен через SSH)
  - batman (sudo права, SSH по ключу)

## Структура проекта на сервере
**Путь:** /home/batman/expense_bot/

### Файлы и директории:
- `.env` (настройки окружения)
- `docker-compose.yml`
- `docker-entrypoint.sh` (существует, права 644, владелец root:root)
- `Dockerfile`
- `bot/` (код бота)
- `expenses/` (Django приложение)
- `expense_bot/` (Django проект)
- `venv/` (виртуальное окружение)
- `logs/` (логи)
- `database/` (данные БД)
- `requirements.txt`

## Infrastructure

### Docker Containers
- **expense_bot_web:** Django admin (port 8000)
- **expense_bot_app:** Telegram bot
- **expense_bot_celery:** Background tasks
- **expense_bot_celery_beat:** Scheduled tasks
- **expense_bot_db:** PostgreSQL 15
- **expense_bot_redis:** Redis cache

### Web Server
- Nginx 1.18.0 with SSL (Let's Encrypt)
- Reverse proxy to Django on localhost:8000
- Static files served directly from /home/batman/expense_bot/staticfiles/

### Database
- PostgreSQL 15 (Alpine)
- Database: expense_bot
- User: batman
- Container: expense_bot_db

### Admin Panel
- URL: https://expensebot.duckdns.org/admin/
- Superuser: admin/batman

### Deployment
Standard update process:
```bash
cd /home/batman/expense_bot && \
docker-compose down && \
git fetch --all && \
git reset --hard origin/master && \
git pull origin master && \
docker-compose build --no-cache && \
docker-compose up -d --force-recreate && \
docker image prune -f
```

## Текущий статус
- Контейнеры успешно перезапущены
- docker-compose версия 1.29.2 (есть проблемы с ContainerConfig, но решены через docker-compose down -v)
- Все контейнеры созданы: expense_bot_db, expense_bot_redis, expense_bot_app, expense_bot_celery, expense_bot_celery_beat, expense_bot_web
- Есть orphan контейнер expense_bot_nginx который нужно удалить

## Решенные проблемы
1. **Ошибка "exec /docker-entrypoint.sh: no such file or directory"** - решена пересборкой образов
2. **Ошибка KeyError: 'ContainerConfig'** - решена через docker-compose down -v и docker system prune
3. **Ошибка "exec /docker-entrypoint.sh: no such file or directory"** - причина: Windows line endings (^M) в файле docker-entrypoint.sh
   Решение: dos2unix docker-entrypoint.sh или sed -i 's/\r$//' docker-entrypoint.sh

## Важные замечания
- При копировании файлов с Windows всегда проверяйте line endings командой: cat -A filename | head
- Если видите ^M$ в конце строк, конвертируйте файл: dos2unix filename

Это критически важно для bash скриптов в Docker контейнерах.

### Критически важные правила работы с кодом:
- **НИКОГДА не сохраняем изменения на сервере**. Версия на сервере всегда должна соответствовать GitHub
- При любых локальных изменениях на сервере используем: `git fetch origin && git reset --hard origin/master`
- Все изменения делаются только локально и пушатся в GitHub, затем pull на сервер

**Это критически важное правило для поддержания консистентности кода.**

## Диагностика проблем

### Команды для проверки статуса:
```bash
# Проверка статуса контейнеров
docker ps

# Проверка логов бота
docker logs expense_bot_app --tail 50

# Проверка подключения к базе данных
docker exec expense_bot_app python -c "from django.db import connection; cursor = connection.cursor(); print('DB connection successful!')"

# Проверка логов других контейнеров
docker-compose logs --tail=50 expense_bot_celery
docker-compose logs --tail=50 expense_bot_web

# Проверка файловой системы
ls -la docker-entrypoint.sh
file docker-entrypoint.sh
```

### Команды для обслуживания:
1. **Удаление orphan контейнера nginx:**
   ```bash
   docker rm -f expense_bot_nginx
   ```

2. **Полный перезапуск с очисткой volumes (при проблемах с ContainerConfig):**
   ```bash
   docker-compose down -v
   docker system prune
   docker-compose build --no-cache
   docker-compose up -d
   ```

3. **Проверить права доступа к entrypoint файлу:**
   ```bash
   chmod +x docker-entrypoint.sh
   ```

4. **Проверить формат файла (Windows vs Linux line endings):**
   ```bash
   dos2unix docker-entrypoint.sh
   ```

## Установленное ПО
- **Docker version:** 27.5.1
- **docker-compose version:** 1.29.2
- **git version:** 2.34.1

## Сетевая конфигурация
- **SSH порт:** 22 (доступ только по ключу)
- **HTTP порт:** 80 (Nginx, redirect to HTTPS)
- **HTTPS порт:** 443 (Nginx with Let's Encrypt SSL)
- **Django admin:** 8000 (внутренний порт контейнера)
- **Domain:** expensebot.duckdns.org
- **Admin URL:** https://expensebot.duckdns.org/admin/

## Мониторинг и логирование
- **Логи Docker:** `docker-compose logs`
- **Логи приложения:** `/home/batman/expense_bot/logs/`
- **Системные логи:** `/var/log/`

## Резервное копирование
- **База данных:** PostgreSQL в Docker volume
- **Код проекта:** Git репозиторий
- **Конфигурация:** `.env` файл (не в репозитории)

## Безопасность
- **Firewall:** UFW (необходимо проверить настройки)
- **SSH ключи:** Ed25519
- **Docker сеть:** Изолированная сеть для контейнеров
- **Secrets:** Хранятся в `.env` файле

## Финальная рабочая конфигурация

### Решенные проблемы:
1. Windows line endings в docker-entrypoint.sh - решено через dos2unix
2. Неправильный адрес Redis (127.0.0.1 вместо redis) - исправлено на redis
3. Отсутствие пароля в Redis URL - добавлен пароль RedisExpense2024

### Правильные настройки .env для сервера:
```
REDIS_URL=redis://:RedisExpense2024@redis:6379/0
CELERY_BROKER_URL=redis://:RedisExpense2024@redis:6379/0
CELERY_RESULT_BACKEND=redis://:RedisExpense2024@redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=RedisExpense2024
```

### Рабочий бот:
- Telegram бот: @showmecoinbot
- ID: 8239680156
- Режим: polling

Сохранена эта конфигурация как эталонная.