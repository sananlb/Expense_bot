# Code Quality Review Plan - Expense Bot

**Дата:** 2026-03-17 (v9.0 - conservative / safety-first, expense router income/category symmetry expanded)
**Проект:** expense_bot (~58,500 строк, ~240 Python файлов)
**Исходная оценка по аудиту:** 5.2/10

---

## Исходный baseline (до начала работ)

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

## Статус выполнения на 2026-03-16

### Уже сделано

- Настроен baseline tooling:
  - добавлены `pyproject.toml`, `requirements-dev.txt`, `.pre-commit-config.yaml`
  - зафиксированы базовые конфиги `ruff`, `black`, `isort`, `mypy`
- Закрыты активные `bare except` в рабочем коде:
  - исправлены high-risk и low/medium-risk места в роутерах, сервисах, utils, view и dev-скриптах
  - silent fallback'и заменены на более узкие исключения или `except Exception as e` с логированием
- Добавлены защитные тесты:
  - `tests/test_safety_fallbacks.py`
  - `tests/test_smoke_critical_flows.py`
  - `tests/test_logging_safety.py`
  - `tests/test_service_create_characterization.py`
  - `tests/test_expense_service.py`
- Стабилизирован test contour:
  - убран ручной `django.setup()` из тестов
  - отключён DB side-effect hook `admin_panel` во время тестов
  - добавлена изоляция test DB и `--reuse-db`
  - устранены проблемы async DB-тестов
- Приведены в соответствие с текущим контрактом тесты number parser:
  - `tests/test_number_parser.py` теперь проверяет реальное intended behavior `convert_words_to_numbers()`
- Начат PII-аудит логов:
  - добавлен privacy-safe helper для логирования
  - очищены batched log points в middleware, parser, formatter, reports, income, expense, tasks, onboarding/privacy flow и related modules
  - дополнительно очищены noisy log chains в `bot/routers/chat.py`, `bot/services/affiliate.py`, `bot/tasks/subscription_notifications.py`, `bot/services/monthly_insights.py`
  - дочищены оставшиеся хвосты в `notification_settings`, `faq_service`, `services/recurring`, `export_service`, `validators`, `blogger_stats`, `commands`, voice/AI service chain и нескольких middleware/router service модулях
  - отдельно закрыты последние telemetry-хвосты в `bot/services/admin_notifier.py` и `bot/services/currency_conversion.py`
  - выполнена финальная repo-wide сверка `INFO+` по типовым утечкам (`telegram_id/chat_id`, raw text, callback payload, referral/utm, суммы)
- Начат inventory по производительности:
  - найдены и исправлены low-risk `N+1` точки в `bot/services/top5.py`, `bot/services/analytics_query.py`, `bot/services/cashback.py`, `bot/services/utm_tracking.py`, `bot/services/expense.py`, `bot/services/export_service.py`, `bot/services/income.py`
  - transaction-hotspots `create_expense` / `create_income` покрыты characterization-тестами и частично стабилизированы
  - `create_expense` / `create_income` переведены на локальный `transaction.atomic()` вокруг основной записи
  - non-critical side effect `clear_expense_reminder()` больше не ломает успешное создание операции
- Запущен мягкий CI baseline:
  - добавлен hard-gate workflow `tests`
  - добавлен informational workflow `quality-baseline` для `ruff` / `black` / `isort` / `mypy`
  - строгие quality gates пока сознательно не включаются: текущий baseline линтеров и typecheck остаётся шумным
  - включён coverage measurement в `pytest.ini`
- Добавлен первый service-test batch для `bot/services/expense.py`:
  - покрыты `get_expenses_by_period`, `update_expense`, `get_expense_by_id`, `delete_expense`
  - выявлен и исправлен latent bug: `get_expenses_by_period()` возвращал coroutine вместо `Dict`
  - добавлены regression/boundary tests для empty period, missing/foreign access и validation paths в `create_expense`
- Добавлен зеркальный service-test batch для `bot/services/income.py`:
  - покрыты `get_incomes_by_period`, `update_income`, `get_income_by_id`, `delete_income`
  - добавлены regression/boundary tests для empty period, missing/foreign access и validation paths в `create_income`
  - отдельно зафиксирован текущий контракт: слишком длинное описание дохода обрезается, а не отклоняется
- Добавлен service-test batch для `bot/services/category.py`:
  - покрыты `create_category`, `get_or_create_category_sync`, `get_user_categories`, `update_category_name`, `get_category_by_id`, `delete_category`
  - зафиксированы idempotency и fallback-контракты для `create_default_categories_sync`
  - добиты category-tail tests: limit contract, user isolation, foreign rename guard, repeat-call idempotency
- Добавлен service-test batch для `bot/services/subscription.py`:
  - покрыты `check_subscription`, `is_trial_active`, `get_active_subscription`, `deactivate_expired_subscriptions`
  - зафиксированы контракты для beta access, trial handling и деактивации премиум-настроек после истечения подписки
  - добавлены boundary-контракты для expired/paid subscription paths, пустой таблицы и профиля без подписок
- Добавлен service-test batch для `bot/services/household.py`:
  - покрыты `create_household`, `generate_invite_link`, `join_household`, `leave_household`
  - зафиксированы контракты для invite rotation, beta/subscription access, disband vs regular leave и household query helpers
  - добит ownership-контракт: пользователь из household A не может вступить в household B по чужому invite
- Добавлен unit-test batch для `bot/utils/validators.py`:
  - покрыты `validate_amount`, `validate_date_format`, `validate_phone_number`, `validate_email`
  - отдельно зафиксированы generic-fallback контракт для нестрокового ввода и нижняя граница `0.01` для `validate_amount`
- Добавлен integration-ish smoke batch для `bot/routers/household.py`:
  - покрыты `household_menu`, `generate_invite`, `process_family_invite`
  - зафиксированы контракты для subscription gate, household settings view, copyable invite link и self-invite guard
- Добавлен integration-ish smoke batch для `bot/routers/reports.py` и `bot/routers/expense.py`:
  - покрыты делегирование `/expenses`, `expenses_month` и `toggle_view_scope_expenses`
  - зафиксированы контракты для report delegation, переключения personal/household scope и guard'а без household
  - дополнительно покрыты `callback_expenses_today`, `callback_show_month_start`, `callback_back_to_summary`, `show_prev_month_expenses`
  - зафиксированы контракты для period navigation, state-based return to summary и year-boundary month rollback
  - дополнительно покрыт `callback_show_diary`
  - зафиксированы контракты для empty personal diary, empty household diary с toggle-кнопкой и guard при `toggle_view_scope_diary` без household
  - дополнительно покрыт happy path `toggle_view_scope_diary`
  - зафиксирован контракт для переключения personal -> household и повторного рендера дневника уже в household-mode
  - дополнительно покрыты `callback_export_month_csv`, `callback_export_month_excel`, `callback_monthly_report_pdf`
  - зафиксированы premium-guard контракты для CSV/XLSX экспорта и duplicate-lock guard для monthly PDF generation
  - дополнительно покрыты state-missing error paths у `callback_export_month_csv` и `callback_export_month_excel`
  - зафиксирован контракт для `export_error` fallback после успешного premium-check при пустом report period в state
  - дополнительно покрыты `callback_monthly_report_csv` и `callback_monthly_report_xlsx`
  - зафиксированы контракты для empty-month fallback и timeout fallback при генерации monthly exports
  - дополнительно покрыты success paths у `callback_monthly_report_csv` и `callback_monthly_report_xlsx`
  - зафиксированы контракты для callback-period parsing, вызова `ExportService` и отправки итогового файла пользователю
  - дополнительно покрыты success paths у `callback_export_month_csv` и `callback_export_month_excel`
  - зафиксированы контракты для чтения report period из state, premium-pass export orchestration и отправки итогового файла пользователю
- Добавлен integration-ish smoke batch для `bot/routers/expense.py`:
  - покрыты `cancel_expense_input`, `edit_expense`, `delete_expense`, `show_edit_menu`, `show_edit_menu_callback`
  - зафиксированы контракты для cancel-flow cleanup, not-found guard paths при редактировании и success/failure веток удаления
  - дополнительно покрыты `edit_cancel`, `edit_back_to_menu`, `show_updated_expense`, `show_updated_expense_callback`
  - зафиксированы контракты для возврата в edit menu, expired/missing-id guard paths и симметричных not-found веток после обновления операции
  - дополнительно покрыты success paths у `show_updated_expense` и `show_updated_expense_callback`
  - зафиксированы контракты для финального рендера обновлённой расходной/доходной карточки и очистки edit-state после успешного обновления
  - дополнительно покрыты success paths у `show_edit_menu_callback`, `edit_field_amount`, `edit_field_description`, `edit_field_category`
  - зафиксированы контракты для рендера edit menu, сохранения `editing_*` в FSM state и построения клавиатур для prompt/category selection
  - дополнительно покрыты `edit_done` и `process_edit_category`
  - зафиксированы контракты для финализации edit-flow, error fallback при чтении обновлённой операции и category-update orchestration
  - дополнительно покрыты success/failure paths у `edit_expense`, `delete_income` и `show_edit_menu`
  - зафиксированы контракты для полного рендера expense/income edit menu, симметричного failure path удаления дохода и message-based edit menu через `send_message_with_cleanup`
  - дополнительно покрыты success/not-found/error paths у `remove_cashback`
  - зафиксированы контракты для сброса cashback, рендера обновлённой карточки без cashback и error fallback при сбое сохранения
  - дополнительно покрыты income/menu symmetry paths у `show_edit_menu_callback`, `edit_field_category`, `process_edit_category`
  - зафиксированы контракты для income edit-menu rendering, no-categories alerts и income category-update orchestration
- Добавлен integration-ish smoke batch для `bot/routers/subscription.py` и `bot/routers/start.py`:
  - покрыты `cmd_subscription`, `show_subscription_menu`, `privacy_decline`, `callback_start`
  - зафиксированы контракты для subscription menu rendering, invoice cleanup, privacy-decline language selection и fallback при неудачном `edit_text`
  - дополнительно покрыты `ask_promocode`, `offer_decline`, `help_main_handler`, `help_back_handler`
  - зафиксированы FSM/menu-контракты для promo flow, help navigation и language-aware offer decline
  - дополнительно покрыты `privacy_accept`, `send_stars_invoice` и `process_subscription_purchase`
  - зафиксированы контракты для privacy-accept onboarding, trial creation, invoice state persistence и offer-before-payment orchestration
  - дополнительно покрыты error paths в `process_promocode`
  - зафиксированы контракты для missing/reused promo code и language-aware возврата в меню подписки
  - дополнительно покрыты success paths в `process_promocode`
  - зафиксированы контракты для days-promo activation, usage recording и сохранения `active_promocode` для discount-promo followup purchase
  - дополнительно покрыт `process_subscription_purchase_with_promo`
  - зафиксированы guard path без `active_promocode`, free-promo purchase без invoice и discounted invoice path с сохранением state
- Начат безопасный вынос реально общих констант:
  - `bot/constants.py` дополнен бизнес-лимитами без нарушения старого import-contract
  - повторяющиеся лимиты и fallback-значения переведены на константы в `bot/services/income.py` и `bot/services/expense.py`
  - сохранена обратная совместимость `get_privacy_url_for()` / `get_offer_url_for()` через тот же модуль
  - добавлены `DEFAULT_TIMEZONE`, `DEFAULT_FOREIGN_CURRENCY_CODE` и helper `get_default_currency_for_language()`
  - дефолты `bot/services/profile.py` переведены на общий constants module без изменения поведения
- Добавлен service-test batch для `bot/services/profile.py`:
  - зафиксированы shared defaults для создаваемого профиля
  - зафиксирован fallback-контракт `toggle_cashback()` для отсутствующего профиля
  - зафиксирован выбор дефолтной валюты по языку в `get_or_create_profile()`
- Исправлен latent bug в `bot/routers/subscription.py`:
  - в `process_promocode()` error paths восстановлен корректный `lang` resolution
  - возврат в меню подписки после promo failure теперь использует язык профиля, а не default fallback
  - в `process_promocode()` исправлен discount-promo flow: `active_promocode` больше не очищается раньше времени до followup purchase

### Текущий подтверждённый результат

- Полный прогон тестов на чистой test DB: `352 passed, 1 skipped`
- Единственный skip ожидаемый: отсутствуют native-библиотеки WeasyPrint в локальном окружении
- Известных регрессий после выполненных изменений не обнаружено
- Проект находится в состоянии `baseline stabilized`
- PII-cleanup подтверждён повторными полными прогонами после нескольких отдельных batched changes
- Финальная repo-wide сверка `INFO+` пройдена; явные raw-ID/raw-text утечки в обычных application logs больше не обнаружены
- Low-risk `N+1` cleanup уже внесён в семь сервисов без изменения пользовательского поведения
- Запуск Phase 3 подготовлен: тестовый CI вынесен в отдельный hard gate, lint/typecheck добавлены как non-blocking baseline jobs
- `quality-baseline` переведён на `changed files` scope:
  - `ruff`, `black`, `isort` запускаются только по изменённым Python-файлам
  - `mypy` запускается только по изменённым файлам в `bot/services`, `bot/routers`, `bot/utils`
  - legacy-wide blocking пока сознательно не включается
- CI baseline зафиксирован локально на текущем scope:
  - `ruff`: 3929 замечаний
  - `black --check`: 216 файлов требуют форматирования
  - `isort --check-only`: 157 файлов с import-order drift
  - `mypy bot/services bot/routers bot/utils`: 886 ошибок
- Текущий coverage baseline по `bot + expenses`: `26%`
- Покрытие `bot/services/expense.py` поднято до `42%`
- Покрытие `bot/services/income.py` поднято до `40%`
- Покрытие `bot/services/category.py` поднято до `42%`
- Покрытие `bot/services/subscription.py` поднято до `61%`
- Покрытие `bot/services/profile.py` поднято до `44%`
- Покрытие `bot/services/household.py` поднято до `75%`
- Покрытие `bot/utils/validators.py` поднято до `84%`
- Покрытие `bot/routers/household.py` поднято до `41%`
- Покрытие `bot/routers/reports.py` поднято до `60%`
- Покрытие `bot/routers/expense.py` поднято до `38%`
- Покрытие `bot/routers/start.py` поднято до `50%`
- Покрытие `bot/routers/subscription.py` поднято до `54%`

### Следующие действия

1. Продолжить недорогие integration batches в `expense` router: оставшиеся callback parsing и соседние not-found/error paths вокруг edit/callback flows, либо переключиться на другой критичный router flow ради более равномерного покрытия
2. Продолжить Фазу 1.3: точечно вынести ещё только действительно общие константы (`DEFAULT_TIMEZONE` и аналогичные), без расширения scope на локальные числа
3. После достижения формальных порогов постепенно переводить CI jobs из informational в blocking
4. Не делать массовый lint/typecheck cleanup по legacy-wide scope без отдельной бизнес-причины

### Что осталось по плану

- **Фаза 1.3:** точечно добрать оставшиеся действительно общие константы; без массового выноса локальных чисел
- **Фаза 1.4:** расширить characterization coverage на следующие рискованные сервисные сценарии до любого заметного рефакторинга
- **Фаза 3:** довести CI от baseline до управляемых gate'ов; changed-file scope уже включён, дальше постепенно ужесточать правила
- **Фаза 4:** инкрементальная типизация основных структур и hot-path сервисов
- **Фаза 5:** документация, стандарты и архитектурные правила

---

## Принципы выполнения (Safety First)

**Главная цель:** улучшать качество без регрессий в работающем продукте.

**Обязательные правила:**
- Не рефакторить стабильный код только ради метрики длины функции
- Любое изменение в критичном коде делать маленькими батчами с возможностью быстрого отката
- Сначала фиксировать текущее поведение тестами, потом менять структуру
- Предпочитать локальные исправления и защитные обёртки вместо глубокой декомпозиции
- Для длинных функций использовать правило: "если не трогаем по бизнес-задаче или багу, не трогаем вообще"

**Go / No-Go для рефакторинга:**
- `GO`: есть characterization/интеграционный тест, понятный выигрыш, маленький объём изменений
- `NO-GO`: нет тестов, функция стабильна в проде, изменение делается только ради длины/красоты кода

---

## Фаза 1: Стабилизация baseline и защитные меры (1-2 недели)

### 1.1 Настройка линтеров и форматтеров в мягком режиме

**Проблема:** Нет единого стиля кода, нет автоматических проверок.

**Задачи:**
- [x] Создать `pyproject.toml` с конфигурацией ruff, black, isort, mypy
- [x] Добавить ruff, black, isort, mypy в requirements-dev.txt
- [x] Первый прогон ruff/mypy — зафиксировать текущие ошибки как baseline, не пытаться исправить всё сразу
- [x] Настроить pre-commit hooks для автоматической проверки
- [x] Ограничить обязательные проверки новыми/изменёнными файлами до стабилизации baseline

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

**Статус:** `выполнено` для активного рабочего кода. Активные `bare except` закрыты; оставшиеся broad-except допустимы только там, где уже есть логирование и безопасный fallback.

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
2. Затем **Средний риск** только там, где можно добавить тест или есть понятный безопасный fallback
3. **Низкий риск** делать в последнюю очередь и только малыми батчами

**Консервативная стратегия:**
- Не переписывать окружающую логику ради исправления `bare except`
- Заменять `except:` на максимально узкие исключения там, где это очевидно
- Если точный тип исключения неочевиден, временно использовать `except Exception as e` с логированием и TODO, а не делать агрессивный рефакторинг
- Для high-risk путей обязательно проверять существующее поведение тестом или ручным smoke-сценарием до и после правки

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

### 1.3 Вынос хардкод-значений в константы только для реально общих значений

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
- [x] Собрать только повторяющиеся и доменно-значимые значения из `bot/services/expense.py` / `bot/services/income.py`
- [x] Дополнить существующий `bot/constants.py` секцией бизнес-лимитов, не ломая старые URL helper'ы
- [ ] Не выносить локальные одноразовые числа, если это ухудшает читаемость
- [x] Заменить хардкод на константы сначала в критичных или часто изменяемых файлах
- [ ] Отдельно проверить, нужны ли ещё безопасные константы для `DEFAULT_TIMEZONE` и других действительно глобальных значений

### 1.4 Characterization тесты и smoke checks для критичных сценариев

**Проблема:** Рефакторинг длинных функций без тестов — высокий риск регрессий.

**Задачи:**
- [ ] Написать characterization тесты для 4 функций Tier 1 (>500 строк):
  - `generate_xlsx_with_charts` — snapshot тест на структуру xlsx
  - `format_function_result` — snapshot тесты для каждого типа результата
  - `handle_text_expense` — E2E тесты основных сценариев парсинга
  - `_add_summary_sheet` — snapshot тест на структуру листа
- [x] Добавить минимальный smoke-набор для основных пользовательских сценариев:
  - `/start` для нового пользователя с privacy gate
  - `privacy_accept`
  - `show_recurring_menu`
  - `show_expenses_summary`
- [x] Добавить safety fallback tests для критичных обработчиков форматирования/аналитики/PDF
- [x] Добавить characterization tests для `create_expense()` / `create_income()` перед review transaction-hotspots
- [x] Настроить CI с этими тестами как quality gate перед изменениями в критичном коде
- [ ] **Правило:** НЕ рефакторить функцию, пока нет хотя бы characterization теста или воспроизводимого smoke-сценария

### 1.5 Аудит безопасности и производительности без массовых переписываний

**Проблема:** CLAUDE.md требует PII-safe логирование, оптимизацию запросов, кеширование. Ниже — формализованные задачи и критерии приёмки.

**Статус:** `закрыто` — logging/PII часть завершена: основные high/noisy points в middleware, reports, income, expense, tasks, onboarding/privacy flow, chat, affiliate, subscription notifications, monthly insights, voice/AI chain и оставшихся service/router хвостах очищены, финальная repo-wide сверка выполнена. Low-risk `N+1` устранены в ключевых сервисах, `create_expense` / `create_income` покрыты characterization-тестами и стабилизированы по side effects. Remaining performance tail зафиксирован как inventory без расширения scope.

**Безопасность:**
- [x] Аудит логов на PII: убедиться что telegram_id, имена, суммы, referral/utm payload'ы не логируются на уровне INFO и выше
- [x] Проверить все `logger.error()` и `logger.warning()` на наличие пользовательских данных
- [x] Добавить sanitize-хелпер для логирования: `log_safe_user(user_id)` → маскирует данные

**Производительность:**
- [~] Аудит N+1 запросов: проверить все циклы с ORM-запросами в `bot/services/`
- [~] Добавить `select_related`/`prefetch_related` где отсутствует
- [~] Проверить Redis-кеширование: что кешируется, что нет, TTL-политика
- [~] Обернуть критичные операции в `transaction.atomic()` (create_expense, create_income)

**Inventory remaining low-priority hotspots:**
- `bot/services/export_service.py`: export/report generation остаётся тяжёлым по CPU/памяти; есть отдельные profile/cashback lookup'и, но это offline/export path, не hot write path
- `bot/routers/expense.py` и `bot/routers/reports.py`: используются lock-key cache записи с фиксированным TTL (`600s`); критичных дефектов инвалидации не найдено, но TTL policy пока не централизована
- `bot/services/notifications.py`, `bot/services/admin_notifier.py`, `bot/services/currency_conversion.py`: кеш используется как dedup/rate-limit и rate cache; политика TTL есть, но не вынесена в единый cache policy document
- `bot/services/expense_functions.py`: остаётся legacy-heavy analytics/read path с большим числом запросов и циклов; не находится на критичном hot write path, поэтому оставлен вне текущего safety-first scope
- Мульти-записные transaction paths уже покрыты в `expense.py`, `income.py`, `household.py`, `settings.py`, `affiliate.py`, `recurring.py`, `reports.py`; remaining single-row updates не дают достаточного выигрыша для дополнительного `atomic()` без бизнес-причины

**Критерии приёмки:**
- Ноль PII в логах уровня INFO+
- Ноль подтверждённых N+1 запросов в основных сценариях
- Все денежные операции в транзакциях

---

## Фаза 2: Точечный рефакторинг только по необходимости (2-4 недели)

**Масштаб проблемы:** 93 функции >100 строк. Это индикатор сложности, но не самостоятельный дефект.

**ВАЖНО:** Рефакторинг начинается ТОЛЬКО после наличия characterization тестов (Фаза 1.4) и только для функций, где ожидаемая польза превышает риск.

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

### 2.1 Подфаза A: Функции >500 строк, но только выбранные кандидаты

**Приоритет — не более 1-2 функций за итерацию.**
**Предусловие:** characterization тесты из 1.4 проходят, есть бизнес-причина менять функцию или высокий риск дальнейшего сопровождения.

| Функция | Файл | Строк | Начало | План рефакторинга |
|---------|------|------:|--------|-------------------|
| `generate_xlsx_with_charts` | `bot/services/export_service.py` | 1 140 | :1210 | Рефакторить только если меняется экспорт или найдены баги; предпочесть extraction без изменения алгоритма |
| `format_function_result` | `bot/services/response_formatter.py` | 852 | :254 | Рефакторить частями по типам результатов, сохраняя текущий текстовый output как контракт |
| `handle_text_expense` | `bot/routers/expense.py` | 844 | :1239 | Очень высокий риск; не трогать без сильной бизнес-необходимости и E2E тестов |
| `_add_summary_sheet` | `bot/services/export_service.py` | 757 | :451 | Рефакторить только вместе с тестами на xlsx-структуру |

**Рекомендация:** начать не с самой большой функции, а с той, где меньше зависимостей и лучше тестируемость.

### 2.2 Подфаза B: Функции 200-500 строк только при касании кода

**Не обязательная волна.** Эти функции не являются самостоятельным блокером, если проект стабилен.

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

### 2.3 Подфаза C: Функции 100-199 строк (не целевой scope)

**73 функции.** Не блокирует разработку. Не ставить отдельную задачу "сделать <100 строк". Улучшать только по `boy scout rule`.

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

### 2.4 Устранение дублирования кода только в безопасных паттернах

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

### 2.5 Исправление импортов внутри функций только после проверки на circular imports

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

## Фаза 3: CI/CD и quality gates (1 неделя)

**Статус:** тестовый hard gate уже включён, informational quality baseline jobs добавлены, coverage baseline измерен; `quality-baseline` уже ограничен changed-file scope, обязательные lint/typecheck gates ещё не ужесточались.

### 3.1 Настройка CI/CD (GitHub Actions)

**Единая стратегия:** hard-gate для тестов + informational baseline jobs для качества, без агрессивного блокирования legacy-шумом.

**Критерий перевода `quality-baseline` в blocking:**
- Сначала checks ограничены `changed files` или заранее выбранным безопасным scope, а не всем legacy-репозиторием
- На этом scope `ruff`, `black --check` и `isort --check-only` дают `0` замечаний в течение как минимум 10 последовательных локальных/CI прогонов
- `mypy` на gated scope снижен до `<= 50` ошибок и не растёт в течение 2 недель
- `tests` hard gate и критичные smoke/service tests остаются зелёными без новых флаки-падений

**Задачи:**
- [x] Создать `requirements-dev.txt` с dev-зависимостями (ruff, black, mypy, pytest, coverage)
- [x] Добавить workflow для тестов (`.github/workflows/tests.yml`)
- [x] Добавить workflow для baseline quality checks (`.github/workflows/quality-baseline.yml`)
- [x] Ограничить `quality-baseline` changed-file scope до стабилизации legacy baseline
- [ ] Настроить badge покрытия в README
- [ ] Добавить запуск smoke/characterization тестов как обязательный gate для PR с изменениями в критичном коде

### 3.2 Расширение покрытия тестами без погони за процентом ради процента

**Текущее состояние:** coverage измеряется, текущий baseline `22%` по `bot + expenses`, сервисный слой и первые router smoke batches уже добавлены.

**Приоритет тестирования:**

| Модуль | Текущие тесты | Нужны тесты для |
|--------|--------------|-----------------|
| `bot/utils/expense_parser.py` | Есть | Добавить edge cases |
| `bot/services/expense.py` | Есть расширенный service batch | расширить summary / search / household paths |
| `bot/services/category.py` | Есть service batch | keyword/default-language paths |
| `bot/services/income.py` | Есть расширенный service batch | categorize / category-management / report paths |
| `bot/services/subscription.py` | Есть service batch | require_subscription / button / message paths |
| `bot/services/household.py` | Есть service batch + router smoke | deeper household/report integration paths |
| `bot/utils/validators.py` | Есть unit batch | parse/edge paths уже частично покрыты, дальше только при касании |
| `expenses/models.py` | Нет | Model constraints |

**Задачи:**
- [x] Включить coverage в pytest.ini (`--cov=bot --cov=expenses`)
- [x] Измерить текущий % покрытия
- [x] Написать тесты для `bot/services/expense.py` (самый критичный)
- [x] Написать тесты для `bot/services/category.py`
- [x] Написать тесты для `bot/services/subscription.py`
- [x] Написать тесты для `bot/services/household.py`
- [x] Написать тесты для `bot/utils/validators.py`
- [ ] Добавить интеграционные тесты для основных сценариев
- [ ] Не поднимать coverage искусственно тестами на тривиальный код
- [ ] Цель: сначала покрыть критичные сценарии, потом наращивать общий %

---

## Фаза 4: Инкрементальная типизация (1 неделя)

### 4.1 Полная типизация сервисного слоя

**Задачи:**
- [ ] Полная типизация `bot/services/expense.py` только если не вызывает каскадных правок по всему проекту
- [ ] Типизировать новые и активно изменяемые участки в первую очередь
- [ ] Типизация возвращаемых значений во всех роутерах только для затронутых файлов
- [ ] Настроить mypy strict mode только для новых файлов/отдельных модулей, а не для всего проекта сразу

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

## Фаза 5: Документация и стандарты

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
Неделя 1:   [Фаза 1.1-1.2] Baseline линтеров + исправление bare except + стабилизация test contour  [выполнено]
Неделя 2:   [Фаза 1.4] Safety fallback tests + первые smoke tests + очистка test suite            [выполнено]
Неделя 3:   [Фаза 1.5 + 1.3] PII audit логов + первые общие константы + inventory N+1 hotspots    [выполнено]
Неделя 4:   [Фаза 3] CI/CD и quality gates                                                     [в процессе, baseline собран]
Неделя 4-5: [Фаза 2.1] Не более 1-2 рефакторингов Tier 1 или Tier 2, только при наличии бизнес-причины
Неделя 6:   [Фаза 2.4-2.5] Безопасные устранения дублей + импорты без circular regressions
Неделя 7:   [Фаза 3.2] Тесты для сервисного слоя
Неделя 8:   [Фаза 4-5] Инкрементальная типизация + документация
Постоянно:   Функции 100-199 строк — только по мере касания кода (boy scout rule)
```

**Целевая оценка после фаз 1-5: 7.5-8.0/10 без существенных регрессий**
**Приоритет выше оценки:** сохранить стабильность прод-поведения

---

## Метрики успеха

| Метрика | Сейчас | Цель (фазы 1-5) | Цель (с 2C) |
|---------|--------|:---:|:---:|
| bare except | 0 | 0 | 0 |
| Покрытие тестами | smoke + safety + characterization + expense/income/category/subscription/profile/household service batches + household/reports/expense/subscription/start router smoke + validators unit batch, `295 passed / 1 skipped`, coverage `24%` | Критичные сценарии покрыты | 40-60% |
| Линтер ошибки | baseline зафиксирован: `ruff 3929`, `black 216 files`, `isort 157 files`, `mypy 886`; jobs уже добавлены и ограничены changed-file scope, legacy scope ещё шумный | baseline зафиксирован, новые не добавляются | 0 warnings |
| Функции >500 строк | 4 | 2-4 (только если безопасно) | 0-2 |
| Функции 200-500 строк | 16 | без обязательной цели | по мере касания |
| Функции 100-199 строк | 73 | 73 (boy scout) | по мере касания |
| Magic numbers | критичные дубли в core services уже частично вынесены; profile defaults тоже синхронизированы через constants | критичные вынесены | 0 |
| CI/CD pipelines | `tests` hard gate + `quality-baseline` informational jobs | 3 (lint, test, typecheck) | 3 |
| PII в логах INFO+ | основной audit batched cleanup выполнен, финальная repo-wide сверка пройдена | 0 | 0 |
| N+1 запросы | low-risk точки в `top5` / `analytics_query` / `cashback` / `utm_tracking` / `expense` / `export_service` / `income` уже сняты; остаётся формальный inventory tail | 0 подтверждённых в основных сценариях | 0 |
| Денежные операции в транзакциях | частично: `create_expense` / `create_income` уже под локальным `atomic()`, остальные hotspots ещё не проверены | 100% | 100% |
| Регрессии в основных сценариях | 0 известных после текущего батча | 0 известных регрессий | 0 |

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
