# 🔒 Актуальный план удаления PII из проекта

**Дата создания:** 2025-11-11
**Статус:** 📋 Готов к выполнению
**Приоритет:** 🔴 Высокий (GDPR compliance)

---

## ⚠️ ВАЖНО: Текущая ситуация

### ✅ **УЖЕ ВЫПОЛНЕНО (04.08.2025):**
- **Миграция 0008** удалила поля `username`, `first_name`, `last_name` из модели `Profile`
- **Модель `expenses/models.py`** НЕ СОДЕРЖИТ PII полей
- **База данных** уже очищена от этих полей

### ❌ **ЧТО ОСТАЛОСЬ ИСПРАВИТЬ:**
Персональные данные все еще **используются в коде** при обработке Telegram объектов (`user.username`, `from_user.first_name` и т.д.)

---

## 🔍 Найденные PII (автоматическое сканирование)

**Скрипт:** `python check_pii.py`
**Результат:** 6 файлов, 25 совпадений (включая параметры функций и использование переменных)

### Список файлов:

| # | Файл | Строки | Использование | Приоритет |
|---|------|--------|---------------|-----------|
| 1 | `bot/middlewares/logging_middleware.py` | 62 | `user.username` в логах | 🔴 Критично |
| 2 | `bot/middlewares/privacy_check.py` | 98-100 | FSM state: username, first_name, last_name | 🟠 Высокий |
| 3 | `bot/routers/start.py` | 235-237 | FSM state: username, first_name, last_name | 🟠 Высокий |
| 4 | `bot/middleware/activity_tracker.py` | 56 | `user.username or user.first_name` | 🟡 Средний |
| 5 | `bot/services/pdf_report_html.py` | 186 | `profile.username` (legacy) | 🟢 Низкий |
| 6 | `bot/services/admin_notifier.py` | 284-288 | параметры username/first_name | 🟡 Средний |

**Итого:** 6 файлов требуют изменений

---

## 🗑️ Что будет удалено

### Из кода:
- ❌ Логирование `user.username` в middlewares
- ❌ Сохранение username/first_name/last_name в FSM state
- ❌ Передача username/first_name в функции
- ❌ Отправка username/first_name админу в уведомлениях
- ❌ Использование `profile.username` (legacy)

### Что останется:
- ✅ `telegram_id` - единственный идентификатор пользователя
- ✅ `language_code` - для локализации
- ✅ `bot_username` - username БОТА (не PII!)

---

## 🚀 План выполнения (3-4 часа)

### ШАГ 1: Подготовка (10 минут)

#### 1.1. Создать baseline отчет

```bash
python check_pii.py
cp pii_scan_report.txt pii_scan_baseline.txt
```

#### 1.2. Создать backup (на сервере)

```bash
ssh batman@94.198.220.155
docker exec expense_bot_db pg_dump -U expense_user expense_bot > \
    /home/batman/backups/before_pii_code_removal_$(date +%Y%m%d_%H%M%S).sql
```

---

### ШАГ 2: Изменения в коде (2-3 часа)

#### 2.1. 🔴 Логирование (bot/middlewares/logging_middleware.py)

**Строка 62** - УДАЛИТЬ:
```python
# УДАЛИТЬ эту строку:
'username': user.username if user else None,
```

**Результат:**
```python
log_data = {
    'request_id': self.request_count,
    'timestamp': datetime.now().isoformat(),
    'user_id': user.id if user else None,
    # 'username': УДАЛЕНО для privacy
    'chat_id': chat.id if chat else None,
    'chat_type': chat.type if chat else None,
}
```

**Проверка:** `python check_pii.py` - должно стать 15 совпадений (было 17)

---

#### 2.2. 🟠 FSM State - privacy_check.py (bot/middlewares/privacy_check.py)

**Строки 98-100** - УДАЛИТЬ PII:
```python
# УДАЛИТЬ:
'username': user.username,
'first_name': user.first_name,
'last_name': user.last_name,

# Результат (строки 94-102):
await state.update_data(
    pending_profile_data={
        'telegram_id': user.id,
        'language_code': display_lang,
        'raw_language_code': user.language_code,
        # username, first_name, last_name - УДАЛЕНЫ для privacy
    }
)
```

**Добавить fallback для старых states:**

```python
# ДОБАВИТЬ функцию в файл (перед использованием):
async def _get_pending_data_safe(state: FSMContext) -> dict:
    """Безопасно получить pending_profile_data, удалив PII из старых states"""
    data = await state.get_data()
    pending = data.get('pending_profile_data', {})

    # Удалить PII если они есть (для старых states)
    pending.pop('username', None)
    pending.pop('first_name', None)
    pending.pop('last_name', None)

    return pending

# ИСПОЛЬЗОВАТЬ вместо прямого обращения:
# Было: data['pending_profile_data']
# Стало: await _get_pending_data_safe(state)
```

**Проверка:** `python check_pii.py` - должно стать 9 совпадений (было 15)

---

#### 2.3. 🟠 FSM State - start.py (bot/routers/start.py)

**Строки 235-237** - УДАЛИТЬ PII:
```python
# УДАЛИТЬ:
'username': message.from_user.username,
'first_name': message.from_user.first_name,
'last_name': message.from_user.last_name,

# Результат (строки 231-238):
await state.update_data(
    start_command_args=start_args,
    pending_profile_data={
        'telegram_id': user_id,
        'language_code': display_lang,
        'raw_language_code': message.from_user.language_code,
        # username, first_name, last_name - УДАЛЕНЫ для privacy
    },
)
```

**Проверка:** `python check_pii.py` - должно стать 3 совпадения (было 9)

---

#### 2.4. 🟡 Activity Tracker (bot/middleware/activity_tracker.py)

**Строка 56** - ИЗМЕНИТЬ:
```python
# БЫЛО:
await self._track_user_activity(user.id, user.username or user.first_name)

# СТАЛО:
await self._track_user_activity(user.id)
```

**Изменить сигнатуру метода (строка ~77):**
```python
# БЫЛО:
async def _track_user_activity(self, user_id: int, username: str):

# СТАЛО:
async def _track_user_activity(self, user_id: int):
```

**Изменить уведомление админу (строка ~104):**
```python
# БЫЛО:
f"Пользователь: {username} \\(ID: `{user_id}`\\)\n"

# СТАЛО:
f"User ID: `{user_id}`\n"
```

**Проверка:** `python check_pii.py` - должно стать 1 совпадение (было 3)

---

#### 2.5. 🟡 Admin Notifier (bot/services/admin_notifier.py)

**Строка 270** - изменить сигнатуру:
```python
# БЫЛО:
async def notify_new_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):

# СТАЛО:
async def notify_new_user(user_id: int):
```

**Строки 284-288** - УДАЛИТЬ блоки:
```python
# УДАЛИТЬ:
if first_name:
    message += f"Имя: {escape_markdown_v2(first_name)}\n"

if username:
    message += f"Username: @{escape_markdown_v2(username)}\n"

# Оставить только:
message = (
    f"🎉 *Новый пользователь\\!*\n\n"
    f"ID: `{user_id}`\n"
    f"Время: {escape_markdown_v2(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
)
```

**Найти все вызовы `notify_new_user()`:**
```bash
grep -rn "notify_new_user" bot/ --include="*.py" | grep -v "^bot/services/admin_notifier.py"
```

Убрать передачу username/first_name из всех вызовов.

**Проверка:** `python check_pii.py` - должно стать 1 совпадение

---

#### 2.6. 🟢 PDF Reports (bot/services/pdf_report_html.py)

**Строка 186** - ИЗМЕНИТЬ:
```python
# БЫЛО:
'user_name': profile.full_name or f"@{profile.username}" if profile.username else "Пользователь",

# СТАЛО:
'user_name': f"User {profile.telegram_id}",
```

**Проверка:** `python check_pii.py` - должно стать 0 совпадений ✅

---

### ШАГ 3: Тестирование (30 минут)

#### 3.1. Финальная проверка кода

```bash
python check_pii.py
# Должно вывести: [OK] PII not found in code!
```

#### 3.2. Локальное тестирование

1. **Регистрация:** /start → принять политику
2. **Создание траты:** создать 3-5 трат
3. **Логи:** проверить что нет username
4. **Django admin:** проверить что работает

#### 3.3. Проверить файлы

```bash
# Проверить что изменения сохранены
git diff bot/middlewares/logging_middleware.py
git diff bot/middlewares/privacy_check.py
git diff bot/routers/start.py
git diff bot/middleware/activity_tracker.py
git diff bot/services/admin_notifier.py
git diff bot/services/pdf_report_html.py
```

---

### ШАГ 4: Коммит и деплой (30 минут)

#### 4.1. Git commit

```bash
git status
git add bot/ check_pii.py docs/PII_REMOVAL_PLAN_ACTUAL.md
git diff --cached

git commit -m "Privacy: Remove PII from code (username, first_name, last_name)

- Remove user.username from logging middleware
- Remove username/first_name/last_name from FSM states
- Remove PII from admin notifications
- Remove PII from activity tracker
- Update PDF reports to show User ID instead of username
- Add automated PII detection script (check_pii.py)

Database migration already completed: 0008_remove_profile_* (2025-08-04)
This commit removes PII usage from code only.

BREAKING CHANGE: Logging format changed, admin notifications changed

Refs: GDPR compliance, privacy by design
Verified: python check_pii.py returns 0 matches"

git push origin master
```

#### 4.2. Деплой

```bash
# На сервере
ssh batman@94.198.220.155
cd /home/batman/expense_bot

# Остановить
docker-compose down

# Обновить код
git pull origin master

# Запустить
docker-compose up -d

# Проверить логи
docker-compose logs --tail=100 bot | grep -i error
```

#### 4.3. Проверка после деплоя

```bash
# Проверить что username не логируется
docker-compose logs --tail=200 bot | grep "username"
# Должно быть ПУСТО или только в старых логах

# Проверить последние 20 записей
docker-compose logs --tail=20 bot | grep "user_id"
# Должно показывать только telegram_id
```

---

## ✅ Чеклист выполнения

### Подготовка
- [ ] Запущен `python check_pii.py` → создан baseline
- [ ] Backup БД создан на сервере

### Изменения кода
- [ ] `logging_middleware.py:62` - удалена строка с username
- [ ] `privacy_check.py:98-100` - удалены PII из FSM state
- [ ] `privacy_check.py` - добавлен fallback `_get_pending_data_safe()`
- [ ] `start.py:235-237` - удалены PII из FSM state
- [ ] `activity_tracker.py:56` - изменен вызов без username
- [ ] `activity_tracker.py:~77` - изменена сигнатура метода
- [ ] `activity_tracker.py:~104` - изменено уведомление
- [ ] `admin_notifier.py:270` - изменена сигнатура
- [ ] `admin_notifier.py:284-288` - удалены блоки с PII
- [ ] Найдены все вызовы `notify_new_user()` - убраны параметры
- [ ] `pdf_report_html.py:186` - изменено на User ID

### Проверки после каждого блока
- [ ] После logging: `python check_pii.py` → 23 совпадения (было 25)
- [ ] После privacy_check: `python check_pii.py` → 17 совпадений (было 23)
- [ ] После start.py: `python check_pii.py` → 11 совпадений (было 17)
- [ ] После activity_tracker: `python check_pii.py` → 7 совпадений (было 11)
- [ ] После admin_notifier: `python check_pii.py` → 1 совпадение (было 7)
- [ ] После pdf_report_html: `python check_pii.py` → 0 совпадений ✅

### Тестирование
- [ ] Финальная проверка: `python check_pii.py` → [OK] PII not found
- [ ] Регистрация работает локально
- [ ] Создание трат работает
- [ ] Логи не содержат username
- [ ] Django admin работает

### Деплой
- [ ] Git commit создан
- [ ] Git push выполнен
- [ ] Код обновлен на сервере: `git pull`
- [ ] Контейнеры перезапущены
- [ ] Логи проверены на ошибки
- [ ] Username не появляется в новых логах

---

## 🔄 Откат (если что-то пошло не так)

### Быстрый откат кода

```bash
# На сервере
ssh batman@94.198.220.155
cd /home/batman/expense_bot

# Найти commit hash ДО изменений
git log --oneline -5

# Откатить код
git reset --hard <commit_hash_before_pii_removal>

# Перезапустить
docker-compose restart

# Проверить
docker-compose logs --tail=50 bot
```

**Примечание:** Откат БД НЕ требуется, т.к. миграция уже была применена 4 месяца назад.

---

## 📊 Автоматизированные проверки

### Скрипт check_pii.py

**Использование:**
```bash
python check_pii.py

# Вывод если PII найдено:
[PII FOUND] 5 files contain PII:
...
[SUMMARY] 17 total matches in 5 files

# Вывод если PII НЕ найдено:
[OK] PII not found in code!
```

### Pre-commit hook (опционально)

Создать `.git/hooks/pre-commit`:
```bash
#!/bin/bash
python check_pii.py
if [ $? -ne 0 ]; then
    echo "[BLOCKED] PII detected in code! Please remove before commit."
    exit 1
fi
echo "[OK] No PII found, proceeding with commit"
```

```bash
chmod +x .git/hooks/pre-commit
```

---

## 🎯 Ожидаемый результат

После выполнения:
1. ✅ **Код**: не содержит использования username/first_name/last_name
2. ✅ **Логи**: только telegram_id для идентификации
3. ✅ **FSM states**: не хранят PII
4. ✅ **Уведомления админу**: только user_id
5. ✅ **PDF отчеты**: "User {telegram_id}" вместо имени
6. ✅ **GDPR compliance**: минимизация персональных данных
7. ✅ **Автоматическая проверка**: `python check_pii.py` → 0 совпадений

---

## 📝 История изменений

| Дата | Событие | Статус |
|------|---------|--------|
| 04.08.2025 | Миграция 0008: удаление PII из БД | ✅ Выполнено |
| 11.11.2025 | Создание плана удаления PII из кода | 📋 В процессе |
| TBD | Удаление PII из кода | ⏳ Планируется |
| TBD | Деплой на production | ⏳ Планируется |

---

**Время выполнения:** 3-4 часа
**Downtime:** нет (только перезапуск контейнеров 10-30 секунд)
**Риски:** минимальные (БД уже очищена)
**Откат:** простой (git reset)
