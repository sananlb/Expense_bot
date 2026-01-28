# PDF Timeout Incident - 2026-01-24 16:21

## 📋 Краткое резюме

**Дата:** 2026-01-24
**Время:** 16:15:47 - 16:21:33 (длительность: ~6 минут)
**Пользователь:** 348740371
**Основная проблема:** Timeout при генерации PDF отчета
**Последствия:** Каскад из 15+ ошибок, невозможность отправки уведомлений админу

---

## 🕐 Хронология событий

### 16:15:47 - Начало инцидента
```
INFO logging_middleware: callback_data="pdf_generate_current", user_id=348740371
```
- Пользователь нажал кнопку "Сформировать PDF отчет"
- Запрос `request_id=30` начал обработку

### 16:15:52 - Повторное нажатие (5 секунд спустя)
```
INFO logging_middleware: callback_data="pdf_generate_current", user_id=348740371
```
- Пользователь не дождался ответа и нажал кнопку **еще раз**
- Запрос `request_id=31` создан (дубликат)

### 16:16:13 - Пользователь начал нажимать другие кнопки
```
INFO logging_middleware: callback_data="edit_cancel_expense_1360", user_id=348740371
```
- Пользователь начал редактировать траты (думал что PDF не сработал)
- Создается очередь из нескольких запросов

### 16:21:29 - Первый timeout (315 секунд!)
```
ERROR message_utils: Unexpected error deleting message: HTTP Client says - Request timeout error
ERROR logging_middleware: Request error: type=callback_query, duration=315.55s, user=348740371,
                          error=HTTP Client says - Request timeout error
```
- **Telegram request timeout**: первый запрос истек через 315 секунд (5 минут 15 секунд)
- Telegram начал отправлять все накопившиеся updates одновременно

### 16:21:29 - Каскад дублирующих callbacks
```
WARNING security: SECURITY_EVENT: burst_activity_detected
ERROR logging_middleware: error=Telegram server says - Bad Request: query is too old and
                          response timeout expired or query ID is invalid
ERROR logging_middleware: error=Telegram server says - Bad Request: message is not modified
```
- Система зафиксировала "burst activity" (подозрительная активность)
- 15+ duplicate callbacks обрабатываются одновременно
- Большинство падают с ошибками "query is too old" или "message is not modified"

### 16:21:30 - PDF Timeout Error
```
ERROR pdf_report: Error generating PDF report: Timeout 30000ms exceeded.
WARNING logging_middleware: Slow request detected: type=callback_query, duration=338.44s, user=348740371
INFO dispatcher: Update id=310883884 is handled. Duration 338492 ms by bot id=8239680156
```
- **Playwright timeout**: генерация PDF не удалась через 30 секунд
- **Общее время обработки**: 338 секунд (5 минут 38 секунд!)

### 16:21:30 - Admin Notifier ошибки
```
ERROR admin_notifier: Ошибка при отправке в Telegram: Telegram API error: Bad Request:
                      can't parse entities: Character '-' is reserved and must be escaped with the preceding '\'
ERROR admin_notifier: Детали ошибки: chat_id=881292737, message_length=676
```
- Система пыталась отправить уведомление админу (user 881292737)
- **10+ попыток** отправки упали из-за неэкранированного markdown
- Символ `-` в сообщении не был экранирован как `\-`

---

## 🐛 Выявленные проблемы

### 1. ⏰ PDF Generation Timeout (КРИТИЧНО)

**Проблема:** Генерация PDF заняла > 6 минут и завершилась timeout

**Файл:** `bot/services/pdf_report.py:742-768`

**Код:**
```python
async def _html_to_pdf(self, html_content: str) -> bytes:
    """Конвертация HTML в PDF используя Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2
        )

        # ПРОБЛЕМА: wait_until='networkidle' ждет загрузки всех сетевых ресурсов
        await page.set_content(html_content, wait_until='networkidle')  # ← БЕЗ TIMEOUT!

        await page.wait_for_timeout(2000)

        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '10px', 'bottom': '10px', 'left': '15px', 'right': '15px'},
            scale=0.95
        )
```

**Корневая причина:**

1. **HTML шаблон загружает Chart.js с CDN:**
   ```html
   <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
   ```
   Файл: `reports/templates/report_modern.html:6`

2. **`wait_until='networkidle'` БЕЗ timeout:**
   - Playwright ждет пока **все** сетевые запросы завершатся
   - Default timeout: 30 секунд
   - Если CDN медленный/недоступен → timeout

3. **В момент инцидента cdn.jsdelivr.net:**
   - Был медленным или недоступен
   - Playwright ждал 30 секунд → timeout
   - Default Playwright timeout сработал

**Почему сейчас работает:**
- CDN быстро отвечает
- Есть кеширование браузера
- Сетевые условия улучшились

---

### 2. 🔄 Telegram Request Timeout (315 секунд)

**Проблема:** Основной request обработки callback превысил 5 минут

**Последствия:**
- Telegram считает что бот "завис"
- Telegram начинает повторно отправлять все pending updates
- Создается каскад дублирующих запросов

**Почему 315 секунд:**
- Telegram webhook timeout для callback queries
- После этого времени Telegram переотправляет update

---

### 3. 🔁 Duplicate Callbacks Cascade

**Проблема:** Пользователь нажал кнопку PDF дважды + начал нажимать другие кнопки

**Что произошло:**
```
16:15:47 - pdf_generate_current (request_id=30) → STARTED, зависает
16:15:52 - pdf_generate_current (request_id=31) → STARTED, зависает
16:16:13 - edit_cancel_expense (request_id=32) → STARTED, зависает
...
16:21:29 - ВСЕ ТАЙМАУТЯТСЯ ОДНОВРЕМЕННО → каскад из 15+ ошибок
```

**Ошибки:**
```
ERROR: Telegram server says - Bad Request: query is too old and response timeout expired
ERROR: Telegram server says - Bad Request: message is not modified
```

**Security alert:**
```
WARNING security: SECURITY_EVENT: burst_activity_detected
```

---

### 4. 📧 Admin Notifier Markdown Escaping (КРИТИЧНО)

**Проблема:** Невозможность отправки уведомлений админу об ошибках

**Файл:** Предположительно `bot/utils/admin_notifier.py` или похожий

**Ошибка:**
```
ERROR admin_notifier: Ошибка при отправке в Telegram:
    Telegram API error: Bad Request: can't parse entities:
    Character '-' is reserved and must be escaped with the preceding '\'
```

**Попытки отправки:** 10+ раз, все упали

**Детали:**
- `chat_id`: 881292737 (админ)
- `message_length`: 666-676 символов
- `parse_mode`: вероятно `MarkdownV2`

**Проблема:**
В MarkdownV2 следующие символы ОБЯЗАТЕЛЬНО экранировать:
```
_ * [ ] ( ) ~ ` > # + - = | { } . !
```

**Пример неправильного кода:**
```python
# ❌ НЕПРАВИЛЬНО:
message = f"Error at {timestamp}\nUser: {user_id} - Status: failed"
await bot.send_message(chat_id=admin_id, text=message, parse_mode="MarkdownV2")
```

**Правильный код:**
```python
# ✅ ПРАВИЛЬНО:
from telegram.helpers import escape_markdown

message = f"Error at {timestamp}\\nUser: {user_id} \\- Status: failed"
# ИЛИ:
message = escape_markdown(f"Error at {timestamp}\nUser: {user_id} - Status: failed", version=2)
await bot.send_message(chat_id=admin_id, text=message, parse_mode="MarkdownV2")
```

**Последствия:**
- ❌ Админ НЕ получил уведомления об ошибках
- ❌ Ошибки остались незамеченными
- ❌ Мониторинг не работает

---

## ⚠️ КРИТИЧЕСКАЯ ПРОБЛЕМА: Блокирующая генерация PDF

### Почему другие запросы не обрабатывались?

**Ответ:** PDF генерируется **синхронно с блокировкой handler'а**, а не асинхронно в фоне!

**Файл:** `bot/routers/pdf_report.py:93`

**Текущий код:**
```python
@router.callback_query(lambda c: c.data.startswith("pdf_report_"))
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """Обработка запроса на генерацию отчета"""
    await callback.answer()

    # Отправляем сообщение о начале генерации
    progress_msg = await callback.message.edit_text('Генерирую отчет...')

    try:
        # ❌ ПРОБЛЕМА: Блокирующий await на 6 минут!
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=callback.from_user.id,
            year=year,
            month=month,
            lang=lang
        )
        # ... handler блокируется пока PDF не сгенерируется
```

### Почему это проблема:

1. **Handler блокируется на `await pdf_service.generate_monthly_report()`**
   - Выполнение handler'а останавливается на строке 93
   - Ждет пока PDF полностью сгенерируется (в данном случае 6 минут!)
   - Только после этого продолжает работу

2. **Aiogram обрабатывает updates последовательно (по умолчанию)**
   - По умолчанию aiogram 3.x обрабатывает updates один за другим
   - Следующие updates от пользователя попадают в очередь
   - Очередь "замораживается" пока первый handler не завершится

3. **Нет параллельной обработки для одного пользователя**
   - Файл: `bot/main.py:162`
   - Dispatcher создается без специальной стратегии:
   ```python
   dp = Dispatcher(storage=storage)  # Нет FSMStrategy или параллельной обработки
   ```

4. **Результат:**
   ```
   16:15:47 - PDF handler START → блокируется на 6 минут
   16:15:52 - edit_cancel callback → ждет в очереди
   16:16:13 - edit_expense callback → ждет в очереди
   ...все ждут...
   16:21:30 - PDF handler TIMEOUT → очередь разблокируется
   16:21:30 - ВСЕ накопившиеся callbacks обрабатываются ОДНОВРЕМЕННО → каскад ошибок
   ```

### Подтверждение из логов:

```
16:15:47 - Request #30 started (pdf_generate_current)
16:21:30 - Request #30 finished (Duration: 338492ms = 5.6 минут!)
16:21:29 - Request #31 finished (Duration: 345121ms = 5.75 минут!)
16:21:29 - Request #32 finished (Duration: 164005ms = 2.7 минуты!)
```

Все запросы завершились **одновременно** когда первый handler разблокировался.

### Почему Celery не используется?

**Проверка текущего кода:**
- `bot/routers/pdf_report.py:93` - генерация вызывается **напрямую с await**
- **НЕТ** вызова Celery task
- **НЕТ** `asyncio.create_task()` для фоновой генерации

**Вывод:** PDF генерируется **полностью синхронно** в контексте webhook handler'а.

---

## 📊 Статистика инцидента

| Метрика | Значение |
|---------|----------|
| Длительность инцидента | 5 минут 46 секунд |
| Время обработки request #30 | 338.44 секунды |
| Время обработки request #34 | 315.55 секунды |
| Количество duplicate callbacks | 15+ |
| Количество ошибок | 37+ |
| Попытки отправки admin alerts | 10+ |
| Успешных admin alerts | 0 |

---

## 💡 Решения

### ✅ Решение 1: Исправить PDF timeout (ПРИОРИТЕТ 1)

**Вариант A: Не зависеть от networkidle (РЕКОМЕНДУЕТСЯ)**

```python
async def _html_to_pdf(self, html_content: str) -> bytes:
    """Конвертация HTML в PDF используя Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2
        )

        # ✅ Используем domcontentloaded вместо networkidle
        await page.set_content(html_content, wait_until='domcontentloaded', timeout=15000)

        # ✅ Явно ждем загрузки Chart.js с timeout
        try:
            await page.wait_for_function(
                "typeof Chart !== 'undefined'",
                timeout=10000
            )
        except PlaywrightTimeoutError:
            logger.warning("Chart.js not loaded from CDN, PDF may not have charts")

        # Ждем отрисовки графиков
        await page.wait_for_timeout(2000)

        pdf_bytes = await page.pdf(
            format='A4',
            print_background=True,
            margin={'top': '10px', 'bottom': '10px', 'left': '15px', 'right': '15px'},
            scale=0.95
        )

        await browser.close()
        return pdf_bytes
```

**Вариант B: Использовать локальный Chart.js (ЛУЧШИЙ, но требует времени)**

1. Скачать Chart.js локально в `reports/templates/static/chart.min.js`
2. Встроить в HTML как inline script или загружать локально
3. Не зависеть от внешних CDN

```html
<!-- ВМЕСТО: -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- ИСПОЛЬЗОВАТЬ: -->
<script>
{{ chart_js_code }}  <!-- Встроенный Chart.js код -->
</script>
```

**Вариант C: Увеличить timeout (БЫСТРО, но не решает проблему)**

```python
await page.set_content(html_content, wait_until='networkidle', timeout=60000)  # 60 секунд
```

---

### ✅ Решение 2: Исправить Admin Notifier (ПРИОРИТЕТ 1)

**Файл:** Найти где отправляются admin уведомления

**Поиск:**
```bash
grep -r "admin_notifier\|ADMIN_TELEGRAM_ID" bot/
```

**Исправление:**

```python
from telegram.helpers import escape_markdown

async def send_admin_alert(message: str, parse_mode: str = "MarkdownV2"):
    """Отправить уведомление админу с правильным экранированием"""
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    if not admin_id:
        return

    try:
        # ✅ Экранируем спецсимволы для MarkdownV2
        if parse_mode == "MarkdownV2":
            escaped_message = escape_markdown(message, version=2)
        else:
            escaped_message = message

        await bot.send_message(
            chat_id=admin_id,
            text=escaped_message,
            parse_mode=parse_mode
        )
        logger.info(f"Admin alert sent successfully to {admin_id}")

    except Exception as e:
        logger.error(f"Failed to send admin alert: {e}")
        # ✅ Fallback: отправить без форматирования
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=None  # Без форматирования
            )
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
```

**ИЛИ проще - не использовать MarkdownV2:**

```python
# ✅ Использовать HTML вместо MarkdownV2
message = f"<b>Error</b>\nUser: {user_id} - Status: failed"
await bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
```

---

### ✅ Решение 3: Добавить защиту от duplicate callbacks (ПРИОРИТЕТ 2)

**Проблема:** Пользователь может нажать кнопку несколько раз

**Решение:** Добавить debounce/throttle для PDF генерации

```python
# Хранилище активных генераций
active_pdf_generations = {}

async def handle_pdf_generate(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    # ✅ Проверяем есть ли уже активная генерация
    if user_id in active_pdf_generations:
        await callback_query.answer(
            "PDF уже генерируется, пожалуйста подождите...",
            show_alert=True
        )
        return

    try:
        # Помечаем что генерация началась
        active_pdf_generations[user_id] = datetime.now()

        # Показываем индикатор загрузки
        await callback_query.message.edit_text("⏳ Генерирую PDF отчет...")

        # Генерируем PDF
        pdf_bytes = await pdf_generator.generate_monthly_report(user_id, year, month)

        if pdf_bytes:
            await callback_query.message.answer_document(
                BufferedInputFile(pdf_bytes, filename=f"report_{year}_{month}.pdf")
            )
        else:
            await callback_query.message.answer("❌ Не удалось создать отчет")

    finally:
        # ✅ Убираем флаг генерации
        active_pdf_generations.pop(user_id, None)
```

---

### ✅ Решение 4: Добавить мониторинг медленных запросов (ПРИОРИТЕТ 3)

**Текущий код уже есть:**
```python
WARNING logging_middleware: Slow request detected: type=callback_query, duration=338.44s
```

**Улучшение:** Добавить автоматическую отмену слишком долгих запросов

```python
import asyncio

async def handle_with_timeout(handler, timeout=30):
    """Обработчик с timeout"""
    try:
        await asyncio.wait_for(handler(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Handler timeout after {timeout}s")
        # Отправить пользователю сообщение
        await send_timeout_message(user_id)
        # Отправить админу alert
        await send_admin_alert(f"Handler timeout: {handler.__name__}")
```

---

### ✅ Решение 5: Перенести PDF генерацию в фоновую задачу (КРИТИЧНО, ПРИОРИТЕТ 1)

**Проблема:** PDF генерируется синхронно в webhook handler, блокируя обработку других запросов

**Решение A: Использовать Celery (РЕКОМЕНДУЕТСЯ для production)**

**Шаг 1: Создать Celery task**

Файл: `bot/tasks/pdf_tasks.py` (создать новый)
```python
from celery import shared_task
from bot.services.pdf_report import PDFReportService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_pdf_report_task(self, user_id: int, year: int, month: int, lang: str = 'ru'):
    """Фоновая генерация PDF отчета"""
    try:
        pdf_service = PDFReportService()
        # Обратите внимание: здесь sync версия, нужно будет адаптировать
        pdf_bytes = pdf_service.generate_monthly_report_sync(user_id, year, month, lang)

        if pdf_bytes:
            # Сохранить во временный файл или отправить через webhook callback
            return {
                'status': 'success',
                'user_id': user_id,
                'filename': f"report_{year}_{month}.pdf"
            }
        else:
            return {'status': 'error', 'message': 'No data for report'}

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        # Повторить попытку через 60 секунд
        raise self.retry(exc=e, countdown=60)
```

**Шаг 2: Изменить router handler**

Файл: `bot/routers/pdf_report.py:74-98`
```python
@router.callback_query(lambda c: c.data.startswith("pdf_report_"))
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """Обработка запроса на генерацию отчета"""
    await callback.answer()

    # Парсим год и месяц
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])

    lang = await get_user_language(callback.from_user.id)
    user_id = callback.from_user.id

    # ✅ Запускаем Celery task в фоне
    from bot.tasks.pdf_tasks import generate_pdf_report_task

    task = generate_pdf_report_task.delay(user_id, year, month, lang)

    # Отправляем сообщение что задача запущена
    await callback.message.edit_text(
        get_text('pdf_generation_started', lang) +
        f"\n\nЭто может занять 1-2 минуты. Я пришлю отчет когда он будет готов."
    )

    # ✅ Handler завершается НЕМЕДЛЕННО, не блокируя другие запросы
    # PDF будет сгенерирован в фоне и отправлен через callback
```

**Шаг 3: Добавить callback для отправки готового PDF**

```python
# В Celery task после успешной генерации:
from aiogram import Bot

async def send_pdf_to_user(user_id: int, pdf_bytes: bytes, filename: str):
    """Отправить готовый PDF пользователю"""
    bot = Bot(token=os.getenv('BOT_TOKEN'))

    try:
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)
        await bot.send_document(
            chat_id=user_id,
            document=pdf_file,
            caption="📊 Ваш отчет готов!"
        )
    finally:
        await bot.session.close()
```

**Решение B: Использовать asyncio.create_task() (БЫСТРОЕ, но менее надежное)**

```python
@router.callback_query(lambda c: c.data.startswith("pdf_report_"))
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """Обработка запроса на генерацию отчета"""
    await callback.answer()

    # Парсим параметры
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    lang = await get_user_language(callback.from_user.id)

    # Отправляем сообщение о начале
    progress_msg = await callback.message.edit_text(
        "⏳ Генерирую отчет... Это может занять 1-2 минуты."
    )

    # ✅ Создаем фоновую задачу (НЕ блокирует handler)
    asyncio.create_task(
        generate_and_send_pdf(
            callback.from_user.id,
            callback.message.chat.id,
            year,
            month,
            lang,
            progress_msg.message_id
        )
    )

    # ✅ Handler завершается НЕМЕДЛЕННО

async def generate_and_send_pdf(user_id, chat_id, year, month, lang, progress_msg_id):
    """Фоновая генерация и отправка PDF"""
    try:
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(user_id, year, month, lang)

        if pdf_bytes:
            # Формируем имя файла
            months = get_month_names(lang)
            filename = f"Отчет_Coins_{months[month-1]}_{year}.pdf"

            # Отправляем PDF
            pdf_file = BufferedInputFile(pdf_bytes, filename=filename)
            bot = Bot(token=os.getenv('BOT_TOKEN'))

            await bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                caption=f"📊 Отчет за {months[month-1]} {year}"
            )

            # Удаляем сообщение о прогрессе
            await bot.delete_message(chat_id, progress_msg_id)
            await bot.session.close()
        else:
            # Обновляем сообщение об ошибке
            bot = Bot(token=os.getenv('BOT_TOKEN'))
            await bot.edit_message_text(
                "❌ Нет данных для отчета",
                chat_id,
                progress_msg_id
            )
            await bot.session.close()

    except Exception as e:
        logger.error(f"Background PDF generation failed: {e}")
        # Уведомляем пользователя об ошибке
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        await bot.edit_message_text(
            "❌ Не удалось создать отчет. Попробуйте позже.",
            chat_id,
            progress_msg_id
        )
        await bot.session.close()
```

**Преимущества Celery (Решение A):**
- ✅ Надежность - если задача упала, можно повторить
- ✅ Масштабируемость - можно запустить несколько воркеров
- ✅ Мониторинг - Flower для отслеживания задач
- ✅ Приоритеты - можно настроить очереди

**Преимущества asyncio.create_task (Решение B):**
- ✅ Быстрая реализация - 15 минут кода
- ✅ Не требует дополнительной инфраструктуры
- ✅ Простота отладки
- ❌ Нет retry при ошибках
- ❌ Задачи теряются при перезапуске бота

**Рекомендация:** Использовать **Решение A (Celery)** для production, **Решение B (create_task)** для быстрого hotfix.

---

### ✅ Решение 6: Per-user lock для предотвращения дубликатов

**Проблема:** Пользователь может нажать кнопку PDF несколько раз, создавая множество параллельных генераций

**Приоритет:** 🔴 КРИТИЧНО (10 минут кода)

**Файл:** `bot/routers/pdf_report.py`

```python
from django.core.cache import cache

@router.callback_query(lambda c: c.data.startswith("pdf_report_"))
async def process_pdf_report_request(callback: types.CallbackQuery, state: FSMContext):
    """Обработка запроса на генерацию отчета"""
    await callback.answer()

    # Парсим параметры
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    # ✅ Проверяем lock
    lock_key = f"pdf_generation:{user_id}:{year}:{month}"
    if cache.get(lock_key):
        await callback.answer(
            "⏳ PDF уже генерируется для этого периода. Пожалуйста, подождите...",
            show_alert=True
        )
        return

    # ✅ Устанавливаем lock на 5 минут
    cache.set(lock_key, True, timeout=300)

    try:
        # Отправляем сообщение о начале
        progress_msg = await callback.message.edit_text(
            "⏳ Генерирую отчет... Это может занять 1-2 минуты."
        )

        # Создаем фоновую задачу
        asyncio.create_task(
            generate_and_send_pdf(
                user_id, callback.message.chat.id, year, month, lang,
                progress_msg.message_id, lock_key  # ← Передаем lock_key
            )
        )
    except Exception as e:
        # ✅ Снимаем lock при ошибке
        cache.delete(lock_key)
        raise

async def generate_and_send_pdf(user_id, chat_id, year, month, lang, progress_msg_id, lock_key):
    """Фоновая генерация с автоматическим снятием lock"""
    try:
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(user_id, year, month, lang)

        # ... отправка PDF

    except Exception as e:
        logger.error(f"Background PDF generation failed: {e}")
        # ... обработка ошибки

    finally:
        # ✅ ВСЕГДА снимаем lock
        cache.delete(lock_key)
        logger.info(f"Released PDF lock for user {user_id}, {year}/{month}")
```

**Преимущества:**
- ✅ Предотвращает дубликаты генерации
- ✅ Информирует пользователя что процесс уже идет
- ✅ Автоматически снимает lock через 5 минут даже при зависании
- ✅ Работает с Redis (уже есть в проекте)

---

### ✅ Решение 7: HTML вместо MarkdownV2

**Проблема:** MarkdownV2 требует экранирования 14 символов: `_ * [ ] ( ) ~ \` > # + - = | { } . !`

**Особенно проблемно:** Даты формата `YYYY-MM-DD` содержат `-` который не экранируется

**Приоритет:** 🔴 КРИТИЧНО (15 минут кода)

**Файл:** `bot/services/admin_notifier.py`

```python
import html
from typing import Optional

async def send_admin_alert(
    message: str,
    disable_notification: bool = False,
    parse_mode: str = "HTML"  # ← Изменено с MarkdownV2 на HTML
):
    """
    Отправить алерт администратору

    Args:
        message: Текст сообщения (НЕ требует экранирования, автоматически)
        disable_notification: Отправить без звука
        parse_mode: HTML (по умолчанию) или None
    """
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')
    if not admin_id:
        logger.warning("ADMIN_TELEGRAM_ID not set, cannot send admin alert")
        return

    monitoring_token = os.getenv('MONITORING_BOT_TOKEN') or os.getenv('BOT_TOKEN')
    if not monitoring_token:
        logger.error("No bot token available for admin notifications")
        return

    admin_notifier = AdminNotifier(monitoring_token)

    try:
        # ✅ Экранируем HTML автоматически (безопасно)
        if parse_mode == "HTML":
            escaped_message = html.escape(message)
        else:
            escaped_message = message

        await admin_notifier.send_message(
            chat_id=int(admin_id),
            text=escaped_message,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
        logger.info(f"Admin alert sent successfully to {admin_id}")

    except Exception as e:
        logger.error(f"Failed to send admin alert: {e}")

        # ✅ Fallback: отправить без форматирования
        try:
            await admin_notifier.send_message(
                chat_id=int(admin_id),
                text=message,  # Оригинальный текст без экранирования
                parse_mode=None,
                disable_notification=disable_notification
            )
            logger.info("Admin alert sent without formatting (fallback)")
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}")
```

**Использование (теперь проще):**

```python
# ❌ Старый способ (MarkdownV2):
from bot.services.admin_notifier import escape_markdown_v2
message = f"User {escape_markdown_v2(user_id)} failed at {escape_markdown_v2(timestamp)}"

# ✅ Новый способ (HTML):
message = f"<b>Error</b>\nUser: {user_id}\nDate: {date}\nStatus: failed"
await send_admin_alert(message)  # Автоматическое экранирование внутри
```

**Преимущества HTML:**
- ✅ Проще - `html.escape()` экранирует только `< > & " '`
- ✅ Меньше ошибок - не нужно помнить 14 символов
- ✅ Читабельнее - `<b>текст</b>` вместо `*текст*`
- ✅ Безопаснее - автоматическое экранирование
- ✅ **Даты работают сразу** - `2026-01-24` не требует экранирования

---

### ✅ Решение 8: Pre-render графиков на сервере

**Проблема:** Chart.js требует загрузки с CDN, что может быть медленным

**Приоритет:** 🟡 Средний (2-3 часа, альтернатива локальному Chart.js)

**Решение: Генерировать графики на сервере через matplotlib**

**Файл:** `bot/services/pdf_report.py` (добавить методы)

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Без GUI
from io import BytesIO
import base64

class PDFReportService:

    def _generate_pie_chart_image(self, data: Dict[str, float], colors: List[str]) -> str:
        """Генерирует круговую диаграмму как base64 PNG"""
        fig, ax = plt.subplots(figsize=(6, 6))

        labels = list(data.keys())
        values = list(data.values())

        ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90
        )
        ax.axis('equal')

        # Сохраняем в BytesIO
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)

        # Конвертируем в base64
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')

        return f'data:image/png;base64,{img_base64}'

    async def _render_html(self, report_data: Dict, lang: str) -> str:
        """Рендерит HTML с встроенными графиками"""
        # Генерируем графики как base64 PNG
        pie_chart = self._generate_pie_chart_image(
            report_data['category_data'],
            self.CATEGORY_COLORS
        )

        # В шаблоне используем <img> вместо <canvas>
        html_content = self.template.render(
            **report_data,
            pie_chart_img=pie_chart,  # ← Base64 PNG
            use_chart_js=False  # ← Отключаем Chart.js
        )

        return html_content
```

**В HTML шаблоне (`reports/templates/report_modern.html`):**

```html
<!-- ВМЕСТО Chart.js: -->
<!-- <canvas id="pieChart"></canvas> -->
<!-- <script src="https://cdn.jsdelivr.net/npm/chart.js"></script> -->

<!-- ИСПОЛЬЗУЕМ pre-rendered PNG: -->
{% if use_chart_js %}
    <!-- Старый вариант с Chart.js -->
    <canvas id="pieChart"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
{% else %}
    <!-- Новый вариант с matplotlib -->
    <img src="{{ pie_chart_img }}" alt="Категории" style="max-width: 100%;">
{% endif %}
```

**Преимущества:**
- ✅ Не зависит от CDN
- ✅ Быстрее - нет загрузки внешних ресурсов
- ✅ Надежнее - графики всегда работают
- ✅ Matplotlib - стандартная библиотека для Python
- ✅ Лучше для PDF - статичные изображения

**Недостатки:**
- ❌ Больше размер HTML (base64 увеличивает размер на ~33%)
- ❌ Требует matplotlib в requirements

---

### ✅ Решение 9: Метрики и наблюдаемость

**Проблема:** Нет видимости насколько часто и долго генерируются отчеты

**Приоритет:** 🟡 Средний (20 минут кода)

**Файл:** `bot/routers/pdf_report.py`

```python
import time
import logging

logger = logging.getLogger(__name__)

async def generate_and_send_pdf(user_id, chat_id, year, month, lang, progress_msg_id, lock_key):
    """Фоновая генерация с метриками"""
    start_time = time.time()

    try:
        pdf_service = PDFReportService()

        # ✅ Логируем начало
        logger.info(f"[PDF_START] user={user_id}, period={year}/{month}")

        pdf_bytes = await pdf_service.generate_monthly_report(user_id, year, month, lang)

        duration = time.time() - start_time

        # ✅ Логируем успех с длительностью
        logger.info(
            f"[PDF_SUCCESS] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, size={len(pdf_bytes) if pdf_bytes else 0}"
        )

        # ✅ Алерт если > 30 секунд
        if duration > 30:
            from bot.services.admin_notifier import send_admin_alert
            await send_admin_alert(
                f"⚠️ <b>Slow PDF generation</b>\n"
                f"User: {user_id}\n"
                f"Period: {year}/{month}\n"
                f"Duration: {duration:.2f}s\n"
                f"Size: {len(pdf_bytes) if pdf_bytes else 0} bytes",
                disable_notification=True
            )

        if pdf_bytes:
            # ... отправка PDF
            pass
        else:
            logger.warning(f"[PDF_NO_DATA] user={user_id}, period={year}/{month}")

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(f"[PDF_TIMEOUT] user={user_id}, period={year}/{month}, duration={duration:.2f}s")

        # ✅ Критический алерт
        await send_admin_alert(
            f"🔴 <b>PDF Timeout</b>\n"
            f"User: {user_id}\n"
            f"Period: {year}/{month}\n"
            f"Duration: {duration:.2f}s"
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[PDF_ERROR] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, error={str(e)}"
        )

    finally:
        cache.delete(lock_key)
```

**Анализ метрик:**

```bash
# Средняя длительность генерации PDF
grep "PDF_SUCCESS" logs/bot.log | awk -F'duration=' '{print $2}' | awk '{print $1}' | \
  awk '{sum+=$1; n++} END {print sum/n}'

# P95 (95-й перцентиль)
grep "PDF_SUCCESS" logs/bot.log | awk -F'duration=' '{print $2}' | awk '{print $1}' | \
  sort -n | awk 'NR==int(NR*0.95)'

# Количество timeout'ов за день
grep "PDF_TIMEOUT" logs/bot.log | grep "$(date +%Y-%m-%d)" | wc -l

# Топ пользователей по количеству генераций
grep "PDF_SUCCESS" logs/bot.log | awk -F'user=' '{print $2}' | awk '{print $1}' | \
  sort | uniq -c | sort -rn | head -10
```

---

### ✅ Решение 10: Обработка "message is not modified"

**Проблема:** Ошибка "message is not modified" засоряет логи, но не критична

**Приоритет:** 🟢 Низкий (15 минут кода, улучшение UX)

**Файл:** `bot/utils/message_utils.py` (создать новый)

```python
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def safe_edit_message(message: Message, text: str, **kwargs) -> Optional[Message]:
    """
    Безопасное редактирование сообщения с обработкой 'not modified'

    Args:
        message: Сообщение для редактирования
        text: Новый текст
        **kwargs: Дополнительные параметры (parse_mode, reply_markup, etc.)

    Returns:
        Отредактированное сообщение или оригинальное если не изменилось
    """
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        error_text = str(e).lower()
        if "message is not modified" in error_text:
            logger.debug(f"Message not modified (ignored): {text[:50]}...")
            return message  # Возвращаем оригинальное сообщение
        elif "message to edit not found" in error_text:
            logger.warning(f"Message to edit not found: {message.message_id}")
            return None
        else:
            raise  # Другие ошибки пробрасываем

async def safe_delete_message(bot, chat_id: int, message_id: int) -> bool:
    """
    Безопасное удаление сообщения

    Returns:
        True если удалено, False если уже было удалено
    """
    try:
        await bot.delete_message(chat_id, message_id)
        return True
    except TelegramBadRequest as e:
        error_text = str(e).lower()
        if "message to delete not found" in error_text:
            logger.debug(f"Message already deleted (ignored): {chat_id}/{message_id}")
            return False
        else:
            raise
```

**Использование:**

```python
# ❌ Старый способ:
await message.edit_text(new_text)  # Может упасть с "not modified"

# ✅ Новый способ:
from bot.utils.message_utils import safe_edit_message

await safe_edit_message(message, new_text, parse_mode="HTML")

# ✅ Для удаления:
from bot.utils.message_utils import safe_delete_message

await safe_delete_message(bot, chat_id, message_id)
```

---

## 📊 Сравнение подходов

### Admin Notifier: MarkdownV2 vs HTML

| Критерий | MarkdownV2 | HTML |
|----------|------------|------|
| Количество спецсимволов | 14 | 5 |
| Экранирование дат | Нужно (`2026\-01\-24`) | Не нужно (`2026-01-24`) |
| Читабельность | `*текст*` | `<b>текст</b>` |
| Частота ошибок | Высокая | Низкая |
| **Рекомендация** | ❌ Не использовать | ✅ **Использовать** |

### Графики: Chart.js vs Matplotlib

| Критерий | Chart.js (CDN) | Chart.js (локально) | Matplotlib (pre-render) |
|----------|----------------|---------------------|-------------------------|
| Зависимость от CDN | ❌ Да | ✅ Нет | ✅ Нет |
| Скорость генерации | ❌ Медленно | ✅ Быстро | ✅ Быстро |
| Размер HTML | ✅ Маленький | ✅ Маленький | ❌ Большой (+33%) |
| Интерактивность | ✅ Да | ✅ Да | ❌ Нет (статичные) |
| **Рекомендация** | ❌ | ✅ **Простое решение** | ✅ **Надежное решение** |

### PDF генерация: Синхронно vs Фон

| Критерий | Текущий способ | asyncio.create_task | Celery |
|----------|----------------|---------------------|--------|
| Блокирует handler | ❌ Да (6+ минут!) | ✅ Нет | ✅ Нет |
| Retry при ошибках | ❌ Нет | ❌ Нет | ✅ Да |
| Простота | ✅ Очень просто | ✅ Просто | ❌ Сложнее |
| Надежность | ❌ Низкая | 🟡 Средняя | ✅ Высокая |
| **Рекомендация** | ❌ УБРАТЬ СРОЧНО | ✅ **Hotfix** | ✅ **Production** |

---

## 🎯 План действий

### 🔴 КРИТИЧНО - Сегодня (1 час работы):
1. **Admin Notifier → HTML** - 15 минут (Решение 7)
2. **Per-user lock для PDF** - 10 минут (Решение 6)
3. **PDF Playwright timeout** - 15 минут (Решение 1)
4. **PDF в фон (asyncio.create_task)** - 20 минут (Решение 5B)

### 🟡 Важно - Эта неделя (3-4 часа):
5. **Timeout для CSV/XLSX** - 30 минут (Приложение)
6. **Метрики PDF** - 20 минут (Решение 9)
7. **safe_edit_message helper** - 15 минут (Решение 10)
8. **PDF в Celery** - 2-3 часа (Решение 5A)
9. **Chart.js локально** ИЛИ **Pre-render графики** - 1-3 часа (Решение 1B или Решение 8)

### 🟢 Опционально:
10. **Grafana dashboard** - мониторинг метрик
11. **Flower для Celery** - веб-интерфейс

---

## 📝 Выводы

### Критические уроки из инцидента:

1. **🔴 КРИТИЧНО: Долгие операции НЕЛЬЗЯ выполнять в webhook handler'е** - это блокирует обработку всех остальных запросов от пользователя. Используй Celery или asyncio.create_task() для фоновой обработки.

2. **CDN зависимость опасна** - внешние сервисы могут быть медленными/недоступными. Загружай критичные ресурсы (Chart.js, шрифты) локально или используй pre-rendering на сервере.

3. **Admin уведомления критичны** - markdown escaping ОБЯЗАТЕЛЕН. Лучше использовать HTML вместо MarkdownV2, или всегда экранировать спецсимволы. HTML требует экранирования только 5 символов вместо 14.

4. **Пользователи нетерпеливы** - если кнопка не отвечает 5 секунд, они нажмут еще раз. Нужна защита от duplicate callbacks через per-user locks и информативное сообщение "⏳ Обрабатываю...".

5. **Timeout'ы должны быть везде** - никогда не ждать бесконечно. Всегда указывай явные timeout для сетевых запросов, Playwright операций, и долгих вычислений.

6. **Fallback необходим** - если что-то упало, должен быть запасной вариант. Например, если Chart.js не загрузился, генерируй PDF без графиков.

7. **Мониторинг должен работать** - если admin alerter сломан, никто не узнает об ошибках в production. Тестируй уведомления отдельно.

8. **Метрики критичны** - без логирования длительности операций невозможно понять что работает медленно. Добавляй structured logging с метриками времени и размера.

9. **Дубликаты надо предотвращать** - per-user locks через Redis обязательны для долгих операций. Lock должен автоматически сниматься даже при зависании.

10. **MarkdownV2 сложнее чем кажется** - 14 спецсимволов требуют экранирования. HTML проще (5 символов) и безопаснее, особенно для дат формата `YYYY-MM-DD`.

### Быстрые победы (можно сделать за 1 час):
- ✅ Admin notifier → HTML (15 мин)
- ✅ Per-user lock (10 мин)
- ✅ PDF timeout fix (15 мин)
- ✅ PDF в фон hotfix (20 мин)

### Долгосрочные улучшения:
- 🔄 PDF → Celery (надежность)
- 🔄 Chart.js → локально или matplotlib (независимость от CDN)
- 🔄 Метрики → Grafana (наблюдаемость)

---

## 🔗 Связанные файлы

### ⚠️ Требуют немедленного исправления:
- `bot/services/pdf_report.py:742-768` - PDF генератор (wait_until='networkidle' БЕЗ timeout) - **Решение 1**
- `bot/routers/pdf_report.py:74-130` - PDF роутер (синхронная генерация, блокирует handler) - **Решения 5, 6**
- `bot/services/admin_notifier.py` - Admin уведомления (markdown escaping) - **Решение 7**

### 📋 Для анализа:
- `reports/templates/report_modern.html:6` - HTML шаблон с CDN Chart.js - **Решение 8**
- `bot/main.py:162` - Dispatcher без параллельной обработки
- `bot/middleware/rate_limit.py` - Rate limiting (работает корректно)
- `bot/middleware/logging_middleware.py` - Логирование медленных запросов (работает корректно)
- `bot/routers/reports.py` - CSV/XLSX генерация (требует timeout) - **Приложение**

### 🆕 Требуется создать:
- `bot/tasks/pdf_tasks.py` - Celery task для фоновой генерации PDF - **Решение 5A**
- `bot/utils/message_utils.py` - safe_edit_message и safe_delete_message - **Решение 10**
- `reports/templates/static/chart.min.js` - Локальная версия Chart.js - **Решение 1B** (опция)

### 🔧 Требуется модифицировать:
- `bot/routers/pdf_report.py` - добавить per-user lock и метрики - **Решения 6, 9**
- `bot/services/pdf_report.py` - добавить matplotlib рендеринг - **Решение 8** (опция)

---

**Дата создания документа:** 2026-01-24
**Автор:** Claude Code (автоматический анализ логов + дополнительные решения)
**Статус:** 🔴 Требует СРОЧНОГО исправления (4 критичных проблемы)

**Этот документ объединяет:**
- Первоначальный анализ инцидента (5 решений)
- Дополнительные решения на основе внешнего AI анализа (5 решений)
- Сравнительные таблицы подходов
- Обновленный план действий с приоритетами

**Следующие шаги (в порядке приоритета):**
1. ✅ Admin notifier → HTML (15 мин) - КРИТИЧНО
2. ✅ Per-user lock для PDF (10 мин) - КРИТИЧНО
3. ✅ PDF timeout fix domcontentloaded (15 мин) - КРИТИЧНО
4. ✅ PDF в фон asyncio.create_task (20 мин) - КРИТИЧНО
5. ⏰ Timeout для CSV/XLSX (30 мин)
6. ⏰ Метрики и логирование (20 мин)
7. ⏰ safe_edit_message helper (15 мин)
8. ⏰ PDF в Celery для production (2-3 часа)
9. ⏰ Chart.js локально ИЛИ matplotlib (1-3 часа)
10. 🟢 Grafana + Flower (опционально)

---

## 📎 Приложение: Другие типы отчетов

### CSV/XLSX генерация - анализ

**Файл:** `bot/routers/reports.py`

**Найденные handler'ы генерации отчетов:**

1. **CSV отчеты:**
   - `callback_export_csv()` - строка 907: `await generate_csv_file()`
   - `callback_monthly_report_csv()` - строка 1151: `await generate_csv_file()`

2. **XLSX отчеты:**
   - `callback_export_xlsx()` - строка 1044: `await generate_xlsx_file()`
   - `callback_monthly_report_xlsx()` - строка 1258: `await generate_xlsx_file()`

3. **PDF отчеты из monthly report:**
   - `callback_monthly_report_pdf()` - строка 1309: `await pdf_service.generate_monthly_report()`

### ⚠️ Проблема: Нет timeout защиты!

**Все handler'ы выполняют генерацию БЕЗ timeout:**
```python
# ❌ Нет защиты от зависания:
csv_bytes = await generate_csv_file()  # Может зависнуть навсегда
xlsx_buffer = await generate_xlsx_file()  # Может зависнуть навсегда
pdf_bytes = await pdf_service.generate_monthly_report(...)  # Может зависнуть
```

### 💡 Рекомендация: Добавить timeout для всех отчетов

**Даже если CSV/XLSX обычно генерируются быстро (1-3 секунды), нужна защита:**

```python
import asyncio

# ✅ С timeout защитой:
try:
    csv_bytes = await asyncio.wait_for(
        generate_csv_file(),
        timeout=10.0  # 10 секунд максимум
    )
except asyncio.TimeoutError:
    await callback.message.answer("❌ Не удалось создать отчет: превышено время ожидания")
    logger.error(f"CSV generation timeout for user {user_id}")
    return
```

**Рекомендуемые timeout'ы:**
- CSV: 10 секунд (обычно < 1 секунды)
- XLSX: 30 секунд (обычно 1-3 секунды, но есть графики)
- PDF: 60 секунд (обычно 5-10 секунд, но может быть медленным)

### Почему не выносим CSV/XLSX в фоновые задачи?

**Причины оставить CSV/XLSX синхронными (с timeout):**
1. ✅ Быстрая генерация (< 3 секунд обычно)
2. ✅ Простой код - легче отлаживать
3. ✅ Не требует дополнительной инфраструктуры
4. ✅ Пользователь получает файл сразу

**Но ОБЯЗАТЕЛЬНО добавить:**
- Timeout защиту (10-30 секунд)
- Логирование медленных генераций
- Graceful error handling

**PDF в фон ОБЯЗАТЕЛЬНО потому что:**
- ❌ Медленная генерация (5-10 секунд минимум)
- ❌ Зависит от внешних ресурсов (CDN)
- ❌ Может зависнуть на 6+ минут (как было)
- ❌ Блокирует обработку других запросов

### Пример универсального wrapper'а с timeout:

```python
async def with_timeout(coro, timeout: float, error_message: str):
    """Универсальный wrapper для выполнения с timeout"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Operation timeout: {error_message}")
        raise TimeoutError(error_message)

# Использование:
csv_bytes = await with_timeout(
    generate_csv_file(),
    timeout=10.0,
    error_message=f"CSV generation for user {user_id}, {year}/{month}"
)
```
