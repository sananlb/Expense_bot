# ExpenseBot - Документация

## Обзор проекта

ExpenseBot - это умный Telegram-бот для учета личных расходов с поддержкой AI-анализа, голосовых сообщений и автоматических отчетов. Бот разработан на aiogram 3.x с использованием Django в качестве бэкенда и Redis для кэширования.

### Основные возможности

- **Интеллектуальный парсинг расходов** из текстовых сообщений
- **AI категоризация** с использованием OpenAI GPT-4o-mini и Google Gemini 2.0 Flash
- **Обработка голосовых сообщений** через OpenAI Whisper API и Yandex SpeechKit
- **Конвертация валют** с курсами ЦБ РФ
- **Управление бюджетами** с уведомлениями о превышении
- **Автоматические отчеты** (ежедневные, еженедельные, месячные)
- **Экспорт данных** в Excel/PDF форматах
- **Реферальная система** и подписки

## Архитектура

### Структура проекта

```
expense_bot/
├── bot/                        # Telegram бот (aiogram)
│   ├── main.py                 # Главный файл бота
│   ├── routers/                # Обработчики команд
│   │   ├── start.py           # Стартовые команды
│   │   ├── expense.py         # Обработка расходов
│   │   ├── categories.py      # Управление категориями
│   │   ├── settings.py        # Настройки пользователя
│   │   ├── reports.py         # Отчеты и статистика
│   │   └── ...
│   ├── services/              # Бизнес-логика
│   │   ├── ai_categorization.py    # AI категоризация
│   │   ├── voice_processing.py     # Обработка голоса
│   │   ├── currency_conversion.py  # Конвертация валют
│   │   ├── notifications.py        # Уведомления
│   │   ├── pdf_report.py          # PDF отчеты
│   │   └── ...
│   ├── utils/                 # Утилиты
│   │   ├── expense_parser.py  # Парсинг расходов
│   │   ├── ai_config.py       # Конфигурация AI
│   │   └── ...
│   └── middlewares/           # Middleware
│       ├── database.py        # Подключение к БД
│       └── localization.py    # Локализация
├── database/                  # Django модели
│   └── models.py             # Модели данных
├── requirements.txt          # Зависимости
└── run_bot.py               # Точка входа
```

### Основные компоненты

1. **Telegram Bot (aiogram 3.x)** - обработка сообщений и команд
2. **Django Backend** - управление данными и API
3. **Redis** - кэширование и хранение состояний FSM
4. **PostgreSQL** - основная база данных
5. **Celery** - фоновые задачи и уведомления

## Функции бота

### 1. Парсинг расходов из текста

Бот автоматически извлекает информацию о расходах из текстовых сообщений:

```python
# Примеры распознаваемых форматов:
"Кофе 300"           # → 300 ₽, категория "Кафе"
"Такси домой 450р"   # → 450 ₽, категория "Транспорт"
"$25 обед"           # → 25 USD, категория "Еда"
"Продукты 1500 руб"  # → 1500 ₽, категория "Продукты"
```

**Файл:** `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/utils/expense_parser.py`

### 2. AI категоризация

Система использует два AI провайдера с автоматическим переключением:

#### Основной: Google Gemini 2.5 Flash
- Последняя стабильная версия модели Gemini Flash
- Оптимизирована для быстрых ответов
- Улучшенное понимание русского языка

#### Резервный: OpenAI GPT-4o-mini
- Высокое качество понимания русского языка
- Контекстуальный анализ
- Резерв при недоступности Gemini

**Файл:** `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/ai_categorization.py`

```python
# Пример AI ответа:
{
    "amount": 300,
    "description": "Кофе",
    "category": "Кафе и рестораны",
    "confidence": 0.9,
    "currency": "RUB"
}
```

### 3. Обработка голосовых сообщений

Поддержка множественных провайдеров распознавания речи:

#### Основной: Yandex SpeechKit (для русского языка)
- Оптимизирован для русской речи
- Высокая точность
- Интеграция с Yandex Cloud

#### Резервный: OpenAI Whisper
- Мультиязычность
- Высокое качество
- Простая интеграция

**Файл:** `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/voice_processing.py`

### 4. Конвертация валют

Интеграция с Центральным Банком РФ для получения актуальных курсов:

**Файл:** `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/currency_conversion.py`

```python
# Поддерживаемые валюты:
CURRENCIES = {
    'USD': 'R01235',  # Доллар США
    'EUR': 'R01239',  # Евро  
    'CNY': 'R01375',  # Китайский юань
    'GBP': 'R01035',  # Британский фунт
    'JPY': 'R01820',  # Японская йена
    # ... и другие
}
```

### 5. Автоматические отчеты и уведомления

**Файл:** `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/notifications.py`

- **Ежедневные отчеты** - сводка трат за день
- **Еженедельные отчеты** - анализ недельных трендов  
- **Месячные отчеты** - подробная статистика месяца
- **Уведомления о бюджете** - предупреждения о превышении

### 6. Управление бюджетами

- Создание бюджетов по периодам (день/неделя/месяц/год)
- Привязка к категориям
- Уведомления при приближении к лимиту (по умолчанию 80%)
- Контроль превышения

## API и интеграции

### OpenAI API
```python
# Конфигурация
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Использование
- Категоризация расходов (резервный провайдер)
- Распознавание речи (Whisper API)
```

### Google AI (Gemini)
```python
# Конфигурация  
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_MODEL = os.getenv('GOOGLE_MODEL', 'gemini-2.0-flash-exp')

# Использование
- Основной провайдер для AI категоризации
- Быстрый анализ текста
```

### Yandex SpeechKit
```python
# Конфигурация
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID') 
YANDEX_OAUTH_TOKEN = os.getenv('YANDEX_OAUTH_TOKEN')

# Использование
- Распознавание русской речи
- Обработка голосовых сообщений
```

### Центральный Банк РФ
```python
# API курсов валют
CBRF_DAILY_URL = "http://www.cbr.ru/scripts/XML_daily.asp"
CBRF_DYNAMIC_URL = "http://www.cbr.ru/scripts/XML_dynamic.asp"

# Использование
- Получение актуальных курсов валют
- Конвертация между валютами
- Кэширование курсов на 24 часа
```

## Настройка окружения

### Обязательные переменные .env

```bash
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
BOT_MODE=polling  # или webhook

# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/expense_bot

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Провайдеры
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

GOOGLE_API_KEY=your_google_ai_api_key
GOOGLE_MODEL=gemini-2.0-flash-exp

# Yandex SpeechKit
YANDEX_API_KEY=your_yandex_api_key
YANDEX_FOLDER_ID=your_yandex_folder_id
YANDEX_OAUTH_TOKEN=your_yandex_oauth_token

# AI настройки
AI_CONFIDENCE_THRESHOLD=0.7
MAX_AI_REQUESTS_PER_DAY=100
MAX_AI_REQUESTS_PER_HOUR=20
AI_CACHE_TTL_HOURS=24
```

### Дополнительные настройки

```bash
# Webhook (для продакшена)
WEBHOOK_URL=https://your-domain.com

# Django
SECRET_KEY=your_django_secret_key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,localhost

# Мониторинг
SENTRY_DSN=your_sentry_dsn

# Локализация
DEFAULT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
```

## Установка и запуск

### 1. Клонирование репозитория
```bash
git clone <repository_url>
cd expense_bot
```

### 2. Создание виртального окружения
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка базы данных
```bash
# Применение миграций
python manage.py migrate

# Создание суперпользователя (опционально)
python manage.py createsuperuser
```

### 5. Запуск Redis (если используется)
```bash
redis-server
```

### 6. Запуск бота
```bash
# Polling режим (для разработки)
python run_bot.py

# Или через Django management команду
python manage.py runbot

# Webhook режим (для продакшена)
BOT_MODE=webhook python run_bot.py
```

### 7. Запуск Celery (для фоновых задач)
```bash
# Worker
celery -A expense_bot worker -l info

# Beat (планировщик)
celery -A expense_bot beat -l info
```

## Команды бота

### Основные команды

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация и приветствие |
| `/expenses` | 📊 Траты за сегодня |
| `/cashback` | 💳 Информация о кешбэке |
| `/categories` | 📁 Управление категориями |
| `/settings` | ⚙️ Настройки пользователя |
| `/info` | ℹ️ Информация о боте |

### Интерактивные функции

- **Добавление расходов**: Отправка текста или голосового сообщения
- **Быстрые категории**: Inline кнопки для частых категорий
- **Отчеты**: Генерация отчетов за разные периоды
- **Бюджеты**: Создание и управление бюджетами
- **Экспорт**: Выгрузка данных в Excel/PDF

## Модели данных

### Profile (Профиль пользователя)
```python
class Profile(models.Model):
    telegram_id = models.BigIntegerField(unique=True, primary_key=True)
    first_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True, blank=True)
    
    # Подписка
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    is_beta_tester = models.BooleanField(default=False)
    
    # Реферальная система
    referrer = models.ForeignKey('self', on_delete=models.SET_NULL, null=True)
    referral_code = models.CharField(max_length=20, unique=True)
    
    # Локализация
    locale = models.CharField(max_length=10, default='ru')
```

### ExpenseCategory (Категории расходов)
```python
class ExpenseCategory(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=2, choices=ICON_CHOICES)
    color = models.CharField(max_length=7, default='#808080')
    
    # Бюджет на категорию
    monthly_budget = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Системные категории
    is_system = models.BooleanField(default=False)
```

### Expense (Расходы)
```python
class Expense(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='RUB')
    description = models.CharField(max_length=255)
    
    # Дата и время
    date = models.DateField(db_index=True)
    time = models.TimeField(null=True, blank=True)
    
    # Дополнительная информация
    location = models.CharField(max_length=255)
    tags = ArrayField(models.CharField(max_length=50))
    
    # AI обработка
    ai_processed = models.BooleanField(default=False)
    ai_confidence = models.FloatField(null=True, blank=True)
    
    # Мягкое удаление
    is_deleted = models.BooleanField(default=False)
```

### Budget (Бюджеты)
```python
class Budget(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='RUB')
    
    # Категории бюджета
    categories = models.ManyToManyField(ExpenseCategory, blank=True)
    
    # Уведомления
    notify_on_exceed = models.BooleanField(default=True)
    approach_threshold = models.IntegerField(default=80)
```

### UserSettings (Настройки пользователя)
```python
class UserSettings(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE)
    
    # Основная валюта
    currency = models.CharField(max_length=3, default='RUB')
    
    # Уведомления
    daily_report_enabled = models.BooleanField(default=True)
    daily_report_time = models.TimeField(default='21:00')
    weekly_report_enabled = models.BooleanField(default=True)
    monthly_report_enabled = models.BooleanField(default=True)
    
    # Локализация
    timezone = models.CharField(max_length=50, default='Europe/Moscow')
    language = models.CharField(max_length=2, default='ru')
```

## Сервисы и утилиты

### AI Categorization Service
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/ai_categorization.py`
- **Функции**: Автоматическая категоризация расходов с использованием AI
- **Провайдеры**: Google Gemini 2.0 Flash, OpenAI GPT-4o-mini
- **Кэширование**: 24 часа
- **Лимиты**: 100 запросов/день, 20 запросов/час

### Voice Processing Service
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/voice_processing.py`
- **Функции**: Распознавание речи из голосовых сообщений
- **Провайдеры**: Yandex SpeechKit, OpenAI Whisper
- **Ограничения**: Максимум 60 секунд на сообщение

### Currency Conversion Service
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/currency_conversion.py`
- **Функции**: Конвертация валют по курсам ЦБ РФ
- **Обновление**: Ежедневно
- **Кэширование**: 24 часа

### Notification Service
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/notifications.py`
- **Функции**: Отправка автоматических уведомлений и отчетов
- **Типы**: Ежедневные, еженедельные, месячные отчеты

### Expense Parser
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/utils/expense_parser.py`
- **Функции**: Извлечение суммы, валюты и описания из текста
- **Поддержка**: Множественные форматы ввода

### PDF Report Generator
- **Файл**: `/mnt/c/Users/_batman_/Desktop/expense_bot/bot/services/pdf_report.py`
- **Функции**: Генерация PDF отчетов с графиками
- **Библиотеки**: ReportLab, Matplotlib

---

*Документация обновлена: 02.08.2025*
*Версия бота: 3.x (aiogram)*