# План удаления поля normalized_weight

**Дата создания:** 2025-01-14
**Статус:** В планировании
**Причина:** Поле `normalized_weight` стало мертвым кодом после перехода на строгую уникальность ключевых слов

---

## 📋 Обоснование

### Почему удаляем:
1. **Функция пересчета весов удалена** - `recalculate_normalized_weights()` больше не существует
2. **Строгая уникальность** - одно слово = одна категория, вес всегда 1.0
3. **Бессмысленные умножения** - `score += keyword.normalized_weight * 3` = `score += 1.0 * 3`
4. **Индекс впустую** - замедляет INSERT/UPDATE без пользы
5. **Вводит в заблуждение** - создает иллюзию что существует логика весов
6. **Тест ожидает отсутствия** - `test_income_keywords_uniqueness.py:340` проверяет `not hasattr(kw1, 'normalized_weight')`

### Что получим:
- ✅ Честный и понятный код
- ✅ Экономия 8 байт × количество ключевых слов в БД
- ✅ Ускорение INSERT/UPDATE (нет лишнего индекса)
- ✅ Соответствие документации (INCOME_KEYWORDS_UNIQUENESS_PLAN.md)
- ✅ Упрощение логики поиска

---

## 🎯 Затронутые файлы

### 1. Модели Django (expenses/models.py)
**Строки для удаления:**

**CategoryKeyword (расходы):**
- Строка 409: `normalized_weight = models.FloatField(default=1.0, verbose_name='Нормализованный вес')`
- Строка 422: `models.Index(fields=['normalized_weight'])`
- Строка 428: Обновить `__str__` (убрать вес из строки)

**IncomeCategoryKeyword (доходы):**
- Строка 1093: `normalized_weight = models.FloatField(default=1.0, verbose_name='Нормализованный вес')`
- Строка 1110: Уже НЕТ в `__str__` - ничего не делаем

### 2. Парсер доходов (bot/utils/expense_parser.py)
**Строки 953-959 - упростить логику:**

**Было:**
```python
best_match = None
best_weight = 0

for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower and keyword_obj.normalized_weight > best_weight:
        best_match = keyword_obj.category
        best_weight = keyword_obj.normalized_weight
```

**Станет:**
```python
best_match = None

for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower:
        best_match = keyword_obj.category
        break  # Уникальность гарантирована - дальше искать не нужно!
```

### 3. Категоризатор расходов (bot/utils/expense_categorizer.py)
**Строки 627-633 - убрать умножение на 1.0:**

**Было:**
```python
for keyword in keywords:
    if keyword.keyword.lower() == clean_word:
        score += keyword.normalized_weight * 3  # Всегда 1.0 * 3
    elif clean_word.startswith(keyword.keyword.lower()):
        score += keyword.normalized_weight * 2  # Всегда 1.0 * 2
    elif keyword.keyword.lower() in clean_word:
        score += keyword.normalized_weight * 1  # Всегда 1.0 * 1
```

**Станет:**
```python
for keyword in keywords:
    if keyword.keyword.lower() == clean_word:
        score += 3  # Точное совпадение
    elif clean_word.startswith(keyword.keyword.lower()):
        score += 2  # Префикс
    elif keyword.keyword.lower() in clean_word:
        score += 1  # Вхождение
```

### 4. Celery задачи (expense_bot/celery_tasks.py)
**Строки для изменения:**

- **Строка 1152:** `defaults={'normalized_weight': 1.0, 'usage_count': 0}` → `defaults={'usage_count': 0}`
- **Строка 1272:** `defaults={'normalized_weight': 1.0, 'usage_count': 1}` → `defaults={'usage_count': 1}`

### 5. Сервис категорий (bot/services/category.py)
**Строка 1216:**
- `defaults={'normalized_weight': 1.0, 'usage_count': 1}` → `defaults={'usage_count': 1}`

---

## 📝 Пошаговый план выполнения

### Этап 1: Подготовка (локально, 15 минут)

#### 1.1 Полная проверка упоминаний normalized_weight
```bash
# ОБЯЗАТЕЛЬНАЯ проверка всех упоминаний в проекте
grep -r "normalized_weight" --include="*.py" bot/ expenses/ expense_bot/ | grep -v "__pycache__" | grep -v ".pyc"

# Проверить:
# - admin.py (админки Django)
# - serializers.py (DRF сериализаторы)
# - views.py (API endpoints)
# - forms.py (Django формы)
# - templates/ (HTML шаблоны)

# Если найдены дополнительные файлы:
# → Добавить их в список изменений!
# → Обновить план перед продолжением!
```

**Ожидаемые места (уже в плане):**
- ✅ `expenses/models.py` - модели (2 места)
- ✅ `bot/utils/expense_parser.py` - поиск по keywords
- ✅ `bot/utils/expense_categorizer.py` - scoring
- ✅ `expense_bot/celery_tasks.py` - defaults (2 места)
- ✅ `bot/services/category.py` - defaults

**Возможные неожиданные места:**
- ⚠️ `expenses/admin.py` - list_display, list_filter
- ⚠️ `expenses/serializers.py` - fields, read_only_fields
- ⚠️ API endpoints - возвращаемые JSON
- ⚠️ Формы редактирования keywords

**Если найдены новые файлы:**
1. Остановить выполнение
2. Добавить файлы в раздел "Затронутые файлы"
3. Обновить чеклист
4. Продолжить с учетом новых файлов

#### 1.2 Резервная копия
```bash
# Создать бэкап текущей локальной БД
python manage.py dumpdata expenses.CategoryKeyword expenses.IncomeCategoryKeyword > backup_keywords_before_migration.json

# Создать архив измененных файлов
mkdir -p archive_$(date +%Y%m%d)
cp expenses/models.py archive_$(date +%Y%m%d)/models_before_normalized_weight_removal.py
cp bot/utils/expense_parser.py archive_$(date +%Y%m%d)/expense_parser_before.py
cp bot/utils/expense_categorizer.py archive_$(date +%Y%m%d)/expense_categorizer_before.py
```

#### 1.2 Проверка текущего состояния
```bash
# Убедиться что поле существует
python manage.py shell -c "from expenses.models import CategoryKeyword; print(CategoryKeyword._meta.get_field('normalized_weight'))"

# Проверить количество записей
python manage.py shell -c "from expenses.models import CategoryKeyword, IncomeCategoryKeyword; print(f'CategoryKeyword: {CategoryKeyword.objects.count()}'); print(f'IncomeCategoryKeyword: {IncomeCategoryKeyword.objects.count()}')"
```

---

### Этап 2: Изменение моделей (5 минут)

#### 2.1 Редактировать expenses/models.py

**CategoryKeyword (строки 405-428):**
```python
# УДАЛИТЬ строку 409:
# normalized_weight = models.FloatField(default=1.0, verbose_name='Нормализованный вес')

# ИЗМЕНИТЬ строку 428:
# Было:
return f"{self.keyword} ({self.language}) -> {self.category.name} (вес: {self.normalized_weight:.2f})"

# Стало:
return f"{self.keyword} ({self.language}) -> {self.category.name}"

# УДАЛИТЬ из indexes (строка 422):
models.Index(fields=['normalized_weight']),
```

**IncomeCategoryKeyword (строки 1088-1111):**
```python
# УДАЛИТЬ строку 1093:
# normalized_weight = models.FloatField(default=1.0, verbose_name='Нормализованный вес')

# __str__ уже корректный - ничего не делаем
```

#### 2.2 Создать миграцию Django
```bash
python manage.py makemigrations --name remove_normalized_weight_field

# Проверить созданную миграцию
cat expenses/migrations/00XX_remove_normalized_weight_field.py
```

**Ожидаемая миграция:**
```python
# Generated by Django

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('expenses', '00XX_previous_migration'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='categorykeyword',
            name='expenses_ca_normali_a5af6b_idx',
        ),
        migrations.RemoveField(
            model_name='categorykeyword',
            name='normalized_weight',
        ),
        migrations.RemoveField(
            model_name='incomecategorykeyword',
            name='normalized_weight',
        ),
    ]
```

---

### Этап 3: Изменение бизнес-логики (15 минут)

#### 3.1 Упростить expense_parser.py

**Файл:** `bot/utils/expense_parser.py`
**Строки:** 950-968

```python
# БЫЛО (строки 953-959):
best_match = None
best_weight = 0

for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower and keyword_obj.normalized_weight > best_weight:
        best_match = keyword_obj.category
        best_weight = keyword_obj.normalized_weight

# СТАЛО:
best_match = None

for keyword_obj in keywords:
    if keyword_obj.keyword.lower() in text_lower:
        best_match = keyword_obj.category
        break  # При строгой уникальности достаточно первого совпадения
```

**Обоснование:**
- При строгой уникальности ключевое слово может быть только в одной категории
- Найденное совпадение гарантированно единственное
- `break` ускоряет поиск

#### 3.2 Упростить expense_categorizer.py

**Файл:** `bot/utils/expense_categorizer.py`
**Строки:** 620-639

```python
# БЫЛО (строки 627-633):
for keyword in keywords:
    if keyword.keyword.lower() == clean_word:
        score += keyword.normalized_weight * 3
    elif clean_word.startswith(keyword.keyword.lower()):
        score += keyword.normalized_weight * 2
    elif keyword.keyword.lower() in clean_word:
        score += keyword.normalized_weight * 1

# СТАЛО:
for keyword in keywords:
    if keyword.keyword.lower() == clean_word:
        score += 3  # Точное совпадение (приоритет)
    elif clean_word.startswith(keyword.keyword.lower()):
        score += 2  # Префикс (средний приоритет)
    elif keyword.keyword.lower() in clean_word:
        score += 1  # Вхождение (низкий приоритет)
```

**Обоснование:**
- Умножение на 1.0 бессмысленно
- Константы понятнее и быстрее

#### 3.3 Убрать defaults из celery_tasks.py

**Файл:** `expense_bot/celery_tasks.py`

**Строка 1152 (функция update_keywords_weights):**
```python
# БЫЛО:
defaults={'normalized_weight': 1.0, 'usage_count': 0}

# СТАЛО:
defaults={'usage_count': 0}
```

**Строка 1272 (функция learn_keywords_on_create):**
```python
# БЫЛО:
defaults={'normalized_weight': 1.0, 'usage_count': 1}

# СТАЛО:
defaults={'usage_count': 1}
```

#### 3.4 Убрать defaults из category.py

**Файл:** `bot/services/category.py`
**Строка 1216 (функция learn_from_category_change):**

```python
# БЫЛО:
defaults={'normalized_weight': 1.0, 'usage_count': 1}

# СТАЛО:
defaults={'usage_count': 1}
```

---

### Этап 4: Локальное тестирование (20 минут)

#### 4.1 Применить миграцию локально
```bash
# Применить миграцию к локальной БД
python manage.py migrate

# Проверить что поле удалено
python manage.py shell -c "
from expenses.models import CategoryKeyword, IncomeCategoryKeyword
kw = CategoryKeyword.objects.first()
if kw:
    assert not hasattr(kw, 'normalized_weight'), 'Поле должно быть удалено!'
    print('✓ CategoryKeyword: поле normalized_weight удалено')

ikw = IncomeCategoryKeyword.objects.first()
if ikw:
    assert not hasattr(ikw, 'normalized_weight'), 'Поле должно быть удалено!'
    print('✓ IncomeCategoryKeyword: поле normalized_weight удалено')
"
```

#### 4.2 Запустить тесты
```bash
# Тест уникальности ключевых слов доходов (ДОЛЖЕН ПРОЙТИ!)
python test_income_keywords_uniqueness.py

# Проверить что тест 6 проходит
# Ожидаем: "✓ ТЕСТ 6 ПРОЙДЕН: normalized_weight не используется"
```

#### 4.3 Функциональное тестирование

**Тест 1: Создание траты с AI категоризацией**
```python
# Запустить бота локально
python run_bot.py

# Отправить боту:
"кофе 300"

# Проверить:
# 1. Категория определилась корректно
# 2. Ключевое слово "кофе" добавилось
# 3. В БД для слова "кофе" НЕТ поля normalized_weight
```

**Тест 2: Изменение категории вручную**
```python
# Создать трату:
"такси 500" → категория "Транспорт"

# Изменить категорию на "Развлечения"

# Проверить:
# 1. Слово "такси" удалилось из "Транспорт"
# 2. Слово "такси" добавилось в "Развлечения"
# 3. Никаких ошибок в логах
```

**Тест 3: Поиск по ключевым словам**
```python
# Добавить ключевые слова в категорию "Кафе":
# - кофе
# - старбакс

# Отправить боту:
"кофе в старбаксе 450"

# Проверить:
# 1. Категория "Кафе" определилась
# 2. Поиск работает быстро (break после первого совпадения)
```

#### 4.4 Проверка логов
```bash
# Запустить бота и проверить что нет ошибок связанных с normalized_weight
tail -f logs/bot.log | grep -i "normalized_weight\|AttributeError"

# Не должно быть вывода!
```

---

### Этап 5: Подготовка к деплою (10 минут)

#### 5.1 Коммит изменений
```bash
git status

# Должны быть изменены:
# modified:   expenses/models.py
# modified:   bot/utils/expense_parser.py
# modified:   bot/utils/expense_categorizer.py
# modified:   expense_bot/celery_tasks.py
# modified:   bot/services/category.py
# new file:   expenses/migrations/00XX_remove_normalized_weight_field.py
# new file:   docs/REMOVE_NORMALIZED_WEIGHT_PLAN.md

git add expenses/models.py \
        bot/utils/expense_parser.py \
        bot/utils/expense_categorizer.py \
        expense_bot/celery_tasks.py \
        bot/services/category.py \
        expenses/migrations/00XX_remove_normalized_weight_field.py \
        docs/REMOVE_NORMALIZED_WEIGHT_PLAN.md

git commit -m "Refactor: Удалено поле normalized_weight (мертвый код после перехода на строгую уникальность)

Changes:
- expenses/models.py: Удалено поле normalized_weight из CategoryKeyword и IncomeCategoryKeyword
- expenses/models.py: Удалён индекс normalized_weight
- bot/utils/expense_parser.py: Упрощена логика поиска категории (break после первого совпадения)
- bot/utils/expense_categorizer.py: Убрано бессмысленное умножение на 1.0
- expense_bot/celery_tasks.py: Удалены normalized_weight из defaults при создании keywords
- bot/services/category.py: Удалён normalized_weight из defaults
- Migration: 00XX_remove_normalized_weight_field.py

Why:
- Функция recalculate_normalized_weights() удалена ранее
- При строгой уникальности (одно слово = одна категория) вес всегда 1.0
- Поле занимало 8 байт × количество keywords в БД
- Индекс замедлял INSERT/UPDATE без пользы
- Соответствует документации INCOME_KEYWORDS_UNIQUENESS_PLAN.md

Testing:
- ✓ test_income_keywords_uniqueness.py (тест 6 теперь проходит)
- ✓ Функциональное тестирование: создание трат, изменение категорий, поиск

🤖 Generated with Claude Code
"

git push origin master
```

---

### Этап 6: Деплой на сервер (15 минут)

#### 6.1 Определить на каком сервере работаем
```bash
# Попросить пользователя выполнить:
hostname -I && pwd

# PRIMARY сервер: 94.198.220.155 → путь /home/batman/expense_bot
# BACKUP сервер: 72.56.67.202 → путь /home/batman/expense_bot_deploy/expense_bot/
```

#### 6.2 Резервная копия БД на сервере
```bash
# PRIMARY сервер (94.198.220.155):
ssh batman@94.198.220.155

# Создать бэкап БД ПЕРЕД миграцией
cd /home/batman/expense_bot
docker exec expense_bot_db pg_dump -U expense_user expense_bot > backups/backup_before_normalized_weight_removal_$(date +%Y%m%d_%H%M%S).sql

# Проверить что бэкап создан
ls -lh backups/backup_before_normalized_weight_removal_*.sql
```

#### 6.3 Обновить код на сервере
```bash
# Убедиться что находимся в правильной директории
cd /home/batman/expense_bot

# Получить обновления из GitHub
git fetch origin
git pull origin master

# Проверить что миграция появилась
ls -la expenses/migrations/*remove_normalized_weight*
```

#### 6.4 Применить миграцию на сервере

**ВАЖНО:** Миграция изменяет структуру БД!

```bash
# Остановить бота (чтобы избежать конфликтов)
cd /home/batman/expense_bot && docker-compose stop bot celery celery-beat

# Применить миграцию
cd /home/batman/expense_bot && docker-compose exec web python manage.py migrate

# Ожидаемый вывод:
# Running migrations:
#   Applying expenses.00XX_remove_normalized_weight_field... OK

# Проверить структуру таблицы
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot -c "\d expenses_category_keyword"

# Поле normalized_weight НЕ должно быть в списке столбцов!
```

#### 6.5 Пересобрать и перезапустить контейнеры
```bash
# Пересобрать образы (т.к. изменился код)
cd /home/batman/expense_bot && docker-compose build --no-cache bot web celery celery-beat

# Запустить все сервисы
cd /home/batman/expense_bot && docker-compose up -d

# Проверить что все контейнеры запущены
cd /home/batman/expense_bot && docker-compose ps
```

#### 6.6 Проверка после деплоя
```bash
# Проверить логи бота (не должно быть ошибок)
cd /home/batman/expense_bot && docker-compose logs --tail=100 bot | grep -i "error\|exception\|normalized_weight"

# Проверить логи Celery
cd /home/batman/expense_bot && docker-compose logs --tail=100 celery | grep -i "error\|exception\|normalized_weight"

# Если нет вывода - всё ОК!
```

---

### Этап 7: Продакшн тестирование (10 минут)

#### 7.1 Функциональный тест в реальном боте

**Тест 1: Создание траты с AI**
```
Telegram → отправить боту:
"кофе 300"

Проверить:
- Бот ответил корректно
- Категория определилась
- Нет ошибок в логах
```

**Тест 2: Изменение категории**
```
Telegram:
1. Создать трату: "такси 500"
2. Изменить категорию на другую
3. Проверить что всё работает
```

**Тест 3: Добавление ключевых слов**
```
Telegram:
1. Зайти в управление категориями
2. Добавить ключевое слово к категории
3. Создать трату с этим словом
4. Проверить что категория определилась
```

#### 7.2 Мониторинг логов
```bash
# Следить за логами в реальном времени (5-10 минут)
cd /home/batman/expense_bot && docker-compose logs -f bot celery

# Убедиться что:
# - Нет упоминаний normalized_weight
# - Нет AttributeError
# - Нет ошибок при создании трат
# - Нет ошибок при AI категоризации
```

#### 7.3 Проверка БД
```bash
# Подключиться к БД
cd /home/batman/expense_bot && docker-compose exec db psql -U expense_user -d expense_bot

# Проверить что индекса нет
\di expenses_ca_normali_a5af6b_idx
# Ожидаем: "Did not find any relation named..."

# Проверить что поля нет
SELECT column_name FROM information_schema.columns
WHERE table_name = 'expenses_category_keyword' AND column_name = 'normalized_weight';
# Ожидаем: 0 rows

# Выйти из psql
\q
```

---

## 🔄 Откат в случае проблем

### Если что-то пошло не так на продакшене:

#### Вариант 1: Откат миграции Django (быстро, 2 минуты)
```bash
# Узнать номер ПРЕДЫДУЩЕЙ миграции
cd /home/batman/expense_bot && docker-compose exec web python manage.py showmigrations expenses

# Откатиться на предыдущую миграцию
cd /home/batman/expense_bot && docker-compose exec web python manage.py migrate expenses 00XX_previous_migration

# Вернуть старую версию кода
cd /home/batman/expense_bot && git reset --hard HEAD~1

# Пересобрать контейнеры
cd /home/batman/expense_bot && docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

#### Вариант 2: Восстановление из бэкапа БД (если миграция что-то сломала, 5 минут)
```bash
# Остановить все сервисы
cd /home/batman/expense_bot && docker-compose down

# Восстановить бэкап
cd /home/batman/expense_bot && docker-compose up -d db
sleep 5  # Дождаться запуска БД

cd /home/batman/expense_bot && docker-compose exec -T db psql -U expense_user -d expense_bot < backups/backup_before_normalized_weight_removal_YYYYMMDD_HHMMSS.sql

# Запустить все сервисы
cd /home/batman/expense_bot && docker-compose up -d

# Вернуть старую версию кода
cd /home/batman/expense_bot && git reset --hard HEAD~1
cd /home/batman/expense_bot && docker-compose build --no-cache && docker-compose restart
```

---

## 📊 Чеклист выполнения

### Локально:
- [ ] Создан бэкап `backup_keywords_before_migration.json`
- [ ] Архивированы файлы в `archive_YYYYMMDD/`
- [ ] Изменен `expenses/models.py` (CategoryKeyword)
- [ ] Изменен `expenses/models.py` (IncomeCategoryKeyword)
- [ ] Создана миграция `00XX_remove_normalized_weight_field.py`
- [ ] Упрощен `bot/utils/expense_parser.py` (убран best_weight)
- [ ] Упрощен `bot/utils/expense_categorizer.py` (убрано умножение)
- [ ] Убраны defaults в `expense_bot/celery_tasks.py` (2 места)
- [ ] Убран default в `bot/services/category.py`
- [ ] Миграция применена локально (`python manage.py migrate`)
- [ ] Тест `test_income_keywords_uniqueness.py` проходит
- [ ] Функциональные тесты пройдены (создание/изменение трат)
- [ ] Коммит создан и запушен в GitHub

### На сервере:
- [ ] Определен сервер (`hostname -I && pwd`)
- [ ] Создан бэкап БД `backup_before_normalized_weight_removal_*.sql`
- [ ] Код обновлен (`git pull origin master`)
- [ ] Бот остановлен (`docker-compose stop bot celery celery-beat`)
- [ ] Миграция применена (`docker-compose exec web python manage.py migrate`)
- [ ] Проверена структура таблицы (поле удалено)
- [ ] Контейнеры пересобраны (`docker-compose build --no-cache`)
- [ ] Сервисы запущены (`docker-compose up -d`)
- [ ] Логи проверены (нет ошибок)
- [ ] Функциональный тест 1: создание траты с AI ✓
- [ ] Функциональный тест 2: изменение категории ✓
- [ ] Функциональный тест 3: добавление ключевых слов ✓
- [ ] Мониторинг 5-10 минут (нет ошибок)
- [ ] Проверка БД (индекс удален, поле удалено)

---

## 📈 Ожидаемые результаты

### Экономия ресурсов:
- **БД:** 8 байт × количество keywords (CategoryKeyword + IncomeCategoryKeyword)
- **Индекс:** Удален индекс `expenses_ca_normali_a5af6b_idx`
- **Производительность:** Ускорение INSERT/UPDATE (нет обновления индекса)

### Качество кода:
- **Понятность:** Нет иллюзии что существует логика весов
- **Честность:** Код соответствует реальной логике (строгая уникальность)
- **Документация:** Соответствие INCOME_KEYWORDS_UNIQUENESS_PLAN.md
- **Тесты:** test_income_keywords_uniqueness.py проходит без ошибок

### Риски:
- **Низкий:** Поле не использовалось активно (всегда 1.0)
- **Откат простой:** Миграция обратима, есть бэкап БД
- **Время простоя:** ~2 минуты (остановка бота для миграции)

---

## 📝 Примечания

### Почему удаляем поле полностью, а не просто оставляем?
1. **Принцип YAGNI** (You Aren't Gonna Need It) - не нужно хранить неиспользуемое
2. **Экономия ресурсов** - каждый байт имеет значение при масштабе
3. **Чистота кода** - новые разработчики не будут путаться
4. **Соответствие документации** - честность архитектуры

### Что если захотим вернуть логику весов в будущем?
- Можно создать новую миграцию добавив поле обратно
- История в Git сохранена - можно посмотреть старый код
- Архивные файлы в `archive_YYYYMMDD/` - можно восстановить

### Альтернативы:
- ❌ Оставить поле "на всякий случай" - засоряет БД и код
- ❌ Только удалить индекс - половинчатое решение
- ✅ **Полное удаление** - чистое и честное решение

---

**Автор плана:** Claude Code
**Дата:** 2025-01-14
**Версия:** 1.0
