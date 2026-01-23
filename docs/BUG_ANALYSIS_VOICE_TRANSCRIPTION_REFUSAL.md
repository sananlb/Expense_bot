# Анализ бага: AI отказ попал в описание траты

**Дата обнаружения:** 23 января 2026
**Статус:** Анализ завершён, исправление не применено
**Severity:** Medium (влияет на UX, данные не теряются)

---

## Описание проблемы

В админке обнаружена трата с описанием:
```
"I'm sorry, but I cannot transcribe this audio as there is no audio file or link provided in your message. Please provide the audio you would like me to transcribe. кружок матвей нейропсихолог"
```

Это ответ AI модели (Gemini через OpenRouter), который был ошибочно принят как успешная транскрипция голосового сообщения.

---

## Затронутые данные

| Поле | Значение |
|------|----------|
| **Expense ID** | 1329 |
| **User ID** | 348740371 |
| **Сумма** | 1600 RUB |
| **Дата создания** | 2026-01-23 10:17:13 |

---

## Хронология инцидента

| Время | Событие | Детали |
|-------|---------|--------|
| 10:16:58 | Голосовое сообщение #1 | duration: 1 сек, size: 1151 байт (очень короткое) |
| 10:16:59 | Yandex Speech упал | Primary провайдер не смог распознать |
| 10:16:59 | Fallback на OpenRouter | `[VoiceRecognition] Primary (yandex) failed, trying fallback (openrouter)` |
| 10:17:06 | OpenRouter вернул отказ | `"I'm sorry, but I cannot transcribe this audio..."` |
| 10:17:06 | Текст принят как транскрипция | Код не проверил содержимое ответа |
| 10:17:06 | Парсер не нашёл сумму | Текст сохранён в `expense_description` |
| 10:17:06 | Состояние FSM | `waiting_for_amount_clarification` |
| 10:17:13 | Голосовое сообщение #2 | duration: 4 сек, size: 19031 байт |
| 10:17:13 | Yandex Speech успешно | `"1600 кружок матвей нейропсихолог"` |
| 10:17:13 | Объединение текстов | `full_text = f"{description} {text}"` |
| 10:17:13 | Создана трата 1329 | С объединённым "мусорным" описанием |

---

## Анализ кода

### Цепочка вызовов

```
voice_to_text.py:70 → process_voice_for_expense()
       ↓
voice_recognition.py:184 → VoiceRecognitionService.transcribe()
       ↓
voice_recognition.py:94 → _transcribe_single(provider='yandex')
       ↓ (Yandex упал)
voice_recognition.py:101 → _transcribe_single(provider='openrouter')
       ↓
unified_ai_service.py:621 → transcribe_voice()
       ↓
Gemini возвращает: "I'm sorry, but I cannot transcribe..."
       ↓
unified_ai_service.py:719 → return transcribed_text  ← БАГ: нет валидации!
       ↓
voice_to_text.py:74 → data['voice_text'] = text
       ↓
expense.py:1690 → state.update_data(expense_description=text)
       ↓
expense.py:851 → full_text = f"{description} {text}"  ← объединение с мусором
       ↓
Трата создана с некорректным описанием
```

### Проблема: Отсутствие валидации ответа OpenRouter (ЕДИНСТВЕННАЯ)

**Файл:** `bot/services/unified_ai_service.py`
**Строки:** 704-719

```python
content = response.choices[0].message.content
transcribed_text = content.strip() if content else ""

# ... логирование ...

logger.info(f"[OpenRouter] Транскрибировано за {response_time:.2f}s: {transcribed_text[:50]}...")
return transcribed_text if transcribed_text else None  # ← НЕТ ПРОВЕРКИ НА ОТКАЗ!
```

**Проблема:** Код проверяет только что текст не пустой, но не проверяет его содержимое. Ответ AI типа "I'm sorry, I cannot..." принимается как успешная транскрипция.

### Следствие: Объединение текстов с "мусором"

**Файл:** `bot/routers/expense.py`
**Строка:** 851

```python
# Объединяем описание и сумму для полного парсинга с AI
full_text = f"{description} {text}"
```

**Это НЕ отдельная проблема** — объединение работает корректно. Проблема в том, что туда попал "мусор" из-за отсутствия валидации в `transcribe_voice`.

Если исправить проблему #1, то мусор не попадёт в `expense_description` и объединение будет работать правильно.

---

## Почему оба провайдера не распознали речь?

### Анализ аудио файла

Проблемное голосовое имело **аномально маленький размер**:

| Параметр | Проблемное | Нормальные 1-сек |
|----------|------------|------------------|
| Duration | 1 сек | 1 сек |
| Size | **1151 байт** | 5000-8500 байт |
| Bitrate | ~9 кбит/с | ~40-70 кбит/с |

**Вывод:** Пользователь случайно нажал и сразу отпустил кнопку записи. В аудио была только тишина/фоновый шум.

### Сравнение с успешными распознаваниями

В тот же день другие 1-секундные голосовые с нормальным размером были успешно распознаны:

| Время | Size | Результат Yandex |
|-------|------|------------------|
| 11:59:40 | 5852 байт | ✅ "78 продуктов" (0.19s) |
| 11:59:44 | 5896 байт | ✅ "296" (0.22s) |
| 12:00:00 | 6503 байт | ✅ "78 продуктов" (0.28s) |

### Поведение провайдеров

| Провайдер | Поведение | Оценка |
|-----------|-----------|--------|
| **Yandex** | Вернул пустой результат за 0.22s | ✅ **Корректно** — речи нет |
| **OpenRouter/Gemini** | Вернул текст отказа "I'm sorry..." | ⚠️ **Проблема** — должен вернуть пустоту |

### Корневая причина бага

**Не Yandex и не Gemini виноваты** — оба корректно определили отсутствие речи.

**Проблема в коде:** `unified_ai_service.py` не проверяет, является ли ответ Gemini отказом, и возвращает текст отказа как успешную транскрипцию.

---

## Рекомендуемые исправления

### Исправление #1: Проверка минимального размера аудио (ранняя защита)

**Файл:** `bot/services/voice_recognition.py`
**Место:** В начале метода `transcribe()`, перед обращением к провайдерам

```python
# Минимальный размер аудио для распознавания (байт на секунду)
# Нормальное аудио: 5000-8500 байт/сек
# Проблемное (тишина): ~1000 байт/сек
MIN_BYTES_PER_SECOND = 3000

# Проверяем что аудио не "пустое"
if len(audio_bytes) < MIN_BYTES_PER_SECOND:
    logger.warning(f"[VoiceRecognition] User {user_id} | Audio too small: {len(audio_bytes)} bytes, skipping")
    return None
```

**Почему это важно:**
- Экономит API запросы к Yandex и OpenRouter
- Предотвращает обработку "случайных нажатий" кнопки записи
- Быстрая проверка без сетевых вызовов

### Исправление #2: Валидация ответа OpenRouter (защита от отказов AI)

**Файл:** `bot/services/unified_ai_service.py`
**Место:** После строки 705, перед return

```python
# Проверяем, не является ли ответ отказом AI
AI_REFUSAL_PATTERNS = [
    "i'm sorry",
    "i cannot",
    "i'm unable",
    "sorry, but",
    "cannot transcribe",
    "no audio",
    "unable to process",
    "unable to transcribe",
    "no speech detected",
    "could not transcribe",
]

transcribed_lower = transcribed_text.lower()
for pattern in AI_REFUSAL_PATTERNS:
    if pattern in transcribed_lower:
        logger.warning(f"[OpenRouter] AI вернул отказ вместо транскрипции: {transcribed_text[:100]}...")
        return None
```

**Почему нужны оба исправления:**
- #1 предотвращает ненужные API вызовы
- #2 защищает от edge cases, когда аудио прошло проверку, но AI всё равно не смог распознать

---

## Логи сервера (релевантные)

```
INFO 2026-01-23 10:16:58,793 logging_middleware Request: {"user_id": 348740371, "message_type": "voice", "voice_duration": 1, "voice_size": 1151}
INFO 2026-01-23 10:16:59,049 voice_recognition [VOICE_INPUT] User 348740371 | Duration: 1s | Lang: ru
INFO 2026-01-23 10:16:59,267 voice_recognition [VoiceRecognition] Primary (yandex) failed, trying fallback (openrouter)
INFO 2026-01-23 10:17:06,847 unified_ai_service [OpenRouter] Транскрибировано за 5.05s: I'm sorry, but I cannot transcribe this audio as t...
INFO 2026-01-23 10:17:06,847 voice_recognition [VoiceRecognition] User 348740371 | Lang: ru | Time: 7.80s | Text: I'm sorry, but I cannot transcribe this audio as t...
INFO 2026-01-23 10:17:06,847 voice_to_text [VoiceToText] User 348740371: voice transcribed to 'I'm sorry, but I cannot transcribe this audio as t...'
INFO 2026-01-23 10:17:06,848 expense [VOICE_EXPENSE] User 348740371 | Voice recognized | Processing text: I'm sorry, but I cannot transcribe this audio as there is no audio file or link provided in your mes
INFO 2026-01-23 10:17:06,859 expense Starting parse_expense_message for text: 'I'm sorry, but I cannot transcribe this audio as there is no audio file or link provided in your message. Please provide the audio you would like me to transcribe.', user_id: 348740371
```

---

## Действия

- [x] Исправление #1: Добавить проверку минимального размера аудио в `voice_recognition.py` ✅ (строки 48-55)
- [x] Исправление #2: Добавить валидацию ответа на отказы AI в `unified_ai_service.py` ✅ (строки 707-727)
- [ ] Задеплоить на сервер
- [ ] Мониторить логи на предмет повторения проблемы
- [ ] (опционально) Исправить описание траты 1329 в БД

---

## Связанные файлы

| Файл | Описание |
|------|----------|
| `bot/services/unified_ai_service.py` | Метод `transcribe_voice` (строки 621-731) |
| `bot/services/voice_recognition.py` | Сервис распознавания с fallback |
| `bot/middlewares/voice_to_text.py` | Middleware транскрипции |
| `bot/routers/expense.py` | Обработчик `handle_amount_clarification` (строка 851) |
