# План реализации уникальности ключевых слов для доходов
## Упрощенная версия: Строгая уникальность без весов

**Дата создания:** 2025-11-11
**Дата обновления:** 2025-11-11 (упрощение - убрана логика весов)
**Статус:** В разработке
**Автор:** Claude Code

---

## ⚠️ ВАЖНОЕ РЕШЕНИЕ ПО АРХИТЕКТУРЕ

**ОТКАЗАЛИСЬ от логики весов (normalized_weights)!**

Вместо сложной системы разрешения конфликтов через веса используем **строгую уникальность**:
- ✅ Одно ключевое слово = одна категория
- ✅ При смене категории слово **удаляется** из старой и **создается** в новой
- ✅ Никаких `recalculate_normalized_weights()` не нужно
- ✅ Простой и понятный паттерн: delete → create

---

## 🎯 Цель

Гарантировать **строгую уникальность ключевых слов** для доходов (IncomeCategoryKeyword):
- ✅ Одно слово может быть только в одной категории дохода пользователя
- ✅ При изменении категории слово удаляется из старой и добавляется ТОЛЬКО в новую
- ✅ Никаких дубликатов, никаких весов для разрешения конфликтов
- ✅ Минимальные изменения существующего кода

**ПРИНЦИП РАБОТЫ:**
```
Пользователь вводит: "кофе 200"
Система находит: категория "Кафе и рестораны" (есть слово "кофе")
Пользователь меняет на: "Продукты"
Результат:
  - Слово "кофе" УДАЛЯЕТСЯ из "Кафе и рестораны"
  - Слово "кофе" СОЗДАЕТСЯ в "Продукты"
  - Теперь "кофе" существует ТОЛЬКО в "Продукты"
```

**НЕ ЦЕЛЬ:**
- ❌ Логика весов (normalized_weights) - ПОЛНОСТЬЮ ОТКАЗАЛИСЬ
- ❌ Разрешение конфликтов через веса - НЕ ИСПОЛЬЗУЕМ
- ❌ Функция recalculate_normalized_weights() - НЕ НУЖНА
- ❌ Переписывание архитектуры

**ОБНОВЛЕНИЕ ПЛАНА:**
✅ Celery задачи ВКЛЮЧЕНЫ в MVP для полной симметрии с расходами

---

## 📊 Текущее состояние

### Проблема
**3 точки входа** создают IncomeCategoryKeyword **БЕЗ проверки уникальности:**

1. `learn_from_income_category_change_sync()` (bot/services/income_categorization.py:197)
   - Пользователь меняет категорию дохода вручную
   - Создает ключевые слова через `get_or_create()`
   - **НЕ удаляет** из других категорий

2. `generate_keywords_for_income_category_sync()` (:254)
   - Создание новой категории → добавление дефолтных слов
   - **НЕ проверяет** дубликаты

3. `save_income_category_keywords()` (:332)
   - AI генерирует ключевые слова
   - **НЕ проверяет** дубликаты

### Что уже есть
- ✅ `cleanup_old_keywords()` поддерживает `is_income=True`
- ✅ Модель IncomeCategoryKeyword идентична CategoryKeyword
- ✅ Constraint `unique_together = ['category', 'keyword']` защищает от дублей в одной категории

### Чего не хватает
- ❌ Гарантии уникальности между категориями
- ❌ Централизованной логики создания ключевых слов

---

## 🗺️ ПЛАН РЕАЛИЗАЦИИ

Разделен на **MVP (делаем сейчас)** и **БУДУЩЕЕ (когда понадобится)**

---

## 📦 MVP: Минимально необходимое (20-30 минут)

### ЭТАП 1: Helper функция (5-10 минут)

**Создать:** `ensure_unique_income_keyword()` в `bot/services/income_categorization.py`

**Место:** В начале файла, после imports

**ВАЖНО:** Эта функция будет использоваться из двух мест:
1. ✅ Синхронных сервисных функций (3 штуки)
2. ✅ Celery задач (2 штуки)

Это избегает дублирования логики удаления!

**Сигнатура:**
```python
def ensure_unique_income_keyword(
    profile: Profile,
    category: IncomeCategory,
    word: str,
    defaults: dict = None
) -> Tuple[IncomeCategoryKeyword, bool, int]:
    """
    Гарантирует уникальность ключевого слова дохода.

    Удаляет слово из ВСЕХ категорий доходов пользователя,
    затем создает в целевой категории.

    Returns:
        (keyword, created, removed_count)
    """
```

**Логика:**
```python
# 1. Нормализовать
word = word.lower().strip()

# 2. Удалить из ВСЕХ категорий доходов профиля
deleted = IncomeCategoryKeyword.objects.filter(
    category__profile=profile,
    keyword=word
).delete()
removed_count = deleted[0]

# 3. Создать/получить в целевой (usage_count инициализируется в 0)
keyword, created = IncomeCategoryKeyword.objects.get_or_create(
    category=category,
    keyword=word,
    defaults=defaults or {'usage_count': 0}
)

# 4. Логировать
if removed_count > 0:
    logger.info(f"Removed '{word}' from {removed_count} income categories")

return keyword, created, removed_count
```

**ВАЖНО:** Никаких `normalized_weight` - только строгая уникальность!

**Зависимости:** НЕТ

---

### ЭТАП 2: Исправить 3 существующие функции (10-15 минут)

#### 2.1. `learn_from_income_category_change_sync()`

**Файл:** `bot/services/income_categorization.py:197`

**Было:**
```python
keyword, created = IncomeCategoryKeyword.objects.get_or_create(
    category=new_category,
    keyword=word,
    defaults={'normalized_weight': 1.0}  # НЕ НУЖНО!
)
```

**Станет:**
```python
keyword, created, removed = ensure_unique_income_keyword(
    profile=income.profile,
    category=new_category,
    word=word
    # defaults не нужны - helper использует usage_count: 0
)
```

**Дополнительно (опционально):**
- Импортировать `extract_words_from_description()` из celery_tasks
- Заменить `.split()` на extract_words
- Добавить `check_and_correct_text()` для орфографии

**Время:** 3-5 минут

---

#### 2.2. `generate_keywords_for_income_category_sync()`

**Файл:** `bot/services/income_categorization.py:254`

**Аналогично 2.1** - заменить `get_or_create()` на `ensure_unique_income_keyword()`

**Добавить подсчет:**
```python
total_removed = 0
for keyword in keywords:
    kw_obj, created, removed = ensure_unique_income_keyword(...)
    total_removed += removed

if total_removed > 0:
    logger.info(f"Removed {total_removed} duplicates during default keywords generation")
```

**Время:** 3-5 минут

---

#### 2.3. `save_income_category_keywords()`

**Файл:** `bot/services/income_categorization.py:332`

**Аналогично 2.2**

**Время:** 2-3 минуты

---

### ЭТАП 3: Создание Celery задач (15-20 минут)

**Создать в `expense_bot/celery_tasks.py`:**

#### 3.1. `update_income_keywords()` - аналог `update_keywords_weights()`

**Назначение:** Фоновое обновление при изменении категории дохода вручную

**Сигнатура:**
```python
@shared_task
def update_income_keywords(income_id: int, old_category_id: int, new_category_id: int):
    """
    Обновление ключевых слов после изменения категории дохода пользователем.
    Запускается в фоне после редактирования.

    ВАЖНО: Ключевые слова уникальны - одно слово только в одной категории!
    """
```

**Логика:**
```python
# 1. Получить объекты
income = Income.objects.select_related('profile').get(id=income_id)
new_category = IncomeCategory.objects.get(id=new_category_id)

# 2. Извлечь слова
words = extract_words_from_description(income.description)

# 3. Для каждого слова - вызвать helper
for word in words:
    ensure_unique_income_keyword(
        profile=income.profile,
        category=new_category,
        word=word
    )

# 4. Проверить лимит 50 слов
check_category_keywords_limit(new_category)
```

**Время:** 8-10 минут

---

#### 3.2. `learn_income_keywords_on_create()` - аналог для расходов

**Назначение:** Обучение при AI-категоризации нового дохода

**Сигнатура:**
```python
@shared_task
def learn_income_keywords_on_create(income_id: int):
    """
    Обучение ключевых слов для нового дохода с AI-категоризацией.
    Запускается в фоне после создания дохода.
    """
```

**Логика:**
```python
# 1. Получить доход
income = Income.objects.select_related('profile', 'category').get(id=income_id)

# 2. Только если была AI-категоризация
if not income.ai_categorized:
    return

# 3. Извлечь слова
words = extract_words_from_description(income.description)

# 4. Для каждого слова - вызвать helper
for word in words:
    ensure_unique_income_keyword(
        profile=income.profile,
        category=income.category,
        word=word
    )
```

**Время:** 7-10 минут

---

### ЭТАП 4: Интеграция Celery задач (10-15 минут)

**Файл:** `bot/services/income.py`

#### 4.1. В `update_income()` - заменить asyncio на Celery

**Найти (примерно строка 526):**
```python
# Старый код с asyncio.new_event_loop()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(
    learn_from_income_category_change_sync(income, new_category)
)
loop.close()
```

**Заменить на:**
```python
# Импортировать вверху файла
from expense_bot.celery_tasks import update_income_keywords

# В коде функции
if old_category_id != category_id:
    # Запустить обучение в фоне
    update_income_keywords.delay(
        income.id,
        old_category_id,
        category_id
    )
```

**Время:** 5-7 минут

---

#### 4.2. В `create_income()` - добавить вызов Celery

**Найти:** Место где создается Income с AI-категоризацией

**Добавить после создания:**
```python
# Импортировать вверху файла
from expense_bot.celery_tasks import learn_income_keywords_on_create

# После income = await sync_to_async(Income.objects.create)(...)
if income.ai_categorized and income.category:
    # Обучить ключевые слова в фоне
    learn_income_keywords_on_create.delay(income.id)
```

**Время:** 5-8 минут

---

### ЭТАП 5: Миграция существующих дубликатов (10 минут)

**Создать:** `fix_income_keyword_duplicates.py` в корне проекта

**Аналог:** `fix_expenses_with_foreign_categories.py`

**Логика:**
```python
# 1. Найти все дубликаты по (profile, keyword)
duplicates = IncomeCategoryKeyword.objects.values('keyword')\
    .annotate(
        profiles=ArrayAgg('category__profile_id', distinct=True),
        count=Count('id')
    )\
    .filter(count__gt=1)

# 2. Для каждого дубликата:
for dup in duplicates:
    for profile_id in dup['profiles']:
        keywords = IncomeCategoryKeyword.objects.filter(
            category__profile_id=profile_id,
            keyword=dup['keyword']
        ).order_by('-usage_count', '-last_used')

        # Оставить первую (с max usage_count), удалить остальные
        keep = keywords.first()
        keywords.exclude(id=keep.id).delete()

# 3. Режимы: --dry-run (по умолчанию) и --apply
```

**Когда запускать:**
- Перед деплоем в режиме --dry-run
- Затем с --apply если результаты ОК

**Время:** 5-10 минут на написание, 1 минута на выполнение

---

### ЭТАП 6: Быстрый аудит (5 минут)

**Задача:** Убедиться что нет других точек входа

**Команда:**
```bash
grep -r "IncomeCategoryKeyword.objects.create\|IncomeCategoryKeyword.objects.get_or_create" \
  --include="*.py" \
  --exclude-dir=archive \
  --exclude-dir=venv
```

**Ожидаемый результат:**
- Только 3 исправленные функции + 2 Celery задачи
- Возможно что-то в тестах (там можно оставить как есть)

**Если найдены другие места:**
- Применить тот же паттерн или helper функцию

**Время:** 5 минут

---

## ✅ ИТОГО MVP (с Celery для полной симметрии)

| Этап | Время | Файлы |
|------|-------|-------|
| 1. Helper функция | 5-10 мин | income_categorization.py |
| 2. Исправить 3 функции | 10-15 мин | income_categorization.py |
| 3. **Создать 2 Celery задачи** | 15-20 мин | celery_tasks.py |
| 4. **Интегрировать Celery** | 10-15 мин | income.py (create/update) |
| 5. Миграция дубликатов | 10 мин | fix_income_keyword_duplicates.py |
| 6. Аудит | 5 мин | grep |
| **ИТОГО** | **55-85 мин** | **4 файла** |

**Результат:**
- ✅ Строгая уникальность работает
- ✅ Дубликаты удалены
- ✅ **Полная симметрия с расходами (включая Celery)**
- ✅ Фоновое обучение не блокирует бота

---

## 🔮 БУДУЩИЕ УЛУЧШЕНИЯ (после MVP)

### Возможные оптимизации

#### 1. Расширение существующих функций параметром `is_income`
Вместо дублирования кода можно расширить:
- `check_category_keywords_limit(category)` → duck typing или параметр
- `extract_words_from_description()` → уже используется для доходов

**Когда делать:** Если количество общего кода превысит 70%

#### 2. Проверка орфографии для доходов
Добавить `check_and_correct_text()` в Celery задачи для доходов:
```python
# В update_income_keywords()
for word in words:
    corrected = check_and_correct_text(word)
    ensure_unique_income_keyword(..., word=corrected)
```

**Когда делать:** Если пользователи часто делают опечатки в описаниях доходов

#### 3. AI-генерация ключевых слов для доходов
Аналог `generate_keywords_for_income_category()` но с AI:
- Умная генерация слов на основе названия категории
- Кросс-языковая поддержка

**Когда делать:** Если доходы станут использоваться активно (>30% пользователей)

### Принципы расширения
- ✅ Расширять существующие функции, не дублировать код
- ✅ Использовать параметр `is_income` где возможно
- ✅ Поэтапное внедрение по мере необходимости
- ❌ НЕ создавать параллельный стек для доходов

---

## 📋 ЧЕК-ЛИСТ MVP

### Этап 1: Helper функция
- [ ] Создана `ensure_unique_income_keyword()` в income_categorization.py
- [ ] Функция возвращает (keyword, created, removed_count)
- [ ] Добавлено логирование удалений
- [ ] Протестирована вручную

### Этап 2: Исправление функций
- [ ] `learn_from_income_category_change_sync()` использует helper
- [ ] `generate_keywords_for_income_category_sync()` использует helper
- [ ] `save_income_category_keywords()` использует helper
- [ ] Все три функции логируют удаленные дубликаты

### Этап 3: Celery задачи
- [ ] Создана `update_income_keywords()` в celery_tasks.py
- [ ] Создана `learn_income_keywords_on_create()` в celery_tasks.py
- [ ] Обе задачи используют helper функцию
- [ ] Добавлена проверка лимита 50 слов

### Этап 4: Интеграция Celery
- [ ] В `update_income()` заменен asyncio на Celery
- [ ] В `create_income()` добавлен вызов Celery при AI-категоризации
- [ ] Импорты добавлены корректно
- [ ] Протестировано в продакшене

### Этап 5: Миграция
- [ ] Создан скрипт `fix_income_keyword_duplicates.py`
- [ ] Режимы --dry-run и --apply работают
- [ ] Скрипт протестирован на копии БД
- [ ] Выполнен на продакшене (если нужно)

### Этап 6: Аудит
- [ ] Выполнен grep по IncomeCategoryKeyword
- [ ] Все точки входа проверены
- [ ] Нет других мест создания без уникальности
- [ ] Обновлен CLAUDE.md (ссылка на этот план)

---

## 📚 REFERENCE: Паттерн строгой уникальности

**Для справки:** Паттерн строгой уникальности (без весов)

```python
# ПАТТЕРН СТРОГОЙ УНИКАЛЬНОСТИ
# Применяется во всех точках входа создания ключевых слов

# 1. Удалить из ВСЕХ категорий пользователя
deleted = CategoryKeyword.objects.filter(
    category__profile=profile,  # или expense.profile
    keyword=word.lower()
).delete()

if deleted[0] > 0:
    logger.info(f"Removed keyword '{word}' from {deleted[0]} other categories")

# 2. Создать в целевой категории (без весов!)
CategoryKeyword.objects.get_or_create(
    category=target_category,
    keyword=word.lower(),
    defaults={'usage_count': 0}  # Только счетчик использования
)
```

**Принцип:** Одно слово = одна категория. Никаких конфликтов, никаких весов.

**Этот же паттерн** инкапсулирован в `ensure_unique_income_keyword()` для доходов

---

## 🔍 Найденные точки входа

| Функция | Строка | Когда вызывается | Статус |
|---------|--------|------------------|--------|
| `learn_from_income_category_change_sync()` | :197 | Ручное изменение категории | ✅ Исправить |
| `generate_keywords_for_income_category_sync()` | :254 | Создание категории (дефолты) | ✅ Исправить |
| `save_income_category_keywords()` | :332 | AI генерация слов | ✅ Исправить |

**Откуда вызываются:**
- `update_income()` в bot/services/income.py:526 → через asyncio loop
- `create_income_category()` в bot/services/income.py:1136 → через asyncio loop
- `generate_keywords_for_income_category()` → AI fallback

---

## ⚠️ КРИТИЧЕСКИЕ ВОПРОСЫ (решено)

### 1. Уровень симметрии
**Ответ:** ПОЛНАЯ симметрия с расходами включая Celery (Этапы 1-6)
- ✅ Helper функция для уникальности
- ✅ Исправление 3 синхронных функций
- ✅ Создание 2 Celery задач (аналогично расходам)
- ✅ Интеграция в create_income() и update_income()

### 2. Местоположение create_income()
**Ответ:** `bot/services/income.py` - найдено, добавим вызов `learn_income_keywords_on_create.delay()`

### 3. Миграция дубликатов
**Ответ:** Да, скрипт обязателен. Запускать перед деплоем в режиме --dry-run

### 4. Приоритет функций
**Ответ:**
- **Критично:** Строгая уникальность (helper + 3 функции)
- **Критично:** Celery задачи для симметрии с расходами
- **Важно:** Миграция дубликатов
- **Обязательно:** Аудит кодовой базы

**РЕШЕНИЕ:** Celery теперь часть MVP, не опционально!

### 5. Логика весов (normalized_weights)
**Ответ:** НЕ НУЖНА! Используем строгую уникальность - одно слово = одна категория.
При смене категории слово удаляется из старой и создается в новой.

### 6. Зачем Celery если доходы редко используются?
**Ответ:** Для полной симметрии с расходами и правильной архитектуры:
- ✅ Бот не блокируется при обучении
- ✅ Единообразный код (легче поддерживать)
- ✅ Готовность к росту использования доходов
- ✅ Возможность тяжелых операций в будущем (AI, орфография)

---

## 📝 ИСТОРИЯ ИЗМЕНЕНИЙ

| Дата | Событие | Статус |
|------|---------|--------|
| 2025-11-11 08:00 | Создан первоначальный план (полная симметрия) | ✅ |
| 2025-11-11 09:00 | Упрощение: разделение на MVP и будущее | ✅ |
| 2025-11-11 10:00 | **КРИТИЧНО:** Убрана вся логика весов по требованию пользователя | ✅ |
| 2025-11-11 10:00 | Изменен подход: строгая уникальность без normalized_weights | ✅ |
| 2025-11-11 11:00 | **РЕШЕНИЕ:** Celery задачи включены в MVP для полной симметрии | ✅ |
| | **MVP Этап 1:** Helper функция (без весов) | ⏳ |
| | **MVP Этап 2:** Исправление 3 функций | ⏳ |
| | **MVP Этап 3:** Создание 2 Celery задач | ⏳ |
| | **MVP Этап 4:** Интеграция Celery | ⏳ |
| | **MVP Этап 5:** Миграция дубликатов | ⏳ |
| | **MVP Этап 6:** Аудит | ⏳ |

### Ключевые решения

#### Решение 1: Строгая уникальность (2025-11-11 10:00)
**Пользователь:** "не надо делать такую логику с весами... Только одна уникальная трата во всех расходах и доходах, никаких весов не надо."

**Принятое решение:**
- Убрана вся логика `normalized_weights` и `recalculate_normalized_weights()`
- Используется строгая уникальность: одно слово = одна категория
- Паттерн: удалить из всех → создать в целевой
- Пример: "кофе" в "Продукты" → удаляется из "Кафе и рестораны"

#### Решение 2: Включение Celery в MVP (2025-11-11 11:00)
**Обоснование:**
- Helper функция будет использоваться и из синхронных функций, и из Celery
- Celery обеспечивает полную симметрию с расходами
- Избегает дублирования логики в будущем
- Единообразный код легче поддерживать
- Время реализации: +40 минут (55-85 минут total вместо 30-40)

---

## 🔗 СВЯЗАННЫЕ ДОКУМЕНТЫ

- `CLAUDE.md` - Основная документация проекта
- `docs/CELERY_DOCUMENTATION.md` - Документация Celery (для будущих задач)
- `bot/services/category.py` - Реализация уникальности для расходов (reference)
- `fix_expenses_with_foreign_categories.py` - Пример скрипта миграции

---

## 💡 РЕКОМЕНДАЦИИ

### Порядок работы
1. **Этапы 1-2 (20-25 мин):** Helper + исправление 3 функций
   - Протестировать локально
   - Убедиться что уникальность работает

2. **Этапы 3-4 (25-35 мин):** Celery задачи + интеграция
   - Создать обе задачи в celery_tasks.py
   - Интегрировать в create_income() и update_income()
   - Протестировать что .delay() вызывается корректно

3. **Этап 5 (10 мин):** Миграция дубликатов
   - Запустить в режиме --dry-run на продакшене
   - Проверить результаты
   - Применить --apply

4. **Этап 6 (5 мин):** Аудит
   - Выполнить grep по IncomeCategoryKeyword
   - Убедиться нет других точек входа

5. **После деплоя:** Мониторинг
   - Проверить логи Celery
   - Убедиться что задачи выполняются
   - Мониторить несколько дней

### Тестирование Celery локально
```bash
# Запустить Redis
docker compose up redis -d

# Запустить Celery worker
celery -A expense_bot worker -l info

# В другом терминале - тестировать бота
python run_bot.py
```

### Как расширять в будущем
- Не дублировать код → добавлять параметр `is_income`
- Не создавать новые функции → расширять существующие
- Не переписывать всё → поэтапно, по мере необходимости

---

## 🎯 ИТОГОВЫЙ ПЛАН

**Статус:** Готов к реализации
**Время:** 55-85 минут (полная симметрия с расходами)
**Файлов:** 4 (income_categorization.py, celery_tasks.py, income.py, fix_income_keyword_duplicates.py)

**Что получим:**
- ✅ Строгая уникальность ключевых слов (одно слово = одна категория)
- ✅ Полная симметрия с расходами (включая Celery)
- ✅ Фоновое обучение не блокирует бота
- ✅ Чистая кодовая база без дубликатов
- ✅ Готовность к росту использования доходов

**Следующий шаг:** Начать с Этапа 1 - создать helper функцию `ensure_unique_income_keyword()`
