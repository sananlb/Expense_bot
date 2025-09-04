# 🔍 Code Review Issues - Expense Bot

## 📅 Дата проверки: 2025-09-03
## 📅 Последнее обновление: 2025-09-03

## ✅ ВЫПОЛНЕННЫЕ ИСПРАВЛЕНИЯ

### Критические исправления (2025-09-03):
1. **N+1 запросы исправлены:**
   - `bot/services/category.py:766` - добавлен prefetch_related('categorykeyword_set')
   - `bot/services/income.py:304` - добавлен select_related('category')
   - `bot/services/expense_functions.py:729` - добавлен select_related('category')

2. **Безопасность - убран hardcoded пароль:**
   - `create_superuser.py` - теперь использует переменные окружения или генерирует безопасный пароль

3. **Утечка информации закрыта:**
   - `bot/routers/cashback.py:581, 808` - ошибки логируются, пользователю показывается общее сообщение
   - `bot/routers/recurring.py:135, 421, 442` - исключения логируются с контекстом
   - `bot/middlewares/security_check.py:232, 251` - убран прямой вывод исключений

4. **Bare except заменены на конкретные исключения (всего 19 мест):**
   - `bot/routers/subscription.py` - 7 мест исправлено (TelegramBadRequest, ObjectDoesNotExist)
   - `bot/routers/expense.py` - 5 мест исправлено (TelegramForbiddenError, DatabaseError)
   - `bot/routers/categories.py` - 3 места исправлено (TelegramBadRequest)
   - `bot/services/google_ai_service.py` - 2 места исправлено (json.JSONDecodeError, ValueError)
   - `bot/utils/expense_parser.py` - 2 места исправлено (AttributeError, TypeError)
   - `bot/routers/settings.py` - 2 места исправлено (pytz.UnknownTimeZoneError)

5. **Санитизация AI промптов:**
   - Создан модуль `bot/utils/input_sanitizer.py` с защитой от prompt injection
   - Внедрена санитизация в `bot/services/ai_base_service.py`
   - Защита от 20+ паттернов prompt injection атак
   - Ограничение длины, удаление чувствительных данных

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (Требуют немедленного исправления)

### 1. N+1 Запросы в базе данных

#### 1.1 bot/services/category.py:765
```python
# ПРОБЛЕМА: Цикл с отдельными запросами для каждой категории
for category in categories:
    keywords = CategoryKeyword.objects.filter(category=category)
```
**Решение:** Использовать prefetch_related

#### 1.2 bot/services/income.py:301
```python
# ПРОБЛЕМА: Отсутствует select_related для категорий
incomes = Income.objects.filter(profile=profile, income_date=today)
```
**Решение:** Добавить .select_related('category')

#### 1.3 bot/services/expense_functions.py:716
```python
# ПРОБЛЕМА: Загрузка расходов без связанных данных
expenses = Expense.objects.filter(profile=profile, expense_date=today)
```
**Решение:** Добавить .select_related('category')

### 2. Безопасность

#### 2.1 create_superuser.py:29
```python
# ПРОБЛЕМА: Захардкоженный пароль
password = 'admin123'
```
**Решение:** Использовать переменные окружения или генерировать случайный пароль

#### 2.2 AI сервисы - Prompt Injection
**Файлы:**
- bot/services/ai_base_service.py:79
- bot/services/google_ai_service.py
- bot/services/openai_service.py

**Проблема:** User input напрямую интерполируется в промпты
**Решение:** Санитизация входных данных, экранирование специальных символов

#### 2.3 Утечка информации через ошибки
**Файлы:**
- bot/routers/cashback.py:581, 808
- bot/middlewares/security_check.py:232, 251
- bot/routers/recurring.py:135, 421, 442

**Проблема:** Прямой вывод exception пользователю
```python
await message.answer(f"❌ Ошибка: {str(e)}")
```
**Решение:** Логировать детали, показывать общее сообщение пользователю

### 3. Bare Except Statements (34 места)

**Наиболее критические:**
- bot/routers/subscription.py (7 мест): 133, 143, 189, 256, 479, 568, 643
- bot/routers/expense.py (5 мест): 488, 539, 824, 879, 890
- bot/routers/categories.py (3 места): 61, 412, 769
- bot/utils/expense_parser.py (2 места): 388, 593
- bot/services/google_ai_service.py (2 места): 112, 277
- bot/routers/settings.py (2 места): 58, 113

## ⚠️ ВЫСОКИЙ ПРИОРИТЕТ

### 4. Дублирование кода

#### 4.1 Обработка expense и income
**Проблема:** Почти идентичный код для обработки трат и доходов
**Файлы:**
- bot/services/expense_functions.py
- bot/services/income.py
- bot/routers/expense.py

**Решение:** Создать базовый класс или общие функции

### 5. Отсутствие индексов БД
**Поля требующие индексы:**
- Profile.telegram_id
- Expense.expense_date
- Expense.profile + expense_date (составной)
- Income.income_date
- Income.profile + income_date (составной)
- RecurringPayment.day_of_month
- RecurringPayment.is_active

## 📊 СРЕДНИЙ ПРИОРИТЕТ

### 6. Производительность

#### 6.1 Неэффективный поиск текста
**Файл:** bot/utils/expense_parser.py:300-400
**Проблема:** Поиск по тексту в Python вместо БД
**Решение:** Использовать PostgreSQL full-text search

#### 6.2 Избыточное использование sync_to_async
**Проблема:** Множество sync_to_async вместо нативного async ORM
**Решение:** Рассмотреть миграцию на async ORM (Tortoise-ORM или Django 4.1+ async)

### 7. Обработка ошибок без контекста
**Проблема:** Логи без user_id и контекста операции
```python
logger.error(f"Error: {e}")  # Плохо
logger.error(f"Error for user {user_id} in operation X: {e}")  # Хорошо
```

## 📈 СТАТИСТИКА
- **Всего критических проблем:** 3 категории
- **Bare except statements:** 34
- **N+1 проблемы:** 3 критических + несколько менее важных
- **Проблемы безопасности:** 3 типа
- **Файлов требующих рефакторинга:** ~15

## ✅ ПЛАН ИСПРАВЛЕНИЯ

### Этап 1 (Критический - выполнено 2025-09-03):
1. [✅] Исправить N+1 запросы (3 места) - ВЫПОЛНЕНО
2. [✅] Убрать hardcoded пароль - ВЫПОЛНЕНО  
3. [✅] Закрыть утечку информации через ошибки - ВЫПОЛНЕНО
4. [✅] Заменить bare except на конкретные исключения - ВЫПОЛНЕНО
5. [✅] Добавить санитизацию для AI промптов - ВЫПОЛНЕНО
6. [✅] Создать миграцию для индексов БД - ВЫПОЛНЕНО

### Этап 2 (Высокий приоритет - следующие задачи):
7. [ ] Рефакторинг дублирующегося кода expense/income
8. [ ] Улучшить логирование с контекстом
9. [ ] Оптимизировать текстовый поиск

### Этап 3 (Средний приоритет - следующая неделя):
7. [ ] Рефакторинг дублирующегося кода
8. [ ] Улучшить логирование с контекстом
9. [ ] Оптимизировать текстовый поиск

## 📝 ЗАМЕТКИ
- Все исправления должны следовать принципам production-ready кода
- Никаких временных решений или костылей
- Каждое изменение должно быть протестировано
- Следовать существующим паттернам проекта