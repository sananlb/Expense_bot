# План исправления Monthly Insights

## Контекст проблемы

При генерации ежемесячных AI-инсайтов (1 марта 2026) произошло несколько ошибок:

1. **`NameError: name 'primary_currency' is not defined`** — переменная `primary_currency` использовалась в `_build_analysis_prompt()` но не была определена в этом scope. Она определялась только в `_collect_month_data()` как локальная переменная.

2. **DeepSeek timeout** — AI-провайдер таймаутил на сложных промптах с историей за 6 месяцев. Таймаут был 15 секунд — недостаточно для больших промптов.

3. **Поле `ai_recommendations` всегда пустое** — промпт запрашивает рекомендацию как 3-й пункт в `analysis`, но код прокидывал `'recommendations': ''` через весь pipeline.

4. **Отправка битых инсайтов пользователям** — задача `send-monthly-reports` была активна и могла отправить некорректные инсайты.

## Внесённые изменения

### 1. `bot/services/monthly_insights.py` — Фикс primary_currency (уже был в коммите 123abdd)

**Строка 340:** Добавлено определение `primary_currency` в начале `_build_analysis_prompt()`:
```python
primary_currency = month_data.get('currency', 'RUB')
```

### 2. `bot/services/unified_ai_service.py` — Параметр timeout для AI-вызовов

**Проблема:** Таймаут 15 секунд зашит глобально в создание OpenAI клиента. Для инсайтов с большими промптами этого мало (DeepSeek стабильно таймаутил за 13 сек).

**Решение:** Добавлен опциональный параметр `timeout` в цепочку вызовов:

- `chat(timeout=None)` — новый параметр в публичном методе
- `_simple_chat(timeout=None)` — прокидывается внутрь
- В `client.chat.completions.create(**call_kwargs)` — передаётся как per-request timeout

Дефолт: `None` (используется клиентский timeout 15 сек). Для инсайтов: `timeout=60.0`.

### 3. `bot/services/monthly_insights.py` — timeout=60 для инсайтов

**Строка 623:** Вызов AI с увеличенным таймаутом:
```python
response = await self.ai_service.chat(
    ...,
    timeout=60.0  # Increased timeout for large prompts with historical data
)
```

### 4. `bot/services/monthly_insights.py` — Удаление неиспользуемого recommendations

Убрано прокидывание `'recommendations': ''` из:
- `_generate_ai_insights()` — return dict (строка 682)
- `_fallback_parse_response()` — sections dict и parsing (строки 725-750)
- `_generate_basic_summary()` — return dict (строка 834)

Обновлён код сохранения в модель:
- `existing_insight.ai_recommendations = ''` (строка 979)
- `ai_recommendations=''` при create (строка 1002)

Поле `ai_recommendations` в модели `MonthlyInsight` оставлено (не требует миграции).

### 5. `admin_panel/beat_setup.py` — Временное отключение send-monthly-reports

```python
upsert(
    name='send-monthly-reports',
    ...,
    enabled=False,  # TEMPORARILY DISABLED
)
```

Предотвращает отправку некорректных инсайтов пользователям до полного деплоя фиксов.

## Действия на сервере (уже выполнены)

1. Файл `beat_setup.py` отредактирован внутри контейнера `expense_bot_celery_beat`
2. Задача `send-monthly-reports` отключена в БД (`enabled=False`)
3. Все битые инсайты удалены из таблицы `monthly_insights` (38 записей)
4. Файл `monthly_insights.py` пропатчен внутри контейнера `expense_bot_celery` (добавлена строка 340)
5. Celery перезапущен, инсайты перегенерированы через openrouter/gemini-3-pro — успешно

## Файлы изменённые локально (для коммита)

- `bot/services/monthly_insights.py` — primary_currency fix + timeout + cleanup recommendations
- `bot/services/unified_ai_service.py` — параметр timeout в chat/simple_chat
- `admin_panel/beat_setup.py` — enabled=False для send-monthly-reports

## План деплоя

1. Коммит и пуш всех изменений
2. Полная пересборка контейнеров на сервере (docker-compose build + up)
3. После деплоя: запустить `generate_monthly_insights` принудительно
4. Проверить что инсайты генерируются корректно
5. Включить обратно `send-monthly-reports` (enabled=True в beat_setup.py)
6. Отправить инсайты пользователям вручную или дождаться следующего 1-го числа
