# Важные инструкции для Claude

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
- Server IP: 80.66.87.178
- Domain: expensebot.duckdns.org
- Server path: /home/batman/expense_bot
- Server OS: Ubuntu 22.04.5 LTS
- SSL: Let's Encrypt certificate (expires 2025-11-07)
- Web server: Nginx 1.18.0 with reverse proxy to Django on port 8000

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
- User: batman
- Container: expense_bot_db

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