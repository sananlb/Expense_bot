# План перехода на AsyncOpenAI + async SOCKS

## Краткий анализ текущей реализации
- Есть минимум два сервиса с AI-вызовами: `bot/services/unified_ai_service.py` (DeepSeek/Qwen/OpenRouter) и `bot/services/openai_service.py` (прямые вызовы OpenAI).
- Центральная точка вызовов в unified сервисе - `_make_api_call_with_proxy_fallback()`, сейчас используется `asyncio.to_thread(...)`, что удерживает потоки на время сетевых запросов.
- Прокси используется только для OpenRouter через `httpx.Client(proxies=...)` в `_initialize_proxy_client()`.
- Логика fallback на прямое соединение завязана на `_is_proxy_error()` и `_get_client(use_proxy=...)`.
- Клиенты создаются синхронно и передаются через `http_client` (sync); в openai_service.py есть пул клиентов на уровне модуля.

## Цель перехода
- Уйти от `to_thread` на чистый `await` сетевых запросов.
- Сохранить текущее поведение прокси и fallback (proxy -> direct).
- Сохранить контроль таймаутов и журналирование метрик.

## План перехода

### 1. Подготовка и зависимости
- Добавить зависимость `httpx-socks` (для async SOCKS).
- Проверить совместимость текущих версий `openai` и `httpx` в `requirements.txt`.

### 2. Асинхронные http-клиенты
- В `UnifiedAIService` заменить `httpx.Client` на `httpx.AsyncClient`.
- Для SOCKS использовать `httpx_socks.AsyncProxyTransport.from_url(proxy_url)`.
- Ввести асинхронный метод закрытия клиента `async def aclose()` и вызывать его при завершении приложения.
- Удалить/минимизировать `__del__` или оставить его безопасным, но основной путь - явное `aclose()`.

### 3. Перевод OpenAI клиента на async
- Заменить `from openai import OpenAI` на `from openai import AsyncOpenAI`.
- В `_get_client()` возвращать `AsyncOpenAI` вместо `OpenAI`.
- Передавать `http_client=httpx.AsyncClient(...)`.

### 4. Удаление to_thread для AI-запросов
- В `_make_api_call_with_proxy_fallback()` заменить:
  - `await asyncio.to_thread(create_call, client)` на `await create_call(client)`
- Убедиться, что `create_call` возвращает awaitable (async вызов SDK).
- Перевести `create_call` на `async def` там, где он вызывается через `await create_call(...)`.

### 5. Проверка логики fallback
- Убедиться, что proxy-клиент используется только при `OPENROUTER_CONNECTION_MODE=proxy`.
- При ошибке прокси - повторить через direct клиент (без proxy transport), как сейчас.

### 6. Миграция openai_service.py
- Заменить пул `OPENAI_CLIENTS` с sync клиентов на `AsyncOpenAI` либо перейти на lazy initialization.
- Убрать `asyncio.to_thread()` из методов, которые дергают OpenAI напрямую.
- Проверить, что нигде не остались sync клиенты или sync `httpx.Client`.

### 7. Жизненный цикл клиентов
- Добавить `async def aclose()` (или `close()`) для закрытия `httpx.AsyncClient`.
- Обеспечить вызов при shutdown бота (startup/shutdown хук или signal handler).
- Не полагаться на `__del__` для async ресурсов.

### 8. Тестирование и валидация
- Проверить:
  - прямой режим (`OPENROUTER_CONNECTION_MODE=direct`)
  - прокси режим (`OPENROUTER_CONNECTION_MODE=proxy` + `AI_PROXY_URL`)
  - fallback при искусственной ошибке прокси
- Проверить, что `openai_service.py` работает без `to_thread` и с async клиентами.
- Измерить p95/p99 по времени ответа и сравнить с текущим.

## Оценка рисков
- Риск нестабильности `httpx-socks` с нестандартными прокси.
- Риск утечек соединений при забытом `aclose()`.
- Возможные отличия в обработке ошибок/таймаутов между sync и async клиентами.

## Ожидаемый результат
- Устранение блокировки потоков на сетевых вызовах.
- Более стабильная работа под высокой конкуренцией AI-запросов.
- Сохранение текущего поведения proxy-fallback.
