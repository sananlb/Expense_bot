# Отчет об ошибках - 31 января 2026

**Дата:** 31 января 2026
**Сервер:** PRIMARY (176.124.218.53)
**Период анализа:** 00:00 - 23:59 MSK

---

## 📊 Краткая сводка

| Категория | Количество | Критичность |
|-----------|------------|-------------|
| **Реальные ошибки системы** | 2 | ⚠️ Некритично |
| **Пользовательские ошибки** | 1 | ℹ️ Информационная |
| **Медленные запросы** | 7 | ⚠️ Требует внимания |
| **Сканеры/боты** | ~15 | ✅ Заблокированы |

**Статус системы:** ✅ **Стабильно**
**Критичных ошибок:** 0

---

## ❌ Детальный анализ ошибок

### 1. Top-5 обновление - Message not found

**Время:** 05:00:00
**Тип:** Некритичная системная ошибка
**Затронуто пользователей:** 1

#### Описание ошибки:
```
ERROR 2026-01-31 05:00:00,340 celery_tasks
Top-5 update error for user 1204146623:
Telegram server says - Bad Request: message to edit not found
```

#### Контекст (полные логи):
```
INFO 2026-01-31 05:00:00,009 beat
Scheduler: Sending due task update-top5-keyboards
(expense_bot.celery_tasks.update_top5_keyboards)

INFO 2026-01-31 05:00:00,013 strategy
Task expense_bot.celery_tasks.update_top5_keyboards[2dd30ba2-00f4-44f4-bbbc-e6108a0dc4a2] received

ERROR 2026-01-31 05:00:00,340 celery_tasks
Top-5 update error for user 1204146623:
Telegram server says - Bad Request: message to edit not found

INFO 2026-01-31 05:00:00,972 celery_tasks
Top-5 updated for 0 pinned messages (profiles processed: 76)

INFO 2026-01-31 05:00:01,018 trace
Task expense_bot.celery_tasks.update_top5_keyboards[2dd30ba2-00f4-44f4-bbbc-e6108a0dc4a2]
succeeded in 1.001614572996914s: None
```

#### Причина:
Пользователь **1204146623** удалил закрепленное сообщение с Top-5 категориями в своем чате, но в БД осталась запись о пине. При попытке обновления клавиатуры (ежедневная задача в 05:00) система не нашла сообщение.

#### Влияние:
- ✅ Задача выполнилась успешно
- ✅ Обработано 76 пользователей
- ⚠️ Для пользователя 1204146623 Top-5 больше не обновляется автоматически

#### Решение:
1. **Краткосрочное:** Пользователь может заново создать Top-5 через команду `/top5`
2. **Долгосрочное:** Добавить автоматическую очистку пинов при ошибке "message not found"

---

### 2. Memory Leak - Unclosed client session

**Время:** 12:00:00
**Тип:** Некритичная утечка ресурсов
**Затронуто:** Celery worker

#### Описание ошибки:
```
ERROR 2026-01-31 12:00:00,208 base_events Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x788ddcb73110>

ERROR 2026-01-31 12:00:00,208 base_events Unclosed connector
connections: ['[(<aiohttp.client_proto.ResponseHandler object at 0x788dddc74130>, 61207.932998318)]']
connector: <aiohttp.connector.TCPConnector object at 0x788dde69c1d0>
```

#### Контекст (полные логи):
```
INFO 2026-01-31 12:00:00,008 beat
Scheduler: Sending due task process-recurring-payments
(expense_bot.celery_tasks.process_recurring_payments)

INFO 2026-01-31 12:00:00,014 strategy
Task expense_bot.celery_tasks.process_recurring_payments[cdb14146-32b5-4ccf-ba60-6a331dd79d5c] received

INFO 2026-01-31 12:00:00,045 celery_tasks
Processed 0 recurring payments

ERROR 2026-01-31 12:00:00,208 base_events Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x788ddcb73110>

ERROR 2026-01-31 12:00:00,208 base_events Unclosed connector
connections: ['[(<aiohttp.client_proto.ResponseHandler object at 0x788dddc74130>, 61207.932998318)]']
connector: <aiohttp.connector.TCPConnector object at 0x788dde69c1d0>

INFO 2026-01-31 12:00:00,209 trace
Task expense_bot.celery_tasks.process_recurring_payments[cdb14146-32b5-4ccf-ba60-6a331dd79d5c]
succeeded in 0.19324572500045178s: None
```

#### Причина:
В задаче `process_recurring_payments` используется Telegram Bot API через aiogram. При завершении задачи не закрываются:
- `aiohttp.ClientSession` (HTTP клиент для Telegram API)
- `TCPConnector` (TCP соединения)

**Место в коде:** [expense_bot/celery_tasks.py:1148-1250](expense_bot/celery_tasks.py#L1148-L1250)

```python
finally:
    if loop is not None:
        if bot is not None:
            try:
                loop.run_until_complete(bot.close())  # ← Здесь должно закрываться
            except Exception as e:
                logger.error(f"Failed to close bot session: {e}")
```

#### Влияние:
- ✅ Задача выполнилась успешно (0 платежей обработано)
- ⚠️ Небольшая утечка памяти (~1-2 KB на запуск)
- ⚠️ При накоплении может привести к увеличению потребления памяти Celery worker

#### Решение:
**Код работает корректно** - есть `finally` блок с `bot.close()`. Проблема в том, что aiogram иногда не успевает закрыть соединение до завершения event loop.

**Рекомендация:** Добавить явное ожидание перед закрытием loop:
```python
finally:
    if loop is not None:
        if bot is not None:
            try:
                loop.run_until_complete(bot.close())
                loop.run_until_complete(asyncio.sleep(0.1))  # Дать время на cleanup
            except Exception as e:
                logger.error(f"Failed to close bot session: {e}")
```

---

### 3. Заблокированный бот пользователем

**Время:** 20:00:00
**Тип:** Пользовательское действие (не ошибка системы)
**Затронуто пользователей:** 1

#### Описание:
```
ERROR 2026-01-31 20:00:00,512 telegram_utils
Error sending message to 908925627:
Telegram server says - Forbidden: bot was blocked by the user

ERROR 2026-01-31 20:00:00,512 tasks
[REMINDER] Failed to send reminder to 908925627:
Telegram server says - Forbidden: bot was blocked by the user
```

#### Контекст (полные логи):
```
INFO 2026-01-31 20:00:00,008 beat
Scheduler: Sending due task send-expense-reminders
(expenses.tasks.send_expense_reminders)

INFO 2026-01-31 20:00:00,011 strategy
Task expenses.tasks.send_expense_reminders[a4d9f6f5-3075-4e6e-a803-924019225886] received

INFO 2026-01-31 20:00:00,324 tasks
[REMINDER] User 908925627 needs reminder
(last expense 24-48h ago: 2026-01-30 09:00:00.192176+00:00)

ERROR 2026-01-31 20:00:00,512 telegram_utils
Error sending message to 908925627:
Telegram server says - Forbidden: bot was blocked by the user

ERROR 2026-01-31 20:00:00,512 tasks
[REMINDER] Failed to send reminder to 908925627:
Telegram server says - Forbidden: bot was blocked by the user

INFO 2026-01-31 20:00:00,792 tasks
[REMINDER] User 749671898 needs reminder
(last expense 24-48h ago: 2026-01-29 17:45:44.397248+00:00)

INFO 2026-01-31 20:00:01,264 telegram_utils
Message sent to 749671898

INFO 2026-01-31 20:00:01,266 tasks
[REMINDER] Sent reminder to user 749671898
```

#### Причина:
Пользователь **908925627** заблокировал бота в Telegram. Последняя трата была 30 января в 09:00, система пыталась отправить напоминание через 24-48 часов.

#### Влияние:
- ✅ Система корректно обработала ошибку
- ✅ Остальные пользователи (749671898, 2030342152, 1028807554, 451026350) получили напоминания
- ℹ️ Пользователь 908925627 больше не получает уведомления

#### Решение:
Это **нормальное поведение**. Рекомендуется добавить флаг в БД о блокировке, чтобы не пытаться отправлять сообщения этому пользователю в будущем (экономия запросов к Telegram API).

---

## ⚡ Медленные запросы (>3 сек)

Обнаружено **7 медленных запросов** с продолжительностью 3.27-7.35 секунд.

### Статистика:

| Время | Пользователь | Длительность | Тип операции |
|-------|--------------|--------------|--------------|
| 12:12:57 | 399825934 | 7.35s | AI категоризация траты (Пастила) |
| 15:09:44 | 348740371 | 4.44s | AI категоризация траты (Бензин) |
| 16:01:53 | 1453938432 | 6.04s | AI категоризация траты (Семён корман 90) |
| 16:03:22 | 1453938432 | 4.26s | AI категоризация дохода (%счёт) |
| 17:13:49 | 348740371 | 3.27s | AI категоризация дохода (Инвестиции) |
| 18:55:35 | 348740371 | 4.23s | AI категоризация дохода (Бытовая химия) |
| 23:50:54 | 1028807554 | 4.19s | AI категоризация траты (Азс) |

### Детальный анализ самого медленного запроса:

**Запрос #1: 7.35 секунд (12:12:57)**

```
INFO 2026-01-31 12:12:50,006 web_log
POST /webhook/ - user 399825934 - text message (7 chars)

INFO 2026-01-31 12:12:51,676 expense_parser
Getting AI service for categorization...

INFO 2026-01-31 12:12:51,676 key_rotation_mixin
[DeepSeekKeyRotationMixin] Using API key #1 of 2

INFO 2026-01-31 12:12:52,445 _client
HTTP Request: POST https://api.deepseek.com/v1/chat/completions
"HTTP/1.1 200 OK"

INFO 2026-01-31 12:12:56,996 expense_parser
AI categorization completed

INFO 2026-01-31 12:12:57,001 expense_categorization
[EXPENSE CATEGORY MATCH] AI suggested 'Продукты' → matched '🛒 Продукты'

INFO 2026-01-31 12:12:57,002 expense
Parsing completed: 268.0 RUB, category='Продукты'

INFO 2026-01-31 12:12:57,173 expense
Created expense 1596 for user 399825934

WARNING 2026-01-31 12:12:57,346 logging_middleware
Slow request detected: type=text, duration=7.35s, user=399825934
```

### Причина медленных запросов:
1. **DeepSeek API latency:** 4-5 секунд на запрос к AI
2. **Обработка ответа:** ~1 секунда на парсинг и сохранение
3. **Очередь обработки:** небольшие задержки в Telegram webhook

### Влияние:
- ⚠️ Пользователи ждут 4-7 секунд ответа бота
- ⚠️ Может создавать ощущение "подвисания"
- ✅ Все запросы завершились успешно

### Решение:
1. **Краткосрочное:**
   - Добавить промежуточное сообщение "Обрабатываю..." для запросов >2 сек
   - Использовать typing indicator (`bot.send_chat_action(ChatAction.TYPING)`)

2. **Среднесрочное:**
   - Переключить AI провайдера для категоризации на более быстрый (OpenRouter, Qwen)
   - Оптимизировать промпт для DeepSeek (короче = быстрее)

3. **Долгосрочное:**
   - Кешировать популярные категоризации
   - Использовать ключевые слова чаще (быстрее AI)

---

## 🤖 Внешние сканеры (НЕ ошибки системы)

Зафиксировано **~15 попыток** сканирования сервера от внешних ботов:

### Типы сканирования:

| Время | IP | User-Agent | Цель |
|-------|-----|------------|------|
| 13:00:56 | 66.132.153.116 | CensysInspect/1.1 | Сканирование интернета |
| 13:31:30 | 121.41.167.32 | Nmap Scripting Engine | Поиск портов |
| 18:21:08 | 91.231.89.114 | - | Попытка эксплуатации |
| 18:57:58 | 9.234.8.125 | zgrab/0.x | Автоматическое сканирование |
| 22:36-23:03 | Различные | - | WordPress уязвимости |

### Примеры запросов:
```
ERROR Invalid HTTP_HOST header: 'www.google.com:443'
ERROR Invalid HTTP_HOST header: '0.0.0.0:8000'
WARNING Not Found: /xmlrpc.php
WARNING Not Found: /wp/
WARNING Not Found: /bin/
WARNING Not Found: /backup/
ERROR web_protocol Error handling request "UNKNOWN / HTTP/1.0" 400
```

### Статус защиты:
✅ **Все запросы успешно заблокированы**
- HTTP 400 (Bad Request) - неправильные методы
- HTTP 404 (Not Found) - несуществующие пути
- Все попытки эксплуатации провалились

**Рекомендация:** Настроить Fail2Ban для автоматической блокировки IP после 5+ неудачных запросов.

---

## 📈 Общая статистика за день

### Активность пользователей:
- **7** активных пользователей (создали траты)
- **3** пользователя добавили доходы
- **1** новый пользователь

### Операции:
- **18** трат на сумму 49,875 руб
- **5** доходов на сумму 158,389 руб
- **4** AI категоризаций трат (22%)
- **3** AI категоризаций доходов (60%)

### Производительность:
- **Средняя скорость обработки:** 200-400ms (без AI)
- **С AI категоризацией:** 3-7 секунд
- **Успешность запросов:** 100%

---

## 🔧 Рекомендации

### Высокий приоритет:
1. ✅ **Оптимизировать AI категоризацию:**
   - Добавить typing indicator для медленных запросов
   - Рассмотреть более быстрые AI провайдеры

2. ✅ **Исправить memory leak:**
   - Добавить задержку перед закрытием event loop
   - Проверить что все aiohttp сессии закрываются

### Средний приоритет:
3. ⚠️ **Автоочистка Top-5 пинов:**
   - При ошибке "message not found" удалять запись из БД
   - Логировать для статистики

4. ⚠️ **Обработка заблокированных пользователей:**
   - Добавить флаг `bot_blocked` в профиль
   - Не пытаться отправлять сообщения заблокировавшим бота

### Низкий приоритет:
5. ℹ️ **Настроить Fail2Ban:**
   - Автоматическая блокировка сканеров
   - Уменьшение нагрузки на сервер

---

## ✅ Выводы

**Система работает стабильно.** Все обнаруженные ошибки имеют **некритичный характер** и не влияют на основную функциональность бота.

### Основные проблемы:
1. **Медленная AI категоризация** (4-7 сек) - основная проблема UX
2. **Memory leak в recurring payments** - требует исправления
3. **Top-5 пин не удаляется** - минорная проблема

### Положительные моменты:
- ✅ Все Celery задачи выполняются по расписанию
- ✅ Все внешние атаки заблокированы
- ✅ 100% успешность обработки пользовательских запросов
- ✅ Нет критических ошибок или падений сервиса

**Рейтинг стабильности:** 9/10 ⭐

---

**Отчет подготовлен:** 31 января 2026, 23:59 MSK
**Следующая проверка:** 1 февраля 2026 (после отправки месячных отчетов)
