# API документация ExpenseBot

## Обзор API

ExpenseBot предоставляет REST API для управления расходами, категориями, кешбэками и получения аналитики. API построен на Django REST Framework и поддерживает JSON формат данных.

## Базовый URL
```
Development: http://localhost:8000/api/
Production: https://expensebot.example.com/api/
```

## Аутентификация

API использует аутентификацию через JWT токены. Токен получается автоматически при первом обращении пользователя к боту.

### Заголовки запросов
```http
Authorization: Bearer <jwt_token>
Content-Type: application/json
Accept: application/json
```

## Формат ответов

Все API endpoints возвращают данные в стандартном формате:

### Успешный ответ
```json
{
    "success": true,
    "data": { ... },
    "message": "Success",
    "errors": null,
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 100,
        "pages": 5
    }
}
```

### Ошибка
```json
{
    "success": false,
    "data": null,
    "message": "Error description",
    "errors": {
        "field_name": ["Error message"]
    }
}
```

## API Endpoints

### 1. Пользователи

#### Получение профиля пользователя
```http
GET /api/users/profile/
```

**Ответ:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "telegram_id": 123456789,
        "username": "user123",
        "first_name": "Иван",
        "last_name": "Петров",
        "language_code": "ru",
        "timezone": "Europe/Moscow",
        "currency": "RUB",
        "is_active": true,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-20T10:30:00Z"
    }
}
```

#### Обновление профиля
```http
PUT /api/users/profile/
```

**Тело запроса:**
```json
{
    "language_code": "en",
    "timezone": "UTC",
    "currency": "USD"
}
```

### 2. Категории

#### Получение списка категорий
```http
GET /api/categories/
```

**Параметры запроса:**
- `is_active` (boolean) - фильтр по активности
- `page` (integer) - номер страницы
- `per_page` (integer) - количество записей на странице

**Ответ:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Супермаркеты",
            "icon": "🛒",
            "is_active": true,
            "expenses_count": 25,
            "total_amount": 15000.50,
            "created_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": 2,
            "name": "АЗС",
            "icon": "⛽",
            "is_active": true,
            "expenses_count": 12,
            "total_amount": 8500.00,
            "created_at": "2024-01-01T00:00:00Z"
        }
    ]
}
```

#### Создание категории
```http
POST /api/categories/
```

**Тело запроса:**
```json
{
    "name": "Спортивные товары",
    "icon": "🏀"
}
```

#### Обновление категории
```http
PUT /api/categories/{id}/
```

**Тело запроса:**
```json
{
    "name": "Новое название",
    "icon": "🆕",
    "is_active": false
}
```

#### Удаление категории
```http
DELETE /api/categories/{id}/
```

### 3. Расходы

#### Получение списка расходов
```http
GET /api/expenses/
```

**Параметры запроса:**
- `start_date` (date) - начальная дата (YYYY-MM-DD)
- `end_date` (date) - конечная дата (YYYY-MM-DD)
- `category_id` (integer) - ID категории
- `min_amount` (decimal) - минимальная сумма
- `max_amount` (decimal) - максимальная сумма
- `search` (string) - поиск по описанию
- `page` (integer) - номер страницы
- `per_page` (integer) - количество записей на странице

**Ответ:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "amount": 4095.00,
            "description": "дизель",
            "category": {
                "id": 2,
                "name": "АЗС",
                "icon": "⛽"
            },
            "expense_date": "2024-01-20",
            "expense_time": "14:30:00",
            "receipt_photo": null,
            "ai_categorized": true,
            "ai_confidence": 0.95,
            "created_at": "2024-01-20T14:30:00Z"
        }
    ]
}
```

#### Создание расхода
```http
POST /api/expenses/
```

**Тело запроса:**
```json
{
    "amount": 200.50,
    "description": "кофе",
    "category_id": 3,
    "expense_date": "2024-01-20",
    "expense_time": "09:15:00"
}
```

**Примечание**: Если `category_id` не указан, категория будет определена автоматически через AI.

#### Обновление расхода
```http
PUT /api/expenses/{id}/
```

#### Удаление расхода
```http
DELETE /api/expenses/{id}/
```

#### Загрузка чека
```http
POST /api/expenses/{id}/upload-receipt/
```

**Тело запроса:** multipart/form-data
```
receipt: <image_file>
```

### 4. Кешбэки

#### Получение списка кешбэков
```http
GET /api/cashbacks/
```

**Параметры запроса:**
- `month` (integer) - месяц (1-12)
- `category_id` (integer) - ID категории
- `bank_name` (string) - название банка

**Ответ:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "category": {
                "id": 2,
                "name": "АЗС",
                "icon": "⛽"
            },
            "bank_name": "Тинькофф",
            "cashback_percent": 5.00,
            "month": 1,
            "limit_amount": 3000.00,
            "current_spent": 2500.00,
            "potential_cashback": 125.00,
            "created_at": "2024-01-01T00:00:00Z"
        }
    ]
}
```

#### Создание кешбэка
```http
POST /api/cashbacks/
```

**Тело запроса:**
```json
{
    "category_id": 2,
    "bank_name": "Альфа-Банк",
    "cashback_percent": 3.0,
    "month": 1,
    "limit_amount": 2000.00
}
```

#### Обновление кешбэка
```http
PUT /api/cashbacks/{id}/
```

#### Удаление кешбэка
```http
DELETE /api/cashbacks/{id}/
```

### 5. Аналитика

#### Сводка за период
```http
GET /api/analytics/summary/
```

**Параметры запроса:**
- `start_date` (date, обязательный) - начальная дата
- `end_date` (date, обязательный) - конечная дата
- `group_by` (string) - группировка: day, week, month, category

**Ответ:**
```json
{
    "success": true,
    "data": {
        "period": {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "days": 31
        },
        "totals": {
            "total_amount": 156780.50,
            "total_expenses": 145,
            "total_cashback": 4835.20,
            "average_per_day": 5057.43
        },
        "categories": [
            {
                "category": {
                    "id": 1,
                    "name": "Супермаркеты",
                    "icon": "🛒"
                },
                "amount": 45320.00,
                "percentage": 28.9,
                "expenses_count": 42,
                "potential_cashback": 1500.00
            }
        ],
        "daily_data": [
            {
                "date": "2024-01-01",
                "amount": 2500.00,
                "expenses_count": 4
            }
        ]
    }
}
```

#### Анализ по категориям
```http
GET /api/analytics/categories/
```

**Параметры запроса:**
- `start_date` (date) - начальная дата
- `end_date` (date) - конечная дата
- `top_n` (integer) - количество топ категорий (по умолчанию 10)

#### Тренды расходов
```http
GET /api/analytics/trends/
```

**Параметры запроса:**
- `period` (string) - период: week, month, quarter, year
- `category_id` (integer) - ID категории (опционально)

### 6. Отчеты

#### Генерация PDF отчета
```http
POST /api/reports/pdf/
```

**Тело запроса:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "include_charts": true,
    "include_cashbacks": true,
    "group_by": "category"
}
```

**Ответ:**
```json
{
    "success": true,
    "data": {
        "report_id": "report_123456",
        "download_url": "/api/reports/download/report_123456/",
        "expires_at": "2024-01-21T00:00:00Z"
    }
}
```

#### Скачивание отчета
```http
GET /api/reports/download/{report_id}/
```

**Ответ:** PDF файл

### 7. Настройки

#### Получение настроек пользователя
```http
GET /api/settings/
```

**Ответ:**
```json
{
    "success": true,
    "data": {
        "daily_reminder_enabled": true,
        "daily_reminder_time": "20:00:00",
        "weekly_summary_enabled": true,
        "monthly_summary_enabled": true,
        "budget_alerts_enabled": true,
        "preferred_currency": "RUB",
        "timezone": "Europe/Moscow"
    }
}
```

#### Обновление настроек
```http
PUT /api/settings/
```

**Тело запроса:**
```json
{
    "daily_reminder_enabled": false,
    "weekly_summary_enabled": true,
    "daily_reminder_time": "21:00:00"
}
```

## Обработка ошибок

### Коды ошибок

| Код | Описание |
|-----|----------|
| 400 | Неверные данные запроса |
| 401 | Не авторизован |
| 403 | Доступ запрещен |
| 404 | Ресурс не найден |
| 422 | Ошибка валидации |
| 429 | Превышен лимит запросов |
| 500 | Внутренняя ошибка сервера |

### Примеры ошибок

#### Ошибка валидации
```json
{
    "success": false,
    "message": "Validation failed",
    "errors": {
        "amount": ["Это поле обязательно для заполнения"],
        "category_id": ["Категория не найдена"]
    }
}
```

#### Превышение лимита запросов
```json
{
    "success": false,
    "message": "Rate limit exceeded",
    "errors": {
        "detail": "Превышен лимит запросов. Попробуйте позже.",
        "retry_after": 60
    }
}
```

## Лимиты API

### Rate Limiting
- **Стандартные пользователи**: 100 запросов в минуту
- **Premium пользователи**: 500 запросов в минуту
- **Telegram Bot**: без ограничений

### Ограничения данных
- Максимальный размер запроса: 10MB
- Максимальный размер файла чека: 5MB
- Максимальное количество записей на странице: 100

## Примеры использования

### Добавление расхода через API
```javascript
const response = await fetch('/api/expenses/', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        amount: 200.00,
        description: 'кофе',
        expense_date: '2024-01-20'
    })
});

const result = await response.json();
if (result.success) {
    console.log('Расход добавлен:', result.data);
}
```

### Получение сводки за месяц
```python
import requests

response = requests.get('/api/analytics/summary/', {
    'start_date': '2024-01-01',
    'end_date': '2024-01-31'
}, headers={
    'Authorization': f'Bearer {token}'
})

data = response.json()
if data['success']:
    print(f"Потрачено за месяц: {data['data']['totals']['total_amount']}")
```

## Webhook уведомления

API поддерживает отправку webhook уведомлений о важных событиях:

### Настройка webhook
```http
POST /api/webhooks/
```

**Тело запроса:**
```json
{
    "url": "https://example.com/webhook",
    "events": ["expense.created", "budget.exceeded"],
    "secret": "webhook_secret"
}
```

### События
- `expense.created` - создан новый расход
- `expense.updated` - обновлен расход
- `budget.exceeded` - превышен бюджет
- `monthly.summary` - месячная сводка

### Формат webhook
```json
{
    "event": "expense.created",
    "timestamp": "2024-01-20T14:30:00Z",
    "data": {
        "expense": { ... }
    },
    "signature": "sha256=..."
}
```