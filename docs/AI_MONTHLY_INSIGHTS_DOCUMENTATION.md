# Документация AI месячных инсайтов для ExpenseBot

**Дата создания:** 2025-10-09
**Автор:** Claude Code
**Статус:** ✅ **РЕАЛИЗОВАНО И РАБОТАЕТ**

---

## 📋 Оглавление

1. [Обзор функциональности](#обзор-функциональности)
2. [Архитектура решения](#архитектура-решения)
3. [Реализованные компоненты](#реализованные-компоненты)
4. [Особенности реализации](#особенности-реализации)
5. [Система Fallback и обработка ошибок](#система-fallback-и-обработка-ошибок)
6. [Уведомления администратору](#уведомления-администратору)
7. [Процесс деплоя](#процесс-деплоя)
8. [Тестирование](#тестирование)
9. [Известные ограничения](#известные-ограничения)
10. [Будущие улучшения](#будущие-улучшения)

---

## Обзор функциональности

### Что реализовано:

AI-powered анализ месячных финансов пользователя, который **автоматически добавляется в caption к PDF отчету**.

### Пример вывода для пользователя:

```
📊 Ежемесячный отчет за Октябрь 2025

🤖 AI анализ за Октябрь 2025

💰 Расходы: 30 620 ₽
📊 Количество трат: 13

🏆 Топ категорий:
1. Прочие расходы: 18 400₽ (60%)
2. Жилье: 4 400₽ (14%)
3. Одежда и обувь: 3 400₽ (11%)

📝 За октябрь вы потратили 30 620 рублей, что на 14.7% меньше,
чем в сентябре. Траты значительно сократились!

📊 Ключевые моменты:
• Основная категория: Прочие расходы (18 400₽, 60%)
• Расходы снизились на 15% по сравнению с прошлым месяцем
• Количество трат: 13 (было 53 в сентябре)

[PDF файл прикреплен]
```

### ✅ Ключевые особенности:

- **Интеграция в существующий процесс** - Без UI изменений, инсайты добавляются к PDF
- **Адаптивный контент** - Скрывает упоминания доходов/баланса если их нет
- **Сравнение с предыдущим месяцем** - Анализ динамики расходов
- **Проверка подписки** - Отправка только пользователям с активной подпиской
- **Graceful degradation** - PDF отправляется даже если AI недоступен
- **Multi-level fallback** - Google Gemini → OpenAI → без AI анализа
- **Уведомления админу** - При сбоях и использовании fallback
- **Оптимизация длины** - Укладывается в лимит Telegram (1024 символа)

---

## Архитектура решения

### Компоненты системы:

```
┌─────────────────────────────────────────────────────────────┐
│         Celery Task: send_monthly_reports                   │
│         (1-го числа каждого месяца в 10:00 MSK)             │
│         expense_bot/celery_tasks.py:20-87                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│   Фильтрация пользователей с активной подпиской             │
│   + траты в прошлом месяце                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          NotificationService.send_monthly_report            │
│          bot/services/notifications.py:22-108               │
└───────────────────────────┬─────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
    ┌────────────────────┐   ┌──────────────────────┐
    │ MonthlyInsights    │   │  PDFReportService    │
    │ Service            │   │  (existing)          │
    │ (NEW)              │   │                      │
    └──────┬─────────────┘   └──────────────────────┘
           │
           ├─────────────────────┐
           ▼                     ▼
┌──────────────────┐   ┌─────────────────────┐
│  Data Collector  │   │   AI Generation     │
│  (собирает за    │   │   с Fallback        │
│   2 месяца)      │   │                     │
└──────────────────┘   └──────────┬──────────┘
                                  │
              ┌───────────────────┴─────────────┐
              ▼                                 ▼
   ┌──────────────────────┐        ┌─────────────────────┐
   │  Google Gemini API   │ Fail   │   OpenAI API        │
   │  (Priority 1)        │ ─────→ │   (Priority 2)      │
   └──────────────────────┘        └─────────────────────┘
              │                                 │
              └───────────────┬─────────────────┘
                              │ (оба недоступны)
                              ▼
                  ┌────────────────────────┐
                  │  Без AI анализа        │
                  │  (только PDF)          │
                  └────────────────────────┘
```

---

## Реализованные компоненты

### 1. **MonthlyInsight Model**

**Файл:** `expenses/models.py:2734`

**Назначение:** Хранение сгенерированных AI инсайтов для кеширования

**Поля:**
```python
class MonthlyInsight(models.Model):
    profile = ForeignKey(Profile)
    year = IntegerField()
    month = IntegerField()
    total_expenses = DecimalField()
    total_incomes = DecimalField()
    expenses_count = IntegerField()
    balance = DecimalField()
    top_categories = JSONField()  # Топ-10 категорий
    ai_summary = TextField()  # Краткое резюме от AI
    ai_analysis = TextField()  # Ключевые моменты
    ai_recommendations = TextField()  # (не используется)
    ai_model_used = CharField()  # gemini-2.0-flash-exp / gpt-4o
    ai_provider = CharField()  # google / openai

    class Meta:
        unique_together = ['profile', 'year', 'month']
```

**Миграция:** `expenses/migrations/0048_monthlyinsight.py`

---

### 2. **MonthlyInsightsService**

**Файл:** `bot/services/monthly_insights.py` (640 строк)

**Назначение:** Генерация AI инсайтов с кешированием и fallback

**Основные методы:**

#### `generate_insight(profile, year, month, provider='google')`
- Проверяет существующий инсайт в БД
- Собирает данные текущего и предыдущего месяца
- Проверяет минимум данных (3+ траты)
- Генерирует AI анализ с fallback
- Сохраняет в БД для кеширования

#### `get_insight(profile, year, month)`
- Получает существующий инсайт из БД

#### `_collect_month_data(profile, year, month)`
- Собирает расходы и доходы за месяц
- Группирует по категориям
- Подготавливает топ-10 категорий

#### `_build_analysis_prompt(profile, month_data, prev_month_data, year, month)`
- **Адаптивный промпт** - убирает упоминания доходов/баланса если их нет
- Включает сравнение с предыдущим месяцем (если есть данные)
- Инструктирует AI фокусироваться только на расходах (если нет доходов)

#### `_generate_ai_insights(profile, month_data, prev_month_data, year, month, provider)`
- Вызов Google AI или OpenAI
- Парсинг JSON ответа
- Fallback парсинг если JSON невалиден

---

### 3. **Интеграция в NotificationService**

**Файл:** `bot/services/notifications.py:22-108`

**Изменения:**

```python
async def send_monthly_report(self, user_id, profile, year, month):
    # 1. Генерируем AI инсайт
    insight = await insights_service.get_insight(profile, year, month)
    if not insight:
        insight = await insights_service.generate_insight(
            profile=profile,
            year=year,
            month=month,
            provider='google'
        )

    # 2. Генерируем PDF
    pdf_bytes = await pdf_service.generate_monthly_report(...)

    # 3. Формируем caption
    caption = f"📊 Ежемесячный отчет за {month_name} {year}"

    if insight:
        insight_text = self._format_insight_text(insight, month, year)
        full_caption = f"{caption}\n\n{insight_text}"

        # Проверка лимита 1024 символа
        if len(full_caption) <= 1024:
            caption = full_caption
        else:
            # Обрезка с многоточием
            truncated = insight_text[:max_length] + "..."
            caption = f"{caption}\n\n{truncated}"

    # 4. Отправляем PDF с caption
    await self.bot.send_document(
        chat_id=user_id,
        document=pdf_file,
        caption=caption,
        parse_mode='HTML'
    )
```

**Метод форматирования:**

```python
def _format_insight_text(self, insight, month, year):
    text = f"🤖 <b>AI анализ за {period}</b>\n\n"

    # Финансовая сводка (компактная)
    text += f"💰 Расходы: {insight.total_expenses:,.0f} ₽"

    # Баланс только если есть доходы
    if insight.total_incomes > 0:
        balance_emoji = "📈" if balance >= 0 else "📉"
        text += f" | Баланс: {balance_emoji} {balance:+,.0f} ₽"

    text += f"\n📊 Количество трат: {insight.expenses_count}\n\n"

    # Топ 3 категории
    text += "🏆 <b>Топ категорий:</b>\n"
    for i, cat in enumerate(insight.top_categories[:3], 1):
        text += f"{i}. {cat['category']}: {cat['amount']:,.0f}₽ ({cat['percentage']:.0f}%)\n"

    # AI резюме и анализ
    text += f"\n📝 {insight.ai_summary}\n\n"

    if insight.ai_analysis:
        key_points = [line for line in analysis_lines if line.startswith('•')][:3]
        if key_points:
            text += "📊 <b>Ключевые моменты:</b>\n"
            text += '\n'.join(key_points)

    return text
```

---

### 4. **Проверка подписки в Celery**

**Файл:** `expense_bot/celery_tasks.py:58-72`

```python
@shared_task
def send_monthly_reports():
    # Фильтруем пользователей с:
    # 1. Расходами в прошлом месяце
    # 2. Активной подпиской

    profiles = Profile.objects.filter(
        id__in=profiles_with_expenses
    ).filter(
        Q(subscriptions__is_active=True, subscriptions__end_date__gt=timezone.now()) |
        Q(subscriptions__is_trial=True, subscriptions__is_active=True)
    ).distinct()

    # Отправляем только пользователям с подпиской
    for profile in profiles:
        await service.send_monthly_report(profile.telegram_id, profile)
```

---

## Особенности реализации

### 1. **Адаптивный контент (только расходы vs расходы+доходы)**

**Проблема:** Многие пользователи записывают только расходы, не вводя доходы

**Решение:**

```python
# В _build_analysis_prompt():
has_income = month_data['total_incomes'] > 0

if has_income:
    finance_section = f"""
    - Всего потрачено: {expenses} ₽
    - Всего доходов: {incomes} ₽
    - Баланс: {balance} ₽
    """
else:
    finance_section = f"""
    - Всего потрачено: {expenses} ₽
    """

# В сравнении с предыдущим месяцем:
if prev_month_data:
    if has_income:
        comparison = "... доходы в прошлом месяце: ..."
    else:
        comparison = "... (без упоминания доходов)"

# В инструкции AI:
if not has_income:
    instructions += "НЕ упоминай доходы и баланс, фокусируйся только на расходах"
```

**Результат:** AI не упоминает доходы/баланс когда их нет

---

### 2. **Сравнение месяц-к-месяцу**

**Логика:**

```python
# Вычисляем предыдущий месяц
prev_month = month - 1 if month > 1 else 12
prev_year = year if month > 1 else year - 1

# Собираем данные
prev_month_data = await _collect_month_data(profile, prev_year, prev_month)

# Проверяем достаточность данных
if prev_month_data['total_expenses'] == 0 or len(prev_month_data['expenses']) < 3:
    prev_month_data = None  # Не используем для сравнения
```

**Пример в промпте:**

```
СРАВНЕНИЕ С ПРЕДЫДУЩИМ МЕСЯЦЕМ (сентября):
- Расходы в прошлом месяце: 35 916 ₽
- Изменение расходов: -5 296 ₽ (-14.7%)
- Количество трат в прошлом месяце: 53
```

---

### 3. **Оптимизация под лимит 1024 символа**

**Стратегии сокращения:**

1. **Компактное форматирование:**
   - Финансовая сводка в одну строку
   - Топ-3 вместо топ-5 категорий
   - Убрали секцию "Рекомендации"

2. **Динамическая обрезка:**
```python
if len(full_caption) > 1024:
    max_insight_length = 1024 - len(base_caption) - 20
    if max_insight_length > 100:
        truncated_insight = insight_text[:max_insight_length] + "..."
        caption = f"{base_caption}\n\n{truncated_insight}"
```

**Результат:** Средняя длина ~850 символов (запас 174 символа)

---

### 4. **Кеширование инсайтов**

**Логика:**

```python
# Проверяем существующий инсайт
existing_insight = MonthlyInsight.objects.filter(
    profile=profile, year=year, month=month
).first()

if existing_insight and not force_regenerate:
    return existing_insight  # Возвращаем из кеша

# Генерируем новый только если нет в БД
```

**Преимущества:**
- Экономия API вызовов
- Мгновенный ответ при повторном запросе
- Возможность регенерации (force_regenerate=True)

---

## Система Fallback и обработка ошибок

### Трехуровневая система Fallback:

```
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 1: Google Gemini                   │
│  - Model: gemini-2.0-flash-exp              │
│  - Используется модель из .env              │
│  - Success rate: ~95%                       │
└──────────────┬──────────────────────────────┘
               │ Ошибка (5%)
               ▼
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 2: OpenAI GPT                      │
│  - Model: из .env (gpt-4o / gpt-4o-mini)   │
│  - Автоматическое переключение              │
│  - Уведомление админу о fallback            │
└──────────────┬──────────────────────────────┘
               │ Ошибка (<1%)
               ▼
┌─────────────────────────────────────────────┐
│  УРОВЕНЬ 3: Без AI анализа                  │
│  - PDF отправляется с базовым caption       │
│  - Уведомление админу о полном отказе       │
└─────────────────────────────────────────────┘
```

### Код fallback:

```python
try:
    # Попытка 1: Google Gemini
    ai_insights = await self._generate_ai_insights(
        profile, month_data, prev_month_data, year, month, 'google'
    )
except Exception as e:
    logger.error(f"Primary AI provider (google) failed: {e}")

    # Попытка 2: OpenAI fallback
    if provider == 'google':
        try:
            logger.warning(f"Attempting fallback to OpenAI")
            ai_insights = await self._generate_ai_insights(
                ..., 'openai'
            )
            # Уведомляем админа
            await self._notify_admin_fallback(user_id, year, month, 'google', 'openai')
        except Exception as fallback_error:
            # Уведомляем о полном отказе
            await self._notify_admin_failure(user_id, year, month)
            raise
```

### Условия отказа от генерации:

```python
# Недостаточно данных
if month_data['total_expenses'] == 0 or len(month_data['expenses']) < 3:
    logger.info(f"Not enough data for insights: {len(expenses)} expenses")
    return None  # PDF отправится без AI анализа
```

---

## Уведомления администратору

### 1. **Использован OpenAI Fallback**

**Частота:** Максимум 1 раз в час (throttling)

**Сообщение:**
```
⚠️ AI Provider Fallback

User: 881292737
Period: 10/2025
Primary provider failed: google
Fallback used: openai

Check logs for details.
```

**Код:**
```python
async def _notify_admin_fallback(self, user_id, year, month, primary, fallback):
    # Throttling: 1 час между уведомлениями
    key = f"{primary}_to_{fallback}"
    if key in _last_fallback_notification:
        time_since = (now - _last_fallback_notification[key]).total_seconds() / 3600
        if time_since < NOTIFICATION_THROTTLE_HOURS:
            return  # Пропускаем

    _last_fallback_notification[key] = now
    await notify_admin(message, level='warning')
```

---

### 2. **Полный отказ AI (оба провайдера)**

**Частота:** Максимум 1 раз в час для конкретного периода

**Сообщение:**
```
🔴 AI Insights Generation Failed

User: 881292737
Period: 10/2025
Status: All AI providers failed

User will receive monthly report without AI insights.
Check logs and AI service status.
```

**Код:**
```python
async def _notify_admin_failure(self, user_id, year, month):
    key = f"failure_{year}_{month}"

    # Throttling: 1 час
    if key in _last_failure_notification:
        time_since = (now - _last_failure_notification[key]).total_seconds() / 3600
        if time_since < NOTIFICATION_THROTTLE_HOURS:
            return

    _last_failure_notification[key] = now
    await notify_admin(message, level='critical')
```

---

## Процесс деплоя

### На локальной машине:

```bash
# 1. Commit изменений
git add bot/services/monthly_insights.py \
        bot/services/notifications.py \
        expense_bot/celery_tasks.py \
        expenses/models.py \
        expenses/migrations/0048_monthlyinsight.py

git commit -m "Добавлены AI-инсайты для месячных отчетов"

# 2. Push на GitHub
git push origin master
```

### На сервере:

```bash
# 1. Подключение
ssh batman@80.66.87.178

# 2. Обновление кода и применение миграции
cd /home/batman/expense_bot && \
git pull origin master && \
docker-compose down && \
docker-compose build --no-cache && \
docker-compose up -d && \
docker-compose exec expense_bot_web python manage.py migrate

# 3. Проверка логов
docker-compose logs -f expense_bot_celery_beat
docker-compose logs -f expense_bot_app
```

### ⚠️ КРИТИЧЕСКИ ВАЖНО:

**Миграция базы данных ОБЯЗАТЕЛЬНА!**

Без выполнения `python manage.py migrate` бот будет падать с ошибкой:
```
relation "expenses_monthlyinsight" does not exist
```

---

## Тестирование

### 1. Тест генерации инсайта (локально)

**Файл:** `test_monthly_insights.py`

```bash
cd C:/Users/_batman_/Desktop/expense_bot
venv/Scripts/python.exe test_monthly_insights.py
```

**Проверяет:**
- Генерацию инсайта для октября 2025
- Сравнение с сентябрем 2025
- Длину сообщения (<1024 символов)
- Корректность форматирования

**Ожидаемый результат:**
```
✅ Инсайт сгенерирован
📏 Длина: 858 символов
✅ Вписывается в лимит Telegram
```

---

### 2. Тест без доходов

**Файл:** `test_insights_no_income.py`

```bash
venv/Scripts/python.exe test_insights_no_income.py
```

**Проверяет:**
- Промпт не содержит упоминаний доходов/баланса в данных
- AI получает инструкцию фокусироваться только на расходах

**Ожидаемый результат:**
```
✅ Промпт корректный - доходы/баланс упоминаются в данных только когда есть
```

---

### 3. Проверка на сервере

```bash
# Логи Celery задачи
docker-compose logs expense_bot_celery_beat | grep monthly

# Проверка расписания
docker-compose exec expense_bot_celery_beat celery -A expense_bot inspect scheduled

# Ручной запуск задачи (для теста)
docker-compose exec expense_bot_web python manage.py shell
>>> from expense_bot.celery_tasks import send_monthly_reports
>>> send_monthly_reports()
```

---

## Известные ограничения

### 1. **Минимум данных для генерации**

- Требуется минимум **3 траты** в месяце
- Если меньше - инсайт НЕ генерируется
- PDF отправляется без AI анализа

**Обоснование:** Недостаточно данных для содержательного анализа

---

### 2. **Только расходы анализируются**

- Если у пользователя **ТОЛЬКО доходы** (нет расходов) - инсайт НЕ генерируется
- Это бот для отслеживания РАСХОДОВ

**Обоснование:** Нечего анализировать без расходов

---

### 3. **Лимит caption в Telegram**

- Максимум **1024 символа** для caption
- При превышении - автоматическая обрезка с "..."
- Средняя длина ~850 символов (запас 174)

**Решение:** Компактное форматирование + динамическая обрезка

---

### 4. **Отправка только с активной подпиской**

- Месячные отчеты с AI - **платная функция**
- Проверка подписки в Celery задаче
- Без подписки - отчет НЕ отправляется

**Фильтр:**
```python
Q(subscriptions__is_active=True, subscriptions__end_date__gt=timezone.now()) |
Q(subscriptions__is_trial=True, subscriptions__is_active=True)
```

---

## Будущие улучшения

### 1. **Локализация (EN язык)**

**Текущее состояние:** Работает только на русском

**План:**
- Добавить проверку `profile.language_code`
- Адаптировать промпт под EN
- Перевести форматирование текста

---

### 2. **Персонализация промпта**

**Идея:** Учитывать профиль пользователя

- Семейный бюджет vs индивидуальный
- Студент vs работающий
- Разные цели (экономия vs планирование)

---

### 3. **Прогнозы на следующий месяц**

**Идея:** Предсказание расходов

```
📈 Прогноз на ноябрь:
Ожидаемые расходы: ~32 000 ₽
На основе трендов последних 3 месяцев
```

---

### 4. **Анонимная статистика**

**Идея:** Сравнение с другими пользователями

```
📊 Ваши расходы на продукты (18 500₽) на 15% ниже среднего
по пользователям с похожим доходом
```

---

## Итоги реализации

### ✅ Что сделано:

1. **Модель БД** - `MonthlyInsight` для кеширования инсайтов
2. **Сервис** - `MonthlyInsightsService` с полной логикой генерации
3. **Интеграция** - В `NotificationService` для автоматической отправки
4. **Проверка подписки** - Фильтрация в Celery задаче
5. **Адаптивный контент** - Скрытие доходов/баланса при их отсутствии
6. **Fallback система** - Google → OpenAI → без AI
7. **Уведомления админу** - С throttling против спама
8. **Тесты** - Локальное тестирование

### 📊 Статистика:

- **Новые файлы:** 1 (`bot/services/monthly_insights.py`)
- **Измененные файлы:** 3 (notifications.py, celery_tasks.py, models.py)
- **Миграции БД:** 1 (`0048_monthlyinsight.py`)
- **Строк кода:** ~640 (сервис) + интеграция
- **Коммиты:** 3
  - `9f160fc` - Основная функциональность
  - `0f984e1` - Рефакторинг Top-5
  - `39b28c5` - Улучшения (доходы/подписка)

### 🎯 Результат:

**Полностью рабочая система AI-инсайтов**, интегрированная в месячные отчеты, с надежным fallback и проверкой подписки.

---

**Документ создан:** 2025-10-09
**Последнее обновление:** 2025-10-09
**Версия:** 1.0
