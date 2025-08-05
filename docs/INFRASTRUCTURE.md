# Инфраструктура проекта expense_bot

## Сервер
- **IP:** 80.66.87.178
- **OS:** Ubuntu 22.04.5 LTS
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

## Docker контейнеры
- **expense_bot_db** (PostgreSQL 15-alpine) - работает
- **expense_bot_redis** (Redis 7-alpine) - работает  
- **expense_bot_app** (основной бот) - работает
- **expense_bot_celery** - работает
- **expense_bot_celery_beat** - работает
- **expense_bot_web** (Django admin) - работает

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
- **HTTP порт:** 80 (Nginx)
- **HTTPS порт:** 443 (Nginx)
- **Django admin:** 8000 (внутренний порт контейнера)

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