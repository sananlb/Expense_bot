# 🔍 Сводный отчёт аудита кода ExpenseBot

**Дата:** 2025-11-28
**Версия плана:** 2.0
**Этап:** 1 (Критические проверки безопасности и стабильности)

---

## 📊 Общая оценка

| Секция | Оценка | Статус |
|--------|--------|--------|
| 1.1 Обработка ошибок | 6.5/10 | ⚠️ Требует внимания |
| 1.2 Валидация входных данных | 9/10 | ✅ Отлично |
| 1.3 Проверка владельца сущностей | ❌ | 🔴 КРИТИЧНО |
| 1.4 Логирование и PII | 7/10 | ⚠️ Требует внимания |
| 1.5 Транзакции БД | ❌ | 🔴 КРИТИЧНО |
| 1.6 AI-интеграция | 7.8/10 | ⚠️ Требует внимания |
| 1.7 Блокирующие вызовы | 9.5/10 | ✅ Отлично |
| 1.8 Конфигурация и секреты | 7/10 | ⚠️ Требует внимания |
| 1.9 Зависимости | 7/10 | ⚠️ CVE найдены |

**Средняя оценка: 7.4/10** (без учёта критических секций 1.3 и 1.5)

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (P0) - Исправить немедленно

### 1. Отсутствие валидации владельца при UPDATE операциях

**Файл:** `bot/services/expense.py` (строки 567-656)
```python
# ❌ ПРОБЛЕМА: update_expense() НЕ проверяет category_id
# Пользователь может подставить category_id чужой категории
```

**Файл:** `bot/services/income.py` (строки 564-576)
```python
# ❌ ПРОБЛЕМА: update_income() проверяет только profile=profile
# Игнорирует household (семейный бюджет)
```

**Файл:** `bot/services/recurring.py`
```python
# ❌ ПРОБЛЕМА: Нет проверки household при работе с recurring expenses
```

**Риск:** Пользователь A может использовать категории пользователя B, нарушая изоляцию данных.

---

### 2. Отсутствие транзакций в критических операциях

**Файл:** `bot/services/subscription.py` (строки 96-129)
```python
# ❌ deactivate_expired_subscriptions() - каждая подписка обрабатывается отдельно
# При ошибке пользователь может остаться с premium после истечения подписки
```

**Файл:** `bot/services/expense.py`
```python
# ❌ create_expense() - создание траты + обновление бюджета без atomic()
```

**Файл:** `bot/services/income.py`
```python
# ❌ create_income() - создание дохода без транзакции
```

**Риск:** Частичное выполнение операций, несогласованность данных.

---

### 3. Django CVE уязвимости

**Файл:** `requirements.txt`
```
Django==5.0.9  # ❌ CVE-2024-53907, CVE-2024-53908
```

**Исправление:**
```
Django==5.0.10  # или 5.1.4+
```

---

## 🟠 ВЫСОКИЙ ПРИОРИТЕТ (P1) - Исправить в ближайшее время

### 4. Небезопасные дефолтные значения

**Файл:** `expense_bot/settings.py`
```python
# Строка 21:
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-expense-bot-dev-key-change-in-production')
# ❌ Небезопасный дефолт - если .env не загрузится, будет использован этот ключ

# Строки 97-108:
'PASSWORD': os.getenv('DB_PASSWORD', 'expense_password'),
# ❌ Дефолтный пароль БД
```

**Исправление:**
```python
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']  # Упадёт без .env - это правильно!
'PASSWORD': os.environ['DB_PASSWORD'],
```

---

### 5. Логирование API ключей

**Файлы:** 4 файла в `bot/services/google_ai_service*.py`
```python
logger.info(f"[GoogleAI] API key obtained: {self.api_key[:10]}...")
# ❌ Даже первые 10 символов API ключа - это утечка
```

**Исправление:** Убрать логирование ключей полностью или заменить на:
```python
logger.info(f"[GoogleAI] API key configured: {'***' if self.api_key else 'MISSING'}")
```

---

### 6. Bare except и проглоченные ошибки

**Найдено:** 9 случаев `except:` или `except Exception:` без логирования

**Файлы:**
- `bot/services/export_service.py` - 82% функций без try/except
- `bot/services/analytics_service.py`
- `bot/routers/` - несколько роутеров

**Исправление:** Заменить на:
```python
except Exception as e:
    logger.exception(f"Описание контекста: {e}")
    raise  # или вернуть fallback значение
```

---

### 7. Отсутствие таймаутов в AI сервисах

**Файлы:**
- `bot/services/openai_service.py` - нет явных таймаутов
- `bot/services/unified_ai_service.py` - нет таймаутов

**Исправление:**
```python
# Добавить таймаут в httpx клиент
client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
```

---

## 🟡 СРЕДНИЙ ПРИОРИТЕТ (P2) - Запланировать на рефакторинг

### 8. Логирование точных сумм (PII)

**Найдено:** 4 места где логируются точные суммы трат/доходов

```python
logger.info(f"Created expense: {amount} {currency}")  # ❌ PII
```

**Исправление:**
```python
logger.info(f"Created expense for user {user_id}")  # ✅ Без суммы
```

---

### 9. Отсутствие retry логики в AI сервисах

**Проблема:** При временной недоступности AI провайдера - мгновенный fallback без retry.

**Рекомендация:** Добавить tenacity или ручной retry:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def call_ai_service(...):
    ...
```

---

### 10. Callback.data парсинг без try/except

**Найдено:** ~30 мест в роутерах где `callback.data.split(":")` без обработки ошибок.

**Исправление:**
```python
try:
    action, category_id = callback.data.split(":", 1)
    category_id = int(category_id)
except (ValueError, AttributeError) as e:
    logger.warning(f"Invalid callback data: {callback.data}")
    await callback.answer("Ошибка данных")
    return
```

---

## ✅ ЧТО СДЕЛАНО ХОРОШО

1. **Валидация входных данных (9/10)**
   - 4-уровневая защита: Middleware → InputSanitizer → SecurityValidator → Services
   - 91+ опасный паттерн блокируется
   - XSS, SQL injection, path traversal - защита есть

2. **Отсутствие блокирующих вызовов (9.5/10)**
   - Нет `time.sleep()` в async коде
   - Нет синхронного `requests` - используется `httpx`
   - Django ORM правильно обёрнут в `sync_to_async`

3. **Версии зависимостей зафиксированы**
   - Все 66 пакетов с `==` (не `>=`)
   - Воспроизводимые билды

4. **Правильная обработка ошибок в error_handler.py**
   - Correlation ID для каждой ошибки
   - Graceful degradation для Telegram ошибок
   - Уведомление админа о критических ошибках

---

## 📋 План исправлений

### Фаза 1: Критические (1-2 дня)
- [ ] Добавить валидацию category_id в `update_expense()`
- [ ] Добавить валидацию в `update_income()` с учётом household
- [ ] Обернуть subscription операции в `transaction.atomic()`
- [ ] Обновить Django до 5.0.10+

### Фаза 2: Высокий приоритет (2-3 дня)
- [ ] Убрать небезопасные дефолты в settings.py
- [ ] Удалить логирование API ключей (4 файла)
- [ ] Добавить try/except в export_service.py
- [ ] Добавить таймауты в AI сервисы

### Фаза 3: Средний приоритет (3-5 дней)
- [ ] Убрать PII из логов (4 места)
- [ ] Добавить retry в AI сервисы
- [ ] Добавить try/except для callback.data парсинга

---

## 📁 Файлы требующие изменений

| Приоритет | Файл | Проблема |
|-----------|------|----------|
| P0 | `bot/services/expense.py` | Валидация category в update |
| P0 | `bot/services/income.py` | Валидация + household в update |
| P0 | `bot/services/subscription.py` | Транзакции |
| P0 | `requirements.txt` | Django CVE |
| P1 | `expense_bot/settings.py` | Небезопасные дефолты |
| P1 | `bot/services/google_ai_service*.py` (4) | Логирование ключей |
| P1 | `bot/services/export_service.py` | Error handling |
| P1 | `bot/services/openai_service.py` | Таймауты |
| P2 | `bot/routers/*.py` | Callback.data parsing |

---

## 🎯 Следующие этапы аудита

После исправления критических проблем, продолжить с:

- **Этап 2:** Качество кода (дублирование, типизация, документация)
- **Этап 3:** Архитектура (разделение слоёв, паттерны)
- **Этап 4:** Производительность (N+1, кеширование, индексы)
- **Этап 5:** Инфраструктура (Docker, CI/CD)
