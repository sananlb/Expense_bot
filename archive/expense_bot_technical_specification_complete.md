# Техническое задание для Telegram-бота учета расходов ExpenseBot

## 1. Общие сведения

### 1.1 Наименование проекта
ExpenseBot - Telegram-бот для учета личных финансовых расходов с системой кешбэков

### 1.2 Назначение системы
Система предназначена для учета и анализа личных расходов пользователей через интерфейс Telegram-бота с возможностью отслеживания потенциальных кешбэков от банковских карт.

### 1.3 Цели проекта
- Автоматизация учета личных расходов
- Категоризация и анализ трат
- Отслеживание потенциальных кешбэков
- Предоставление аналитики и отчетов
- Удобное управление бюджетом

### 1.4 Целевая аудитория
Физические лица, желающие контролировать свои расходы и максимизировать получение кешбэков от банковских карт.

## 2. Функциональные требования

### 2.1 Регистрация и авторизация
- Регистрация пользователя через Telegram
- Создание профиля пользователя
- Настройка часового пояса и валюты

### 2.2 Управление категориями расходов
- Создание, редактирование и удаление любых категорий (включая базовые)
- Автоматическое создание базовых категорий при регистрации
- Выбор иконки для пользовательских категорий

### 2.3 Учет расходов
- Добавление расходов с указанием суммы и описания
- Автоматическое определение категории через AI (если пользователь не указал)
- Автоматическая фиксация даты и времени траты
- Возможность изменить дату при необходимости
- Прикрепление фотографий чеков

### 2.4 Управление бюджетом
- Установка лимитов по категориям
- Уведомления о превышении бюджета
- Планирование расходов на период

### 2.5 Аналитика и отчеты

#### Краткие сводки в чате:
- Общая сумма трат за период
- Траты по категориям с процентами
- Потенциальные кешбэки по категориям
- Кнопка "Сформировать PDF отчет"

#### PDF отчеты:
- Красивый дизайн с логотипом
- Столбчатые диаграммы по дням
- Круговая диаграмма по категориям
- Детальный список всех трат с датой и временем

### 2.6 Многоязычность
- Поддержка русского и английского языков
- Автоматическое определение языка по языку Telegram
- Возможность смены языка в настройках
- Локализация всех сообщений и интерфейса

### 2.7 Настройки уведомлений
- Еженедельные сводки (опционально)
- Месячные отчеты (автоматически в конце месяца)

### 2.8 Обработка естественного языка
- Распознавание трат в текстовых и голосовых сообщениях
- Понимание запросов на отчеты ("покажи траты за июль")
- Извлечение суммы, категории и описания из текста
- Пример: "Дизель 4095 АЗС" → АЗС, 4095₽, Дизель

### 2.9 Система кешбэков
- Добавление информации о кешбэках банковских карт
- Указание процента кешбэка по категориям
- Установка лимитов кешбэков
- Расчет потенциального кешбэка в отчетах
- Автоматическое отображение кешбэков в сводках
- Месячные заметки о доступных кешбэках

## 3. Нефункциональные требования

### 3.1 Производительность
- Время отклика бота не более 2 секунд
- Поддержка до 10000 одновременных пользователей
- Обработка до 1000 запросов в секунду

### 3.2 Надежность
- Доступность системы 99.5%
- Автоматическое резервное копирование данных
- Восстановление после сбоев в течение 15 минут

### 3.3 Безопасность
- Шифрование персональных данных
- Защита от SQL-инъекций
- Аутентификация через Telegram API
- Регularные обновления безопасности

### 3.4 Масштабируемость
- Горизонтальное масштабирование
- Микросервисная архитектура
- Использование очередей для обработки задач

## 4. Технические требования

### 4.1 Технологический стек
- **Backend**: Python 3.11+, Django 4.2+
- **База данных**: PostgreSQL 14+
- **Кеширование**: Redis 7+
- **Очереди**: Celery + Redis
- **Bot Framework**: aiogram 3.x
- **Контейнеризация**: Docker, Docker Compose

### 4.2 Системные требования
- **Операционная система**: Linux Ubuntu 20.04+
- **RAM**: минимум 2GB, рекомендуется 4GB
- **Дисковое пространство**: минимум 20GB SSD
- **CPU**: минимум 2 ядра

### 4.3 Внешние интеграции
- Telegram Bot API
- Возможность интеграции с банковскими API (будущие версии)

## 5. Структура базы данных

### 5.1 Основные таблицы

#### users_profile
```sql
CREATE TABLE users_profile (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(2) DEFAULT 'ru', -- ru/en
    timezone VARCHAR(50) DEFAULT 'UTC',
    currency VARCHAR(3) DEFAULT 'RUB',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### expenses_category
```sql
CREATE TABLE expenses_category (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) NOT NULL,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(10) DEFAULT '💰',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(profile_id, name)
);
```

#### expenses_expense
```sql
CREATE TABLE expenses_expense (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) NOT NULL,
    category_id INTEGER REFERENCES expenses_category(id) NULL, -- Может быть NULL для авто-определения
    amount DECIMAL(12,2) NOT NULL,
    description TEXT,
    expense_date DATE DEFAULT CURRENT_DATE, -- Автоматическая дата
    expense_time TIME DEFAULT CURRENT_TIME, -- Автоматическое время
    receipt_photo VARCHAR(255),
    ai_categorized BOOLEAN DEFAULT FALSE, -- Категория определена AI
    ai_confidence DECIMAL(3,2), -- Уверенность AI в категории
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### expenses_budget
```sql
CREATE TABLE expenses_budget (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) NOT NULL,
    category_id INTEGER REFERENCES expenses_category(id),
    amount DECIMAL(12,2) NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- 'monthly', 'weekly', 'daily'
    start_date DATE NOT NULL,
    end_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### users_settings
```sql
CREATE TABLE users_settings (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) UNIQUE NOT NULL,
    daily_reminder_enabled BOOLEAN DEFAULT TRUE,
    daily_reminder_time TIME DEFAULT '20:00',
    weekly_summary_enabled BOOLEAN DEFAULT TRUE,
    monthly_summary_enabled BOOLEAN DEFAULT TRUE,
    budget_alerts_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Базовые категории

При первом входе пользователя в систему создаются базовые категории (их можно удалить или переименовать):

```sql
-- Базовые категории для каждого нового пользователя
-- Выполняется при регистрации через функцию create_default_categories(profile_id)
INSERT INTO expenses_category (profile_id, name, icon) VALUES
(:profile_id, 'Супермаркеты', '🛒'),
(:profile_id, 'Другие продукты', '🫑'),
(:profile_id, 'Рестораны и кафе', '🍽️'),
(:profile_id, 'АЗС', '⛽'),
(:profile_id, 'Такси', '🚕'),
(:profile_id, 'Общественный транспорт', '🚌'),
(:profile_id, 'Автомобиль', '🚗'),
(:profile_id, 'Жилье', '🏠'),
(:profile_id, 'Аптеки', '💊'),
(:profile_id, 'Медицина', '🏥'),
(:profile_id, 'Спорт', '🏃'),
(:profile_id, 'Спортивные товары', '🏀'),
(:profile_id, 'Одежда и обувь', '👔'),
(:profile_id, 'Цветы', '🌹'),
(:profile_id, 'Развлечения', '🎭'),
(:profile_id, 'Образование', '📚'),
(:profile_id, 'Подарки', '🎁'),
(:profile_id, 'Путешествия', '✈️'),
(:profile_id, 'Связь и интернет', '📱'),
(:profile_id, 'Прочее', '💰');
```

### 5.3 Таблица кешбэков

#### expenses_cashback
```sql
CREATE TABLE expenses_cashback (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER REFERENCES users_profile(id) NOT NULL,
    category_id INTEGER REFERENCES expenses_category(id) NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    cashback_percent DECIMAL(4,2) NOT NULL,
    month INTEGER NOT NULL, -- 1-12
    limit_amount DECIMAL(12,2) NULL, -- может быть пустым
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(profile_id, category_id, bank_name, month)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_cashback_profile_month ON expenses_cashback(profile_id, month);
CREATE INDEX idx_cashback_profile_category ON expenses_cashback(profile_id, category_id);
```

## 6. Архитектура системы

### 6.1 Общая архитектура
Система построена на основе микросервисной архитектуры с разделением на следующие компоненты:

- **Bot Service**: Обработка сообщений от Telegram
- **API Service**: REST API для управления данными
- **Analytics Service**: Генерация отчетов и аналитики
- **Notification Service**: Отправка уведомлений
- **File Service**: Обработка загруженных файлов

### 6.2 Схема взаимодействия
```
Telegram API ↔ Bot Service ↔ API Service ↔ Database
                     ↓
              Analytics Service
                     ↓
            Notification Service
```

### 6.3 Безопасность
- Все API endpoints защищены аутентификацией
- Использование JWT токенов для внутренних сервисов
- Валидация всех входящих данных
- Логирование всех операций

## 7. Пользовательский интерфейс

### 7.1 Основные команды бота
- `/start` - Приветственное сообщение с кнопкой "Справка"
- `/menu` - Показать главное меню

### 7.2 Главное меню

При вызове `/menu` пользователю отображается:

```
💰 Главное меню

Выберите действие:

[📊 Траты сегодня]
[💳 Кешбэк]
[📁 Категории]
[⚙️ Настройки]
[ℹ️ Инфо]
```

### 7.3 Меню "Траты сегодня"

При нажатии на кнопку "📊 Траты сегодня":

```
📊 Сводка за сегодня, 20 января

💰 Всего: 12,350 ₽

📊 По категориям:
⛽ АЗС: 4,095 ₽ (33.2%)
🛒 Супермаркеты: 3,200 ₽ (25.9%)
🍽️ Рестораны: 2,800 ₽ (22.7%)
🚕 Такси: 1,500 ₽ (12.1%)
💊 Аптеки: 755 ₽ (6.1%)

💳 Потенциальный кешбэк: 285 ₽

[📅 Показать с начала месяца]
[🏠 Назад] [❌ Закрыть]
```

При нажатии "Показать с начала месяца" отображается аналогичная сводка за текущий месяц с кнопкой "📄 Сформировать PDF отчет".

### 7.4 Меню "Кешбэк"

При нажатии на кнопку "💳 Кешбэк":

```
💳 Кешбэки на январь

⛽ АЗС - Тинькофф город 5% (2000 руб)
🍽️ Рестораны - Альфа Банк 3%
🛒 Супермаркеты - ВТБ 5% (3000 руб)
🌹 Цветы - Альфа Банк 5% (2000 руб)

[➕ Добавить кешбэк] [➖ Убрать кешбэк]
[🏠 Назад] [❌ Закрыть]
```

#### Добавление кешбэка

При нажатии "➕ Добавить кешбэк":

```
💳 Выберите категорию для кешбэка:

⛽ АЗС - Тинькофф город 5% (2000 руб)
🍽️ Рестораны - Альфа Банк 3%
🛒 Супермаркеты - ВТБ 5% (3000 руб)
🌹 Цветы - Альфа Банк 5% (2000 руб)

[💊 Аптеки] [🏥 Медицина] [🏃 Спорт]
[🏀 Спорттовары] [👔 Одежда] [🚕 Такси]
[🚌 Общ.транспорт] [🚗 Автомобиль] [🏠 Жилье]
[🎭 Развлечения] [📚 Образование] [🎁 Подарки]
[✈️ Путешествия] [📱 Связь] [💰 Прочее]

[🏠 Назад] [❌ Закрыть]
```

После выбора категории:

```
Введите информацию о кешбэке для категории "💊 Аптеки":

Пример: "альфабанк 5% 2000 руб"
```

После ввода пользователь возвращается к выбору категорий, и в сообщении отображается:

```
💳 Выберите категорию для кешбэка:

⛽ АЗС - Тинькофф город 5% (2000 руб)
🍽️ Рестораны - Альфа Банк 3%
🛒 Супермаркеты - ВТБ 5% (3000 руб)
🌹 Цветы - Альфа Банк 5% (2000 руб)
💊 Аптеки - Альфа Банк 5% (2000 руб)

[🏥 Медицина] [🏃 Спорт] [...]
```

### 7.5 Меню "Категории"

При нажатии на кнопку "📁 Категории":

```
📁 Ваши категории:

🛒 Супермаркеты
🫑 Другие продукты
🍽️ Рестораны и кафе
⛽ АЗС
🚕 Такси
🚌 Общественный транспорт
🚗 Автомобиль
🏠 Жилье
💊 Аптеки
🏥 Медицина
🏃 Спорт
🏀 Спортивные товары
👔 Одежда и обувь
🌹 Цветы
🎭 Развлечения
📚 Образование
🎁 Подарки
✈️ Путешествия
📱 Связь и интернет
💰 Прочее

[➕ Добавить категорию] [➖ Удалить категорию]
[🏠 Назад] [❌ Закрыть]
```

#### Добавление категории

При нажатии "➕ Добавить категорию":

```
Придумайте название новой категории:
```

Пользователь вводит название, оно сохраняется в точности как ввел пользователь.

#### Удаление категории

При нажатии "➖ Удалить категорию":

```
Выберите какую категорию вы хотите удалить:

[🛒 Супермаркеты] [🫑 Другие продукты]
[🍽️ Рестораны] [⛽ АЗС] [🚕 Такси]
... и т.д.

[🏠 Назад] [❌ Закрыть]
```

При выборе категории она удаляется, и пользователь возвращается в предыдущее меню.

### 7.6 Меню "Настройки"

При нажатии на кнопку "⚙️ Настройки":

```
⚙️ Настройки

🌐 Язык: Русский
🕰️ Часовой пояс: UTC+3 (Москва)
💵 Основная валюта: RUB

📊 Отчеты:
✅ Ежедневные: 21:00
✅ Еженедельные: Понедельник

[🌐 Изменить язык]
[🕰️ Изменить часовой пояс]
[💵 Изменить валюту]
[📊 Настройка отчетов]

[🏠 Назад] [❌ Закрыть]
```

### 7.7 Меню "Инфо"

При нажатии на кнопку "ℹ️ Инфо" (аналогично /start):

```
💰 ExpenseBot - ваш помощник в учете расходов

Основные возможности:

🔹 Добавление расходов:
Просто отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

🔹 Отчеты о тратах:
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил сегодня"

🔹 Кешбэки:
Отслеживайте кешбэки по банковским картам

🔹 Категории:
Создавайте свои категории или используйте готовые

🔹 PDF отчеты:
Получайте красивые отчеты с графиками

[📚 Меню]
[🏠 Назад] [❌ Закрыть]
```

### 7.8 Примеры интерфейсов

#### Приветственное сообщение /start
```
💰 Добро пожаловать в ExpenseBot!

Я помогу вам вести учет расходов и отслеживать кешбэки.

🔹 Просто отправьте мне текстовое или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

🔹 Попросите отчет:
"Покажи траты за июль"

[❓ Справка]

Основные команды:
/categories - Категории
/budget - Бюджет
/summary - Отчеты
/cashback - Кешбэки
/settings - Настройки
```

#### Добавление расхода
```
Пользователь: дизель 4095 азс
Бот: ✅ Расход добавлен: 4095 ₽
⛽ Категория: АЗС (определена автоматически)
📝 Описание: дизель

📊 Сегодня потрачено: 12,350 ₽

[🔄 Изменить категорию] [❌ Удалить]
```

#### Краткая сводка
```
Пользователь: покажи траты за июль
Бот: 📊 Сводка за Июль 2024

💰 Всего потрачено: 156,780 ₽

📊 По категориям:
🛒 Супермаркеты: 45,320 ₽ (28.9%)
🍽️ Рестораны: 32,100 ₽ (20.5%)
⛽ АЗС: 24,500 ₽ (15.6%)
🏠 Жилье: 18,000 ₽ (11.5%)
💊 Аптеки: 8,200 ₽ (5.2%)

💳 Потенциальный кешбэк: 4,835 ₽

[📄 Сформировать PDF отчет]
```

#### Интерфейс кешбэков
```
💳 Кешбэки на Январь

🍽️ Рестораны
  • Тинькофф: 5%
  • Альфа: 3% (до 1000₽)

🛒 Супермаркеты
  • ВТБ: 5% (до 2000₽)
  • Тинькофф: 2%

🚗 Транспорт
  • Альфа: 3%

[➕ Добавить] [✏️ Редактировать]
[📅 Другой месяц] [🗑 Удалить]
```

## 8. API документация

### 8.1 Основные endpoints

#### Расходы
- `GET /api/expenses/` - Список расходов
- `POST /api/expenses/` - Создание расхода
- `PUT /api/expenses/{id}/` - Редактирование расхода
- `DELETE /api/expenses/{id}/` - Удаление расхода

#### Категории
- `GET /api/categories/` - Список категорий
- `POST /api/categories/` - Создание категории
- `PUT /api/categories/{id}/` - Редактирование категории
- `DELETE /api/categories/{id}/` - Удаление категории

#### Кешбэки
- `GET /api/cashbacks/` - Список кешбэков
- `POST /api/cashbacks/` - Создание кешбэка
- `PUT /api/cashbacks/{id}/` - Редактирование кешбэка
- `DELETE /api/cashbacks/{id}/` - Удаление кешбэка

#### Аналитика
- `GET /api/analytics/summary/` - Сводка за период
- `GET /api/analytics/categories/` - Анализ по категориям
- `GET /api/analytics/trends/` - Тренды расходов

### 8.2 Формат ответов
Все API endpoints возвращают данные в формате JSON:
```json
{
    "success": true,
    "data": {...},
    "message": "Success",
    "errors": null
}
```

## 9. Этапы разработки

### 9.1 Этап 1 - Базовая функциональность (4 недели)
- Настройка проекта и базы данных
- Регистрация пользователей
- Добавление и управление расходами
- Базовые категории
- Простые отчеты

### 9.2 Этап 2 - Расширенные возможности (3 недели)
- Управление бюджетом
- Продвинутая аналитика
- PDF отчеты
- Система уведомлений
- Загрузка чеков

### 9.3 Этап 3 - Система кешбэков (2 недели)
- Модель данных для кешбэков
- Добавление и управление кешбэками
- Интеграция кешбэков в отчеты
- Автоматические месячные сводки с кешбэками
- UI для управления кешбэками

### 9.4 Этап 4 - Оптимизация и тестирование (2 недели)
- Нагрузочное тестирование
- Оптимизация производительности
- Исправление багов
- Документация

### 9.5 Этап 5 - Деплой и мониторинг (1 неделя)
- Настройка продакшн окружения
- Деплой приложения
- Настройка мониторинга
- Обучение пользователей

## 10. Тестирование

### 10.1 Виды тестирования
- **Unit тесты**: Покрытие критичной бизнес-логики
- **Integration тесты**: Тестирование API endpoints
- **End-to-End тесты**: Тестирование пользовательских сценариев
- **Load тесты**: Проверка производительности под нагрузкой

### 10.2 Тестовые сценарии
- Регистрация нового пользователя
- Добавление расходов различных типов
- Создание и редактирование категорий
- Настройка бюджетов и кешбэков
- Генерация отчетов за различные периоды
- Генерация PDF отчетов с графиками

### 10.3 Критерии качества
- Покрытие кода тестами не менее 80%
- Время отклика API не более 500ms
- Успешная обработка 95% запросов
- Отсутствие критических уязвимостей безопасности

---

# Приложения

## Приложение А - Django модели

### Модель категорий
```python
class ExpenseCategory(models.Model):
    """Категории расходов"""
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='💰')
    # Все категории привязаны к пользователю и могут быть удалены
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['profile', 'name']
        db_table = 'expenses_category'
        
    def __str__(self):
        return f"{self.icon} {self.name}"
```

### Модель кешбэков
```python
class Cashback(models.Model):
    """Информация о кешбэках по категориям"""
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='cashbacks')
    category = models.ForeignKey('ExpenseCategory', on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100, verbose_name='Название банка')
    cashback_percent = models.DecimalField(max_digits=4, decimal_places=2, verbose_name='Процент кешбэка')
    month = models.IntegerField(choices=[(i, i) for i in range(1, 13)], verbose_name='Месяц')
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Лимит')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['profile', 'category', 'bank_name', 'month']
        db_table = 'expenses_cashback'
        verbose_name = 'Кешбэк'
        verbose_name_plural = 'Кешбэки'
    
    def __str__(self):
        return f"{self.bank_name} - {self.category.name} - {self.cashback_percent}%"
```

## Приложение Б - Примеры API запросов

### Добавление расхода
```bash
curl -X POST http://localhost:8000/api/expenses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "amount": 200.00,
    "description": "кофе"
  }'
# Категория будет определена автоматически через AI
```

### Добавление кешбэка
```bash
curl -X POST http://localhost:8000/api/cashbacks/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "category_id": 1,
    "bank_name": "Тинькофф",
    "cashback_percent": 5.0,
    "month": 1,
    "limit_amount": 3000.00
  }'
```

### Получение сводки с кешбэками
```bash
curl -X GET "http://localhost:8000/api/analytics/summary/?start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer {token}"
```

## Приложение В - Команды бота

### Локализация

```python
# texts.py - Словарь для локализации
TEXTS = {
    'ru': {
        'welcome': '💰 Добро пожаловать в ExpenseBot!',
        'expense_added': '✅ Расход добавлен',
        'category': 'Категория',
        'today_spent': 'Сегодня потрачено',
        'summary': 'Сводка за',
        'total_spent': 'Всего потрачено',
        'by_categories': 'По категориям',
        'potential_cashback': 'Потенциальный кешбэк',
        'generate_pdf': 'Сформировать PDF отчет',
        'change_category': 'Изменить категорию',
        'delete': 'Удалить',
        'cashbacks': 'Кешбэки на',
        'add': 'Добавить',
        'edit': 'Редактировать',
        'other_month': 'Другой месяц',
        'help': 'Справка',
        'settings': 'Настройки',
        'language': 'Язык',
        'currency': 'Валюта',
        'budget': 'Бюджет',
        'categories': 'Категории',
        'auto_detected': 'определена автоматически',
        'description': 'Описание'
    },
    'en': {
        'welcome': '💰 Welcome to ExpenseBot!',
        'expense_added': '✅ Expense added',
        'category': 'Category',
        'today_spent': 'Spent today',
        'summary': 'Summary for',
        'total_spent': 'Total spent',
        'by_categories': 'By categories',
        'potential_cashback': 'Potential cashback',
        'generate_pdf': 'Generate PDF report',
        'change_category': 'Change category',
        'delete': 'Delete',
        'cashbacks': 'Cashbacks for',
        'add': 'Add',
        'edit': 'Edit',
        'other_month': 'Other month',
        'help': 'Help',
        'settings': 'Settings',
        'language': 'Language',
        'currency': 'Currency',
        'budget': 'Budget',
        'categories': 'Categories',
        'auto_detected': 'auto detected',
        'description': 'Description'
    }
}

def get_text(key: str, lang: str = 'ru') -> str:
    """Получить текст по ключу и языку"""
    return TEXTS.get(lang, TEXTS['ru']).get(key, key)
```

### Создание базовых категорий
```python
async def create_default_categories(profile_id: int):
    """Создает базовые категории для нового пользователя"""
    default_categories = [
        ('Супермаркеты', '🛒'),
        ('Другие продукты', '🫑'),
        ('Рестораны и кафе', '🍽️'),
        ('АЗС', '⛽'),
        ('Такси', '🚕'),
        ('Общественный транспорт', '🚌'),
        ('Автомобиль', '🚗'),
        ('Жилье', '🏠'),
        ('Аптеки', '💊'),
        ('Медицина', '🏥'),
        ('Спорт', '🏃'),
        ('Спортивные товары', '🏀'),
        ('Одежда и обувь', '👔'),
        ('Цветы', '🌹'),
        ('Развлечения', '🎭'),
        ('Образование', '📚'),
        ('Подарки', '🎁'),
        ('Путешествия', '✈️'),
        ('Связь и интернет', '📱'),
        ('Прочее', '💰')
    ]
    
    for name, icon in default_categories:
        await ExpenseCategory.objects.create(
            profile_id=profile_id,
            name=name,
            icon=icon
        )
```

### Обработка естественного языка

```python
class NaturalLanguageProcessor:
    """Обработчик естественного языка для трат"""
    
    async def process_expense_message(self, text: str) -> dict:
        """
        Обработка сообщения о трате
        
        Примеры:
        - "дизель 4095 азс" -> {
            'amount': 4095,
            'category': 'АЗС',
            'description': 'дизель'
          }
        - "кофе 200" -> {
            'amount': 200,
            'category': 'Рестораны и кафе',
            'description': 'кофе'
          }
        """
        
        # Извлечение суммы
        amount = self._extract_amount(text)
        if not amount:
            return None
            
        # Определение категории через AI
        category = await self._detect_category(text)
        
        # Очистка описания
        description = self._clean_description(text, amount)
        
        return {
            'amount': amount,
            'category': category,
            'description': description
        }
    
    async def process_report_request(self, text: str) -> dict:
        """
        Обработка запроса на отчет
        
        Примеры:
        - "покажи траты за июль" -> {
            'type': 'summary',
            'period': 'month',
            'month': 7,
            'year': 2024
          }
        - "сколько я потратил сегодня" -> {
            'type': 'summary',
            'period': 'day',
            'date': '2024-01-20'
          }
        """
        
        # Определение типа запроса через AI
        request_type = await self._detect_request_type(text)
        
        if request_type == 'summary':
            period_data = self._extract_period(text)
            return {
                'type': 'summary',
                **period_data
            }
        
        return None
```

### Команды для кешбэков

### Основные команды
```python
@router.message(Command("cashback"))
async def cashback_command(message: Message):
    """Показать заметку о кешбэках на текущий месяц"""
    user_id = message.from_user.id
    current_month = datetime.now().month
    
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if not cashbacks:
        text = "💳 <b>Кешбэки на текущий месяц</b>\n\nУ вас пока нет информации о кешбэках.\n\nИспользуйте кнопки ниже для управления."
    else:
        text = format_cashback_note(cashbacks, current_month)
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить", callback_data="cashback_add"),
            InlineKeyboardButton("✏️ Редактировать", callback_data="cashback_edit")
        ],
        [
            InlineKeyboardButton("📅 Другой месяц", callback_data="cashback_month"),
            InlineKeyboardButton("🗑 Удалить", callback_data="cashback_delete")
        ]
    ])
    
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")
```

### Функция форматирования заметки
```python
def format_cashback_note(cashbacks, month):
    """Форматирование заметки о кешбэках"""
    month_name = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month-1]
    
    text = f"💳 <b>Кешбэки на {month_name}</b>\n\n"
    
    # Группируем по категориям
    by_category = {}
    for cb in cashbacks:
        if cb.category.id not in by_category:
            by_category[cb.category.id] = {
                'name': cb.category.name,
                'icon': cb.category.icon,
                'banks': []
            }
        
        bank_info = f"{cb.bank_name}: {cb.cashback_percent}%"
        if cb.limit_amount:
            bank_info += f" (до {cb.limit_amount}₽)"
        
        by_category[cb.category.id]['banks'].append(bank_info)
    
    # Выводим по категориям
    for cat_data in by_category.values():
        text += f"<b>{cat_data['icon']} {cat_data['name']}</b>\n"
        for bank in cat_data['banks']:
            text += f"  • {bank}\n"
        text += "\n"
    
    return text
```

### Автоматическая месячная сводка
```python
@shared_task
def send_monthly_summaries():
    """Отправка месячных сводок в конце месяца"""
    # Запускается последнего числа месяца в 21:00
    today = datetime.now()
    last_day = monthrange(today.year, today.month)[1]
    
    if today.day == last_day:
        users = Profile.objects.filter(
            settings__monthly_summary_enabled=True,
            is_active=True
        )
        
        start_date = today.replace(day=1).date()
        end_date = today.date()
        
        for user in users:
            summary = generate_summary(user.telegram_id, start_date, end_date)
            send_telegram_message.delay(user.telegram_id, summary)
```

---

**Версия документа**: 1.0  
**Дата создания**: 01.08.2025  
**Статус**: Финальная версия  
**Ответственный**: Команда разработки ExpenseBot