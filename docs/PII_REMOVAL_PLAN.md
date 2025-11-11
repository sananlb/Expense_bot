# 🔒 План удаления PII (Personally Identifiable Information) из проекта

**Дата создания:** 2025-11-11
**Статус:** 📋 В планировании
**Ответственный:** DevOps/Backend team
**Приоритет:** 🔴 Высокий (GDPR compliance)

---

## 📌 Содержание

- [Цель и обоснование](#цель-и-обоснование)
- [Текущая ситуация](#текущая-ситуация)
- [Что будет удалено](#что-будет-удалено)
- [План реализации](#план-реализации)
- [Автоматизированные проверки](#автоматизированные-проверки)
- [Риски и меры безопасности](#риски-и-меры-безопасности)
- [Чеклист выполнения](#чеклист-выполнения)
- [Откат изменений](#откат-изменений)

---

## 🎯 Цель и обоснование

### Цель:
Полностью удалить персональные данные (`username`, `first_name`, `last_name`) из кода, логов и базы данных. Использовать ТОЛЬКО `telegram_id` для идентификации пользователей.

### Обоснование:
1. **GDPR Compliance:** Минимизация обработки персональных данных
2. **Privacy by Design:** Невозможность утечки данных, которых нет
3. **Безопасность логов:** Логи не содержат PII и могут безопасно передаваться в системы мониторинга
4. **Упрощение архитектуры:** Меньше данных = меньше ответственности
5. **Защита от утечек:** Даже при компрометации логов/БД невозможно идентифицировать пользователей

### Почему telegram_id достаточно:
- ✅ Уникально идентифицирует пользователя в системе
- ✅ Позволяет найти пользователя в БД для отладки
- ✅ Не раскрывает личность без доступа к Telegram API
- ✅ Необходим для работы Telegram Bot API

---

## 📊 Текущая ситуация

### В базе данных (`database/models.py`):

```python
class Profile(models.Model):
    telegram_id = models.BigIntegerField(unique=True, primary_key=True)  # ✅ Оставляем
    first_name = models.CharField(max_length=100)                         # ❌ Удалить
    username = models.CharField(max_length=100, null=True, blank=True)    # ❌ Удалить
    # ... остальные поля
```

### Найдено файлов с использованием `username`: **31**

#### Распределение по категориям:

| Категория | Файлов | Критичность | Описание |
|-----------|--------|-------------|----------|
| Логирование | 2 | 🔴 Критичная | Пишется в файлы логов постоянно |
| Уведомления админу | 2 | 🟠 Высокая | Хранится в Telegram переписке |
| FSM State | 2 | 🟡 Средняя | Временное хранение в Redis |
| Модели и миграции | 5 | 🟡 Средняя | База данных |
| UI/Отображение | 4 | 🟢 Низкая | PDF, сообщения пользователю |
| Архивные файлы | 16 | ⚪ Не трогаем | Уже в архиве |

**Полный список файлов см. в [Приложении A](#приложение-a-полный-список-файлов)**

---

## 🗑️ Что будет удалено

### Из базы данных:
- ❌ `Profile.first_name`
- ❌ `Profile.username`
- ❌ `Profile.last_name` (если есть)

### Из кода:
- ❌ Все обращения к `user.username`
- ❌ Все обращения к `user.first_name`
- ❌ Все обращения к `user.last_name`
- ❌ Все обращения к `profile.username`
- ❌ Все обращения к `profile.first_name`
- ❌ Property `profile.full_name` (если использует PII)

### Из логов:
- ❌ Username в `logging_middleware.py`
- ❌ Username в `activity_tracker.py`
- ❌ Username в уведомлениях админу

### Из FSM State:
- ❌ `pending_profile_data['username']`
- ❌ `pending_profile_data['first_name']`
- ❌ `pending_profile_data['last_name']`

### Что остается:
- ✅ `telegram_id` (единственный идентификатор)
- ✅ `language_code` (для локализации)
- ✅ Все остальные поля Profile (подписка, настройки и т.д.)

---

## 🚀 План реализации

### **ШАГ 0: Подготовка и автоматизация** ⏱️ 1-2 часа

**Цель:** Создать инструменты для отслеживания прогресса

#### 0.1. Создать скрипт проверки PII в коде

Создать файл `check_pii.py` в корне проекта:

```python
#!/usr/bin/env python3
"""
Скрипт для поиска PII (username, first_name, last_name) в коде
"""
import os
import re
from pathlib import Path

# Паттерны для поиска
PII_PATTERNS = [
    r'\.username\b',
    r'\.first_name\b',
    r'\.last_name\b',
    r'\.full_name\b',
    r'\["username"\]',
    r'\["first_name"\]',
    r'\["last_name"\]',
    r'username\s*=',
    r'first_name\s*=',
    r'last_name\s*=',
]

# Директории для исключения
EXCLUDE_DIRS = {
    'venv', '.git', '__pycache__', 'archive', 'archive_20251102',
    'archive_20251105', 'archive_20251109', 'archive_20251110',
    'node_modules', '.pytest_cache', 'staticfiles'
}

# Файлы для исключения
EXCLUDE_FILES = {
    'check_pii.py',  # Сам скрипт
    'PII_REMOVAL_PLAN.md',  # Этот документ
}

def check_file(file_path: Path) -> list:
    """Проверить файл на наличие PII паттернов"""
    matches = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                for pattern in PII_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        matches.append({
                            'file': str(file_path),
                            'line': line_num,
                            'content': line.strip(),
                            'pattern': pattern
                        })
    except Exception as e:
        print(f"❌ Ошибка при чтении {file_path}: {e}")

    return matches

def scan_project(root_dir: str = '.'):
    """Сканировать весь проект"""
    root = Path(root_dir)
    all_matches = []

    for file_path in root.rglob('*.py'):
        # Пропускаем исключенные директории
        if any(excluded in file_path.parts for excluded in EXCLUDE_DIRS):
            continue

        # Пропускаем исключенные файлы
        if file_path.name in EXCLUDE_FILES:
            continue

        matches = check_file(file_path)
        if matches:
            all_matches.extend(matches)

    return all_matches

def generate_report(matches: list) -> str:
    """Сгенерировать отчет"""
    if not matches:
        return "✅ PII не найдено в коде!"

    # Группировка по файлам
    by_file = {}
    for match in matches:
        file = match['file']
        if file not in by_file:
            by_file[file] = []
        by_file[file].append(match)

    report = f"🔍 Найдено PII в {len(by_file)} файлах:\n\n"

    for file, file_matches in sorted(by_file.items()):
        report += f"\n📄 {file} ({len(file_matches)} совпадений):\n"
        for match in file_matches:
            report += f"   Строка {match['line']}: {match['content'][:80]}\n"

    report += f"\n📊 Всего совпадений: {len(matches)}\n"

    return report

if __name__ == '__main__':
    print("🔍 Сканирование проекта на наличие PII...\n")
    matches = scan_project()
    report = generate_report(matches)
    print(report)

    # Сохранить отчет
    with open('pii_scan_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n📝 Отчет сохранен в pii_scan_report.txt")

    # Exit код для CI/CD
    exit(0 if not matches else 1)
```

#### 0.2. Запустить первичное сканирование

```bash
python check_pii.py
```

**Результат:** Файл `pii_scan_report.txt` с полным списком мест использования PII

#### 0.3. Создать baseline для отслеживания прогресса

```bash
# Сохранить начальное состояние
cp pii_scan_report.txt pii_scan_baseline.txt

# После каждого блока изменений запускать:
python check_pii.py
diff pii_scan_baseline.txt pii_scan_report.txt
```

---

### **ШАГ 1: Анализ и документирование** ⏱️ 1 час

**Цель:** Полное понимание использования PII полей

#### 1.1. Анализ использования в моделях

```bash
# Проверить все property и методы использующие PII
grep -n "self.username\|self.first_name\|self.last_name\|self.full_name" database/models.py expenses/models.py
```

**Результаты занести в таблицу:**

| Файл | Строка | Использование | Замена |
|------|--------|---------------|--------|
| database/models.py | 50 | `__str__` метод | `return f"User {self.telegram_id}"` |
| ... | ... | ... | ... |

#### 1.2. Проверить зависимости в Django admin

```bash
# Найти все места в admin.py использующие PII
grep -rn "username\|first_name\|last_name" expenses/admin.py admin_panel/
```

#### 1.3. Проверить использование в serializers (если есть)

```bash
find . -name "serializers.py" -exec grep -Hn "username\|first_name" {} \;
```

**Результат:** Полный список всех зависимостей с планом замены

---

### **ШАГ 2: Добавление fallback для FSM states** ⏱️ 30 минут

**🔴 КРИТИЧНО:** Выполнить ДО изменения остального кода!

**Цель:** Обеспечить graceful degradation для старых FSM states содержащих PII

#### 2.1. Добавить fallback в `privacy_check.py`

```python
# bot/middlewares/privacy_check.py

# Старый код (строка ~98):
await state.update_data(
    pending_profile_data={
        'telegram_id': user.id,
        'language_code': display_lang,
        'raw_language_code': user.language_code,
        'username': user.username,      # ❌
        'first_name': user.first_name,  # ❌
        'last_name': user.last_name,    # ❌
    }
)

# Новый код с fallback:
await state.update_data(
    pending_profile_data={
        'telegram_id': user.id,
        'language_code': display_lang,
        'raw_language_code': user.language_code,
        # username, first_name, last_name УДАЛЕНЫ для privacy
    }
)

# Добавить функцию обработки старых states:
async def _get_pending_data_safe(state: FSMContext) -> dict:
    """Безопасно получить pending_profile_data, удалив PII из старых states"""
    data = await state.get_data()
    pending = data.get('pending_profile_data', {})

    # Удалить PII если они есть (для старых states)
    pending.pop('username', None)
    pending.pop('first_name', None)
    pending.pop('last_name', None)

    return pending
```

#### 2.2. Добавить fallback в `start.py`

Аналогичные изменения в `bot/routers/start.py` (строка ~235)

#### 2.3. Добавить middleware для очистки старых states

Создать файл `bot/middlewares/fsm_cleanup.py`:

```python
"""
Middleware для очистки PII из старых FSM states
Запускается один раз при каждом запросе пользователя
"""
from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.fsm.context import FSMContext
from typing import Callable, Dict, Any, Awaitable
import logging

logger = logging.getLogger(__name__)

class FSMCleanupMiddleware(BaseMiddleware):
    """Удаляет PII из FSM state если они там есть"""

    def __init__(self):
        self.cleaned_users = set()  # Кеш очищенных пользователей

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        state: FSMContext = data.get('state')

        if state:
            user_id = None
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

            # Очищаем только один раз на пользователя
            if user_id and user_id not in self.cleaned_users:
                await self._cleanup_pii(state, user_id)
                self.cleaned_users.add(user_id)

        return await handler(event, data)

    async def _cleanup_pii(self, state: FSMContext, user_id: int):
        """Удалить PII из state если они есть"""
        try:
            data = await state.get_data()

            if 'pending_profile_data' in data:
                pending = data['pending_profile_data']

                # Проверить наличие PII
                has_pii = any(key in pending for key in ['username', 'first_name', 'last_name'])

                if has_pii:
                    logger.warning(f"Found PII in FSM state for user {user_id}, cleaning...")

                    # Удалить PII
                    pending.pop('username', None)
                    pending.pop('first_name', None)
                    pending.pop('last_name', None)

                    # Обновить state
                    await state.update_data(pending_profile_data=pending)

                    logger.info(f"PII cleaned from FSM state for user {user_id}")

        except Exception as e:
            logger.error(f"Error cleaning FSM state for user {user_id}: {e}")
```

#### 2.4. Зарегистрировать middleware в bot.py

```python
# bot/bot.py или main.py

from bot.middlewares.fsm_cleanup import FSMCleanupMiddleware

# Добавить после других middlewares:
dp.update.middleware(FSMCleanupMiddleware())
```

**Результат:**
- ✅ Старые FSM states не вызывают ошибок
- ✅ PII автоматически удаляется при первом запросе пользователя
- ✅ Логируется для мониторинга

---

### **ШАГ 3: Изменение кода приложения** ⏱️ 3-4 часа

**Цель:** Убрать все обращения к PII полям из кода

**Последовательность изменения (по приоритету):**

#### 3.1. 🔴 Критичные файлы (логирование)

##### `bot/middlewares/logging_middleware.py`

```python
# Строка 62 - УДАЛИТЬ:
'username': user.username if user else None,  # ❌ УДАЛИТЬ ЭТУ СТРОКУ

# Результат (строки 58-65):
log_data = {
    'request_id': self.request_count,
    'timestamp': datetime.now().isoformat(),
    'user_id': user.id if user else None,
    # 'username': УДАЛЕНО для privacy
    'chat_id': chat.id if chat else None,
    'chat_type': chat.type if chat else None,
}
```

**Проверка:** `python check_pii.py` - строка должна исчезнуть из отчета

##### `bot/middleware/activity_tracker.py`

```python
# Строка 56 - ИЗМЕНИТЬ:
# Было:
await self._track_user_activity(user.id, user.username or user.first_name)

# Стало:
await self._track_user_activity(user.id)

# Строка 77, 92, 95 - изменить сигнатуру метода:
async def _track_user_activity(self, user_id: int):  # Убрать username параметр
    """Track user activity in Redis"""
    # ... код без использования username

# Строка 104 - изменить сообщение админу:
# Было:
f"Пользователь: {username} \\(ID: `{user_id}`\\)\n"

# Стало:
f"User ID: `{user_id}`\n"
```

**Проверка:** Запустить `python check_pii.py`

#### 3.2. 🟠 Уведомления админу

##### `bot/services/admin_notifier.py`

```python
# Строка 270 - изменить сигнатуру:
# Было:
async def notify_new_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):

# Стало:
async def notify_new_user(user_id: int):

# Строки 284-288 - УДАЛИТЬ блоки с PII:
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

**Важно:** Найти все вызовы `notify_new_user()` и убрать передачу username/first_name:

```bash
grep -rn "notify_new_user" bot/ --include="*.py"
```

#### 3.3. 🟡 FSM State (уже сделано в Шаге 2)

Проверить что изменения из Шага 2 работают корректно.

#### 3.4. 🟢 UI/Отображение

##### `bot/services/pdf_report_html.py`

```python
# Строка 186 - заменить:
# Было:
'user_name': profile.full_name or f"@{profile.username}" if profile.username else "Пользователь",

# Стало:
'user_name': f"User {profile.telegram_id}",
```

##### Другие места отображения

Найти все места где отображается username в UI:

```bash
grep -rn "\.username\|\.first_name" bot/routers/ bot/keyboards.py --include="*.py"
```

Заменить на:
- `f"User {telegram_id}"` для сообщений
- Убрать вообще, если не критично

#### 3.5. 🔵 Household/Family/Referral

##### `bot/routers/household.py`, `bot/services/household.py`

Найти отображение имен членов семьи:

```bash
grep -n "username\|first_name" bot/routers/household.py bot/services/household.py
```

Заменить на:
- "Член семьи" или "Family Member"
- `f"User {telegram_id}"` если нужен идентификатор

##### `bot/routers/referral.py`, `bot/services/affiliate.py`

Аналогично для рефералов:
- "Реферал #1", "Реферал #2" и т.д.
- Или `f"User {telegram_id}"`

#### 3.6. 📋 Django Admin

##### `expenses/admin.py`

```python
# Изменить класс ProfileAdmin:

class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'telegram_id',          # ✅ Оставить
        # 'username',           # ❌ УДАЛИТЬ
        # 'first_name',         # ❌ УДАЛИТЬ
        'subscription_end_date',
        'is_beta_tester',
        'last_activity',
        'is_active',
    ]

    search_fields = [
        'telegram_id',          # ✅ Оставить
        # 'username',           # ❌ УДАЛИТЬ
        # 'first_name',         # ❌ УДАЛИТЬ
    ]

    list_filter = [
        'is_beta_tester',
        'is_active',
        'locale',
    ]
```

#### 3.7. 🔍 Все места создания Profile

Найти все `Profile.objects.create()`:

```bash
grep -rn "Profile\.objects\.create\|profile\.save()" bot/ --include="*.py"
```

Проверить каждое место и убрать передачу PII:

```python
# Было:
Profile.objects.create(
    telegram_id=user_id,
    username=username,      # ❌ УДАЛИТЬ
    first_name=first_name,  # ❌ УДАЛИТЬ
    ...
)

# Стало:
Profile.objects.create(
    telegram_id=user_id,
    # username, first_name - УДАЛЕНЫ
    ...
)
```

**После каждого подшага:**
```bash
python check_pii.py
git diff pii_scan_baseline.txt pii_scan_report.txt
```

---

### **ШАГ 4: Изменение модели Profile** ⏱️ 30 минут

**Цель:** Удалить поля из модели Django

#### 4.1. Изменить `database/models.py`

```python
class Profile(models.Model):
    """Профиль пользователя Telegram"""
    telegram_id = models.BigIntegerField(unique=True, primary_key=True)
    # first_name = models.CharField(max_length=100)  # ❌ УДАЛЕНО для privacy
    # username = models.CharField(max_length=100, null=True, blank=True)  # ❌ УДАЛЕНО для privacy

    # Подписка и доступ
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    # ... остальные поля без изменений

    def __str__(self):
        # Было: return f"{self.first_name} (@{self.username or 'no_username'})"
        return f"User {self.telegram_id}"  # ✅ НОВОЕ
```

#### 4.2. Проверить property методы

Если есть `full_name` или другие property использующие PII - удалить:

```python
# Если было:
@property
def full_name(self):
    return f"{self.first_name} {self.last_name or ''}".strip()

# УДАЛИТЬ весь property!
```

#### 4.3. Проверить другие модели

```bash
grep -rn "profile\.username\|profile\.first_name" database/models.py expenses/models.py
```

---

### **ШАГ 5: Создание миграции Django** ⏱️ 15 минут

#### 5.1. Создать миграцию

```bash
python manage.py makemigrations --name remove_pii_fields
```

#### 5.2. Просмотреть сгенерированную миграцию

```bash
# Найти номер миграции
ls -la expenses/migrations/ | grep remove_pii

# Просмотреть содержимое
cat expenses/migrations/XXXX_remove_pii_fields.py
```

Должно быть примерно:

```python
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('expenses', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='username',
        ),
    ]
```

#### 5.3. Просмотреть SQL (для понимания что будет выполнено)

```bash
python manage.py sqlmigrate expenses XXXX
```

Вывод должен быть примерно:

```sql
BEGIN;
--
-- Remove field first_name from profile
--
ALTER TABLE "profiles" DROP COLUMN "first_name" CASCADE;
--
-- Remove field username from profile
--
ALTER TABLE "profiles" DROP COLUMN "username" CASCADE;
COMMIT;
```

#### 5.4. Проверить план миграции

```bash
python manage.py migrate --plan
```

---

### **ШАГ 6: Тестирование локально** ⏱️ 1-2 часа

**Цель:** Убедиться что всё работает без PII полей

#### 6.1. Финальная проверка кода

```bash
# Запустить финальное сканирование
python check_pii.py

# Должно вывести:
# ✅ PII не найдено в коде!

# Если есть совпадения - исправить их!
```

#### 6.2. Запустить линтеры (если есть)

```bash
# Flake8
flake8 bot/ database/ expenses/

# Mypy (если используется)
mypy bot/ database/ expenses/

# Pytest
pytest tests/ -v
```

#### 6.3. Применить миграцию локально

```bash
python manage.py migrate
```

#### 6.4. Ручное тестирование

**Сценарии:**

1. **Регистрация нового пользователя:**
   - `/start` → принять политику
   - Проверить что профиль создается
   - Проверить логи: `tail -f logs/django.log | grep -v username`

2. **Создание трат:**
   - Создать 3-5 трат разных категорий
   - Проверить логи на отсутствие PII

3. **PDF отчеты:**
   - Сгенерировать дневной отчет
   - Открыть PDF - проверить что вместо имени "User {telegram_id}"

4. **Django Admin:**
   - Зайти в админку: http://localhost:8000/admin/
   - Перейти в Profiles
   - Проверить что список отображается корректно
   - Попробовать поиск по telegram_id

5. **Старые FSM states (важно!):**
   - Если есть тестовая БД со старыми states:
     - Взаимодействовать с ботом
     - Проверить что нет ошибок
     - Проверить логи на warnings о очистке PII

6. **Семейный бюджет / Рефералы (если используется):**
   - Проверить отображение
   - Не должно быть ошибок AttributeError

**Checklist тестирования:**

- [ ] Новая регистрация работает
- [ ] Создание трат работает
- [ ] PDF отчеты генерируются
- [ ] Django admin работает
- [ ] Поиск по telegram_id работает
- [ ] Нет ошибок в логах
- [ ] `python check_pii.py` возвращает 0 совпадений
- [ ] Все тесты pytest проходят

---

### **ШАГ 7: Подготовка к деплою** ⏱️ 30 минут

#### 7.1. Создать backup БД на сервере

```bash
ssh batman@94.198.220.155

# Создать директорию для бэкапов если не существует
mkdir -p /home/batman/backups/

# Создать backup
docker exec expense_bot_db pg_dump -U expense_user expense_bot > \
    /home/batman/backups/before_pii_removal_$(date +%Y%m%d_%H%M%S).sql

# Проверить размер
ls -lh /home/batman/backups/before_pii_removal_*.sql

# Должен быть > 0, желательно несколько MB
```

#### 7.2. Сохранить backup локально (дополнительная безопасность)

```bash
# На локальной машине
scp batman@94.198.220.155:/home/batman/backups/before_pii_removal_*.sql ./backups/
```

#### 7.3. Коммит изменений

```bash
# Проверить статус
git status

# Добавить все изменения
git add bot/ database/ expenses/ docs/ check_pii.py

# Проверить что добавляется
git diff --cached

# Создать коммит
git commit -m "Privacy: Remove PII fields (username, first_name, last_name)

- Removed username, first_name, last_name from Profile model
- Updated all code to use only telegram_id for identification
- Added FSM cleanup middleware for old states
- Updated logging to exclude PII
- Updated admin notifications to show only user_id
- Updated PDF reports to display 'User {telegram_id}'
- Added automated PII detection script (check_pii.py)

BREAKING CHANGE: Profile model no longer has username/first_name fields
Migration: expenses/XXXX_remove_pii_fields.py

Refs: GDPR compliance, privacy by design"

# Push в репозиторий
git push origin master
```

#### 7.4. Документировать план отката

Создать файл `docs/PII_REMOVAL_ROLLBACK.md`:

```markdown
# План отката удаления PII

## В случае критических проблем после деплоя

### 1. Откат кода
\`\`\`bash
ssh batman@94.198.220.155
cd /home/batman/expense_bot
git fetch origin
git reset --hard <commit_hash_before_pii_removal>
\`\`\`

### 2. Откат миграции БД
\`\`\`bash
# Откат миграции Django
docker-compose run --rm web python manage.py migrate expenses XXXX_previous_migration

# Или полный откат БД из backup
docker exec -i expense_bot_db psql -U expense_user expense_bot < \
    /home/batman/backups/before_pii_removal_YYYYMMDD_HHMMSS.sql
\`\`\`

### 3. Перезапуск
\`\`\`bash
docker-compose restart
\`\`\`

### 4. Проверка
\`\`\`bash
docker-compose logs --tail=100 bot
docker-compose ps
\`\`\`
```

---

### **ШАГ 8: Деплой на production** ⏱️ 30 минут

**⚠️ Лучшее время:** В период минимальной активности (например, 3-4 часа ночи MSK)

#### 8.1. Уведомить пользователей (опционально)

Если есть канал уведомлений:
```
"⚙️ Техническое обслуживание
Сегодня в 03:00-03:30 будет обновление системы.
Возможны кратковременные задержки в работе бота."
```

#### 8.2. Подключиться к серверу

```bash
ssh batman@94.198.220.155
cd /home/batman/expense_bot
```

#### 8.3. Финальный backup (на всякий случай)

```bash
docker exec expense_bot_db pg_dump -U expense_user expense_bot > \
    /home/batman/backups/final_before_pii_removal_$(date +%Y%m%d_%H%M%S).sql
```

#### 8.4. Остановить контейнеры

```bash
docker-compose down
```

#### 8.5. Обновить код

```bash
git fetch origin
git reset --hard origin/master
git pull origin master
```

#### 8.6. Применить миграцию

```bash
# Запустить только для миграции
docker-compose run --rm web python manage.py migrate

# Проверить что миграция прошла успешно
# Должно быть: "Applying expenses.XXXX_remove_pii_fields... OK"
```

#### 8.7. Запустить контейнеры

```bash
docker-compose up -d
```

#### 8.8. Проверить логи

```bash
# Логи бота
docker-compose logs --tail=100 bot

# Логи веб
docker-compose logs --tail=100 web

# Проверить на ошибки
docker-compose logs --tail=200 bot | grep -i error
docker-compose logs --tail=200 web | grep -i error
```

#### 8.9. Проверить статус

```bash
docker-compose ps

# Все контейнеры должны быть "Up"
```

---

### **ШАГ 9: Проверка после деплоя** ⏱️ 30 минут

#### 9.1. Базовые проверки

```bash
# Нет критичных ошибок в логах
docker-compose logs --tail=500 bot | grep -i "error\|exception\|traceback" | wc -l
# Должно быть 0 или минимальное количество

# Бот отвечает на команды
# Попробовать в Telegram: /start
```

#### 9.2. Проверить отсутствие PII в логах

```bash
# Проверить что username не логируется
docker-compose logs --tail=1000 bot | grep "username"
# Должно быть ПУСТО или только в старых логах

# Проверить недавние логи (последние 50 записей)
docker-compose logs --tail=50 bot | grep "user_id"
# Должно показывать только telegram_id, без username
```

#### 9.3. Тестирование основных сценариев

**В Telegram боте:**

1. ✅ Регистрация нового пользователя
2. ✅ Создание траты
3. ✅ Просмотр отчета
4. ✅ Генерация PDF (если доступно)
5. ✅ Команды /start, /help, /expenses

#### 9.4. Django Admin

```bash
# Открыть в браузере
https://expensebot.duckdns.org/admin/

# Проверить:
- ✅ Список профилей отображается
- ✅ Поиск по telegram_id работает
- ✅ Нет ошибок при открытии профиля
```

#### 9.5. Мониторинг метрик

```bash
# Проверить rate limiter stats в логах
docker-compose logs --tail=200 bot | grep "Rate limiter stats"

# Должны быть запросы от пользователей
# Например: "Rate limiter stats: requests=54, blocked=0, unique_users=5"
```

#### 9.6. Проверка БД

```bash
# Проверить что поля удалены
docker exec -it expense_bot_db psql -U expense_user -d expense_bot -c "\d profiles"

# В списке колонок НЕ должно быть:
# - username
# - first_name
# - last_name
```

---

### **ШАГ 10: Очистка и финализация** ⏱️ 30 минут

#### 10.1. Очистить старые логи с PII (опционально)

**⚠️ Осторожно:** Удаляет логи безвозвратно!

```bash
# Архивировать старые логи
ssh batman@94.198.220.155
cd /home/batman/expense_bot

# Создать архив
mkdir -p /home/batman/archive_logs_$(date +%Y%m%d)
mv logs/*.log /home/batman/archive_logs_$(date +%Y%m%d)/

# Или просто удалить старые (если они большие)
# rm logs/django_*.log

# Перезапустить для создания новых чистых логов
docker-compose restart bot web
```

#### 10.2. Обновить документацию

**Файл `CLAUDE.md` - добавить:**

```markdown
## Privacy & GDPR

### PII (Personally Identifiable Information)

**ВАЖНО:** В проекте НЕ используются и НЕ хранятся следующие персональные данные:
- ❌ `username` (Telegram username)
- ❌ `first_name` (Имя пользователя)
- ❌ `last_name` (Фамилия пользователя)

**Используется ТОЛЬКО:**
- ✅ `telegram_id` - уникальный идентификатор пользователя в Telegram

### Логирование

Все логи содержат ТОЛЬКО `telegram_id` для идентификации пользователей.
Username и другие PII НИКОГДА не логируются.

**Пример лога:**
\`\`\`json
{
  "user_id": 123456789,
  "message_type": "text",
  "timestamp": "2025-11-11T20:00:00"
}
\`\`\`

### Проверка на PII

Для автоматической проверки кода на наличие PII:
\`\`\`bash
python check_pii.py
\`\`\`

Скрипт должен возвращать: ✅ PII не найдено в коде!
```

#### 10.3. Обновить README (если есть упоминания PII)

Проверить и удалить любые упоминания username в документации:

```bash
grep -r "username" README.md docs/ --include="*.md" | grep -v "PII_REMOVAL"
```

#### 10.4. Добавить в CI/CD проверку PII (будущее)

Создать файл `.github/workflows/pii-check.yml` (если используется GitHub Actions):

```yaml
name: PII Detection

on: [push, pull_request]

jobs:
  check-pii:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Check for PII in code
        run: |
          python check_pii.py
          if [ $? -ne 0 ]; then
            echo "❌ PII detected in code!"
            exit 1
          fi
          echo "✅ No PII found"
```

#### 10.5. Финальный отчет

Создать файл `docs/PII_REMOVAL_COMPLETION_REPORT.md`:

```markdown
# Отчет о завершении удаления PII

**Дата:** 2025-11-11
**Статус:** ✅ Завершено успешно

## Выполненные работы

- ✅ Удалены поля username, first_name, last_name из модели Profile
- ✅ Обновлены все 31 файл с использованием PII
- ✅ Добавлен FSM cleanup middleware
- ✅ Обновлено логирование (только telegram_id)
- ✅ Обновлены уведомления админу
- ✅ Обновлен Django admin
- ✅ Создан скрипт автоматической проверки (check_pii.py)
- ✅ Миграция БД применена успешно
- ✅ Тестирование пройдено
- ✅ Деплой на production выполнен

## Метрики

- Файлов изменено: 31
- Строк удалено: ~150
- Поля БД удалены: 2 (username, first_name)
- Время выполнения: X часов

## Проверка

\`\`\`bash
python check_pii.py
# Результат: ✅ PII не найдено в коде!
\`\`\`

## Backup

Backup БД создан: `/home/batman/backups/before_pii_removal_YYYYMMDD_HHMMSS.sql`

## Проблемы

Нет. Все работает штатно.
```

---

## 🔍 Автоматизированные проверки

### Скрипт проверки PII в коде

**Файл:** `check_pii.py` (создан в Шаге 0)

**Использование:**

```bash
# Запуск проверки
python check_pii.py

# Вывод если PII найдено:
🔍 Найдено PII в 5 файлах:

📄 bot/middlewares/logging_middleware.py (2 совпадения):
   Строка 62: 'username': user.username if user else None,
   Строка 121: logger.info(f"Request: {json.dumps(log_data)}")

📊 Всего совпадений: 10

# Вывод если PII НЕ найдено:
✅ PII не найдено в коде!
```

### Интеграция в разработку

**Pre-commit hook** (`.git/hooks/pre-commit`):

```bash
#!/bin/bash
# Проверка на PII перед коммитом

python check_pii.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ COMMIT BLOCKED: PII detected in code!"
    echo "Please remove username/first_name/last_name and try again"
    exit 1
fi

echo "✅ No PII found, proceeding with commit"
```

### Регулярные проверки

```bash
# Еженедельная проверка (добавить в cron на сервере)
0 3 * * 0 cd /home/batman/expense_bot && python check_pii.py || echo "PII detected!" | mail -s "PII Alert" admin@example.com
```

---

## ⚠️ Риски и меры безопасности

### Риск 1: Поломка существующего кода
- **Вероятность:** 🟡 Средняя (31 файл на ревизию)
- **Последствия:** Ошибки при работе бота, падение сервиса
- **Меры митигации:**
  - ✅ Автоматизированное сканирование (`check_pii.py`)
  - ✅ Отслеживание прогресса через diff с baseline
  - ✅ Полное тестирование локально
  - ✅ Backup БД перед деплоем
  - ✅ Деплой в период низкой активности
  - ✅ План отката готов

### Риск 2: Старые FSM states с PII
- **Вероятность:** 🟠 Высокая (пользователи с незавершенными сессиями)
- **Последствия:** KeyError при обращении к несуществующим полям
- **Меры митигации:**
  - ✅ FSMCleanupMiddleware (Шаг 2) - автоматическая очистка
  - ✅ Fallback функции `_get_pending_data_safe()`
  - ✅ Graceful degradation без ошибок
  - ✅ Логирование очисток для мониторинга
  - ✅ Выполнено ДО остальных изменений

### Риск 3: Потеря данных при миграции
- **Вероятность:** 🟢 Низкая
- **Последствия:** Потеря username/first_name (не критично, т.к. не используются)
- **Меры митигации:**
  - ✅ Два backup'а (до и во время деплоя)
  - ✅ Копия backup'а локально
  - ✅ Django миграции обратимы (`migrate <previous>`)
  - ✅ План отката БД готов

### Риск 4: Проблемы с Django admin
- **Вероятность:** 🟢 Низкая
- **Последствия:** Админка не отображает пользователей корректно
- **Меры митигации:**
  - ✅ Обновлен `list_display` в admin.py
  - ✅ Обновлен `search_fields`
  - ✅ Метод `__str__` изменен
  - ✅ Тестирование админки локально

### Риск 5: Пропуск редких использований PII
- **Вероятность:** 🟡 Средняя (31 файл, человеческий фактор)
- **Последствия:** PII остается в коде, продолжает логироваться
- **Меры митигации:**
  - ✅ Автоматизированное сканирование `check_pii.py`
  - ✅ Регулярные проверки через grep/ripgrep
  - ✅ Базовый отчет (baseline) для сравнения
  - ✅ Проверка после каждого блока изменений
  - ✅ Финальная проверка перед деплоем

### Риск 6: Downtime во время миграции
- **Вероятность:** 🟢 Низкая
- **Последствия:** Бот недоступен 1-3 минуты
- **Меры митигации:**
  - ✅ Деплой в период низкой активности (3-4 часа ночи)
  - ✅ Уведомление пользователей заранее (опционально)
  - ✅ Быстрая миграция (удаление колонок = быстро)
  - ✅ Мониторинг в реальном времени

---

## ✅ Чеклист выполнения

### Подготовка
- [ ] Создан скрипт `check_pii.py`
- [ ] Запущено первичное сканирование
- [ ] Создан baseline: `pii_scan_baseline.txt`
- [ ] Проанализированы все зависимости

### Код - Fallback для FSM (Шаг 2)
- [ ] Добавлен fallback в `privacy_check.py`
- [ ] Добавлен fallback в `start.py`
- [ ] Создан `FSMCleanupMiddleware`
- [ ] Middleware зарегистрирован в bot.py
- [ ] Протестирован fallback локально

### Код - Логирование (Шаг 3.1)
- [ ] Изменен `logging_middleware.py` (строка 62)
- [ ] Изменен `activity_tracker.py` (строки 56, 77, 92, 95, 104)
- [ ] Запущена проверка: `python check_pii.py`

### Код - Уведомления (Шаг 3.2)
- [ ] Изменен `admin_notifier.py` (строки 270, 284-288)
- [ ] Найдены все вызовы `notify_new_user()`
- [ ] Убраны параметры username/first_name из всех вызовов
- [ ] Запущена проверка: `python check_pii.py`

### Код - UI/Отображение (Шаг 3.4)
- [ ] Изменен `pdf_report_html.py` (строка 186)
- [ ] Проверены все роутеры на отображение username
- [ ] Проверены клавиатуры на отображение username
- [ ] Запущена проверка: `python check_pii.py`

### Код - Household/Family/Referral (Шаг 3.5)
- [ ] Изменен `household.py`
- [ ] Изменен `family.py`
- [ ] Изменен `referral.py`
- [ ] Изменен `affiliate.py`
- [ ] Запущена проверка: `python check_pii.py`

### Код - Django Admin (Шаг 3.6)
- [ ] Изменен `expenses/admin.py` (list_display, search_fields)
- [ ] Протестирован admin локально

### Код - Создание Profile (Шаг 3.7)
- [ ] Найдены все `Profile.objects.create()`
- [ ] Убраны параметры PII из всех мест создания
- [ ] Запущена проверка: `python check_pii.py`

### Модель (Шаг 4)
- [ ] Изменен `database/models.py` - удалены поля
- [ ] Изменен метод `__str__` в Profile
- [ ] Удалены property методы с PII (если есть)
- [ ] Проверены другие модели на использование PII

### Миграция (Шаг 5)
- [ ] Создана миграция: `python manage.py makemigrations --name remove_pii_fields`
- [ ] Просмотрена миграция: `cat expenses/migrations/XXXX_remove_pii_fields.py`
- [ ] Просмотрен SQL: `python manage.py sqlmigrate expenses XXXX`
- [ ] Проверен план: `python manage.py migrate --plan`

### Тестирование (Шаг 6)
- [ ] Финальное сканирование: `python check_pii.py` → 0 совпадений
- [ ] Линтеры пройдены: flake8, mypy
- [ ] Pytest пройден
- [ ] Миграция применена локально
- [ ] Регистрация работает
- [ ] Создание трат работает
- [ ] PDF генерируется
- [ ] Django admin работает
- [ ] Поиск по telegram_id работает
- [ ] Старые FSM states не вызывают ошибок

### Подготовка к деплою (Шаг 7)
- [ ] Backup БД создан на сервере
- [ ] Backup БД скопирован локально
- [ ] Git commit создан с подробным сообщением
- [ ] Git push выполнен
- [ ] Создан план отката: `docs/PII_REMOVAL_ROLLBACK.md`

### Деплой (Шаг 8)
- [ ] Уведомление пользователей (если нужно)
- [ ] Финальный backup перед деплоем
- [ ] Контейнеры остановлены: `docker-compose down`
- [ ] Код обновлен: `git pull origin master`
- [ ] Миграция применена: `docker-compose run --rm web python manage.py migrate`
- [ ] Контейнеры запущены: `docker-compose up -d`
- [ ] Логи проверены на ошибки

### Проверка после деплоя (Шаг 9)
- [ ] Нет критичных ошибок в логах
- [ ] Username не логируется: `docker-compose logs bot | grep username` → пусто
- [ ] Регистрация работает (тест в Telegram)
- [ ] Создание трат работает
- [ ] PDF генерируется
- [ ] Django admin работает
- [ ] Rate limiter показывает активность
- [ ] Поля удалены из БД: `\d profiles` → нет username/first_name

### Финализация (Шаг 10)
- [ ] Старые логи архивированы (опционально)
- [ ] CLAUDE.md обновлен (раздел Privacy & GDPR)
- [ ] README обновлен (если нужно)
- [ ] CI/CD проверка PII добавлена (будущее)
- [ ] Создан отчет: `docs/PII_REMOVAL_COMPLETION_REPORT.md`

---

## 🔄 Откат изменений

### Быстрый откат (при критических проблемах)

```bash
# 1. Подключиться к серверу
ssh batman@94.198.220.155
cd /home/batman/expense_bot

# 2. Найти commit hash ДО изменений
git log --oneline -10
# Найти коммит перед "Privacy: Remove PII fields"

# 3. Откатить код
git reset --hard <commit_hash>

# 4. Откатить миграцию БД
docker-compose run --rm web python manage.py migrate expenses XXXX_previous_migration

# 5. Перезапустить
docker-compose restart

# 6. Проверить
docker-compose logs --tail=100 bot
docker-compose ps
```

### Полный откат БД (если миграция вызвала проблемы)

```bash
# ВНИМАНИЕ: Потеря данных созданных после backup!

# 1. Остановить контейнеры
docker-compose down

# 2. Восстановить БД из backup
docker-compose up -d db  # Только БД
docker exec -i expense_bot_db psql -U expense_user expense_bot < \
    /home/batman/backups/before_pii_removal_YYYYMMDD_HHMMSS.sql

# 3. Запустить все контейнеры
docker-compose up -d

# 4. Проверить
docker-compose ps
```

### Частичный откат (только кода, БД оставить)

```bash
# Если миграция прошла успешно, но в коде ошибки

# 1. Откатить только код
git reset --hard <commit_hash>
docker-compose restart bot web celery

# 2. Применить миграцию обратно (если нужно)
docker-compose run --rm web python manage.py migrate

# 3. Проверить
docker-compose logs --tail=100 bot
```

---

## 📎 Приложения

### Приложение A: Полный список файлов с username

**Найдено: 31 файл**

#### 🔴 Критичные (требуют изменений):
1. `bot/middlewares/logging_middleware.py` - строка 62, 118, 121, 128
2. `bot/middleware/activity_tracker.py` - строка 56, 77, 92, 95, 104
3. `bot/services/admin_notifier.py` - строка 270, 284-288
4. `bot/middlewares/privacy_check.py` - строка 98-100
5. `bot/routers/start.py` - строка 235-237
6. `bot/services/pdf_report_html.py` - строка 186
7. `database/models.py` - строка 15, 50
8. `expenses/admin.py` - list_display, search_fields

#### 🟡 Требуют проверки:
9. `bot/routers/household.py`
10. `bot/routers/family.py`
11. `bot/routers/referral.py`
12. `bot/services/affiliate.py`
13. `bot/services/household.py`
14. `bot/utils/input_sanitizer.py`
15. `expenses/models_old.py`
16. `create_superuser.py`

#### ⚪ Архивные (не трогаем):
17-31. Файлы в `archive/`, `archive_20251102/`, `archive_20251105/` и т.д.

### Приложение B: Паттерны для поиска PII

```bash
# Поиск через ripgrep (быстрее grep)
rg "\.username\b" --type py --iglob '!archive*' --iglob '!venv'
rg "\.first_name\b" --type py --iglob '!archive*' --iglob '!venv'
rg "\.last_name\b" --type py --iglob '!archive*' --iglob '!venv'

# Поиск через grep
grep -rn "\.username\|\.first_name\|\.last_name" \
    --include="*.py" \
    --exclude-dir={venv,archive*,__pycache__} \
    bot/ database/ expenses/

# Поиск в логах
docker-compose logs bot | grep -i "username"
```

### Приложение C: SQL для проверки БД

```sql
-- Проверить структуру таблицы profiles
\d profiles

-- Проверить наличие колонок (должно вернуть 0 после миграции)
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'profiles'
  AND column_name IN ('username', 'first_name', 'last_name');

-- Проверить данные (только telegram_id)
SELECT telegram_id, subscription_end_date, is_beta_tester
FROM profiles
LIMIT 10;
```

---

## 📞 Контакты и поддержка

**Ответственный за выполнение:** DevOps/Backend team
**Дата создания плана:** 2025-11-11
**Последнее обновление:** 2025-11-11

**В случае проблем:**
1. Проверить логи: `docker-compose logs bot`
2. Проверить backup: `ls -lh /home/batman/backups/`
3. Использовать план отката из раздела [Откат изменений](#откат-изменений)

---

**Статус:** 📋 Готов к выполнению
**Ожидаемое время выполнения:** 6-9 часов
**Downtime:** 1-3 минуты (во время миграции)

**После выполнения обновить статус на:** ✅ Завершено
