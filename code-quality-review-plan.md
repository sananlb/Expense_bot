# Code Quality Review Plan - Expense Bot

**Дата:** 2026-02-26 (v4.1 - после Codex auto-review раунд 2)
**Проект:** expense_bot (~58,500 строк, ~240 Python файлов)
**Текущая оценка:** 5.2/10

---

## Текущее состояние

| Область | Оценка | Статус |
|---------|--------|--------|
| Архитектура (разделение слоёв) | 8/10 | Хорошо |
| Django Models (индексы, FK, миграции) | 9/10 | Отлично |
| Миграции БД (61 шт) | 9/10 | Отлично |
| Тесты (8 файлов, pytest настроен) | 7/10 | Есть, но мало |
| Type hints | 6/10 | Частично |
| Дублирование кода | 6/10 | Умеренное |
| Хардкод значений | 5/10 | Много magic numbers |
| Длинные функции | 2/10 | **93 функции >100 строк** (4 из них >500) |
| Обработка ошибок | 4/10 | 28 bare except в 14 файлах |
| Безопасность/производительность | 5/10 | Задачи формализованы (см. 1.5), требуется аудит |
| Линтеры/форматтеры | 0/10 | Не настроены |
| CI/CD | 0/10 | Отсутствует |

---

## Фаза 1: Критические исправления + characterization тесты (2 недели)

### 1.1 Настройка линтеров и форматтеров

**Проблема:** Нет единого стиля кода, нет автоматических проверок.

**Задачи:**
- [ ] Создать `pyproject.toml` с конфигурацией ruff, black, isort, mypy
- [ ] Добавить ruff, black, isort, mypy в requirements-dev.txt
- [ ] Первый прогон ruff — зафиксировать текущие ошибки (baseline)
- [ ] Настроить pre-commit hooks для автоматической проверки

**Конфигурация (ориентир):**
```toml
[tool.ruff]
line-length = 120
target-version = "py311"
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM"]

[tool.black]
line-length = 120
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

### 1.2 Исправление bare except (28 мест в 14 файлах)

**Проблема:** `except: pass` скрывает баги, ловит KeyboardInterrupt и SystemExit.

**Файлы для исправления (полный верифицированный список):**

| Файл | Мест | Строки | Приоритет | Риск |
|------|------|--------|-----------|------|
| `bot/services/response_formatter.py` | 9 | 161, 361, 369, 439, 474, 885, 893, 956, 991 | Средний | Средний — парсинг дат |
| `bot/services/expense_functions.py` | 3 | 357, 459, 1748 | Высокий | Высокий — скрывают ошибки БД |
| `bot/routers/chat.py` | 2 | 297, 465 | Высокий | Высокий — скрывает ошибки профиля |
| `bot/routers/start.py` | 2 | 632, 678 | Низкий | Низкий — удаление сообщений |
| `bot/routers/blogger_stats.py` | 2 | 205, 226 | Низкий | Низкий — удаление сообщений |
| `bot/routers/recurring.py` | 1 | 352 | Низкий | Низкий — удаление сообщений |
| `bot/services/pdf_report.py` | 1 | 606 | Средний | Средний — чтение логотипа |
| `bot/services/pdf_report_weasyprint.py` | 1 | 672 | Средний | Средний — дублирование pdf_report |
| `bot/services/analytics_query.py` | 1 | 510 | Высокий | Высокий — скрывает ошибки ORM |
| `bot/utils/expense_formatter.py` | 1 | 231 | Средний | Средний — парсинг дат |
| `bot/utils/income_formatter.py` | 1 | 263 | Средний | Средний — парсинг дат |
| `expenses/views.py` | 1 | 262 | Низкий | Низкий — вычисление uptime |
| `start_local_dev.py` | 1 | 224 | Низкий | Низкий — dev-скрипт |
| `scripts/reset_user_state.py` | 1 | 50 | Низкий | Низкий — dev-скрипт |

**Итого:** 28 мест в 14 файлах (10 в `bot/`, 4 вне `bot/`)

**Порядок исправления:**
1. Сначала **Высокий риск** (expense_functions, chat, analytics_query) — 6 мест
2. Затем **Средний риск** (response_formatter, pdf, formatters) — 14 мест
3. В конце **Низкий риск** (start, blogger_stats, recurring, views, скрипты) — 8 мест

**Дифференцированные паттерны исправления по уровню риска:**

```python
# === ВЫСОКИЙ РИСК (БД, ORM, бизнес-логика) ===
# Ловить конкретные исключения, логировать на WARNING/ERROR, НЕ подавлять
try:
    category = ExpenseCategory.objects.get(id=category_id)
except ExpenseCategory.DoesNotExist:
    logger.warning(f"Category {category_id} not found for user {user_id}")
    category = None
except Exception as e:
    logger.error(f"Unexpected error fetching category {category_id}: {e}", exc_info=True)
    raise  # re-raise для критичных путей

# === СРЕДНИЙ РИСК (парсинг дат, форматирование) ===
# Ловить ValueError/KeyError, логировать на DEBUG, fallback на безопасное значение
try:
    month_num = datetime.fromisoformat(date_str).month
    period_text = f'в {month_names_ru[month_num]}'
except (ValueError, KeyError) as e:
    logger.debug(f"Date parse fallback for '{date_str}': {e}")
    period_text = ''

# === НИЗКИЙ РИСК (удаление сообщений Telegram, dev-скрипты) ===
# Exception as e + debug лог, подавление допустимо
try:
    await safe_delete_message(message=callback.message)
except Exception as e:
    logger.debug(f"Не удалось удалить сообщение: {e}")
```

### 1.3 Вынос хардкод-значений в константы

**Проблема:** Magic numbers и строки разбросаны по коду.

**ВАЖНО:** `bot/constants.py` уже существует (содержит URL-константы для политики конфиденциальности). Нужно **дополнить** его, а не создавать заново.

**Примеры хардкода:**

| Значение | Где встречается | Куда вынести |
|----------|----------------|-------------|
| `'RUB'` | 50+ мест | `constants.DEFAULT_CURRENCY` |
| `'ru'` | 30+ мест | `constants.DEFAULT_LANGUAGE` |
| `'UTC'` | модели, сервисы | `constants.DEFAULT_TIMEZONE` |
| `100` (лимит трат/день) | `expense.py:92` | `constants.DAILY_EXPENSE_LIMIT` |
| `500` (макс. описание) | `expense.py:97` | `constants.MAX_DESCRIPTION_LENGTH` |
| `365` (дней истории) | `expense.py:74` | `constants.HISTORY_LIMIT_DAYS` |
| `Decimal('9999999999.99')` | `expense.py:102` | `constants.MAX_EXPENSE_AMOUNT` |

**Задачи:**
- [ ] Собрать все magic numbers из `bot/services/expense.py`
- [ ] Дополнить существующий `bot/constants.py` секцией бизнес-лимитов
- [ ] Заменить хардкод на константы во всех файлах

### 1.4 Characterization тесты для критичных функций (ПЕРЕД рефакторингом)

**Проблема:** Рефакторинг длинных функций без тестов — высокий риск регрессий.

**Задачи:**
- [ ] Написать characterization тесты для 4 функций Tier 1 (>500 строк):
  - `generate_xlsx_with_charts` — snapshot тест на структуру xlsx
  - `format_function_result` — snapshot тесты для каждого типа результата
  - `handle_text_expense` — E2E тесты основных сценариев парсинга
  - `_add_summary_sheet` — snapshot тест на структуру листа
- [ ] Написать characterization тесты для топ-5 функций Tier 2 (200-500 строк)
- [ ] Настроить CI с этими тестами как quality gate перед рефакторингом
- [ ] **Правило:** НЕ рефакторить функцию пока нет покрывающих тестов

### 1.5 Задачи по безопасности и производительности

**Проблема:** CLAUDE.md требует PII-safe логирование, оптимизацию запросов, кеширование. Ниже — формализованные задачи и критерии приёмки.

**Безопасность:**
- [ ] Аудит логов на PII: убедиться что telegram_id, имена, суммы не логируются на уровне INFO и выше
- [ ] Проверить все `logger.error()` и `logger.warning()` на наличие пользовательских данных
- [ ] Добавить sanitize-хелпер для логирования: `log_safe_user(user_id)` → маскирует данные

**Производительность:**
- [ ] Аудит N+1 запросов: проверить все циклы с ORM-запросами в `bot/services/`
- [ ] Добавить `select_related`/`prefetch_related` где отсутствует
- [ ] Проверить Redis-кеширование: что кешируется, что нет, TTL-политика
- [ ] Обернуть критичные операции в `transaction.atomic()` (create_expense, create_income)

**Критерии приёмки:**
- Ноль PII в логах уровня INFO+
- Ноль N+1 запросов в основных сценариях
- Все денежные операции в транзакциях

---

## Фаза 2: Рефакторинг длинных функций (3-4 недели)

**Масштаб проблемы:** 93 функции >100 строк. Разбиваем работу на 3 подфазы по порогу длины.

**ВАЖНО:** Рефакторинг начинается ТОЛЬКО после наличия characterization тестов (Фаза 1.4).

### Распределение по директориям

| Директория | Tier 1 (>500) | Tier 2 (200-500) | Tier 3 (100-199) | Итого |
|-----------|:---:|:---:|:---:|:---:|
| `bot/services/` | 3 | 4 | 39 | 46 |
| `bot/routers/` | 1 | 6 | 18 | 25 |
| `bot/utils/` | 0 | 4 | 10 | 14 |
| `bot/middlewares/` | 0 | 0 | 4 | 4 |
| `bot/management/` | 0 | 1 | 0 | 1 |
| `bot/tasks/` | 0 | 0 | 1 | 1 |
| `bot/` (корень) | 0 | 1 | 1 | 2 |
| **Итого** | **4** | **16** | **73** | **93** |

### 2.1 Подфаза A: Функции >500 строк (неделя 3)

**Критический приоритет — 4 функции, суммарно ~3 600 строк.**
**Предусловие:** characterization тесты из 1.4 проходят.

| Функция | Файл | Строк | Начало | План рефакторинга |
|---------|------|------:|--------|-------------------|
| `generate_xlsx_with_charts` | `bot/services/export_service.py` | 1 140 | :1210 | Разбить на: _create_workbook, _write_data_sheets, _add_charts, _apply_styles |
| `format_function_result` | `bot/services/response_formatter.py` | 852 | :254 | Извлечь отдельный форматтер для каждого типа результата (expenses, income, categories, etc.) |
| `handle_text_expense` | `bot/routers/expense.py` | 844 | :1239 | Разбить на: _parse_input, _resolve_category, _create_expense, _handle_duplicates, _send_response |
| `_add_summary_sheet` | `bot/services/export_service.py` | 757 | :451 | Разбить на: _write_header, _write_categories_table, _write_totals, _add_summary_charts |

### 2.2 Подфаза B: Функции 200-500 строк (недели 4-5)

**Высокий приоритет — 16 функций.**

| Функция | Файл | Строк | Начало |
|---------|------|------:|--------|
| `_prepare_report_data` | `bot/services/pdf_report.py` | 496 | :103 |
| `parse_expense_message` | `bot/utils/expense_parser.py` | 452 | :733 |
| `callback_show_diary` | `bot/routers/reports.py` | 362 | :442 |
| `show_expenses_summary` | `bot/routers/reports.py` | 312 | :127 |
| `process_promocode` | `bot/routers/subscription.py` | 309 | :394 |
| `parse_income_message` | `bot/utils/expense_parser.py` | 280 | :1306 |
| `_build_analysis_prompt` | `bot/services/monthly_insights.py` | 277 | :297 |
| `_render_html` | `bot/services/pdf_report_weasyprint.py` | 273 | :190 |
| `get_period_dates` | `bot/utils/date_utils.py` | 270 | :8 |
| `format_currency` | `bot/utils/formatters.py` | 253 | :10 |
| `_generate_and_send_pdf_for_current_month` | `bot/routers/expense.py` | 241 | :449 |
| `cmd_start` | `bot/routers/start.py` | 237 | :112 |
| `process_edit_amount` | `bot/routers/expense.py` | 214 | :763 |
| `chat` | `bot/services/openai_service.py` | 210 | :278 |
| `handle` | `bot/management/commands/setup_periodic_tasks.py` | 206 | :12 |
| `expenses_summary_keyboard` | `bot/keyboards.py` | 200 | :168 |

### 2.3 Подфаза C: Функции 100-199 строк (отложено)

**73 функции.** Не блокирует разработку, рефакторинг по мере касания кода (boy scout rule).

**Топ-10 кандидатов для первоочередного рефакторинга:**

| Функция | Файл | Строк |
|---------|------|------:|
| `process_successful_payment_updated` | `bot/routers/subscription.py` | 196 |
| `_prepare_report_data` | `bot/services/pdf_report_weasyprint.py` | 195 |
| `_generate_and_send_pdf_from_monthly_notification` | `bot/routers/reports.py` | 183 |
| `privacy_accept` | `bot/routers/start.py` | 179 |
| `format_incomes_diary_style` | `bot/utils/income_formatter.py` | 178 |
| `generate_insight` | `bot/services/monthly_insights.py` | 177 |
| `process_chat_message` | `bot/routers/chat.py` | 170 |
| `create_income` | `bot/services/income.py` | 169 |
| `handle_amount_clarification` | `bot/routers/expense.py` | 164 |
| `normalize_function_call` | `bot/services/function_call_utils.py` | 163 |

### 2.4 Устранение дублирования кода

**Проблема:** Одинаковые паттерны повторяются в разных файлах.

**Дубли для устранения:**

1. **Получение профиля пользователя** (10+ мест, 3 разных способа):
   ```python
   # Унифицировать через один хелпер:
   profile = await get_user_profile(telegram_id)
   ```

2. **Безопасное удаление сообщений** (21 место с try/except):
   ```python
   # Уже есть safe_delete_message(), но обёрнут в bare except
   # Исправить safe_delete_message чтобы сам обрабатывал ошибки
   ```

3. **Проверка подписки** — консолидация существующих реализаций:
   ```python
   # В проекте уже есть декораторы/проверки подписки в разных роутерах
   # Задача: выбрать одну каноническую реализацию и мигрировать все call sites
   # НЕ создавать новый декоратор — консолидировать существующие
   ```

4. **Парсинг дат с month_names_ru** — 9 одинаковых bare except в `response_formatter.py`:
   ```python
   # Вынести в утилиту: format_month_name(date_str, lang) -> str
   ```

5. **Чтение логотипа для PDF** — дублируется в `pdf_report.py:606` и `pdf_report_weasyprint.py:672`:
   ```python
   # Вынести в общий метод базового класса или утилиту
   ```

### 2.5 Исправление импортов внутри функций

**Проблема:** В `bot/routers/chat.py` (строки 260-298) импорты делаются внутри вложенных функций.

Обнаруженные проблемы:
- Строка 268: `from expenses.models import Expense` (внутри функции)
- Строка 269: `from datetime import timedelta` (внутри функции)
- Строка 277: `from asgiref.sync import sync_to_async` (внутри функции)
- Строка 294: `from expenses.models import Profile` (повторный импорт — уже импортировано на строке 18!)
- Строка 366: `from ..utils.typing_action import TypingAction` (внутри функции)
- Строка 374: `import re` (повторный — уже импортировано на строке 21!)

**Задачи:**
- [ ] Проверить все файлы на импорты внутри функций
- [ ] Перенести импорты в начало файлов (кроме случаев circular imports)
- [ ] Удалить дублирующиеся импорты

---

## Фаза 3: CI/CD (1 неделя)

### 3.1 Настройка CI/CD (GitHub Actions)

**Единая стратегия:** 3 отдельных workflow с общим подходом к зависимостям.

**Задачи:**
- [ ] Создать `requirements-dev.txt` с dev-зависимостями (ruff, black, mypy, pytest, coverage)
- [ ] Создать `.github/workflows/lint.yml`:
  ```yaml
  name: Lint
  on: [push, pull_request]
  jobs:
    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install -r requirements-dev.txt
        - run: ruff check .
        - run: black --check .
  ```
- [ ] Создать `.github/workflows/test.yml`:
  ```yaml
  name: Test
  on: [push, pull_request]
  jobs:
    test:
      runs-on: ubuntu-latest
      services:
        postgres:
          image: postgres:15
          env: { POSTGRES_DB: test_db, POSTGRES_USER: test_user, POSTGRES_PASSWORD: test_pass }
          ports: ['5432:5432']
        redis:
          image: redis:7
          ports: ['6379:6379']
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install -r requirements.txt -r requirements-dev.txt
        - run: pytest --cov=bot --cov=expenses --cov-report=xml
  ```
- [ ] Создать `.github/workflows/typecheck.yml`:
  ```yaml
  name: Type Check
  on: [push, pull_request]
  jobs:
    mypy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install -r requirements.txt -r requirements-dev.txt
        - run: mypy bot/ --ignore-missing-imports --warn-return-any
  ```
- [ ] Настроить badge покрытия в README

### 3.2 Расширение покрытия тестами

**Текущее состояние:** 8 файлов тестов (6 `test_*.py` + `conftest.py` + `__init__.py`), coverage не измеряется.

**Приоритет тестирования:**

| Модуль | Текущие тесты | Нужны тесты для |
|--------|--------------|-----------------|
| `bot/utils/expense_parser.py` | Есть | Добавить edge cases |
| `bot/services/expense.py` | Нет | create, update, delete, summary |
| `bot/services/category.py` | Нет | create, validate, defaults |
| `bot/services/income.py` | Нет | create, categorize |
| `bot/services/subscription.py` | Нет | check, activate, expire |
| `bot/services/household.py` | Нет | invite, join, leave |
| `bot/utils/validators.py` | Нет | Все валидаторы |
| `expenses/models.py` | Нет | Model constraints |

**Задачи:**
- [ ] Включить coverage в pytest.ini (`--cov=bot --cov=expenses`)
- [ ] Измерить текущий % покрытия
- [ ] Написать тесты для `bot/services/expense.py` (самый критичный)
- [ ] Написать тесты для `bot/services/category.py`
- [ ] Добавить интеграционные тесты для основных сценариев
- [ ] Цель: 60% coverage к концу фазы

---

## Фаза 4: Улучшение типизации (1 неделя)

### 4.1 Полная типизация сервисного слоя

**Задачи:**
- [ ] Полная типизация `bot/services/expense.py`
- [ ] Полная типизация `bot/services/category.py`
- [ ] Полная типизация `bot/services/income.py`
- [ ] Типизация возвращаемых значений во всех роутерах
- [ ] Настроить mypy в strict mode для новых файлов

### 4.2 Создание типов и DTO

**Задачи:**
- [ ] Создать `bot/types.py` с TypedDict/dataclass для основных структур:
  ```python
  class ExpenseSummary(TypedDict):
      total: Decimal
      count: int
      currency: str
      categories: list[CategorySummary]

  class CategorySummary(TypedDict):
      name: str
      total: Decimal
      count: int
      percentage: float
  ```
- [ ] Заменить `Dict[str, Any]` на конкретные типы

---

## Фаза 5: Документация и стандарты (1 неделя)

### 5.1 Стандарты разработки

**Задачи:**
- [ ] Создать `CONTRIBUTING.md` с правилами:
  - Стиль кода (ruff, black)
  - Структура коммитов
  - Процесс ревью
  - Как писать тесты
- [ ] Добавить docstrings к публичным функциям без документации
- [ ] Проверить актуальность существующих 69 файлов документации

### 5.2 Архитектурная документация

**Задачи:**
- [ ] Обновить `docs/ARCHITECTURE.md` с текущей структурой
- [ ] Задокументировать data flow (запрос пользователя -> ответ)
- [ ] Описать правила добавления новых роутеров/сервисов

---

## Порядок выполнения и сроки

```
Неделя 1:   [Фаза 1.1-1.3] Линтеры + bare except (28 мест) + хардкод → константы
Неделя 2:   [Фаза 1.4-1.5] Characterization тесты + security/performance аудит
Неделя 3:   [Фаза 2A] Рефакторинг 4 функций >500 строк (с тестами как gate)
Неделя 4-5: [Фаза 2B] Рефакторинг 16 функций 200-500 строк
Неделя 6:   [Фаза 2.4-2.5] Устранение дублей + импорты + [Фаза 3] CI/CD
Неделя 7:   [Фаза 3.2] Тесты для сервисного слоя
Неделя 8:   [Фаза 4] Типизация + [Фаза 5] Документация
            [Фаза 2C] Функции 100-199 строк — по мере касания кода (boy scout rule)
```

**Целевая оценка после фаз 1-5: 8.0/10**
**Целевая оценка после полного 2C: 8.5/10**

---

## Метрики успеха

| Метрика | Сейчас | Цель (фазы 1-5) | Цель (с 2C) |
|---------|--------|:---:|:---:|
| bare except | 28 | 0 | 0 |
| Покрытие тестами | ~5% | 60% | 60% |
| Линтер ошибки | не измерялось | 0 warnings | 0 warnings |
| Функции >500 строк | 4 | 0 | 0 |
| Функции 200-500 строк | 16 | 0 | 0 |
| Функции 100-199 строк | 73 | 73 (boy scout) | 0 |
| Magic numbers | 50+ | 0 | 0 |
| CI/CD pipelines | 0 | 3 (lint, test, typecheck) | 3 |
| PII в логах INFO+ | не проверено | 0 | 0 |
| N+1 запросы | не проверено | 0 | 0 |
| Денежные операции в транзакциях | частично | 100% | 100% |

---

## Ревью Codex (автоматическое)

### Раунд 1 (v3.1)
- **Reviewer:** Codex (session 019c970c)
- **Findings:** 3 HIGH, 3 MEDIUM
- **Status:** Исправления внесены в v4, финальная валидация в раунде 2

### Раунд 2 (v4)
- **Reviewer:** Codex (session 019c970c, resume)
- **Findings:** 1 HIGH (несогласованность чисел), 2 MEDIUM (формулировки), 1 LOW (текст ревью)
- **Status:** Все 4 замечания приняты и исправлены в v4.1

### Раунд 3 (v4.1)
- **Status:** Ожидание ревью...
