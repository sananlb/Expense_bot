# Важные инструкции для Claude

## ⛔⛔⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА УДАЛЕНИЕ ФАЙЛОВ ⛔⛔⛔
### **НИКОГДА НЕ ИСПОЛЬЗУЙ `rm`, `rm -f`, `rm -rf` или любые команды удаления!**
**ВСЕ ФАЙЛЫ ТОЛЬКО ПЕРЕМЕЩАТЬ В АРХИВ!**

**Правильный способ "удаления" файлов:**
```bash
# НЕПРАВИЛЬНО - НИКОГДА ТАК НЕ ДЕЛАТЬ:
rm test_file.py              # ❌ ЗАПРЕЩЕНО!
rm -f *.css                   # ❌ ЗАПРЕЩЕНО!
rm -rf temp_folder/           # ❌ ЗАПРЕЩЕНО!

# ПРАВИЛЬНО - ВСЕГДА ТАК:
mkdir -p archive_$(date +%Y%m%d)           # ✅ Создать архив
mv test_file.py archive_$(date +%Y%m%d)/   # ✅ Переместить в архив
mv *.css archive_$(date +%Y%m%d)/          # ✅ Переместить в архив
mv temp_folder/ archive_$(date +%Y%m%d)/   # ✅ Переместить в архив
```

**Это правило АБСОЛЮТНОЕ и НЕ ИМЕЕТ ИСКЛЮЧЕНИЙ!**

## 🔴 КРИТИЧЕСКИ ВАЖНО: Требования к качеству кода 🔴
**ЭТО КОММЕРЧЕСКИЙ ПРОЕКТ! ТОЛЬКО PRODUCTION-READY КОД!**

### ⚠️ ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА РАЗРАБОТКИ:
1. **НИКАКИХ временных решений или костылей** - только полноценные решения
2. **НИКАКИХ хардкод значений** - используй константы и конфигурацию
3. **ВСЕГДА делай правильные миграции БД** при изменении моделей Django
4. **ВСЕГДА обрабатывай ошибки** корректно с логированием и graceful degradation
5. **ВСЕГДА добавляй типизацию** (type hints) для всех функций и методов
6. **ВСЕГДА следуй принципам SOLID и DRY**
7. **ВСЕГДА пиши масштабируемый код** с расчетом на рост нагрузки
8. **ВСЕГДА учитывай безопасность** - валидация входных данных, защита от инъекций
9. **ВСЕГДА добавляй индексы в БД** для оптимизации запросов
10. **НИКОГДА не используй маркеры в тексте** для хранения метаданных - создавай правильные поля в моделях

### 📋 Требования к архитектуре:
- Четкое разделение слоев (models, services, routers, utils)
- Использование паттернов проектирования где уместно
- Асинхронный код где возможно для производительности
- Кеширование часто используемых данных через Redis
- Оптимизация запросов к БД (select_related, prefetch_related)
- Транзакционность для критически важных операций

### 💻 Требования к коду:
- Понятные имена переменных и функций на английском
- Документирование всех публичных функций (docstrings)
- Константы в отдельных файлах конфигурации
- Использование Enum для статусов и типов
- Обработка всех edge cases
- Логирование важных операций и ошибок

### 🚀 При добавлении новых фич:
1. Сначала спроектируй архитектуру
2. Создай необходимые модели с правильными полями и индексами
3. Напиши миграцию Django
4. Реализуй сервисный слой с бизнес-логикой
5. Добавь обработчики в роутеры
6. Покрой код обработкой ошибок
7. Добавь логирование
8. Протестируй все сценарии использования

### ⛔ ЧТО ЗАПРЕЩЕНО:
- Временные решения типа "потом исправим"
- Хранение метаданных в текстовых полях через маркеры
- Игнорирование ошибок через bare except
- Дублирование кода
- Синхронный код там, где нужна асинхронность
- SQL инъекции и другие уязвимости
- Отсутствие валидации пользовательского ввода

## Терминология
**ВАЖНО:** Определение терминов в контексте этого проекта:
- **Меню** - это ТОЛЬКО кнопка в Telegram слева от поля ввода текста, которая открывает список команд бота (/start, /help, /cashback и т.д.). Это встроенная функция Telegram для команд бота.
- **Сообщения с inline-кнопками** - это обычные сообщения бота с кнопками под текстом. НЕ называем их "меню".
- **Клавиатура** - набор inline-кнопок под сообщением бота.

## Интерфейс бота
**ВАЖНО:** У бота НЕТ команды /menu! Навигация доступна через встроенные inline-кнопки в сообщениях.

### Основное меню вызывается через:
- Команду /start
- Встроенные кнопки Telegram

### Структура меню трат (появляется после нажатия "💸 Траты сегодня"):
1. **📔 Дневник трат** - показ последних 30 трат
2. **📋 Список трат** - показ трат за последние 2 дня (макс 20)
3. **📅 С начала месяца** - сводка с начала текущего месяца
4. **❌ Закрыть** - закрыть меню

## Использование субагентов для точных ответов
**ВАЖНО:** Используй субагенты Task для получения более точной информации о проекте!

### Доступные субагенты:
1. **general-purpose** - Универсальный агент для поиска и анализа
   - Поиск функций, классов, переменных
   - Анализ структуры проекта
   - Исследование зависимостей

### Рекомендуемые сценарии использования субагентов:

#### 🔍 Поиск в коде
```
Task (general-purpose): "Найди все места где используется модель Expense"
Task (general-purpose): "Где обрабатываются голосовые сообщения в боте?"
Task (general-purpose): "Найди все обработчики команд /start"
```

#### 📊 Анализ архитектуры
```
Task (general-purpose): "Проанализируй структуру моделей Django и их связи"
Task (general-purpose): "Какие celery задачи есть в проекте и что они делают?"
Task (general-purpose): "Как организована работа с AI сервисами (OpenAI/Google)?"
```

#### 🔧 Поиск конфигурации
```
Task (general-purpose): "Найди все переменные окружения используемые в проекте"
Task (general-purpose): "Какие настройки есть для работы с PDF отчетами?"
Task (general-purpose): "Где хранятся настройки для Telegram webhook?"
```

#### 🐛 Отладка и исправление
```
Task (general-purpose): "Найди все места где может возникнуть ошибка с категориями"
Task (general-purpose): "Где обрабатываются ошибки при парсинге трат?"
Task (general-purpose): "Найди все логгеры и что они логируют"
```

#### 📁 Работа с файлами проекта
```
Task (general-purpose): "Какая структура директорий у проекта?"
Task (general-purpose): "Найди все миграции Django и их порядок"
Task (general-purpose): "Где хранятся шаблоны для PDF отчетов?"
```

### Когда ОБЯЗАТЕЛЬНО использовать субагентов:
- ❗ При вопросах о структуре проекта
- ❗ При поиске специфичного кода
- ❗ При необходимости анализа множества файлов
- ❗ Для получения полной картины реализации функционала
- ❗ Перед внесением изменений - для понимания контекста
- ❗ При отладке ошибок - для поиска связанного кода

### Стратегия работы:
1. **Сначала исследуй** - используй субагента для понимания кода
2. **Затем планируй** - на основе полученной информации
3. **Потом реализуй** - вноси изменения с полным пониманием контекста

### Частые задачи и нужные субагенты:
- **"Добавь новую функцию"** → Сначала Task: "Найди похожие функции и как они реализованы"
- **"Исправь ошибку"** → Сначала Task: "Найди где возникает эта ошибка и связанный код"
- **"Измени поведение"** → Сначала Task: "Как сейчас работает эта функциональность?"

## Работа с сервером
**ВАЖНО:** Я НЕ могу напрямую подключаться к серверу через SSH или выполнять команды на удаленном сервере.
**ВАЖНО:** Я работаю ЛОКАЛЬНО и не имею доступа к серверу напрямую!

## 🔴 КРИТИЧЕСКИЕ ПРАВИЛА БЕЗОПАСНОСТИ 🔴

### ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА УДАЛЕНИЕ ФАЙЛОВ ⛔
**НИКОГДА НЕ ИСПОЛЬЗУЙ КОМАНДЫ:**
- `rm` или `rm -f` или `rm -rf` - **ЗАПРЕЩЕНО ПОЛНОСТЬЮ**
- `del` или `delete` - **ЗАПРЕЩЕНО**
- Любые другие команды безвозвратного удаления - **ЗАПРЕЩЕНО**

**ВМЕСТО УДАЛЕНИЯ ВСЕГДА:**
1. Создай архивную папку: `mkdir -p archive_YYYYMMDD`
2. Перемести файлы в архив: `mv файл archive_YYYYMMDD/`
3. НИКОГДА не удаляй архивные папки
4. Даже временные и тестовые файлы - ТОЛЬКО В АРХИВ

**ПРАВИЛА РАБОТЫ С ФАЙЛАМИ:**
- ✅ РАЗРЕШЕНО: `mv файл archive/` (перемещение в архив)
- ✅ РАЗРЕШЕНО: `cp файл backup/` (создание копии)
- ❌ ЗАПРЕЩЕНО: `rm файл` (удаление)
- ❌ ЗАПРЕЩЕНО: удалять файлы "для очистки проекта"

### ПЕРЕД ЛЮБОЙ КОМАНДОЙ ОБЯЗАТЕЛЬНО:
1. **ПРОВЕРЬ локальный код** - используй Read для проверки файлов
2. **ПРОВЕРЬ документацию** - читай docs/SERVER_COMMANDS.md и CLAUDE.md
3. **НЕ ПЕРЕЗАПИСЫВАЙ .env** - всегда делай backup: `cp .env .env.backup_$(date +%Y%m%d_%H%M%S)`
4. **НЕ ИСПОЛЬЗУЙ git reset --hard** без backup важных файлов
5. **НЕ СОЗДАВАЙ новые docker-compose.yml** - используй существующий или спроси
6. **НЕ УДАЛЯЙ файлы** - только перемещай в архив

### ТЕКУЩАЯ АРХИТЕКТУРА (ВАЖНО!):
- **APP сервер**: 80.66.87.178 (Telegram bot, Django admin, Celery)
- **DB сервер**: 5.129.251.120 (PostgreSQL, Redis)
- **Связь**: через публичные IP (планируется WireGuard VPN)

### КРИТИЧЕСКИЕ ФАЙЛЫ - НЕ УДАЛЯТЬ:
- `.env` - содержит токены и пароли (ВСЕГДА делай backup перед изменением!)
- `docker-compose.yml` - конфигурация контейнеров
- `expense_bot.db` - локальная SQLite база (для разработки)
- `/home/batman/expense_bot_backup_*.sql` - резервные копии БД

### ПРАВИЛЬНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ КОМАНД:
```bash
# 1. ВСЕГДА сначала backup
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)

# 2. При обновлении с GitHub
git stash  # сохраняем локальные изменения
git pull origin master
git stash pop  # восстанавливаем локальные изменения

# 3. НЕ используй git reset --hard без необходимости!
```

### 📌 КОМАНДЫ ДЛЯ СЕРВЕРА
**ВСЕГДА используй готовые команды из файла:** `docs/SERVER_COMMANDS.md`
- Там есть ВСЕ рабочие команды для сервера
- Команды уже протестированы и работают
- НЕ придумывай новые команды, используй готовые из документации

При необходимости проверки логов или выполнения команд на сервере:
1. Я должен предоставить команду пользователю
2. Пользователь выполнит команду на сервере
3. Пользователь вставит результат обратно

### Принцип работы с сервером:
- Я даю команды для выполнения на сервере
- Пользователь подключается к серверу и выполняет команды
- Пользователь копирует вывод команд и вставляет мне
- Я анализирую результаты и даю следующие команды

## Server Configuration

### Primary Server (APP + Web)
- Server IP: 80.66.87.178
- Bot Domain: expensebot.duckdns.org
- Landing Domain: www.coins-bot.ru
- Server path: /home/batman/expense_bot
- Server OS: Ubuntu 22.04.5 LTS
- SSL: Let's Encrypt certificate (expires 2025-11-07)
- Web server: Nginx 1.18.0 with reverse proxy to Django on port 8000
- User: batman

### Backup Server (ПОЛНОСТЬЮ НАСТРОЕН)
- **Server IP:** 72.56.67.202
- **Server path:** `/home/batman/expense_bot_deploy/expense_bot/`
- **User:** batman (с sudo правами)
- **OS:** Ubuntu 24.04.1 LTS
- **Docker:** Docker CE v28.4.0, Docker Compose v2.39.4
- **SSL:** Let's Encrypt до 27.12.2025
- **Домен:** https://expensebot.duckdns.org (тот же домен!)
- **Webhook URL:** `https://expensebot.duckdns.org/webhook/` (унифицирован с основным сервером)
- **Purpose:** Полнофункциональный резервный сервер с Docker
- **База данных:** Локальная PostgreSQL в Docker (222 траты, 17 пользователей восстановлены)
- **Redis:** Локальный в Docker
- **Статус:** ✅ ГОТОВ К ЭКСТРЕННОЙ АКТИВАЦИИ

#### Docker контейнеры на резервном сервере:
- `expense_bot_app` - Telegram бот (порт 8001)
- `expense_bot_web` - Django админка (порт 8000)
- `expense_bot_db` - PostgreSQL
- `expense_bot_redis` - Redis
- `expense_bot_celery` - Celery воркер
- `expense_bot_celery_beat` - Celery планировщик

#### Процедура экстренной активации (1-2 минуты):
1. **Изменить DNS:** На DuckDNS изменить IP expensebot с 80.66.87.178 на 72.56.67.202
2. **Запустить резервный сервер:**
   ```bash
   ssh batman@72.56.67.202
   cd /home/batman/expense_bot_deploy/expense_bot
   docker compose start
   docker compose ps
   ```
3. **Webhook переустанавливать НЕ нужно** (URL унифицирован!)

#### Подробная документация:
См. файл `docs/RESERVE_SERVER_72.56.67.202.md`

### Database Server
- Server IP: 5.129.251.120
- Services: PostgreSQL 15, Redis
- Note: Отдельный сервер только для БД

## Docker Containers
- expense_bot_web - Django admin panel (port 8000)
- expense_bot_app - Telegram bot
- expense_bot_celery - Background tasks
- expense_bot_celery_beat - Scheduled tasks
- expense_bot_db - PostgreSQL 15
- expense_bot_redis - Redis cache

## Database
- Type: PostgreSQL 15 (Alpine)
- Database name: expense_bot
- User: expense_user (DB_USER в .env)
- Container: expense_bot_db
- Default credentials: DB_USER=expense_user, DB_NAME=expense_bot
- **ВАЖНО:** Пользователь БД - expense_user, НЕ batman!
- Команда для создания дампа: `docker exec expense_bot_db pg_dump -U expense_user expense_bot > backup.sql`

## Static Files
- Container path: /app/staticfiles/
- Host path: /home/batman/expense_bot/staticfiles/
- Nginx alias: /var/www/expense_bot_static/ (symlink)
- Served directly by Nginx at /static/

## Admin Panel
- URL: https://expensebot.duckdns.org/admin/
- Superuser: admin or batman
- CSRF configured for HTTPS
- Static files served by Nginx

## Update Process
Standard update commands:
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

## Important Files on Server
- /etc/nginx/sites-available/expensebot - Nginx config
- /etc/letsencrypt/live/expensebot.duckdns.org/ - SSL certificates
- ~/expense_bot/.env - Environment variables (not in git)
- ~/expense_bot/nginx/expensebot-ssl.conf - SSL config backup

## Automated Services
- Certbot auto-renewal for SSL
- Cron job for nginx restoration after reboot
- Docker containers auto-restart policy: unless-stopped

## Legal Documents URLs
**Landing page domain:** www.coins-bot.ru

### Russian:
- **Политика конфиденциальности**: https://www.coins-bot.ru/privacy.html
- **Публичная оферта**: https://www.coins-bot.ru/offer.html

### English:
- **Privacy Policy**: https://www.coins-bot.ru/privacy_en.html
- **Terms of Service**: https://www.coins-bot.ru/offer_en.html

**Local files location:** `/Users/aleksejnalbantov/Desktop/expense_bot/landing/`
- privacy.html (RU)
- privacy_en.html (EN)
- offer.html (RU)
- offer_en.html (EN)

## Telegram Channel
**Channel name:** Coins
**Channel handle:** @showmecoins
**URL:** https://t.me/showmecoins

**Purpose:** Короткие советы по финансам, обновления бота, новые функции

**Где упоминается:**
- Приветственное сообщение /start (в конце)
- Можно добавить в меню "О боте" или "Помощь"

## Recent Changes
- Added grocery store keywords (КБ, Красное белое, ВВ) to product category
- Made description optional for recurring payments (uses category name if empty)
- Fixed trial subscription reset issue (now only granted once)
- Fixed case preservation in expense descriptions
- Added HTTPS support with Let's Encrypt
- Configured Django admin panel with proper CSRF settings
- Improved dialog system with better intent recognition
- Added "📋 Список трат" button in expenses menu (shows last 2 days, max 20 items)

## Security Notes
- DEBUG=False in production
- SECURE_SSL_REDIRECT=False (handled by nginx)
- CSRF_TRUSTED_ORIGINS includes https://expensebot.duckdns.org
- SESSION_COOKIE_SECURE=True
- CSRF_COOKIE_SECURE=True

## Legacy Server Information (Old)
- IP: 194.87.98.75
- Путь к проекту: /root/expense_bot
- Логи Django: /root/expense_bot/logs/django.log

## Документация проекта

**ВАЖНО:** Вся документация проекта хранится в папке `docs/`
- `docs/CELERY_DOCUMENTATION.md` - полная документация по Celery (конфигурация, задачи, troubleshooting)
- `docs/MONITORING_DOCUMENTATION.md` - система мониторинга, Sentry, health checks, уведомления админу

## Обновление лендинга на сервере

### ⚠️ ВАЖНО: Правильная последовательность обновления лендинга

**Проблема:** После `git pull` страница может показываться старая из-за кеширования

**Правильный порядок действий:**
```bash
# 1. Подключиться к серверу
ssh batman@80.66.87.178

# 2. Обновить код из репозитория
cd /home/batman/expense_bot
git pull

# 3. Скопировать файлы лендинга в веб-директорию
sudo cp -rf landing/* /var/www/coins-bot/

# 4. Установить правильные права
sudo chown -R www-data:www-data /var/www/coins-bot/

# 5. Перезагрузить nginx для сброса кеша
sudo nginx -s reload
```

**Или одной командой:**
```bash
cd /home/batman/expense_bot && git pull && sudo cp -rf landing/* /var/www/coins-bot/ && sudo chown -R www-data:www-data /var/www/coins-bot/ && sudo nginx -s reload
```

### После обновления на сервере:
1. **В браузере обязательно:** Нажать `Ctrl+F5` (Windows/Linux) или `Cmd+Shift+R` (Mac)
2. **На мобильном:** Очистить кеш браузера или открыть в приватном режиме
3. **Проверить обновление:** Открыть консоль разработчика (F12) и проверить Network → отключить кеш

### Если страница все еще старая:
```bash
# Проверить что файлы обновились
grep -c "искомый_текст" /var/www/coins-bot/index.html

# Принудительно перезапустить nginx
sudo systemctl restart nginx

# Проверить дату изменения файла
ls -la /var/www/coins-bot/index.html
```

## Backup Process
**КРИТИЧЕСКИ ВАЖНО:** Правильные команды для резервного копирования

### Создание дампа БД через Docker
```bash
# Правильная команда с пользователем expense_user
docker exec expense_bot_db pg_dump -U expense_user expense_bot > /home/batman/backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Проверка созданного дампа
ls -la /home/batman/backups/

# Создание папки для бэкапов если не существует
mkdir -p /home/batman/backups/
```

### Архивирование проекта
```bash
# Создание архива проекта с исключениями
cd /home/batman && tar -czf backups/expense_bot_project_$(date +%Y%m%d_%H%M%S).tar.gz \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/.git' \
  --exclude='expense_bot/logs' \
  --exclude='expense_bot/staticfiles' \
  --exclude='expense_bot/.env' \
  expense_bot/
```

### Путь для бэкапов
- Основная директория: `/home/batman/backups/`
- Дампы БД: `/home/batman/backups/backup_YYYYMMDD_HHMMSS.sql`
- Архивы проекта: `/home/batman/backups/expense_bot_project_YYYYMMDD_HHMMSS.tar.gz`

## Common Errors
**ВАЖНЫЕ ОШИБКИ И ИХ РЕШЕНИЯ:**

### ❌ Ошибка "role batman is not permitted to log in"
**Проблема:** Попытка использовать пользователя batman для БД
```bash
# НЕПРАВИЛЬНО:
docker exec expense_bot_db pg_dump -U batman expense_bot

# ПРАВИЛЬНО:
docker exec expense_bot_db pg_dump -U expense_user expense_bot
```
**Решение:** ВСЕГДА используй expense_user для операций с БД!

### ❌ Ошибка с CRLF line endings
**Проблема:** Файлы с Windows line endings на Linux сервере
```bash
# Симптомы:
/bin/bash^M: bad interpreter
syntax error near unexpected token

# РЕШЕНИЕ:
# Установить dos2unix если не установлен
sudo apt-get install dos2unix

# Конвертировать файл
dos2unix filename.sh

# Для всех .sh файлов в директории
find . -name "*.sh" -type f -exec dos2unix {} \;
```

### ❌ Ошибка "Permission denied" при выполнении скриптов
```bash
# Дать права на выполнение
chmod +x script.sh

# Проверить права
ls -la script.sh
```

### ❌ Ошибка подключения к БД
```bash
# Проверить что контейнер БД запущен
docker ps | grep expense_bot_db

# Проверить логи контейнера БД
docker logs expense_bot_db

# Проверить переменные окружения
docker exec expense_bot_app env | grep DB_
```

## Команды для отладки PDF отчетов
```bash
# Проверка последних ошибок в логах Django
tail -n 100 /root/expense_bot/logs/django.log | grep -E "(PDF|pdf|report|отчет|error|ERROR|Exception)"

# Проверка системных логов
journalctl -u expense_bot -n 100 --no-pager

# Проверка установки Playwright
cd /root/expense_bot && source venv/bin/activate && playwright --version

# Проверка браузеров Playwright
cd /root/expense_bot && source venv/bin/activate && playwright show-browsers
```