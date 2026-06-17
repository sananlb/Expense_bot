# Меню «🧰 Инструменты» — Implementation Plan

**Статус:** Plan (готов к ревью, реализация не начата)
**Дата:** 2026-06-15
**Автор:** Claude

## 1. Цель

Разгрузить перегруженное меню настроек. Вынести функции **Кешбэк, Повторяющиеся
платежи, Лимит трат, Цель дохода, Семейный бюджет** в отдельное меню
«🧰 Инструменты», доступное по команде `/tools`.

Дополнительно:
- убрать у кешбэка тумблер вкл/выкл — кнопка кешбэка всегда отображается в
  «Инструментах»;
- **сделать кешбэк бесплатным для всех** — снять гейт подписки с функционала
  кешбэка (управление, расчёт, трекинг). Голосовой ввод в кешбэке остаётся
  премиумом — его не трогаем.

## 2. Зафиксированные решения (из диалога с пользователем)

1. **Точка входа:** только команда `/tools` (без кнопки «Инструменты» в настройках).
2. **Старые команды:** убрать `/cashback` и `/recurring` из списка команд Telegram.
   Обработчики `Command("cashback")` / `Command("recurring")` оставить рабочими
   (на случай прямого ввода).
3. **Лимиты:** перенести обе кнопки — 🚦 общий лимит трат (`total_limit`) и
   🎯 общая цель дохода (`total_goal`).
4. **Кешбэк:** убрать вкл/выкл, всегда показывать в «Инструментах».
5. **Кешбэк бесплатный для всех:** снять гейт подписки с кешбэка (управление,
   расчёт, трекинг). Голосовой ввод остаётся премиумом.

## 3. Итоговая структура

### 3.1 Команды бота (Telegram menu)
```
📊 Расходы          /expenses
📁 Категории        /categories
🧰 Инструменты      /tools        ← новая
⭐ Подписка         /subscription
⚙️ Настройки        /settings
📖 Информация       /start
```
Убраны: `/cashback`, `/recurring`.

### 3.2 Меню «🧰 Инструменты» (callback `tools`)
Порядок кнопок (зафиксирован пользователем):
```
🔄 Ежемесячные операции   → callback "recurring_menu"  (существует)
🚦 Лимит трат             → callback "total_limit"     (существует)
🎯 Цель дохода            → callback "total_goal"      (существует)
💳 Кешбэк                 → callback "cashback_menu"   (существует, после снятия гейтов)
🏠 Семейный бюджет        → callback "household_budget"(существует)
❌ Закрыть                → callback "close"
```

### 3.3 Меню «⚙️ Настройки» после чистки (callback `settings`)
```
🌐 Язык
🕐 Часовой пояс
💱 Валюта
🗑 Удалить профиль
❌ Закрыть
```
Убраны: `total_limit`, `total_goal`, `household_budget`, `toggle_cashback`.

## 4. Кешбэк бесплатный для всех — снятие гейтов

Решение пользователя: **кешбэк доступен всем без подписки.** Это снимает всю
сложность вокруг поля `cashback_enabled`.

### Где сейчас кешбэк гейтится (что снять)

1. **Управление кешбэками** — `bot/routers/cashback.py:callback_cashback_menu`
   (стр. 319–330): `check_subscription` → при отсутствии показывает
   `cashback_management_subscription`. **Удалить блок проверки подписки.**
2. **Тумблер `cashback_enabled`** — гейт `if not user_settings.cashback_enabled`:
   - `cashback.py:callback_cashback_menu` (стр. 315–317);
   - `cashback.py:calculate_potential_cashback` (стр. 126–128);
   - `cashback.py:calculate_expense_cashback_sync` (стр. 189–191).
   **Удалить эти проверки** — кешбэк считается/показывается всегда.
3. **Истечение подписки** — `bot/services/subscription.py:deactivate_expired_subscriptions`
   (стр. 124–127) ставит `cashback_enabled = False`. **Убрать отключение кешбэка**
   при истечении подписки (семейный режим `view_scope` оставить как есть).

### Что делаем с полем `cashback_enabled`

- **Оставляем поле в БД** (миграцию не трогаем) — чтобы не плодить миграции и не
  ломать существующие данные/тесты `test_subscription_service.py`,
  `test_profile_service_defaults.py`.
- Сервис `toggle_cashback` в `bot/services/profile.py` **оставляем** (на него
  ссылаются тесты), но из UI он больше не вызывается.
- Поле перестаёт влиять на доступность кешбэка (все проверки сняты, п. 1–3).
  Фактически становится «спящим» — оставлено для обратной совместимости.

**Deprecated-маркировка (Codex L2):** чтобы dead-поле/метод не вводили в
заблуждение — добавить комментарий `# DEPRECATED: cashback всегда доступен,
поле не читается (см. TOOLS_MENU_IMPLEMENTATION_PLAN.md §4)` к
`UserSettings.cashback_enabled` (модель) и к `toggle_cashback` (docstring).
Полное удаление поля/метода (со схемной миграцией) — отдельной задачей позже,
НЕ в этом изменении.

### Что НЕ трогаем

- **Голосовой ввод** в кешбэке (`cashback.py:507,559,770,846`) остаётся под
  подпиской — это отдельная премиум-фича, к самому кешбэку не относится.

### Результат для пользователя

- Кнопка кешбэка всегда видна в «Инструментах».
- Любой пользователь (с подпиской и без) может создавать/смотреть кешбэки, и
  кешбэк учитывается в отчётах (`calculate_potential_cashback`).

## 5. Изменения по файлам

### 5.1 `bot/utils/commands.py`
- `set_bot_commands`: заменить список — убрать `cashback`, `recurring`;
  добавить `tools`. Описание команды — `get_text('tools_menu', lang)` БЕЗ
  дополнительного префикса эмодзи (ключ уже содержит 🧰, см. §5.8 / Codex L3).
- `update_user_commands`:
  - убрать блок `if has_subscription and cashback_enabled: append(/cashback)`;
  - убрать `BotCommand(command="recurring", ...)`;
  - добавить `BotCommand(command="tools", description=get_text('tools_menu', lang))`
    (без `f"🧰 ..."` — эмодзи уже в ключе);
  - убрать чтение `user_settings.cashback_enabled` (больше не нужно для команд);
  - оставить `get_user_settings`/`check_subscription` только если используются
    для других целей (проверить — если нет, удалить импорт).

### 5.2 `bot/keyboards.py`
- **Новая функция** `tools_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup`:
  кнопки в порядке (п. 3.2): `recurring_button` → `recurring_menu`,
  `total_limit_button` → `total_limit`, `total_goal_button` → `total_goal`,
  `cashback_button` → `cashback_menu`, `household_button` → `household_budget`,
  `close`. `adjust(1,1,1,1,1,1)`.
- `settings_keyboard`: убрать кнопки `total_limit`, `total_goal`,
  `household_budget`, `toggle_cashback`. Убрать параметр `cashback_enabled`
  (или оставить для совместимости сигнатуры, но не использовать —
  предпочтительно убрать и поправить вызовы). Пересчитать `adjust` на
  5 кнопок: `adjust(1,1,1,1,1)`.

### 5.3 Новый роутер `bot/routers/tools.py`
```python
router = Router(name="tools")

async def show_tools_menu(event, state, lang):
    # текст-заголовок get_text('tools_menu', lang)
    # reply_markup=tools_keyboard(lang)
    # Message → send_message_with_cleanup; CallbackQuery → edit_text

@router.message(Command("tools"))
async def cmd_tools(message, state, lang='ru'): ...

@router.callback_query(F.data == "tools")
async def callback_tools(callback, state, lang='ru'): ...
```
- Очистка состояния при входе (как в `cmd_settings`:
  `clear_state_keep_cashback`).
- Экспорт роутера в `bot/routers/__init__.py`.

### 5.4 `bot/routers/__init__.py` + `bot/main.py`
- Добавить `tools_router` в импорт `bot/routers/__init__.py`.
- В `bot/main.py` зарегистрировать `dp.include_router(tools_router)` **выше**
  `expense_router` (рядом с `settings_router`).

**Уточнение обоснования (Codex L1):** жёсткий приоритет над `expense_router`
объективно нужен только `settings_router` — у него есть message-хендлеры FSM
ввода суммы (`waiting_for_total_limit_amount`, `waiting_for_total_goal_amount`),
которые иначе проиграли бы широкому текстовому хендлеру трат. `tools_router`
своих FSM message-хендлеров НЕ имеет (только `Command("tools")` и callback),
а слэш-команды сбрасываются `StateResetMiddleware`. Поэтому формально для
`tools_router` позиция некритична, но размещаем его рядом с `settings_router`
выше `expense_router` для консистентности и на будущее. Добавить
dispatcher-level регресс-тест на порядок (см. п. 7).

### 5.5 Точки входа существующих функций
- **Кешбэк (Codex M1):** существующий `callback_cashback_menu`
  (`F.data == "cashback_menu"`) уже делает очистку FSM (`clear_state_keep_cashback`)
  + показ меню. После снятия из него гейтов подписки (п. 5.9) — переиспользовать
  его: на кнопку в Tools повесить `callback_data="cashback_menu"` (НЕ заводить
  новый `cashback` callback без очистки state). Тогда отдельный handler не нужен,
  поведение единообразно. Если по какой-то причине нужен именно `cashback` —
  он должен сначала вызвать `clear_state_keep_cashback(state)`, затем
  `show_cashback_menu`.
  **Итог:** в `tools_keyboard` кнопка кешбэка → `callback_data="cashback_menu"`.
- **Повторяющиеся:** callback `recurring_menu` уже существует — кнопка ведёт на него.
- **Лимит/Цель/Семейный:** callback'и `total_limit`, `total_goal`,
  `household_budget` уже существуют — менять не нужно.

### 5.6 Кешбэк — удаление тумблера из UI
- `bot/routers/settings.py`: удалить хендлер `handle_toggle_cashback`
  (`F.data == "toggle_cashback"`). Удалить чтение `cashback_enabled` в
  `cmd_settings` и `callback_settings`, а также передачу его в `settings_keyboard`.
- **Cleanup (ревью #2 LOW):** после удаления тумблера в `cmd_settings`/
  `callback_settings` могут стать ненужными локальные `get_user_settings(...)`,
  `cashback_enabled`, `has_subscription` — удалить, если больше нигде в этих
  функциях не используются (проверить по месту: `has_subscription`/`view_scope`
  могут ещё участвовать в тексте/семейном режиме — тогда оставить).
- `settings_keyboard`: убрать неиспользуемый параметр `cashback_enabled` из
  сигнатуры и обновить вызовы (см. §5.2).

### 5.9 Кешбэк — снятие гейтов подписки (см. п. 4)
- `bot/routers/cashback.py`:
  - `callback_cashback_menu`: удалить блок `if not user_settings.cashback_enabled`
    (стр. 315–317) и блок проверки подписки `check_subscription` (стр. 319–330).
    Оставить очистку состояния и вызов `show_cashback_menu`.
- `bot/services/cashback.py`:
  - `calculate_potential_cashback`: удалить проверку `cashback_enabled` (126–128).
  - `calculate_expense_cashback_sync`: удалить проверку `cashback_enabled` (189–191).
- `bot/services/subscription.py`:
  - `deactivate_expired_subscriptions`: убрать отключение `cashback_enabled`
    (124–127). Семейный режим `view_scope → personal` оставить.
  - Обновить docstring (стр. 83–86): убрать упоминание отключения кешбэка и
    `/cashback` из команд.
- **`bot/routers/expense.py` (Codex H1 — был пропущен):** кешбэк гейтится
  `has_subscription` в ТРЁХ местах расчёта/сохранения при создании траты —
  стр. ~1185, ~2001, ~2135 (`if has_subscription and currency == user_currency:`).
  Во всех трёх убрать `has_subscription and`, оставив проверку валюты
  `currency == user_currency`. Убрать ставшие лишними строки
  `has_subscription = await check_subscription(...)`, если они больше нигде в
  этой ветке не используются (проверить по месту — `check_subscription` ещё
  нужен для голосового ввода и др., импорт НЕ удалять).
  Кешбэк в отчётах (`calculate_potential_cashback`, стр. 220, 376) гейта не
  имеет — не трогаем.

### 5.10 Кешбэк убрать из маркетинга подписки (Codex H2 — РАСШИРЕНО ревью #2)
Кешбэк больше не премиум — убрать его из ВСЕХ списков преимуществ подписки.
Внимание: используются ДВЕ формулировки — «Кешбэк-трекер» И «Отслеживание
кэшбэка» (искать обе + EN «Cashback tracking»). Полный список мест:

**`bot/routers/subscription.py`:**
- `SUBSCRIPTION_PRICES` (dict): тариф `month` — `description` (стр. ~190) и
  `features` (стр. ~199); тариф `six_months` — `description` (стр. ~212) и
  `features` (стр. ~222). Убрать строку/элемент «💳 Отслеживание кэшбэка».
- Сообщения об оплате/преимуществах: стр. ~629, ~719, ~867, ~1155 (RU
  «• 💳 Кешбэк-трекер») и ~376 (EN «💳 Cashback tracking»).

**`bot/tasks/subscription_notifications.py`:**
- стр. ~95 и ~107 («• 💳 Отслеживание кэшбэка») — в уведомлениях об истечении/
  продлении подписки. Убрать.

**Проверка перед правкой:** выполнить grep по `кэшб|кешб|[Cc]ashback` в
`bot/routers/subscription.py` и `bot/tasks/subscription_notifications.py`,
свериться с актуальными номерами строк (могли сдвинуться). Убедиться, что после
удаления строк не ломается форматирование многострочных f-string/`'''…'''`
(не остаётся висячих `\n` с битой версткой — при необходимости подчистить).

- Текст `cashback_management_subscription` (`texts.py:406/1450`) и
  `cashback_subscription_required` (`texts.py:524/1557`) станут неиспользуемыми
  после снятия гейтов — пометить deprecated/оставить (не ломают).

### 5.7 Навигация «Назад» внутри инструментов
Переключить кнопку «Назад» с `settings` на `tools` в под-экранах перенесённых
функций:
- `bot/routers/settings.py`: `_total_limit_keyboard` (стр. ~222),
  `_prompt_total_limit_amount` (стр. ~242), `_total_goal_keyboard`,
  `_prompt_total_goal_amount`, и экраны с `back → settings` для лимита/цели.
- Семейный бюджет: `bot/keyboards_household.py` — `back → settings` заменить на
  `back → tools` (стр. 13, 19, 39). Проверить, нет ли других экранов household,
  ведущих в settings.
- Кешбэк/повторяющиеся: у них «Назад» ведёт в собственное под-меню
  (`recurring_menu`) или `close` — не трогаем.

**Success-пути удаления (Codex M3):** после удаления лимита/цели хендлеры
`total_limit_remove` (settings.py:264) и `total_goal_remove` (settings.py:426)
вызывают `callback_settings(...)` → возвращают в Настройки. Заменить на возврат
в Tools (вызвать `callback_tools(...)` из нового роутера, либо показать экран
лимита/цели с состоянием «нет лимита» + кнопкой Назад→tools). Выбрать
консистентный вариант — рекомендуется возврат в Tools-меню.

**Корневые экраны кешбэка/recurring (Codex M3 + ревью #2 LOW):** сейчас в корне
предлагают только «Закрыть», без «Назад в Инструменты». Поскольку вход теперь из
Tools — добавить кнопку «⬅️ Назад» → `callback_data="tools"` (рядом с «Закрыть»).
ВАЖНО: корневая клавиатура кешбэка дублируется в ДВУХ функциях и КАЖДАЯ имеет две
ветки (нет кешбэков / есть кешбэки):
- `bot/routers/cashback.py`: `send_cashback_menu_direct` (ветки ~стр. 90-91 и
  97-104) и `show_cashback_menu` (ветки ~стр. 209-210 и 216-226).
Добавить «Назад»→tools во ВСЕ 4 места (иначе навигация будет непоследовательной).
Для повторяющихся — в корневое меню `show_recurring_menu`.

**Замечание:** под-экраны лимита/цели физически живут в `settings.py`, но логически
теперь принадлежат «Инструментам». Файл не переносим (минимизируем диффы), меняем
только навигацию.

### 5.8 `bot/texts.py`
Добавить ключи (RU + EN):
- `tools_menu` — заголовок меню. RU: `🧰 Инструменты`, EN: `🧰 Tools`
  (уже содержит эмодзи).
- **(Codex L3 — дубль эмодзи):** при формировании `BotCommand` в `commands.py`
  НЕ добавлять префикс `🧰` к `tools_menu` (иначе выйдет «🧰 🧰 Инструменты»).
  Варианты: либо использовать `tools_menu` как есть без префикса (как сделано,
  например, для `recurring_menu`), либо завести отдельный ключ
  `tools_command_desc` без эмодзи. Рекомендуется первый вариант для единообразия
  с существующими командами.

Уже существуют (не создавать): `cashback_button`, `recurring_button`,
`total_limit_button`, `total_goal_button`, `household_button`, `close`, `back`.

Опционально оставить (не удалять, могут использоваться): `toggle_cashback`,
`enable_cashback`, `disable_cashback`, `cashback_enabled_message`,
`cashback_disabled_message` — после удаления тумблера часть станет неиспользуемой,
но удаление текстов не обязательно (не ломает). Пометить как deprecated комментарием
или оставить.

## 6. Порядок реализации

1. `bot/texts.py` — ключ `tools_menu` (RU+EN).
2. `bot/keyboards.py` — `tools_keyboard` (кнопка кешбэка → `cashback_menu`) +
   чистка `settings_keyboard`.
3. `bot/routers/tools.py` — новый роутер; экспорт в `__init__.py`; регистрация в `main.py`.
4. `bot/utils/commands.py` — обновить списки команд (−cashback,−recurring,+tools;
   без дубля 🧰).
5. `bot/routers/settings.py` — удалить toggle, почистить вызовы `settings_keyboard`,
   success-пути удаления лимита/цели → Tools.
6. Снятие гейтов кешбэка (п. 5.9): `bot/routers/cashback.py`,
   `bot/services/cashback.py`, `bot/services/subscription.py`,
   **`bot/routers/expense.py` (H1, 3 места)**.
7. Кешбэк из маркетинга подписки (п. 5.10): `bot/routers/subscription.py` (+тексты).
8. Навигация «Назад» → `tools` (settings.py, keyboards_household.py) + «Назад» в
   корневых меню кешбэка/recurring.
9. Deprecated-маркировка `cashback_enabled`/`toggle_cashback` (§4, L2).
10. Тесты + ручная проверка.

## 7. Тестирование

### Автотесты — требуют правки
- **`test_subscription_service.py`** (стр. 118–151):
  `test_deactivate_expired_subscriptions_disables_premium_settings_and_updates_commands`
  ассертит `settings.cashback_enabled is False` после истечения. Поскольку мы
  больше НЕ отключаем кешбэк при истечении подписки — обновить ассерт на
  `is True` (значение не меняется). Вызов `update_commands.assert_awaited_once_with`
  останется валидным, т.к. `view_scope` всё ещё меняется (changed_fields непустой).
- **`test_profile_service_defaults.py`**: проверяет `toggle_cashback` на
  service-уровне. Сервис `toggle_cashback` НЕ удаляем — тест остаётся зелёным.
- Найти и обновить любые cashback-тесты, ассертящие «выключено без подписки»
  (grep по `cashback_enabled`, `cashback_management_subscription`,
  `cashback_subscription_required` в `tests/`).
- Прогнать весь `tests/` — ожидаем зелёным после правок.

### Новые тесты (Codex M4 — УТОЧНЕНО ревью #2)
- **Бесплатный кешбэк на уровне expense-флоу (главное):** сервисы
  `calculate_expense_cashback`/`calculate_potential_cashback` САМИ `check_subscription`
  НЕ вызывают (раньше гейт был в `expense.py` через `has_subscription and ...`).
  Поэтому мок `check_subscription→False` на сервисах бесполезен. Тестировать надо
  именно 3 пути создания траты в `bot/routers/expense.py` (стр. ~1185, ~2001,
  ~2135): при `check_subscription→False` и совпадении валюты кешбэк всё равно
  считается и сохраняется (`expense.cashback_amount > 0`, в подтверждении есть
  `(+...)`). Это прямая проверка фикса H1.
- **Игнор `cashback_enabled=False`:** при `cashback_enabled=False` сервис
  `calculate_*` всё равно считает кешбэк (поле больше не гейтит) — тест на уровне
  сервиса корректен (там читалось именно поле, а не подписка).
- **Истечение подписки не трогает кешбэк:** дополнить/добавить тест на
  `deactivate_expired_subscriptions` — `cashback_enabled` не меняется.
- **Список команд:** `set_bot_commands`/`update_user_commands` содержат `tools`
  и НЕ содержат `cashback`/`recurring` (default scope; и chat-scope для
  `update_user_commands`).
- **Навигация Tools:** smoke — `/tools` отдаёт меню с 5 кнопками-инструментами;
  callback `tools` рендерит то же меню.
- **Порядок роутеров (L1):** dispatcher-level проверка, что `settings_router`
  (и `tools_router`) зарегистрированы раньше `expense_router`.

### Ручная проверка
- `/tools` открывает меню; каждая из 5 кнопок открывает свой экран.
- «Назад» из лимита/цели/семейного бюджета возвращает в «Инструменты».
- `/settings` больше не содержит перенесённых кнопок и тумблера кешбэка.
- Список команд бота: есть `/tools`, нет `/cashback` и `/recurring`.
- Прямой ввод `/cashback` и `/recurring` по-прежнему работает.
- Кешбэк виден и полностью работает БЕЗ подписки: можно добавить кешбэк,
  посмотреть список, кешбэк учитывается в отчётах.
- После истечения подписки кешбэк продолжает работать (не отключается).

## 8. Риски

- **MEDIUM:** существующие пользователи с `cashback_enabled=False` (выключили
  вручную ИЛИ им отключило истёкшей подпиской). После снятия всех гейтов поле
  больше не читается → кешбэк заработает у всех независимо от значения. Это
  желаемое поведение («бесплатно для всех»), но стоит отметить: дата-миграция
  для приведения поля к `True` НЕ требуется (поле игнорируется).
- **MEDIUM:** `update_user_commands` вызывается во многих местах при смене
  языка/подписки — убедиться, что после правки не осталось обращений к
  удалённой логике `/cashback`/`/recurring`.
- **MEDIUM:** тест `test_subscription_service.py` нужно обновить (см. п. 7) —
  иначе CI красный.
- **MEDIUM (Codex M2 — stale per-chat команды):** `update_user_commands` создаёт
  per-chat override (`BotCommandScopeChat`). У существующих пользователей в
  Telegram-клиенте останутся старые `/cashback`, `/recurring`, пока не вызовется
  `update_user_commands` снова (происходит при `/settings`, смене языка, проверке
  подписки и т.п. — для большинства самочинится при первом же действии). Так как
  обработчики команд сохранены, нажатие старой команды продолжит работать.
  **Решение:** отдельную миграцию/джобу для принудительного сброса НЕ делаем
  (избыточно); полагаемся на естественный refresh. Отметить в ручной проверке:
  после первого `/settings` или `/start` список команд обновляется.
- **LOW:** неиспользуемые тексты тумблера (`enable_cashback`, `disable_cashback`,
  `toggle_cashback`, `cashback_subscription_required`,
  `cashback_management_subscription`) — становятся мёртвыми. Удаление не
  обязательно; можно пометить deprecated.

## 9. Файлы (сводка)

| Файл | Действие |
|------|----------|
| `bot/texts.py` | +ключ `tools_menu` (RU+EN) |
| `bot/keyboards.py` | +`tools_keyboard`, чистка `settings_keyboard` |
| `bot/routers/tools.py` | новый роутер |
| `bot/routers/__init__.py` | +экспорт `tools_router` |
| `bot/main.py` | регистрация `tools_router` выше `expense_router` |
| `bot/routers/cashback.py` | снять гейты подписки/`cashback_enabled` в `callback_cashback_menu`; +«Назад»→tools в корневом меню |
| `bot/utils/commands.py` | списки команд: −cashback,−recurring,+tools (без дубля 🧰) |
| `bot/routers/settings.py` | −toggle_cashback, чистка вызовов keyboard, back→tools, success-пути удаления→tools |
| `bot/keyboards_household.py` | back→tools |
| `bot/services/cashback.py` | убрать проверки `cashback_enabled` в расчёте/трекинге |
| `bot/services/subscription.py` | не отключать кешбэк при истечении подписки; docstring |
| `bot/routers/expense.py` | **H1:** снять `has_subscription` с расчёта кешбэка (3 места) |
| `bot/routers/subscription.py` | **H2:** убрать кешбэк из преимуществ — `SUBSCRIPTION_PRICES` (4) + сообщения (5), формулировки «Кешбэк-трекер»/«Отслеживание кэшбэка» |
| `bot/tasks/subscription_notifications.py` | **H2:** убрать «Отслеживание кэшбэка» из уведомлений (~стр. 95, 107) |
| `expenses/models.py` | DEPRECATED-коммент к `cashback_enabled` (L2) |
| `bot/services/profile.py` | DEPRECATED-коммент к `toggle_cashback` (L2) |
| `tests/test_subscription_service.py` | обновить ассерт `cashback_enabled` |
| `tests/` (новые) | бесплатный кешбэк, command-list, навигация Tools, порядок роутеров |

## 10. История ревью

### Codex review #1 (2026-06-15) — учтено в плане
- **H1** Кешбэк гейтится подпиской в `expense.py` (3 места) → §5.9 (expense.py).
- **H2** Кешбэк рекламируется как премиум в `subscription.py` (5 мест) → §5.10.
- **M1** Новый callback кешбэка без очистки FSM → §5.5 (переиспользуем
  `cashback_menu`).
- **M2** Stale per-chat команды у существующих юзеров → §8 (естественный refresh,
  миграцию не делаем).
- **M3** Success-пути удаления лимита/цели и корневые меню → §5.7 (возврат в Tools).
- **M4** Недостаточно тестов → §7 (новые тесты).
- **L1** Уточнить обоснование порядка роутеров → §5.4.
- **L2** Dead-поле/метод `cashback_enabled`/`toggle_cashback` → §4 (deprecated-коммент).
- **L3** Дубль эмодзи 🧰 в команде → §5.8.

Все 9 findings приняты. Отклонённых нет.

### Codex review #2 (2026-06-15) — учтено в плане
Проверка закрытия findings #1 + новые. Результат: H1/M1/L1/L2 — RESOLVED.
Доработано:
- **H2 (был NOT-RESOLVED):** найдены доп. места рекламы кешбэка с формулировкой
  «Отслеживание кэшбэка» (≠ «Кешбэк-трекер»): `SUBSCRIPTION_PRICES`
  (description+features обоих тарифов) и `subscription_notifications.py` (~95, 107).
  Полный список и предупреждение про форматирование строк → §5.10.
- **M4 (тест-план был неверен):** cashback-сервисы не вызывают `check_subscription`,
  мок бесполезен — тесты бесплатного кешбэка перенесены на 3 пути создания траты
  в `expense.py` → §7.
- **M3 (доп. LOW):** корневая клавиатура кешбэка дублируется в 2 функциях × 2 ветки —
  «Назад»→tools во все 4 места → §5.7.
- **L3 (был PARTIALLY):** §5.1 приведён в соответствие с §5.8 — без префикса 🧰.
- **Cleanup (LOW):** удаление ненужных `get_user_settings`/`has_subscription`/
  параметра `cashback_enabled` в `settings_keyboard` → §5.6.

M2 оставлено как осознанное решение (естественный refresh команд), не блокер.
