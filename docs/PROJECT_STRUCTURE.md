# Структура проекта Expense Bot

Этот документ кратко описывает, как устроен проект, где лежат ключевые файлы и как запускать типовые операции (деплой/восстановление БД).

## Каталоги и файлы

- `expense_bot/`
  - `settings.py` — настройки Django (PostgreSQL в проде, SQLite локально), Celery, Redis, статика.
  - `urls.py`, `wsgi.py` — стандартные точки входа Django.
- `expenses/` — основное приложение (модели расходов/доходов/категорий, подписки и т.д.).
- `admin_panel/` — внутренние административные вьюхи/панель.
- `landing/` — файлы лендинга (статический HTML/CSS/JS).
- `scripts/`
  - `restore_database.sh` — безопасное восстановление БД PostgreSQL из дампа (.dump/.sql/.sql.gz) с бэкапом и миграциями.
  - `health_check.sh`, `initial_server_setup.sh`, `manage_bot.sh` — служебные скрипты.
- `deploy/` — конфигурации для деплоя (nginx и др.).
- `docker-compose.yml` — базовый compose (локальная среда).
- `docker-compose.prod.yml` — продакшн стек: `db` (PostgreSQL 15), `redis` (Redis 7), `web` (Gunicorn), `bot` (Telegram-бот), `celery`, `celery-beat`, `nginx`.
- `Dockerfile` — сборка образа приложения.
- `.env` — переменные окружения (см. ниже).

## Переменные окружения (.env)

- База данных: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` (обычно `db`), `DB_PORT` (`5432`).
- Redis: `REDIS_PASSWORD`.
- Бот/админка: `BOT_TOKEN`, `ADMIN_ID`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.
- Режимы: `DEBUG=false` в проде; опционально `SENTRY_DSN`.

## Быстрый запуск (прод)

```
docker-compose -f docker-compose.prod.yml up -d db redis
docker-compose -f docker-compose.prod.yml up -d web bot celery celery-beat
```

Проверки:

```
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f --tail=50 web
```

## Восстановление базы данных (PostgreSQL)

Скрипт `scripts/restore_database.sh` (делает бэкап → восстановление → миграции → старт сервисов):

```
chmod +x scripts/restore_database.sh
./scripts/restore_database.sh /path/to/dump.sql
```

Ручной минимум:

```
docker exec -i expense_bot_db psql -U expense_user -d postgres -c "DROP DATABASE IF EXISTS expense_bot;"
docker exec -i expense_bot_db psql -U expense_user -d postgres -c "CREATE DATABASE expense_bot OWNER expense_user;"
docker exec -i expense_bot_db psql -U expense_user -d expense_bot < /path/to/dump.sql
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
```

## Доступ

- Админка: `http://<host>/admin/` (например, `http://80.66.87.178/admin/`).

