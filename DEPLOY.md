# 🚀 Развертывание ExpenseBot на сервере

## Первоначальная установка

### 1. Клонируйте репозиторий
```bash
cd ~
git clone https://github.com/yourusername/expense_bot.git
cd expense_bot
```

### 2. Запустите скрипт установки
```bash
chmod +x scripts/*.sh
./scripts/install.sh
```

### 3. Настройте .env файл
```bash
nano .env
```
Обязательно укажите:
- `BOT_TOKEN` - токен вашего бота
- `ADMIN_ID` - ваш Telegram ID
- Другие необходимые настройки

### 4. Настройте алиасы (опционально)
```bash
./scripts/setup_alias.sh
source ~/.bashrc
```

## Обновление из GitHub

### Простой способ (рекомендуется)
После настройки алиасов:
```bash
bot-update
```

### Или используйте скрипт напрямую:
```bash
cd ~/expense_bot
./scripts/update.sh
```

Скрипт автоматически:
- ✅ Сохранит ваш .env файл
- ✅ Получит обновления из GitHub
- ✅ Обновит конфигурацию nginx (если нужно)
- ✅ Пересоберет Docker образы (если нужно)
- ✅ Перезапустит контейнеры
- ✅ Проверит работоспособность

## Полезные команды

### С алиасами:
```bash
bot-update     # Обновить из GitHub
bot-logs       # Все логи
bot-web-logs   # Логи веб-сервера
bot-app-logs   # Логи бота
bot-restart    # Перезапустить
bot-stop       # Остановить
bot-start      # Запустить
bot-status     # Статус
bot-admin      # Создать админа
```

### Без алиасов:
```bash
cd ~/expense_bot
docker-compose logs -f              # Все логи
docker logs expense_bot_web -f      # Логи веб-сервера
docker logs expense_bot_app -f      # Логи бота
docker-compose restart               # Перезапустить
docker-compose ps                    # Статус
```

## Доступ к админке

После установки админка доступна по адресам:
- http://expensebot.duckdns.org/admin/
- http://80.66.87.178/admin/

## Решение проблем

### Админка не доступна
```bash
# Проверьте nginx
sudo nginx -t
sudo systemctl status nginx

# Проверьте контейнеры
docker-compose ps
docker logs expense_bot_web

# Проверьте порты
ss -tulpn | grep -E "80|8000"
```

### Бот не отвечает
```bash
# Проверьте логи бота
docker logs expense_bot_app -f

# Перезапустите бота
docker-compose restart bot
```

### Ошибки при обновлении
```bash
# Восстановите .env из бэкапа
cp .env.backup .env

# Откатите изменения Git
git reset --hard HEAD~1

# Перезапустите контейнеры
docker-compose down
docker-compose up -d
```

## Резервное копирование

### Создать бэкап базы данных:
```bash
docker exec expense_bot_db pg_dump -U expense_user expense_bot > backup_$(date +%Y%m%d).sql
```

### Восстановить из бэкапа:
```bash
docker exec -i expense_bot_db psql -U expense_user expense_bot < backup_20250809.sql
```

## Быстрое восстановление БД из дампа (PostgreSQL)

Если у вас есть дамп `.sql`/`.dump`:

```bash
cd ~/expense_bot
# Пересоздаём базу
docker exec -i expense_bot_db psql -U expense_user -d postgres -c "DROP DATABASE IF EXISTS expense_bot;"
docker exec -i expense_bot_db psql -U expense_user -d postgres -c "CREATE DATABASE expense_bot OWNER expense_user;"

# (Опционально) создаём роль, если её требует дамп
docker exec -i expense_bot_db psql -U expense_user -d postgres -c "CREATE ROLE batman;" || true

# Заливаем дамп
docker exec -i expense_bot_db psql -U expense_user -d expense_bot < /path/to/dump.sql

# Миграции
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput

# Поднимаем сервисы
docker-compose -f docker-compose.prod.yml up -d web bot celery celery-beat
```

Альтернатива: `scripts/restore_database.sh` — автоматизирует шаги (бэкап → восстановление → миграции → старт).
