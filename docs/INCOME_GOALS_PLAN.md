# План реализации: Цели по доходам (зеркало лимитов трат)

**Статус:** Реализовано 2026-06-14
**Дата:** 2026-06-14
**Связан с:** [CATEGORY_LIMITS_PLAN.md](CATEGORY_LIMITS_PLAN.md) — зеркальная фича для расходов

---

## 0. Что уже реализовано по расходам (рабочий референс)

Фича лимитов трат завершена и работает локально. Реализатор целей по доходам должен
зеркалить именно это фактическое состояние (со всеми доработками сессии 2026-06-14).
Ниже — карта готовых компонентов и принятых решений, на которые опираться.

### 0.1 Модель и сервис (референс для зеркала)

- Модель `Budget` — [expenses/models.py:520](../expenses/models.py) (`db_table='expenses_budget'`):
  `profile`, `category` (FK на `ExpenseCategory`, nullable = общий лимит), `amount`,
  `currency`, `period_type`, `start_date`, `end_date`, `is_active`, два частичных
  `UniqueConstraint` (per-category и total), индекс `(profile, is_active)`.
- Миграция [0063_budget_currency_and_more.py](../expenses/migrations/0063_budget_currency_and_more.py):
  AddField currency → RunPython нормализация legacy → AddIndex → 2 AddConstraint.
  **Для доходов data-миграция НЕ нужна** (таблица создаётся с нуля).
- Сервис [bot/services/budget.py](../bot/services/budget.py): `get_limit`, `set_limit`,
  `remove_limit`, `get_limit_status`, `get_active_limits_map`, `get_expense_limit_statuses`.
  `LimitStatus(budget, spent, percent, exceeded, crossed_thresholds)`.
  - `set_limit`: проверка подписки → `transaction.atomic` + `select_for_update` по
    **Profile** (не по Budget — иначе нет lock при отсутствии активной строки) →
    деактивация ВСЕХ активных строк этого типа (вкл. не-monthly) → create → retry на IntegrityError.
  - `_build_status`: `crossed_thresholds` считается только если трата влияет на текущий
    месяц этого лимита (совпадение profile_id + currency + месяц + (для категории) category_id).
  - Пороги: `CATEGORY_LIMIT_THRESHOLDS=[100]`, `TOTAL_LIMIT_THRESHOLDS=[80,100]`.
    → **Для целей дохода у обоих видов будет `[100]`** (только достижение).

### 0.2 Отображение — [bot/utils/budget_display.py](../bot/utils/budget_display.py)

- Категорийная шкала: `▰`/`▱`, **10 сегментов**, `format_category_bar_line` →
  `▰▰▰▱▱ 72%`, при ≥100% добавляет ` 🔴` и полную шкалу.
- Общая шкала (после доработки 2026-06-14): `■`/`□`, **14 сегментов**,
  `format_total_bar_line` → `■■■■□□ 80%` — **БЕЗ статусного эмодзи справа** (кружок убран).
- `_render_bar(percent, filled, empty, segments)` — общий рендер, floor-заполнение.
- `format_limit_screen_body(status, lang)` — тело экрана (лимит/потрачено/остаток/дни).
- `days_left_in_month`, `format_days_left` (RU-склонения).
- `status_emoji(percent)` — оставлен, но в общей шкале больше НЕ используется.

### 0.3 UI лимитов

- **Категория (расход):** карточка [categories.py:~796](../bot/routers/categories.py) —
  кнопка `cat_limit_{id}` с текстом 🚦; экран/FSM:
  `cat_limit_entry`, `cat_limit_edit_`, `cat_limit_remove_`,
  состояние `CategoryForm.waiting_for_limit_amount` (categories.py:39).
- **Общий (настройки):** кнопка `total_limit` в `settings_keyboard`
  ([keyboards.py:28](../bot/keyboards.py), `adjust(1×8)`); экран/FSM в
  [settings.py:212+](../bot/routers/settings.py), состояние
  `SettingsStates.waiting_for_total_limit_amount` (settings.py:31). Экран общей —
  без цифр, объяснение курсивом с 💡.
- Тексты — [bot/texts.py](../bot/texts.py) блоки «Лимиты трат» и «Общий лимит трат»,
  RU+EN. Эмодзи лимитов = **🚦** (и категорийные, и общий — доработка 2026-06-14).

### 0.4 Процент в подтверждении траты

- [bot/utils/expense_messages.py:~78](../bot/utils/expense_messages.py) в
  `format_expense_added_message` — `get_limit_status(...)` и `(72%)` / `(107% 🔴)`
  после названия категории. **Зеркало для доходов — в той же `format_income_added_message`.**

### 0.5 Шкалы в обзоре месяца — [reports.py:show_expenses_summary](../bot/routers/reports.py)

- Хелперы `_limit_percent(spent, limit)` и `_summary_spent_in_currency(summary, currency)`.
- `report_limits = get_active_limits_map(...)` грузится один раз, только при
  `period=='month' and not household_mode`, фильтр по `start_date` месяца.
- Общая шкала — строкой под «💸 Расходы: …».
- Категорийные шкалы — под каждой категорией с лимитом.
- **Доработка отступов 2026-06-14:** введён единый цикл по `shown_categories`,
  локальный хелпер `_category_budget_for(cat)`, флаг `any_category_bar`:
  пустая строка после заголовка «Траты по категориям» если есть хоть одна шкала +
  пустая строка после каждой категории со шкалой. **То же зеркалить для income-секции.**

### 0.6 Уведомления — [bot/utils/budget_notifications.py](../bot/utils/budget_notifications.py)

- `get_expense_limit_alert_messages` + `send_expense_limit_alerts(bot, chat_id, expense, ...)`.
- Для общего лимита при пересечении и 80% и 100% одной тратой шлётся **только старший** (100%).
- Точки вызова: [expense.py](../bot/routers/expense.py) — 3 места ручного ввода (строки
  ~1225, ~2009, ~2144); recurring — [celery_tasks.py:_send_recurring_operation_notification](../expense_bot/celery_tasks.py)
  (для income сейчас alert НЕ шлётся — добавить для целей).

### 0.7 КРИТИЧНЫЙ урок: порядок роутеров (баг сессии 2026-06-14)

Ввод суммы лимита сначала перехватывался хендлером трат и записывался как трата.
Причины и фиксы (оба нужны, зеркалить для доходов):
1. **Порядок в [main.py](../bot/main.py):** все FSM-роутеры должны быть подключены
   **ДО `expense_router`**. `settings_router` был после — перемещён выше (строка ~227).
   Когда expense-хендлер делает `return` на skip-state, aiogram прекращает обход
   роутеров, и до роутера ниже управление не доходит.
2. **`skip_states` в [expense.py:1301+](../bot/routers/expense.py):** добавлены
   `CategoryForm:waiting_for_limit_amount` и `SettingsStates:waiting_for_total_limit_amount`
   (защитный слой, чтобы трата не записывалась даже если порядок изменят).
3. **Также проверить обработчик ТЕКСТА ДОХОДОВ** — если он перехватывает произвольный
   текст, новые состояния целей нужно добавить и в его skip-логику.

### 0.8 Тесты и проверки (эталон)

- [tests/test_budget_limits.py](../tests/test_budget_limits.py) — 27 тестов: set/remove,
  подписка, чужая категория, floor-процент, пороги, пересечение обоих, backdated,
  мультивалюта, проценты в сообщении, admin-регистрация. Тесты НЕ привязаны к глифам шкал.
- `manage.py check`, `makemigrations --check --dry-run`, `pytest -q tests` (424 passed, 1 skip).

---

## 1. Суть фичи

Зеркало лимитов трат, но для доходов и с обратной семантикой: лимит = «не превышай»,
**цель = «достигни»**. Вся терминология в UI — «**Цель**» (RU) / «**Goal**» (EN).

Два вида месячных целей:

1. **Цель по категории дохода** («Зарплата: 100 000 ₽/мес») — процент в подтверждении дохода,
   шкала в обзоре месяца, уведомление при достижении 100%.
2. **Общая цель дохода** («150 000 ₽/мес») — устанавливается в настройках, шкала в обзоре
   месяца, уведомление при достижении 100%.

Цель **информирует, а не ограничивает** — доход записывается всегда.

### Зафиксированные решения (пользователь, 2026-06-14)

1. Полное зеркало: категорийные цели + общая цель.
2. Уведомление **только при 100%** (цель достигнута) — для обоих видов. Нет порога 80%.
3. **Эмодзи целей = 🎯** (мишень — прямая ассоциация со словом «цель»). Это сознательно
   ОТЛИЧАЕТСЯ от эмодзи лимитов трат (🚦 светофор): пользователь по эмодзи сразу
   различает «лимит = не превышай» (🚦) и «цель = достигни» (🎯). Эмодзи 🎯 используется
   в кнопках, заголовках экранов и подсказках ввода — везде, где у лимитов стоит 🚦.
   Статусный эмодзи ДОСТИЖЕНИЯ — 🎉 при 100% (вместо 🔴 у лимитов: достижение цели —
   позитивное событие, а не тревога).
4. Терминология «Цель»/«Goal» везде (никаких «лимит»/«limit» в income-ветке).

---

## 2. Модель данных

### Новая модель `IncomeBudget` (зеркало `Budget`)

`Budget` жёстко завязан на `ExpenseCategory` и таблицу `expenses_budget` с двумя
unique-constraint по расходам — переиспользовать нельзя. Создаём отдельную модель,
полностью симметричную.

```python
class IncomeBudget(models.Model):
    """Цели по доходам: на категорию (category заполнена) либо общая цель на все
    доходы профиля (category IS NULL). Информирует, не ограничивает."""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='income_budgets')
    category = models.ForeignKey(IncomeCategory, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='RUB')
    period_type = models.CharField(max_length=20, choices=[...], default='monthly')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'incomes_income_budget'
        constraints = [
            UniqueConstraint(fields=['profile','category'],
                condition=Q(is_active=True)&Q(category__isnull=False),
                name='unique_active_income_goal_per_category'),
            UniqueConstraint(fields=['profile'],
                condition=Q(is_active=True)&Q(category__isnull=True),
                name='unique_active_total_income_goal_per_profile'),
        ]
        indexes = [models.Index(fields=['profile','is_active'])]
```

### Семантика legacy-полей — как в Budget

| Поле | v1 |
|---|---|
| `period_type` | Всегда `'monthly'`. |
| `start_date` | Дата установки. Для месяцев раньше шкала не показывается. |
| `end_date` | Всегда `NULL`. |
| `is_active` | `False` = цель убрана. |
| `currency` | ISO-код валюты профиля на момент установки. В прогресс попадают только доходы с совпадающей валютой. |

### Миграция

Новая таблица создаётся с нуля — data-миграция не нужна (в отличие от Budget, где
была legacy-таблица). Просто `CreateModel` + constraint + индекс.

---

## 3. UI

### 3.1 Карточка категории дохода (`categories.py:edit_income_category`)

Добавить кнопку (сейчас только Название + Иконку):
```
[ 📝 Название ]
[ 🎨 Иконку  ]
[ 🎯 Цель: 100 000 ₽/мес ]   ← НОВОЕ (без цели: «🎯 Установить цель»)
[ ← Назад ] [ ✖ Закрыть ]
```
Callback: `inc_goal_{cat_id}`. **Важно:** не пересекаться с `cat_limit_` (расходы).

### 3.2 Экран цели категории (если установлена)

```
🎯 Цель для категории
💼 Зарплата

Цель:       100 000 ₽ в месяц
Получено:    72 000 ₽ (72%)
Осталось:    28 000 ₽
До конца месяца: 18 дней

[ ✏️ Изменить цель ]
[ 🗑 Убрать цель   ]
[ ← Назад ] [ ✖ Закрыть ]
```
«Осталось» = сколько ещё до цели (может быть 0 при достижении).

### 3.3 Ввод суммы (FSM)

Состояния: `IncomeCategoryForm.waiting_for_goal_amount` (категория),
`SettingsStates.waiting_for_total_goal_amount` (общая).
Парсинг — тот же `parse_description_amount` + `convert_words_to_numbers`.
Валидация — в сервисе (`ValueError`). Голосовой ввод — как везде.

**КРИТИЧНО (урок из лимитов):** оба FSM-роутера должны быть подключены в `main.py`
**ДО** `expense_router`. `category_router` уже до expense (ок для категорийной цели).
`settings_router` уже перемещён до expense (ок для общей цели). Дополнительно
добавить новые состояния в `skip_states` хендлера трат `expense.py` как защитный слой.
**Также** добавить в `skip_states` обработчика доходов, если таковой перехватывает текст.

### 3.4 Общая цель: меню настроек

Кнопка в `settings_keyboard` под «🚦 Лимит трат», callback `total_goal`:
```
[ 🚦 Лимит трат ]
[ 🎯 Цель дохода ]   ← НОВОЕ
[ 🏠 Семейный бюджет ]
```
`keyboard.adjust(...)` обновить на 9 рядов.

Экран общей цели — **без цифр**, объяснение курсивом с 💡 (как у общего лимита):
прогресс в «Бюджете», уведомление при 100%, категорийные цели в меню «Категории доходов».

### 3.5 Процент в подтверждении дохода (только категорийная цель)

В `format_income_added_message` (`bot/utils/expense_messages.py`) — процент после
названия категории: `💼 Зарплата (72%)`. При достижении: `💼 Зарплата (100% 🎉)`.
Floor-округление. Общая цель в подтверждении дохода **не показывается**.

### 3.6 Шкалы в обзоре месяца (`reports.py`, income-секция)

Сейчас у доходов в обзоре месяца шкал НЕТ — добавить:
- **Общая цель** — крупная шкала под строкой «💰 Доходы: …» (квадраты `■`/`□`, 14 сегм.,
  без статусного эмодзи — единый стиль с общим лимитом после правок 2026-06-14).
- **Категорийная цель** — шкала `▰`/`▱` (10 сегм.) под категорией дохода + процент.
  При достижении 100% — 🎉 вместо 🔴 (у целей достижение — позитив).
- Отступы — те же правила, что добавлены для расходов: пустая строка после заголовка
  «Доходы по категориям» если есть хоть одна шкала; пустая строка после категории со шкалой.
- В семейном режиме (`household_mode`) шкалы скрыты.
- Источник сумм — уже посчитанный `by_income_category`; один запрос активных целей.

**⚠️ ВАЖНАЯ АСИММЕТРИЯ currency (проверено в коде 2026-06-14):**
В отличие от расходов, income-агрегация single-currency:
- `by_income_category` (формируется в [bot/services/expense.py:439-467](../bot/services/expense.py))
  даёт элементы вида `{'id', 'name', 'icon', 'total', 'count'}` — **`total` это одна
  сумма `Sum('amount')` БЕЗ разбивки по валютам** (у расходов — `amounts` dict per-currency).
- `summary` доходов содержит `income_total` (единая сумма), без `currency_totals` для доходов.
- В reports.py income-строки печатаются как `format_amount(cat['total'], summary['currency'], lang)`.

Следствия для целей:
- Для шкал нужен **точный per-currency прогресс**. Смешанная сумма всех валют может
  показать достижение цели в обзоре, хотя сервис и уведомление корректно не считают
  доход в другой валюте. Такой рассинхрон в UI неприемлем.
- `_get_income_summary` дополняется внутренними полями:
  `income_currency_totals: dict[currency, Decimal]` для общей цели и
  `amounts: dict[currency, Decimal]` в каждом элементе `by_income_category`.
  Существующие `income_total`, `total` и текущий пользовательский вывод доходов
  не меняются — новые поля используются только шкалами целей.
- **В сервисе `income_goal.py`** агрегация для `GoalStatus.received` и `crossed_thresholds`
  ВСЕГДА фильтрует по `currency == goal.currency` (как у Budget) — там точность важна
  для уведомлений.

### 3.7 Уведомление о достижении (только 100%)

```
🎉 Цель достигнута!

💼 Зарплата
Цель: 100 000 ₽
Получено: 105 000 ₽ (105%)
```
И общая:
```
🎉 Цель по доходу достигнута!

Цель: 150 000 ₽
Получено: 152 000 ₽ (101%)
```
Механика пересечения порога 100% — идентична лимитам: `received_before < limit <= received_after`,
только если доход попадает в текущий месяц и совпадает по валюте. `crossed_thresholds = [100]`
для обоих видов цели. Точки отправки: ручной ввод дохода (`expense.py` income-ветки) и
recurring-доход (`celery_tasks._send_recurring_operation_notification`, ветка income —
сейчас там alert НЕ шлётся, добавить вызов для целей).

### 3.8 Что НЕ делаем в v1

- Порог 80% для целей (по решению — только 100%).
- Цели в PDF/CSV/XLSX отчётах.
- Недельные/дневные периоды, rollover.
- Учёт доходов членов семьи; история изменений суммы цели.

---

## 4. Сервисный слой

Новый файл `bot/services/income_goal.py` — зеркало `bot/services/budget.py`:

```python
async def get_goal(profile_id, category_id) -> IncomeBudget | None
async def set_goal(profile_id, category_id, amount) -> IncomeBudget
async def remove_goal(profile_id, category_id) -> bool
async def get_goal_status(profile_id, category_id, income=None) -> GoalStatus | None
async def get_active_goals_map(profile_id) -> dict
async def get_income_goal_statuses(profile_id, income) -> dict  # категория+общая за один блок
```
- Агрегация `Sum('amount')` по `Income`, profile + currency цели + календарный месяц по `income_date`.
- `set_goal`: проверка подписки, валидация владельца категории дохода, транзакция +
  `select_for_update` по Profile + деактивация активных + retry на IntegrityError.
- `GoalStatus`: `received`, `percent` (floor), `achieved` (received >= amount),
  `crossed_thresholds` (= [100] при пересечении).
  `remaining = max(amount - received, 0)` — после достижения не показываем
  отрицательный остаток.
- Все ORM — внутри одного `@sync_to_async` блока с `select_related` (async_patterns).

---

## 5. Изменяемые файлы

| Файл | Изменение |
|---|---|
| `expenses/models.py` | новая модель `IncomeBudget` |
| `expenses/migrations/00XX_*.py` | CreateModel + constraint + индекс |
| `bot/services/income_goal.py` | **новый** — бизнес-логика целей |
| `bot/utils/income_goal_display.py` | шкалы/экран цели |
| `bot/utils/income_goal_notifications.py` | **новый** — уведомления о достижении |
| `bot/routers/categories.py` | кнопка/экран/FSM цели категории дохода |
| `bot/keyboards.py` | кнопка «🎯 Цель дохода» в settings_keyboard |
| `bot/routers/settings.py` | экран общей цели + FSM |
| `bot/utils/expense_messages.py` | процент в `format_income_added_message` |
| `bot/routers/reports.py` | шкалы целей в income-секции |
| `bot/routers/expense.py` | уведомления о достижении (income-ветки) + skip_states |
| `expense_bot/celery_tasks.py` | уведомление для recurring-дохода |
| `bot/texts.py` | тексты RU/EN (~22 ключа) |
| `expenses/admin.py` | регистрация IncomeBudget |
| `tests/test_income_goals.py` | **новый** |

---

## 6. Порядок реализации

1. Модель `IncomeBudget` + миграция.
2. Сервис `income_goal.py` + тесты (включая `crossed_thresholds=[100]`).
3. Процент в `format_income_added_message` + тесты.
4. UI категорийной цели (карточка дохода + экран + FSM).
5. UI общей цели (настройки + экран + FSM).
6. Шкалы в income-секции обзора месяца.
7. Уведомления: ручной доход + recurring-доход.
8. Тексты RU/EN, админка.
9. Ручное тестирование: установка/изменение/удаление, достижение 100%
   (вкл. повторное), мультивалюта, доходы задним числом, пролистывание месяцев,
   семейный бюджет, истёкшая подписка, **проверка что доход не пишется при вводе суммы цели**.

---

## 7. Проверенные риски и решения

1. **Callback-неймспейс:** используются отдельные префиксы `inc_goal_`,
   `inc_goal_edit_`, `inc_goal_remove_`; более длинные обработчики регистрируются раньше.
2. **Мультивалюта в обзоре:** `_get_income_summary` получает дополнительные
   per-currency агрегаты только для шкал целей; существующий вывод сумм не меняется.
3. **Перехват ввода суммы:** `category_router` и `settings_router` уже подключены до
   `expense_router`; оба новых состояния также добавляются в `expense.py:skip_states`.
   Отдельного конкурирующего income-роутера нет — доходы обрабатываются внутри того же
   универсального `expense_router`.
4. **Эмодзи достижения:** решение зафиксировано пользователем — 🎉 при 100%.

---

## 8. Результат реализации

Реализованы категорийные и общая месячные цели по доходам:

- модель `IncomeBudget` и миграция `0064_income_budget.py`;
- сервис с транзакционной заменой цели, проверкой подписки и точным учётом валюты;
- UI категорийной цели и общей цели в настройках, включая текстовый и голосовой ввод;
- процент цели в карточке добавленного дохода;
- точные per-currency шкалы в месячном обзоре, скрытые в household-режиме;
- уведомления при первом пересечении 100% для ручных и recurring-доходов;
- RU/EN тексты и регистрация модели в Django Admin;
- защитные FSM skip-state для обоих сценариев ввода суммы.

Проверки:

- `python manage.py check` — без ошибок;
- `python manage.py makemigrations --check --dry-run` — изменений нет;
- `pytest -q tests` — **441 passed, 1 skipped**;
- `ruff` по новым модулям и миграции — без ошибок.
