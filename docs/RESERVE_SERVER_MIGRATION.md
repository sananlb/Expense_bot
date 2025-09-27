# Миграция ExpenseBot на резервный сервер

## Обзор серверов

### Основной сервер
- **IP:** 80.66.87.178
- **Роль:** Продакшн сервер expense_bot
- **Путь:** `/home/batman/expense_bot`
- **Пользователь:** batman

### Резервный сервер
- **IP:** 45.95.2.84
- **Роль:** Резервный сервер (уже есть nutrition_bot)
- **Путь:** `/root/expense_bot` (будет создан)
- **Пользователь:** root

## Пошаговая инструкция миграции

### Шаг 1: Подготовка на основном сервере (80.66.87.178)

```bash
# Подключение к основному серверу
ssh batman@80.66.87.178

# Переход в директорию проекта
cd /home/batman/expense_bot

# Загрузка скриптов миграции из git
git pull origin master

# Сделать скрипт исполняемым
chmod +x scripts/backup_to_reserve.sh

# Запуск резервного копирования
bash scripts/backup_to_reserve.sh
```

Скрипт автоматически:
- Создаст дамп PostgreSQL базы данных
- Архивирует весь проект (без venv и логов)
- Копирует файлы на резервный сервер 45.95.2.84
- Сохраняет timestamp для последующего развертывания

### Шаг 2: Развертывание на резервном сервере (45.95.2.84)

```bash
# Подключение к резервному серверу
ssh root@45.95.2.84

# Создание скрипта развертывания
cat > /root/deploy_expense_bot.sh << 'EOF'
[вставить содержимое scripts/deploy_on_reserve.sh]
EOF

chmod +x /root/deploy_expense_bot.sh

# Запуск развертывания с указанием timestamp
# (timestamp будет показан после выполнения backup_to_reserve.sh)
bash /root/deploy_expense_bot.sh YYYYMMDD_HHMMSS
```

### Шаг 3: Проверка работоспособности

```bash
# На резервном сервере
cd /root/expense_bot

# Проверка статуса контейнеров
docker-compose ps

# Проверка логов бота
docker-compose logs --tail=50 bot

# Проверка подключения к БД
docker exec expense_bot_db psql -U batman expense_bot -c "SELECT COUNT(*) FROM expenses_expense;"
```

### Шаг 4: Переключение трафика (при необходимости)

#### Вариант А: Тестовый режим
```bash
# Временно изменить webhook для тестирования
# В файле .env на резервном сервере установить:
WEBHOOK_URL=http://45.95.2.84/webhook
BOT_TOKEN=<тестовый_токен_если_есть>
```

#### Вариант Б: Полное переключение
1. Остановить бота на основном сервере:
```bash
ssh batman@80.66.87.178
cd /home/batman/expense_bot
docker-compose stop bot
```

2. Обновить webhook в Telegram:
```bash
# На резервном сервере
cd /root/expense_bot
docker exec expense_bot_bot python -c "
import asyncio
from aiogram import Bot
import os

async def set_webhook():
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    await bot.set_webhook('http://45.95.2.84/webhook')
    info = await bot.get_webhook_info()
    print(f'Webhook установлен: {info.url}')
    await bot.close()

asyncio.run(set_webhook())
"
```

## Важные файлы для проверки

### 1. Конфигурация (.env)
```bash
# ОБЯЗАТЕЛЬНО проверить наличие всех переменных:
cat /root/expense_bot/.env | grep -E "BOT_TOKEN|DB_|REDIS_|ADMIN_"
```

Критические переменные:
- `BOT_TOKEN` - токен Telegram бота
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` - подключение к PostgreSQL
- `REDIS_PASSWORD` - пароль Redis
- `ADMIN_TELEGRAM_ID` - ID администратора для уведомлений
- `OPENAI_API_KEY` или `GOOGLE_API_KEY` - для AI категоризации

### 2. Docker volumes
```bash
# Проверка volumes
docker volume ls | grep expense_bot
```

### 3. Статические файлы
```bash
# Проверка статики для Django admin
ls -la /root/expense_bot/staticfiles/
```

## Откат изменений

Если что-то пошло не так на резервном сервере:

```bash
# Остановка контейнеров
cd /root/expense_bot
docker-compose down

# Удаление проекта
cd /root
rm -rf expense_bot

# Очистка Docker
docker system prune -a
```

На основном сервере бот продолжит работать без изменений.

## Автоматизация регулярного бэкапа

Для настройки ежедневного резервного копирования:

```bash
# На основном сервере
crontab -e

# Добавить строку (бэкап каждую ночь в 3:00)
0 3 * * * /home/batman/expense_bot/scripts/backup_to_reserve.sh >> /home/batman/backup.log 2>&1
```

## Мониторинг после миграции

### Проверочный чек-лист:
- [ ] Все контейнеры запущены (`docker-compose ps`)
- [ ] Бот отвечает на команды
- [ ] Django admin доступен (если настроен nginx)
- [ ] Celery обрабатывает задачи
- [ ] База данных содержит актуальные данные
- [ ] Redis работает и доступен
- [ ] Логи не содержат критических ошибок

### Команды мониторинга:
```bash
# Общий статус
docker-compose ps

# Логи всех сервисов
docker-compose logs --tail=20

# Проверка Celery
docker exec expense_bot_celery celery -A expense_bot inspect active

# Проверка Redis
docker exec expense_bot_redis redis-cli ping

# Проверка PostgreSQL
docker exec expense_bot_db pg_isready -U batman
```

## Troubleshooting

### Проблема: Контейнеры не запускаются
```bash
# Проверить логи конкретного контейнера
docker-compose logs bot
docker-compose logs db

# Пересобрать образы
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: База данных пустая
```bash
# Проверить наличие SQL дампа
ls -la /root/expense_bot_backup_*.sql

# Восстановить вручную
docker exec -i expense_bot_db psql -U batman expense_bot < /root/expense_bot_backup_TIMESTAMP.sql
```

### Проблема: Бот не отвечает
```bash
# Проверить webhook
docker exec expense_bot_bot python -c "
import asyncio
from aiogram import Bot
import os

async def check():
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    info = await bot.get_webhook_info()
    print(f'Webhook URL: {info.url}')
    print(f'Pending updates: {info.pending_update_count}')
    await bot.close()

asyncio.run(check())
"
```

## Контакты и поддержка

При возникновении проблем проверить:
1. Документацию в `/docs/`
2. Логи контейнеров
3. Настройки в `.env`
4. Состояние Docker