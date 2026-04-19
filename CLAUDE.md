# Важные инструкции для Claude

## 🌐 ЯЗЫК ОБЩЕНИЯ

**ВСЕГДА отвечай на русском языке.** Весь вывод, объяснения, комментарии к коду и вопросы пользователю — на русском. Исключение: код, имена переменных, команды терминала и технические термины без устоявшегося перевода.

## 👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ

**Telegram ID владельца:** 881292737
**Язык:** ru (Русский)
**Валюта:** RUB (рубли)

## 🤖 РУЧНОЙ ВЫЗОВ CODEX REVIEW

Автоматический запуск Codex **отключён**. Claude вызывает Codex вручную — либо по запросу пользователя, либо по своей инициативе, когда это оправдано (например, после готового большого плана перед реализацией).

### Как вызвать Codex

Записать в файл `.codex-task` в корне проекта через Edit/Write:

```
PROMPT: <что ревьюить, на чём сфокусироваться, какой формат ответа нужен>
FILE: <опциональный путь к целевому файлу, например docs/MY_PLAN.md>
```

После записи автоматически срабатывает хук `codex-task-runner.sh` (PostToolUse), который запускает Codex CLI (1–4 мин). Результат сохраняется в `.codex-review-result.md`.

При следующем tool call PreToolUse-хук `codex-inject-review.sh` инжектит содержимое `.codex-review-result.md` в контекст Claude — ручной Read не нужен.

### Типичные сценарии

**1. Ревью плана:**
```
PROMPT: Review this plan as a senior code reviewer. Focus on architectural issues, missing edge cases, hidden risks, and whether the plan matches project patterns (see CLAUDE.md). For each finding: [SEVERITY] Description - Suggestion. Severities: CRITICAL, HIGH, MEDIUM, LOW. If no issues: NO_FINDINGS. Be concise, do NOT rewrite the plan.
FILE: docs/MY_PLAN.md
```

**2. Ревью git diff:**
```
PROMPT: Review the current git diff for feature XYZ. Focus on correctness, thread-safety, migration risks, and adherence to project conventions. Severities as above.
```

**3. Фокусированный вопрос:**
```
PROMPT: In docs/PLAN.md, evaluate whether the proposed regex-based token check in PostgreSQL is safe against special characters. Give a specific verdict.
```

### Правила использования

- **Не вызывать без нужды.** Мелкие правки, опечатки, тривиальные рефакторинги — без Codex.
- **Вызывать для:** планов перед реализацией, сложных архитектурных изменений, миграций данных, неочевидных решений, где ценно второе мнение.
- **После APPROVED плана** — всё равно спросить пользователя перед началом реализации.
- **Замечания Codex:** для каждого явно принять или аргументированно отклонить, показать пользователю сводку решений.

### Файлы системы

- `.claude/hooks/codex-task-runner.sh` — PostToolUse хук, срабатывает при Edit/Write файла `.codex-task`.
- `.claude/hooks/codex-inject-review.sh` — PreToolUse хук, инжектит `.codex-review-result.md` в контекст.
- `.claude/hooks/codex-session-cleanup.sh` — SessionStart, чистит сессионные файлы.
- `.claude/hooks/codex-review-hook.sh` и `codex-code-review-hook.sh` — скрипты остались на диске, но **не подключены** в `.claude/settings.json`. Если захочется вернуть автоматику — достаточно отредактировать `settings.json`.

---

## 🚨 КРИТИЧЕСКИ ВАЖНО: ПРОТОКОЛ ЗАПУСКА ЛОКАЛЬНОЙ СРЕДЫ 🚨

### ⚠️ ПЕРЕД ЗАПУСКОМ ЛЮБЫХ ПРОЦЕССОВ ОБЯЗАТЕЛЬНО:

**ШАГ 1 - ПРОВЕРИТЬ ЗАПУЩЕННЫЕ ПРОЦЕССЫ:**
```bash
tasklist | findstr -i python
tasklist | findstr -i redis
```

**ШАГ 2 - ЕСЛИ ПРОЦЕССЫ НАЙДЕНЫ - ОСТАНОВИТЬ ВСЕ:**
```bash
taskkill //F //IM python.exe
taskkill //F //IM redis-server.exe
```

**ШАГ 3 - УБЕДИТЬСЯ ЧТО ВСЕ ОСТАНОВЛЕНО:**
```bash
tasklist | findstr -i python  # Должно быть пусто
```

**ШАГ 4 - ТОЛЬКО ПОСЛЕ ЭТОГО ЗАПУСКАТЬ (ПО ОДНОМУ ЭКЗЕМПЛЯРУ КАЖДОГО):**
1. Redis (если нужен)
2. Celery Worker (ОДИН экземпляр)
3. Celery Beat (ОДИН экземпляр)
4. Telegram Bot (ОДИН экземпляр)

### ❌ ЗАПРЕЩЕНО:
- Запускать процессы БЕЗ предварительной проверки
- Запускать несколько экземпляров одного сервиса
- Игнорировать ошибки при запуске (TelegramConflictError и т.п.)

### ✅ ПРАВИЛО:
**ВСЕГДА сначала проверяй → потом останавливай существующие → потом запускай новые!**

---

## 🚨 КРИТИЧЕСКИ ВАЖНО: НЕ ОБНОВЛЯТЬ КОД НА СЕРВЕРЕ БЕЗ УКАЗАНИЯ 🚨

### ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА САМОВОЛЬНОЕ ОБНОВЛЕНИЕ СЕРВЕРА

**НИКОГДА не выполняй на сервере команды обновления кода без ПРЯМОГО указания пользователя:**
- ❌ `git pull` - ЗАПРЕЩЕНО без указания
- ❌ `docker-compose build` - ЗАПРЕЩЕНО без указания
- ❌ `docker-compose up -d` - ЗАПРЕЩЕНО без указания
- ❌ `docker-compose restart` - ЗАПРЕЩЕНО без указания
- ❌ `bash scripts/quick_bot_update.sh` - ЗАПРЕЩЕНО без указания
- ❌ `bash scripts/full_update.sh` - ЗАПРЕЩЕНО без указания
- ❌ ЛЮБЫЕ другие deployment команды - ЗАПРЕЩЕНО без указания

**АБСОЛЮТНОЕ ПРАВИЛО: НИЧЕГО НЕ ДЕПЛОЙ ПОКА ПОЛЬЗОВАТЕЛЬ НЕ СКАЖЕТ ЯВНО!**

**Правило:** Если пользователь попросил "сделай коммит и пуш" - это НЕ означает "обнови сервер".
Обновление сервера требует ОТДЕЛЬНОГО явного указания: "обнови на сервере", "задеплой", "примени на проде", "запусти quick_bot_update.sh".

**Что можно делать без указания:**
- ✅ Читать логи (`docker-compose logs`)
- ✅ Проверять статус (`docker-compose ps`, `docker ps`)
- ✅ Смотреть содержимое файлов (`cat`, `grep`)
- ✅ Проверять настройки

**Что ЗАПРЕЩЕНО делать без явного указания:**
- ❌ Запускать ЛЮБЫЕ скрипты обновления
- ❌ Перезапускать контейнеры
- ❌ Пересобирать Docker образы
- ❌ Обновлять код из Git на сервере

---

## 🚨 КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНЫЙ ПРОТОКОЛ ПЕРЕД КОМАНДАМИ СЕРВЕРА 🚨

### 📍 ДЕФОЛТНЫЙ СЕРВЕР ДЛЯ РАБОТЫ

**ВАЖНО:** Если не оговорено отдельно, мы работаем на **PRIMARY SERVER**:
- **IP:** 144.31.97.139
- **SSH:** `ssh batman@144.31.97.139`
- **Путь к проекту:** `/home/batman/expense_bot`

### ⚠️ НИКОГДА НЕ ДАВАЙ КОМАНДЫ ДЛЯ СЕРВЕРА БЕЗ ПРОВЕРКИ!

**ПЕРЕД ТЕМ КАК ДАТЬ ЛЮБУЮ КОМАНДУ ДЛЯ СЕРВЕРА, ТЫ ОБЯЗАН:**

1. **ОПРЕДЕЛИТЬ НА КАКОМ СЕРВЕРЕ НАХОДИТСЯ ПОЛЬЗОВАТЕЛЬ**
   ```bash
   # Попроси пользователя выполнить:
   hostname -I && pwd
   ```

2. **СВЕРИТЬ С ДОКУМЕНТАЦИЕЙ В ЭТОМ ФАЙЛЕ:**
   - PRIMARY SERVER: 144.31.97.139 → путь `/home/batman/expense_bot` **(ЕДИНСТВЕННЫЙ СЕРВЕР)**

3. **ТОЛЬКО ПОСЛЕ ЭТОГО ДАВАЙ КОМАНДЫ С ПРАВИЛЬНЫМ ПУТЕМ!**

### 📋 Шаблон работы:

**ШАГ 1 - ОПРЕДЕЛЕНИЕ СЕРВЕРА:**
```
Пользователь: "посмотри логи"
Claude: "Сначала определим на каком сервере вы находитесь. Выполните: hostname -I && pwd"
```

**ШАГ 2 - АНАЛИЗ РЕЗУЛЬТАТА:**
```
Пользователь: "144.31.97.139 /home/batman"
Claude: "Вы на PRIMARY сервере. Путь к проекту: /home/batman/expense_bot"
```

**ШАГ 3 - ПРАВИЛЬНАЯ КОМАНДА:**
```
Claude: "cd /home/batman/expense_bot && docker-compose logs --tail=200 bot"
```

### ⚠️ ТИПИЧНЫЕ ОШИБКИ (НЕ ДЕЛАЙ ТАК):

❌ **НЕПРАВИЛЬНО** - давать команды не зная на каком сервере пользователь:
```bash
docker-compose logs --tail=200 bot  # Где cd? Какой сервер?
```

❌ **НЕПРАВИЛЬНО** - предполагать что пользователь на PRIMARY сервере:
```bash
cd /home/batman/expense_bot && ...  # А если он на BACKUP?
```

❌ **НЕПРАВИЛЬНО** - использовать несуществующее имя сервиса:
```bash
cd /home/batman/expense_bot && docker-compose logs --tail=200 app  # ❌ ERROR: No such service: app
```

✅ **ПРАВИЛЬНО** - сначала определить сервер, потом дать команду с правильным именем сервиса:
```bash
# Шаг 1: hostname -I && pwd
# Шаг 2: Анализ → PRIMARY сервер
# Шаг 3: cd /home/batman/expense_bot && docker-compose logs --tail=200 bot  # ✅ bot - это правильное имя!
```

### 📍 Быстрая справка по серверам:

| Сервер | IP | Путь к проекту | Docker Compose |
|--------|-----|----------------|----------------|
| PRIMARY | 144.31.97.139 | `/home/batman/expense_bot` | `docker compose` (новый, без дефиса) |

---

## 🔴 КРИТИЧЕСКИ ВАЖНО: Git коммиты ⚠️

### **ВСЕГДА ВКЛЮЧАЙ ВСЕ ИЗМЕНЁННЫЕ ФАЙЛЫ В КОММИТ!**

**Перед коммитом ОБЯЗАТЕЛЬНО:**
1. ✅ Выполни `git status` и проверь ВСЕ изменённые файлы
2. ✅ Добавь **ВСЕ** релевантные файлы через `git add`
3. ✅ **НЕ ПРОПУСКАЙ** файлы, которые были изменены в процессе работы
4. ✅ Проверь что все файлы добавлены: `git diff --cached`

**Почему это критично:**
- ❌ Пропущенные файлы → код на сервере ломается
- ❌ Частичный коммит → несогласованное состояние
- ❌ Забытые изменения → ошибки импорта/зависимостей

**Правильная последовательность:**
```bash
# 1. Проверить ВСЕ изменения
git status

# 2. Добавить ВСЕ нужные файлы (не по одному!)
git add file1.py file2.py file3.py ...
# ИЛИ для всех изменений в папке
git add bot/services/

# 3. Проверить что добавлено в коммит
git diff --cached

# 4. Только после проверки - коммит
git commit -m "message"

# 5. Push
git push origin master
```

---

## ⛔⛔⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА УДАЛЕНИЕ ФАЙЛОВ ⛔⛔⛔
### **НИКОГДА НЕ ИСПОЛЬЗУЙ `rm`, `rm -f`, `rm -rf` или любые команды удаления!**
**ВСЕ ФАЙЛЫ ТОЛЬКО ПЕРЕМЕЩАТЬ В АРХИВ!**

**Правильный способ "удаления" файлов:**
```bash
# НЕПРАВИЛЬНО - НИКОГДА ТАК НЕ ДЕЛАТЬ:
rm test_file.py              # ❌ ЗАПРЕЩЕНО!
rm -f *.css                   # ❌ ЗАПРЕЩЕНО!
rm -rf temp_folder/           # ❌ ЗАПРЕЩЕНО!

# ПРАВИЛЬНО - ВСЕГДА ТАК:
mkdir -p archive_$(date +%Y%m%d)           # ✅ Создать архив
mv test_file.py archive_$(date +%Y%m%d)/   # ✅ Переместить в архив
mv *.css archive_$(date +%Y%m%d)/          # ✅ Переместить в архив
mv temp_folder/ archive_$(date +%Y%m%d)/   # ✅ Переместить в архив
```

**Это правило АБСОЛЮТНОЕ и НЕ ИМЕЕТ ИСКЛЮЧЕНИЙ!**

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

---

## 🛡️ КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА ВАЛИДАЦИИ ДАННЫХ

### ⚠️ УРОК ИЗ PRODUCTION BUG: Дублирование категорий (ноябрь 2025)

**Найденная проблема:** Пользователи видели дублирование категорий в отчетах из-за двух багов:

#### 🐛 БАГ #1: Создание категорий с пустыми мультиязычными полями
**Симптом:** Категории создавались с заполненным полем `name`, но пустыми `name_ru`/`name_en`
**Причина:** Код использовал устаревшее поле вместо новых мультиязычных полей
**Последствия:** Категории отображались без названия, создавая "призрачные" записи в отчетах

**Решение:** `bot/services/category.py:create_default_categories_sync()`
```python
# ❌ НЕПРАВИЛЬНО (старый код):
ExpenseCategory(
    profile=profile,
    name=f"{icon} {name}",  # Только старое поле!
    icon='',
    is_active=True
)

# ✅ ПРАВИЛЬНО (новый код):
ExpenseCategory(
    profile=profile,
    name=f"{icon} {name}",          # Для обратной совместимости
    name_ru=name if lang == 'ru' else None,
    name_en=name if lang == 'en' else None,
    original_language=lang,
    is_translatable=True,
    icon=icon,
    is_active=True
)
```

#### 🐛 БАГ #2: Отсутствие валидации владельца категории
**Симптом:** Траты пользователя А оказывались с категориями пользователя Б
**Причина:** Нет проверки что `category_id` принадлежит тому же пользователю
**Последствия:** Нарушение целостности данных, дублирование в отчетах

**Решение:** `bot/services/expense.py:create_expense()`
```python
# ОБЯЗАТЕЛЬНАЯ валидация category_id:
if category_id is not None:
    try:
        category = ExpenseCategory.objects.select_related('profile').get(id=category_id)

        is_valid_category = False

        # Случай 1: Категория принадлежит самому пользователю
        if category.profile_id == profile.id:
            is_valid_category = True
        # Случай 2: Семейный бюджет - категория от члена семьи
        elif profile.household_id is not None:
            if category.profile.household_id == profile.household_id:
                is_valid_category = True

        if not is_valid_category:
            raise ValueError("Нельзя использовать категорию другого пользователя")

    except ExpenseCategory.DoesNotExist:
        raise ValueError(f"Категория с ID {category_id} не существует")
```

#### 📋 ПРАВИЛА ВАЛИДАЦИИ ДАННЫХ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):

1. **ВСЕГДА проверяй владельца сущности**
   - При создании траты → проверь что category.profile == expense.profile
   - При изменении данных → проверь что пользователь имеет права
   - Для семейного бюджета → проверь принадлежность к household

2. **ВСЕГДА заполняй ВСЕ обязательные поля модели**
   - Проверяй что новые поля (например мультиязычные) заполнены
   - Не полагайся только на старые поля для обратной совместимости
   - При bulk_create проверяй что все поля корректны

3. **ВСЕГДА валидируй FK перед присвоением**
   - Проверяй существование связанной сущности
   - Проверяй права доступа к связанной сущности
   - Логируй попытки использования чужих данных

4. **ВСЕГДА обрабатывай legacy данные**
   - При обнаружении проблем в продакшене создавай скрипты миграции
   - Скрипты должны работать в режиме dry-run по умолчанию
   - Логируй ВСЕ изменения для отката

#### 🔧 Скрипты для исправления данных:

**1. Исправление битых категорий:**
```bash
# Тестовый прогон (без изменений):
python fix_broken_categories.py

# Применение изменений:
python fix_broken_categories.py --apply
```

**2. Исправление трат с чужими категориями:**
```bash
# Тестовый прогон (без изменений):
python fix_expenses_with_foreign_categories.py

# Применение изменений:
python fix_expenses_with_foreign_categories.py --apply
```

#### ⚡ Масштаб проблемы (ноябрь 2025):
- Затронуто: **сотни пользователей**
- Период: с **20 сентября 2025** (внедрение мультиязычности)
- Битых категорий: **~300**
- Трат с чужими категориями: **требует проверки на продакшене**

---

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

### 🚀 ПАРАЛЛЕЛЬНЫЙ ЗАПУСК СУБАГЕНТОВ ДЛЯ БОЛЬШИХ ЗАДАЧ
**КРИТИЧЕСКИ ВАЖНО:** Для задач требующих изменений в нескольких файлах, ВСЕГДА запускай субагентов ПАРАЛЛЕЛЬНО!

#### Когда запускать субагентов параллельно:
- ❗ Интернационализация (исправление хардкода в 5+ файлах)
- ❗ Рефакторинг (изменения в нескольких модулях)
- ❗ Массовые замены (например, изменение API во всех роутерах)
- ❗ Добавление нового функционала в разных частях кода
- ❗ Любая задача где нужно изменить 3+ файла

#### Преимущества параллельного запуска:
- ⚡ В 4-5 раз быстрее чем последовательный запуск
- 🎯 Каждый субагент фокусируется на своем файле
- 🔄 Работа идет одновременно, не ждем завершения предыдущего
- 💾 Экономия контекста - не нужно держать все файлы в памяти

#### Пример:
Задача: Исправить хардкод в 4 файлах (67 мест)

**НЕПРАВИЛЬНО** - последовательно (займет 40+ минут):
- Исправить файл 1, подождать результата
- Исправить файл 2, подождать результата
- Исправить файл 3, подождать результата
- Исправить файл 4, подождать результата

**ПРАВИЛЬНО** - параллельно (займет 10 минут):
Запустить 4 субагента одновременно в одном вызове Task:
- Субагент 1: исправляет файл 1
- Субагент 2: исправляет файл 2
- Субагент 3: исправляет файл 3
- Субагент 4: исправляет файл 4

Все работают одновременно, результат получаем сразу от всех!

#### Реальные примеры из проекта:

**Пример 1: Интернационализация**
- Задача: Исправить 67 хардкодов в 4 файлах
- Решение: Запущено 4 субагента параллельно
- Время выполнения: 10 минут вместо 40+

**Пример 2: Рефакторинг regex паттернов (декабрь 2025)**
- Задача: Заменить устаревшие regex (без ZWJ) на централизованные в 2 файлах
  - `bot/services/category.py` (4 места)
  - `bot/routers/categories.py` (6+ мест)
- **НЕПРАВИЛЬНО (последовательно):** Править каждый файл по очереди = 15+ минут
- **ПРАВИЛЬНО (параллельно):**
  ```
  Task 1: "Замени все устаревшие regex в category.py на EMOJI_PREFIX_RE"
  Task 2: "Замени все устаревшие regex в categories.py на EMOJI_PREFIX_RE"
  ```
  Время: 5 минут (параллельно)

**Ключевой урок:** Любая задача с изменениями в 2+ файлах → параллельные субагенты!

## Работа с сервером
**ВАЖНО:** Я могу выполнять команды на сервере через SSH используя инструмент Bash.
**Формат команды:** `ssh batman@144.31.97.139 "команда"`
**Важно:** Все правила безопасности и запреты на самовольные действия (git pull, docker restart и т.д.) остаются в силе!

## 🔴 КРИТИЧЕСКИЕ ПРАВИЛА БЕЗОПАСНОСТИ 🔴

### ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ НА УДАЛЕНИЕ ФАЙЛОВ ⛔
**НИКОГДА НЕ ИСПОЛЬЗУЙ КОМАНДЫ:**
- `rm` или `rm -f` или `rm -rf` - **ЗАПРЕЩЕНО ПОЛНОСТЬЮ**
- `del` или `delete` - **ЗАПРЕЩЕНО**
- Любые другие команды безвозвратного удаления - **ЗАПРЕЩЕНО**

**ВМЕСТО УДАЛЕНИЯ ВСЕГДА:**
1. Создай архивную папку: `mkdir -p archive_YYYYMMDD`
2. Перемести файлы в архив: `mv файл archive_YYYYMMDD/`
3. НИКОГДА не удаляй архивные папки
4. Даже временные и тестовые файлы - ТОЛЬКО В АРХИВ

**ПРАВИЛА РАБОТЫ С ФАЙЛАМИ:**
- ✅ РАЗРЕШЕНО: `mv файл archive/` (перемещение в архив)
- ✅ РАЗРЕШЕНО: `cp файл backup/` (создание копии)
- ❌ ЗАПРЕЩЕНО: `rm файл` (удаление)
- ❌ ЗАПРЕЩЕНО: удалять файлы "для очистки проекта"

### ПЕРЕД ЛЮБОЙ КОМАНДОЙ ОБЯЗАТЕЛЬНО:
1. **ПРОВЕРЬ локальный код** - используй Read для проверки файлов
2. **ПРОВЕРЬ структуру БД** - перед SQL командами ВСЕГДА проверяй `expenses/models.py` для правильных имён таблиц и полей
3. **ПРОВЕРЬ документацию** - читай docs/SERVER_COMMANDS.md и CLAUDE.md
4. **НЕ ПЕРЕЗАПИСЫВАЙ .env** - всегда делай backup: `cp .env .env.backup_$(date +%Y%m%d_%H%M%S)`
5. **НЕ ИСПОЛЬЗУЙ git reset --hard** без backup важных файлов
6. **НЕ СОЗДАВАЙ новые docker-compose.yml** - используй существующий или спроси
7. **НЕ УДАЛЯЙ файлы** - только перемещай в архив

### 📋 ФОРМАТ КОМАНД ДЛЯ СЕРВЕРА:
**КРИТИЧЕСКИ ВАЖНО:** Все команды для сервера должны быть в ОДНОМ bash блоке с комментариями!

**ПРАВИЛЬНО** ✅ (можно скопировать целиком):
```bash
# Проверяем профиль пользователя (язык и валюту)
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot -c "SELECT id, telegram_id FROM users_profile WHERE telegram_id = 1190249363;"

# Затем проверяем категории пользователя
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot -c "SELECT id, name FROM expenses_category WHERE profile_id = 280;"
```

**НЕПРАВИЛЬНО** ❌ (невозможно скопировать):
```bash
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot -c "SELECT id FROM users_profile;"
```
Затем:  # ❌ Незакомментированный текст между командами!
```bash
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot -c "SELECT id FROM expenses_category;"
```

**Правило:** Пользователь должен скопировать ВЕСЬ блок и вставить в терминал без редактирования!

### ТЕКУЩАЯ АРХИТЕКТУРА (ВАЖНО!):
- **APP сервер**: 144.31.97.139 (Telegram bot, Django admin, Celery, PostgreSQL, Redis — всё в Docker)

### КРИТИЧЕСКИЕ ФАЙЛЫ - НЕ УДАЛЯТЬ:
- `.env` - содержит токены и пароли (ВСЕГДА делай backup перед изменением!)
- `docker-compose.yml` - конфигурация контейнеров
- `/home/batman/expense_bot_backup_*.sql` - резервные копии БД на сервере

### ПРАВИЛЬНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ КОМАНД:
```bash
# 1. ВСЕГДА сначала backup
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)

# 2. При обновлении с GitHub
git stash  # сохраняем локальные изменения
git pull origin master
git stash pop  # восстанавливаем локальные изменения

# 3. НЕ используй git reset --hard без необходимости!
```

### 📌 КОМАНДЫ ДЛЯ СЕРВЕРА
**ВСЕГДА используй готовые команды из файла:** `docs/SERVER_COMMANDS.md`
- Там есть ВСЕ рабочие команды для сервера
- Команды уже протестированы и работают
- НЕ придумывай новые команды, используй готовые из документации

### Принцип работы с сервером:
- Я могу выполнять команды на сервере напрямую через SSH
- Используя формат: `ssh batman@144.31.97.139 "команда"`
- Все правила безопасности остаются в силе (нельзя git pull, docker restart и т.д. без разрешения)
- Для выполнения нескольких команд использую: `ssh batman@144.31.97.139 "команда1 && команда2"`

## Server Configuration

### Primary Server (APP + Web)
- **Server IP:** 144.31.97.139
- **SSH:** `ssh batman@144.31.97.139`
- **Bot Domain:** expensebot.duckdns.org
- **Landing Domain:** www.coins-bot.ru
- **Server path:** /home/batman/expense_bot
- **User:** batman
- **Docker Compose:** `docker compose` (новый синтаксис, без дефиса)

## Docker Containers
- expense_bot_web - Django admin panel (port 8000)
- expense_bot_app - Telegram bot
- expense_bot_celery - Background tasks
- expense_bot_celery_beat - Scheduled tasks
- expense_bot_db - PostgreSQL 15
- expense_bot_redis - Redis cache

### 🔴 КРИТИЧЕСКИ ВАЖНО: Команды для работы с docker compose на сервере

## ⚠️ ОБЯЗАТЕЛЬНОЕ ПРАВИЛО #1: ВСЕГДА УКАЗЫВАЙ `cd` ПЕРЕД КОМАНДАМИ!
**Docker compose команды работают ТОЛЬКО из директории проекта где находится docker-compose.yml!**

**НЕПРАВИЛЬНО:**
```bash
docker compose logs bot --tail 200  # ❌ ERROR: no configuration file provided: not found
```

**ПРАВИЛЬНО:**
```bash
cd /home/batman/expense_bot && docker compose logs bot --tail 200  # ✅
```

---

## ⚠️ ОБЯЗАТЕЛЬНОЕ ПРАВИЛО #2: Правильный синтаксис для PRIMARY SERVER

**На PRIMARY SERVER (144.31.97.139) - НОВАЯ версия docker compose (без дефиса):**
```bash
# ИМЕНА СЕРВИСОВ В docker-compose.yml:
# - bot (контейнер: expense_bot_app)
# - web (контейнер: expense_bot_web)
# - celery (контейнер: expense_bot_celery)
# - celery-beat (контейнер: expense_bot_celery_beat)
# - db (контейнер: expense_bot_db)
# - redis (контейнер: expense_bot_redis)

# ✅ ПРАВИЛЬНЫЕ КОМАНДЫ:
cd /home/batman/expense_bot && docker compose logs bot --tail 200
cd /home/batman/expense_bot && docker compose logs bot --tail 50
cd /home/batman/expense_bot && docker compose logs web --tail 100
cd /home/batman/expense_bot && docker compose logs --follow bot
cd /home/batman/expense_bot && docker compose ps
cd /home/batman/expense_bot && docker compose restart bot
cd /home/batman/expense_bot && docker compose stop bot
cd /home/batman/expense_bot && docker compose up -d bot

# 🔄 АЛЬТЕРНАТИВА - напрямую через docker (работает без cd):
docker logs --tail 200 expense_bot_app     # Логи бота
docker logs --tail 50 expense_bot_web      # Логи веб
docker logs -f expense_bot_app             # Следить за логами
docker ps                                  # Статус всех контейнеров

# ✅ Фильтрация по времени:
docker logs --since "1h" expense_bot_app   # Логи за последний час
docker logs --since "30m" expense_bot_app  # Логи за последние 30 минут

# ✅ Поиск в логах:
docker logs --tail 5000 expense_bot_app | grep -i "текст" -B 5 -A 10
```

---

## 📋 ШАБЛОНЫ КОМАНД ДЛЯ КОПИРОВАНИЯ

**Просмотр логов на PRIMARY сервере:**
```bash
ssh batman@144.31.97.139 "cd /home/batman/expense_bot && docker compose logs bot --tail 200"
```

**Поиск по логам на PRIMARY сервере:**
```bash
ssh batman@144.31.97.139 "cd /home/batman/expense_bot && docker compose logs bot --tail 500 | grep 'текст_для_поиска'"
```

**Перезапуск контейнера на PRIMARY сервере:**
```bash
ssh batman@144.31.97.139 "cd /home/batman/expense_bot && docker compose restart bot"
```

**ВАЖНО: Имя сервиса в docker-compose.yml:**
- `bot` - Telegram bot (контейнер: expense_bot_app)
- `web` - Django admin (контейнер: expense_bot_web)
- `celery` - Celery worker (контейнер: expense_bot_celery)
- `celery-beat` - Celery beat (контейнер: expense_bot_celery_beat)

## Database

### Production Database (on server)
- Type: PostgreSQL 15 (Alpine)
- Database name: expense_bot
- User: expense_user (DB_USER в .env)
- Container: expense_bot_db
- Default credentials: DB_USER=expense_user, DB_NAME=expense_bot
- **ВАЖНО:** Пользователь БД - expense_user, НЕ batman!
- Команда для создания дампа: `docker exec expense_bot_db pg_dump -U expense_user expense_bot > backup.sql`

### Local Development Database
- **Type:** PostgreSQL 17
- **Database name:** expense_bot_local
- **User:** expense_user
- **Password:** local_password (из .env)
- **Host:** localhost
- **Port:** 5432
- **PostgreSQL bin path:** `C:\Program Files\PostgreSQL\17\bin\`
- **Админ:** postgres / Aa07900790

**Загрузка дампа в локальную БД:**
```bash
# 1. Создать базу (если не существует)
export PGPASSWORD=Aa07900790
psql -h localhost -U postgres -c "CREATE DATABASE expense_bot_local OWNER expense_user;"

# 2. Загрузить дамп
export PGPASSWORD=local_password
psql -h localhost -U expense_user -d expense_bot_local -f dump_file.sql

# 3. Проверить данные
psql -h localhost -U expense_user -d expense_bot_local -c "\dt"
```

**Или через Python скрипт:**
```bash
python load_dump.py  # Скрипт в корне проекта
```

## 🚀 Локальный запуск проекта для разработки и тестирования

### Требования:
- Python 3.11.9
- PostgreSQL 17 (локальная БД)
- Redis (localhost:6379)
- Git Bash или аналогичный терминал

### ⚠️ ВАЖНО: Правильная последовательность запуска

**1. Проверить что Redis запущен:**
```bash
redis-cli ping  # Должен ответить PONG
```

**2. Активировать виртуальное окружение и запустить Celery Worker:**
```bash
# КРИТИЧЕСКИ ВАЖНО: Celery приложение называется 'expense_bot', НЕ 'config'!
source venv/Scripts/activate && export PYTHONPATH=$PWD && python -m celery -A expense_bot worker -l INFO --pool=solo
```
Запустить в фоне или в отдельном терминале.

**3. Активировать виртуальное окружение и запустить Celery Beat:**
```bash
source venv/Scripts/activate && export PYTHONPATH=$PWD && python -m celery -A expense_bot beat -l INFO
```
Запустить в фоне или в отдельном терминале.

**4. Активировать виртуальное окружение и запустить Django сервер (опционально):**
```bash
source venv/Scripts/activate && python manage.py runserver 127.0.0.1:8000
```
**ПРИМЕЧАНИЕ:** Django сервер может застрять на "Performing system checks..." - это не критично для работы бота. Админка будет недоступна, но бот полностью функционален.

**5. Активировать виртуальное окружение и запустить Telegram бота:**
```bash
source venv/Scripts/activate && python run_bot.py
```

### 📋 Статус запущенных сервисов:

После успешного запуска вы должны увидеть:

✅ **Redis:** PONG
✅ **Celery Worker:** "Connected to redis://localhost:6379/0" + список из ~21 задачи
✅ **Celery Beat:** "celery beat v5.4.0 is starting" + отправка периодических задач
✅ **Django Server (опционально):** "Starting development server at http://127.0.0.1:8000/"
✅ **Telegram Bot:** "Run polling for bot @showmecoin_bot" + "Бот запущен и готов к работе"

### 🎯 Готово к тестированию!

Бот работает в режиме **polling** (без webhook) и готов принимать сообщения через @showmecoin_bot.

**Доступные функции:**
- ✅ Обработка текстовых и голосовых сообщений
- ✅ AI категоризация (Google AI / OpenAI)
- ✅ Парсинг трат и доходов
- ✅ Celery фоновые задачи
- ✅ Redis кеширование
- ⚠️ Django админка (если сервер запустился)

### 🐛 Типичные проблемы при запуске:

**Проблема:** `Unable to load celery application. The module config was not found.`
**Решение:** Используйте `-A expense_bot`, НЕ `-A config`!

**Проблема:** `command not found: venvScriptspython.exe`
**Решение:** Используйте правильные слеши: `venv/Scripts/activate` (forward slash)

**Проблема:** Django застрял на "Performing system checks..."
**Решение:** Это не критично. Бот работает без Django сервера. Просто игнорируйте.

**Проблема:** Redis не отвечает
**Решение:** Запустите Redis: `redis-server` (или проверьте что сервис запущен)

### 🛑 Остановка всех процессов:

Нажмите `Ctrl+C` в каждом терминале или используйте:
```bash
# Найти все Python процессы
ps aux | grep python

# Убить процесс по PID
kill <PID>
```

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
docker compose down && \
git fetch --all && \
git reset --hard origin/master && \
git pull origin master && \
docker compose build --no-cache && \
docker compose up -d --force-recreate && \
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

## Legal Documents URLs
**Landing page domain:** www.coins-bot.ru

### Russian:
- **Политика конфиденциальности**: https://www.coins-bot.ru/privacy.html
- **Публичная оферта**: https://www.coins-bot.ru/offer.html

### English:
- **Privacy Policy**: https://www.coins-bot.ru/privacy_en.html
- **Terms of Service**: https://www.coins-bot.ru/offer_en.html

**Local files location:** `/Users/aleksejnalbantov/Desktop/expense_bot/landing/`
- privacy.html (RU)
- privacy_en.html (EN)
- offer.html (RU)
- offer_en.html (EN)

## Marketing & Social Media Channels

### Telegram Channel
**Channel name:** Coins
**Channel handle:** @showmecoins
**URL:** https://t.me/showmecoins

**Purpose:** Короткие советы по финансам, обновления бота, новые функции

**Где упоминается:**
- Приветственное сообщение /start (в конце)
- Можно добавить в меню "О боте" или "Помощь"

### Яндекс.Дзен
**Статус:** ✅ АКТИВНЫЙ АККАУНТ
**URL:** [указать URL канала на Дзене]
**Контент:** Посты из Telegram канала, финансовые советы

**Преимущества:**
- DA 90 (отличная индексация в Яндекс)
- Backlinks для SEO
- Российская аудитория
- Кросс-постинг с Telegram

**Планируемый контент:**
- Личный опыт и кейсы (авто vs такси, семейный бюджет)
- Практические советы по финансам
- Обзоры и сравнения
- Статьи с реальными цифрами

### Другие каналы
**VK:** [URL если есть]
**Instagram:** [URL если есть]
**Планируется:** Кросс-постинг контента с адаптацией под каждую платформу

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


## Документация проекта

**ВАЖНО:** Вся документация проекта хранится в папке `docs/`
- `docs/ARCHITECTURE.md` - **ОСНОВНОЙ ДОКУМЕНТ** - архитектура проекта, компоненты, мониторинг, webhook keepalive
- `docs/CELERY_DOCUMENTATION.md` - полная документация по Celery (конфигурация, задачи, troubleshooting)
- `docs/MONITORING_DOCUMENTATION.md` - система мониторинга, Sentry, health checks, уведомления админу
- `docs/INCOME_KEYWORDS_UNIQUENESS_PLAN.md` - план реализации уникальности ключевых слов для доходов (симметрия с расходами)
- `docs/PII_REMOVAL_PLAN_ACTUAL.md` - **АКТУАЛЬНЫЙ** план удаления PII из кода (6 файлов, 3-4 часа)
- ~~`docs/PII_REMOVAL_PLAN.md`~~ - устаревший, не использовать (описывает уже выполненную миграцию БД)

## Индекс документации

**Карта всех .md файлов:** [docs/INDEX.md](docs/INDEX.md)

**КРИТИЧЕСКИ ВАЖНО:** Читай `INDEX.md` **первым**, прежде чем искать информацию через Grep.
В INDEX есть разделы по статусу:
- **Current** — всегда читай первым для понимания текущего состояния
- **Active** — незавершённая работа, читай если вопрос про неё
- **Reference** — справочники, только по явному запросу
- **Historical** — закрытые инциденты и миграции, **не читай без явной причины**
- **Deprecated** — устарело, **не читай вообще**

### Когда запускать субагента `docs-indexer`

**Обязательно:**
- После создания нового `.md` файла в `docs/`
- После удаления `.md` файла
- После переименования `.md` файла
- После **существенного смыслового изменения** содержимого файла (статус поменялся, описание устарело, план стал отчётом)
- В конце сессии, если были любые изменения в `.md` файлах (action: refresh)

**Не нужно:**
- При косметическом редактировании (опечатки, форматирование, мелкие правки текста)

**Как определить "существенное изменение":**
- Поменялся `Статус:` в шапке файла
- Добавлен/удалён крупный раздел (>20% объёма)
- Изменилось назначение файла (план -> отчёт, актуальный -> устаревший)

### Как вызывать

Точечно (при add/remove/rename/update):
```
Agent(subagent_type: "docs-indexer", description: "Update docs INDEX", prompt: "project: expense_bot\naction: add\nfiles: [docs/NEW_FILE.md]")
```

Полный refresh (в конце сессии):
```
Agent(subagent_type: "docs-indexer", description: "Refresh INDEX", prompt: "project: expense_bot\naction: refresh")
```

## Обновление лендинга на сервере

### ⚠️ ВАЖНО: Правильная последовательность обновления лендинга

**Проблема:** После `git pull` страница может показываться старая из-за кеширования

**Правильный порядок действий:**
```bash
# 1. Подключиться к серверу
ssh batman@144.31.97.139

# 2. Обновить код из репозитория
cd /home/batman/expense_bot
git pull

# 3. Скопировать файлы лендинга в веб-директорию
sudo cp -rf landing/* /var/www/coins-bot/

# 4. Установить правильные права
sudo chown -R www-data:www-data /var/www/coins-bot/

# 5. Перезагрузить nginx для сброса кеша
sudo nginx -s reload
```

**Или одной командой:**
```bash
cd /home/batman/expense_bot && git pull && sudo cp -rf landing/* /var/www/coins-bot/ && sudo chown -R www-data:www-data /var/www/coins-bot/ && sudo nginx -s reload
```

### После обновления на сервере:
1. **В браузере обязательно:** Нажать `Ctrl+F5` (Windows/Linux) или `Cmd+Shift+R` (Mac)
2. **На мобильном:** Очистить кеш браузера или открыть в приватном режиме
3. **Проверить обновление:** Открыть консоль разработчика (F12) и проверить Network → отключить кеш

### Если страница все еще старая:
```bash
# Проверить что файлы обновились
grep -c "искомый_текст" /var/www/coins-bot/index.html

# Принудительно перезапустить nginx
sudo systemctl restart nginx

# Проверить дату изменения файла
ls -la /var/www/coins-bot/index.html
```

## Backup Process
**КРИТИЧЕСКИ ВАЖНО:** Правильные команды для резервного копирования

### Создание дампа БД через Docker
```bash
# Правильная команда с пользователем expense_user
docker exec expense_bot_db pg_dump -U expense_user expense_bot > /home/batman/backups/backup_$(date +%Y%m%d_%H%M%S).sql

# Проверка созданного дампа
ls -la /home/batman/backups/

# Создание папки для бэкапов если не существует
mkdir -p /home/batman/backups/
```

### Архивирование проекта
```bash
# Создание архива проекта с исключениями
cd /home/batman && tar -czf backups/expense_bot_project_$(date +%Y%m%d_%H%M%S).tar.gz \
  --exclude='expense_bot/__pycache__' \
  --exclude='expense_bot/.git' \
  --exclude='expense_bot/logs' \
  --exclude='expense_bot/staticfiles' \
  --exclude='expense_bot/.env' \
  expense_bot/
```

### Путь для бэкапов
- Основная директория: `/home/batman/backups/`
- Дампы БД: `/home/batman/backups/backup_YYYYMMDD_HHMMSS.sql`
- Архивы проекта: `/home/batman/backups/expense_bot_project_YYYYMMDD_HHMMSS.tar.gz`

## Common Errors
**ВАЖНЫЕ ОШИБКИ И ИХ РЕШЕНИЯ:**

### ❌ Ошибка "role batman is not permitted to log in"
**Проблема:** Попытка использовать пользователя batman для БД
```bash
# НЕПРАВИЛЬНО:
docker exec expense_bot_db pg_dump -U batman expense_bot

# ПРАВИЛЬНО:
docker exec expense_bot_db pg_dump -U expense_user expense_bot
```
**Решение:** ВСЕГДА используй expense_user для операций с БД!

### ❌ Ошибка с CRLF line endings
**Проблема:** Файлы с Windows line endings на Linux сервере
```bash
# Симптомы:
/bin/bash^M: bad interpreter
syntax error near unexpected token

# РЕШЕНИЕ:
# Установить dos2unix если не установлен
sudo apt-get install dos2unix

# Конвертировать файл
dos2unix filename.sh

# Для всех .sh файлов в директории
find . -name "*.sh" -type f -exec dos2unix {} \;
```

### ❌ Ошибка "Permission denied" при выполнении скриптов
```bash
# Дать права на выполнение
chmod +x script.sh

# Проверить права
ls -la script.sh
```

### ❌ Ошибка подключения к БД
```bash
# Проверить что контейнер БД запущен
docker ps | grep expense_bot_db

# Проверить логи контейнера БД
docker logs expense_bot_db

# Проверить переменные окружения
docker exec expense_bot_app env | grep DB_
```

## Команды для отладки PDF отчетов
```bash
# Проверка последних ошибок в логах (через Docker)
docker logs --tail 100 expense_bot_app | grep -E "(PDF|pdf|report|отчет|error|ERROR|Exception)"

# Проверка логов Django внутри контейнера
docker exec expense_bot_web cat /app/logs/django.log 2>/dev/null | tail -100 | grep -E "(PDF|error|ERROR)"
```