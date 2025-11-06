# Структура проекта Expense Bot

Этот документ кратко описывает, как устроен проект, где лежат ключевые файлы и как запускать типовые операции (деплой/восстановление БД).

## Каталоги и файлы

- `expense_bot/`
  - `settings.py` — настройки Django (PostgreSQL в проде, SQLite локально), Celery, Redis, статика.
  - `urls.py`, `wsgi.py` — стандартные точки входа Django.
- `expenses/` — основное приложение (модели расходов/доходов/категорий, подписки и т.д.).
- `admin_panel/` — внутренние административные вьюхи/панель.
- `landing/` — файлы лендинга (статический HTML/CSS/JS).
  - `index.html` — главная страница (русская версия).
  - `index_en.html` — главная страница (английская версия).
  - `offer.html`, `offer_en.html` — публичная оферта (RU/EN).
  - `privacy.html`, `privacy_en.html` — политика конфиденциальности (RU/EN).
  - `demos/`, `fonts/`, `*.css`, `*.js` — медиа и стили.
- `bot/` — Telegram бот на aiogram 3.x
  - `routers/` — обработчики команд и callback'ов
    - `subscription.py` — управление подписками с Telegram Stars (локализация RU/EN)
    - `start.py`, `expense.py`, `reports.py` и др.
  - `services/` — бизнес-логика (экспорт отчётов, подписки, AI и т.д.)
  - `texts.py` — тексты локализации (RU/EN)
  - `keyboards.py` — inline клавиатуры
- `scripts/`
  - `restore_database.sh` — безопасное восстановление БД PostgreSQL из дампа (.dump/.sql/.sql.gz) с бэкапом и миграциями.
  - `update_landing.sh` — обновление лендинга на www.coins-bot.ru (rsync + nginx reload).
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
- Лендинг: `https://www.coins-bot.ru` (обслуживается nginx из `/var/www/coins-bot/`).

## Обновление лендинга

Для обновления лендинга на сервере используется скрипт `scripts/update_landing.sh`:

```bash
cd /home/batman/expense_bot
git pull origin master
bash scripts/update_landing.sh
```

Скрипт автоматически:
1. Создаёт резервную копию текущего лендинга
2. Копирует файлы из `landing/` в `/var/www/coins-bot/` через rsync
3. Устанавливает права доступа для www-data
4. Перезагружает конфигурацию nginx
5. Очищает старые резервные копии (хранит последние 5)

**Важно:** После обновления лендинга пользователям нужно очистить кеш браузера (`Ctrl+F5`).

## Последние обновления

### Локализация подписок (ноябрь 2024)
- Добавлена полная локализация Telegram Stars invoice на английский язык
- Локализованы: title, description, кнопка оплаты
- Формат отчётов обновлён везде на "CSV, XLS, PDF отчёты"
- Кнопка отслеживания кешбэка теперь доступна всем пользователям (не только подписчикам)

### Файлы с изменениями:
- `bot/routers/subscription.py` - локализация инвойсов
- `bot/texts.py` - английские переводы
- `bot/keyboards.py` - кешбэк для всех
- `landing/*.html` - обновление описаний форматов отчётов

