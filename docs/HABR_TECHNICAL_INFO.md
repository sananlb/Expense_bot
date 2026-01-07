# Техническая информация для статьи на Хабр

## 1. Стек и Инфраструктура

### Язык программирования
**Python 3.11** (указано в Dockerfile)

### Библиотека для Telegram
**aiogram 3.13.1** — современный асинхронный фреймворк для Telegram Bot API.

Почему aiogram 3.x, а не python-telegram-bot:
- Полностью асинхронный (async/await)
- Встроенная поддержка FSM (Finite State Machine) для диалогов
- Middleware система для обработки сообщений
- Роутеры для организации кода

### База данных
**PostgreSQL 15** (Alpine) в production, SQLite для локальной разработки.

**ORM:** Django ORM (Django 5.1.14) — не SQLAlchemy, не голый SQL.

Почему Django ORM:
- Миграции из коробки
- Админ-панель бесплатно
- Отличная интеграция с Celery

### Хостинг
**VPS сервер** (Ubuntu 22.04) с полной контейнеризацией через **Docker Compose**.

Архитектура контейнеров:
```
+-------------------------------------------------------------+
|                    Docker Compose                           |
+----------+----------+----------+----------+-----------------+
|   bot    |   web    |  celery  |  celery  |       db        |
| (aiogram)| (Django) | (worker) |  (beat)  |   (Postgres)    |
|  :8001   |  :8000   |          |          |     :5432       |
+----------+----------+----------+----------+-----------------+
|                                           |      redis      |
|              Общая сеть Docker            |      :6379      |
+-------------------------------------------+-----------------+
```

### Кэширование
**Redis 7** используется для:
1. **Message Broker для Celery** — очередь фоновых задач
2. **Result Backend** — хранение результатов задач
3. **Django Cache** — кэширование запросов
4. **FSM Storage** — хранение состояний диалогов пользователей

---

## 2. Алгоритм «Каскада»

### Уровень 1: Личный словарь пользователя

**Как реализован:** Отдельная таблица в БД `CategoryKeyword` с foreign key на категорию.

```python
# expenses/models.py
class CategoryKeyword(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    keyword = models.CharField(max_length=100)
    language = models.CharField(max_length=10, default='ru')
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('category', 'keyword', 'language')  # Уникальность на уровне БД
```

**Важно:** Уникальность `(category, keyword, language)` — на уровне БД. Глобальную уникальность (одно слово = одна категория у пользователя) обеспечивают служебные функции при добавлении/обучении, не constraint.

**Как ищется совпадение:**
```python
# bot/utils/expense_parser.py (упрощенно)
async def find_category_by_keywords(text: str, profile) -> Optional[str]:
    text_lower = text.lower()

    categories = ExpenseCategory.objects.filter(
        profile=profile
    ).prefetch_related('keywords')

    for category in categories:
        for kw in category.keywords.all():
            # Проверяем вхождение как целого слова (не подстроки)
            if keyword_matches_in_text(kw.keyword, text_lower):
                kw.usage_count += 1
                kw.save(update_fields=['usage_count', 'last_used'])
                return category.get_display_name()

    return None
```

### Уровень 2: Базовый словарь (EXPENSE_CATEGORY_DEFINITIONS)

**Реализация:** Python словарь в `bot/utils/expense_category_definitions.py` с ~300 строками определений.

```python
# bot/utils/expense_category_definitions.py
EXPENSE_CATEGORY_DEFINITIONS: Dict[str, Dict[str, object]] = {
    'groceries': {
        'name_ru': 'Продукты',
        'name_en': 'Groceries',
        'keywords': [
            # Русские магазины и бренды
            'магнит', 'пятерочка', 'перекресток', 'ашан', 'лента', 'дикси',
            'вкусвилл', 'продукты', 'супермаркет', 'овощи', 'фрукты', 'мясо',
            'молоко', 'хлеб', 'яйца', 'масло', 'сахар',
            # Английские
            'groceries', 'supermarket', 'walmart', 'costco', 'whole foods',
        ],
        'aliases': ['продукты', 'groceries', 'еда', 'food'],
    },
    'cafes_restaurants': {
        'name_ru': 'Кафе и рестораны',
        'name_en': 'Cafes and Restaurants',
        'keywords': [
            'ресторан', 'кафе', 'бар', 'кофейня', 'пиццерия', 'суши',
            'обед', 'ужин', 'кофе', 'капучино', 'латте', 'бургер',
            'mcdonalds', 'kfc', 'starbucks', 'burger king',
        ],
    },
    # ... ещё 15+ категорий
}

DEFAULT_EXPENSE_CATEGORY_KEY = 'other'
```

**Функция поиска категории:**
```python
# bot/utils/expense_category_definitions.py
def detect_expense_category_key(text: str) -> Optional[str]:
    """Detect a category key by checking keywords against the text."""
    best_key = None
    best_score = 0

    for key, data in EXPENSE_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_EXPENSE_CATEGORY_KEY:
            continue

        score = 0
        for keyword in data.get('keywords', []):
            # Проверка целого слова, не подстроки
            if _keyword_matches_in_text(keyword, text):
                score += 1

        if score > best_score:
            best_score = score
            best_key = key

    return best_key
```

**Особенность:** Функция `_keyword_matches_in_text` учитывает русские склонения — если слово начинается с ключевого и окончание <= 2 символа, считается совпадением ("продуктов" -> "продукт").

### Логика переключения между уровнями

```python
# bot/utils/expense_parser.py — упрощенная логика
async def parse_expense_message(text: str, user_id: int, use_ai: bool = True):
    amount = extract_amount(text)
    if not amount:
        return None

    category = None
    ai_categorized = False

    # === УРОВЕНЬ 1: Личный словарь ===
    category = await find_category_by_keywords(text, profile)

    # === УРОВЕНЬ 2: Базовый словарь ===
    if not category:
        category_key = detect_expense_category_key(text)
        if category_key:
            category = get_category_by_key(category_key, profile.language)

    # === УРОВЕНЬ 3: AI категоризация ===
    if not category and use_ai:
        # Собираем контекст: последние 3 использованные категории
        recent_categories = get_recent_categories(profile, limit=3)
        user_context = {'recent_categories': recent_categories}

        ai_service = AISelector('categorization')
        result = await ai_service.categorize_expense(
            text=text,
            categories=get_user_categories(profile),
            user_context=user_context  # <-- Контекст передается!
        )
        if result:
            category = result['category']
            ai_categorized = True

    # === УРОВЕНЬ 4: Fallback ===
    if not category:
        category = "Прочие расходы"

    return {
        'amount': amount,
        'category': category,
        'ai_categorized': ai_categorized
    }
```

### Скорость (эмпирические оценки)

| Этап | Время | Комментарий |
|------|-------|-------------|
| Личный словарь | ~5-15 мс | Запрос в БД с индексом |
| Базовый словарь | ~1-2 мс | In-memory поиск |
| AI (DeepSeek) | 300-800 мс | Зависит от нагрузки API |
| AI (GPT-4o-mini) | 500-1500 мс | Дороже и медленнее |

**Примечание:** Замеры эмпирические, бенчмарков в коде нет.

---

## 3. Работа с AI

### Используемые модели

**OpenAI НЕ используется!** Ключи закомментированы. Вместо этого:

| Задача | Провайдер | Модель | Fallback |
|--------|-----------|--------|----------|
| Категоризация | **DeepSeek** | `deepseek-chat` | OpenRouter |
| Чат | **OpenRouter** | `google/gemini-3-flash-preview` | OpenRouter |
| Insights | **DeepSeek** | `deepseek-reasoner` | OpenRouter |
| Голос | **OpenRouter** | `google/gemini-3-flash-preview` | - |

**Gemini используется через OpenRouter**, не напрямую — так проще с биллингом и нет проблем с российскими картами.

**Конфигурация в `.env`:**
```bash
# Primary провайдеры
AI_PROVIDER_CATEGORIZATION=deepseek
AI_PROVIDER_CHAT=openrouter
AI_PROVIDER_INSIGHTS=deepseek

# Fallback — везде OpenRouter
AI_FALLBACK_CATEGORIZATION=openrouter
AI_FALLBACK_CHAT=openrouter
AI_FALLBACK_INSIGHTS=openrouter

# Модели DeepSeek
DEEPSEEK_MODEL_CATEGORIZATION=deepseek-chat
DEEPSEEK_MODEL_INSIGHTS=deepseek-reasoner

# Модели через OpenRouter (Gemini)
OPENROUTER_MODEL_CHAT=google/gemini-3-flash-preview
OPENROUTER_MODEL_VOICE=google/gemini-3-flash-preview
OPENROUTER_MODEL_INSIGHTS=google/gemini-3-pro-preview

# Прокси для OpenRouter (обход блокировок)
AI_PROXY_URL=socks5://...
OPENROUTER_CONNECTION_MODE=proxy
```

**Важно:** При категоризации берется только ПЕРВЫЙ fallback из цепочки, иначе ожидание 30+ сек.

### Библиотека
**openai** (официальная, **AsyncOpenAI**) — DeepSeek и OpenRouter используют OpenAI-совместимый API, поэтому один SDK работает со всеми. Используется **асинхронный клиент** для неблокирующих вызовов.

```python
from openai import AsyncOpenAI

# DeepSeek через AsyncOpenAI SDK
client_deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# OpenRouter (Gemini) через тот же SDK
client_openrouter = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)
```

**Почему OpenRouter, а не Gemini напрямую:**
- Единый биллинг для разных моделей
- Нет проблем с российскими картами
- OpenAI-совместимый API (не нужен отдельный SDK)

### Системный промпт для категоризации (РЕАЛЬНЫЙ)

```python
# bot/services/ai_base_service.py — метод get_expense_categorization_prompt()
def get_expense_categorization_prompt(self, text, amount, currency, categories, user_context):
    # Убираем эмодзи из категорий для промпта
    categories_clean = [EMOJI_PREFIX_RE.sub('', cat).strip() for cat in categories]

    # Добавляем контекст недавних категорий (до 3)
    context_info = ""
    if user_context and 'recent_categories' in user_context:
        recent_clean = [EMOJI_PREFIX_RE.sub('', cat).strip()
                        for cat in user_context['recent_categories'][:3]]
        context_info = f"\nRecently used categories: {', '.join(recent_clean)}"

    return f"""You are an expense categorization assistant for a personal finance bot.

Expense information:
Description: "{text}"
Amount: {amount} {currency}
{context_info}

User's available categories:
{categories_list}

IMPORTANT INSTRUCTIONS:
1. Choose ONLY from the list above - return the exact category name WITHOUT any emoji
2. Categories may be in different languages (English, Russian, Spanish) - match semantically
3. Return ONLY the text part of the category name, NO emojis
4. Match by meaning, not language:
   - "cookie" or "печенье" -> food/groceries category
   - "coffee" or "кофе" -> cafe/restaurant category
   - "uber" or "такси" -> transport category
5. CRITICAL: "продукт", "продукты" without medical context -> ALWAYS means groceries/food
6. If exact match isn't found, choose the most semantically similar category
7. User-created custom categories are equally valid as default ones

Return JSON:
{{
    "category": "exact category name from the list WITHOUT emoji",
    "confidence": number from 0 to 1,
    "reasoning": "brief explanation of the choice"
}}"""
```

### Принуждение к JSON формату

```python
response = await client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    response_format={"type": "json_object"},  # <-- Ключевой параметр!
    temperature=0.1,
    max_tokens=256
)
```

### Контекст
**Для категоризации:** Передаются `recent_categories` — последние 3 использованные категории из 10 последних трат. НЕ полная история, но контекст есть.

**Для чата:** Передаются последние 10-20 сообщений для поддержания контекста разговора.

---

## 4. Генерация отчетов и Аналитика

### Что отправляется в AI для ежемесячного отчета

**НЕ весь список транзакций!** Используется умная агрегация с конкретными лимитами:

```python
# bot/services/monthly_insights.py — РЕАЛЬНЫЕ лимиты из кода

# Топ категории: 10 штук (строка 168)
for cat_data in sorted_categories[:10]:

# Крупные траты: анализируем топ-50, в промпт — топ-20 (строки 415, 418)
top_expenses = sorted_expenses[:50]
for exp in top_expenses[:20]:

# Необычные траты: >= 2x среднего, максимум 5 (строки 439, 444)
unusual = [exp for exp in expenses if exp.amount >= avg_expense * 2]
for exp in sorted(unusual, ...)[:5]:

# Регулярные расходы: 2+ повторения, максимум 5 (строки 477, 481)
regular = [(desc, count) for desc, count in counter.most_common(10) if count >= 2]
for desc, count in regular[:5]:

# Минимум для отчета: 3 траты (строка 893)
if len(month_data['expenses']) < 3:
    return None
```

**Пример промпта для отчета:**
```
ДАННЫЕ ЗА ОКТЯБРЬ 2025:
- Всего потрачено: 50 000 руб
- Всего доходов: 75 000 руб
- Баланс: +25 000 руб
- Количество трат: 145

РАСХОДЫ ПО КАТЕГОРИЯМ (топ 10):
1. Продукты: 15 000 руб (30%, 52 траты)
2. Транспорт: 8 000 руб (16%, 31 трата)
3. Кафе: 6 000 руб (12%, 28 трат)
...

КРУПНЫЕ ТРАТЫ (топ 20 из 50):
- 15.10: iPhone чехол — 5 000 руб
- 12.10: Ресторан на ДР — 4 500 руб
... и ещё 30 трат

НЕОБЫЧНЫЕ ТРАТЫ (>= 2x среднего, топ 5):
- 10.10: Ремонт ноутбука — 8 000 руб (в 3.3x больше среднего)

РЕГУЛЯРНЫЕ (2+ повторения, топ 5):
- "кофе": 25x, средняя 180 руб, всего 4 500 руб
```

### Проблема токенов при 500+ транзакциях

**Решение:** агрегация + жесткие лимиты

| Что | Лимит | Источник |
|-----|-------|----------|
| Топ категории | 10 | строка 168 |
| Крупные траты (анализ) | 50 | строка 415 |
| Крупные траты (в промпт) | 20 | строка 418 |
| Необычные траты | 5 | строка 444 |
| Регулярные расходы | 5 | строка 481 |
| Минимум трат для отчета | 3 | строка 893 |

**Результат:** 500 транзакций -> ~1500 символов промпта.

---

## 5. Экономика и Боли

### Стоимость обслуживания

**Примерная стоимость на 1 активного пользователя в месяц:**

| Компонент | Стоимость | Комментарий |
|-----------|-----------|-------------|
| AI категоризация | $0.01-0.05 | ~20% трат идут в AI |
| Ежемесячный отчет | $0.005-0.01 | 1-2K токенов |
| Чат (если используют) | $0.01-0.03 | Зависит от активности |
| **ИТОГО** | **$0.02-0.10** | На активного пользователя |

**Примечание:** Оценки эмпирические, точных расчетов в коде нет.

### Примеры ошибок (галлюцинации)

**Пример 1: "Перевод маме"**
```
Вход: "Перевод маме 5000"
Ожидание: "Переводы" или "Семья"
AI выдал: "Благотворительность"

Причина: Модель интерпретировала "помощь маме" как благотворительность.
Решение: Добавили "перевод", "маме", "папе" в EXPENSE_CATEGORY_DEFINITIONS.
```

**Пример 2: "Печенье"**
```
Вход: "Печенье 150"
Ожидание: "Продукты"
AI выдал: "Кафе и рестораны"

Причина: Модель решила, что печенье покупают в кофейнях.
Решение: Явно указали в промпте: "cookie/печенье -> groceries, NOT cafe"
```

---

## 6. Примеры кода для статьи

### 1. Модель Expense (ПОЛНАЯ)

```python
# expenses/models.py
class Expense(models.Model):
    """Траты"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expenses'
    )

    # Основная информация
    amount = models.DecimalField(max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default='RUB')
    description = models.TextField(blank=True)

    # Дата и время
    expense_date = models.DateField(default=date.today)
    expense_time = models.TimeField(default=datetime.now)

    # Вложения
    receipt_photo = models.CharField(max_length=255, blank=True)

    # AI категоризация
    ai_categorized = models.BooleanField(default=False)
    ai_confidence = models.DecimalField(
        max_digits=3, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )

    # Кешбек
    cashback_excluded = models.BooleanField(default=False)
    cashback_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(0)]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-expense_time']
        indexes = [
            models.Index(fields=['profile', '-expense_date']),
            models.Index(fields=['profile', 'category', '-expense_date']),
        ]
```

### 2. Функция запроса к AI для категоризации

```python
# bot/services/unified_ai_service.py (упрощено для статьи)
from openai import AsyncOpenAI
from httpx_socks import AsyncProxyTransport
import httpx
import json

class UnifiedAIService:
    def __init__(self, provider: str = 'deepseek'):
        self.provider = provider
        # Для OpenRouter используем SOCKS5 прокси через httpx
        self._http_client = None
        if provider == 'openrouter' and os.getenv('AI_PROXY_URL'):
            transport = AsyncProxyTransport.from_url(os.getenv('AI_PROXY_URL'))
            self._http_client = httpx.AsyncClient(transport=transport, timeout=15.0)

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self._get_api_key(),
            base_url=self._get_base_url(),
            http_client=self._http_client  # Прокси только для OpenRouter
        )

    async def categorize_expense(
        self,
        text: str,
        amount: float,
        categories: list[str],
        user_context: dict = None
    ) -> dict:
        """Категоризация траты через AI (полностью async, без to_thread)"""
        system_prompt = self._build_categorization_prompt(
            categories, user_context
        )
        user_message = f"Categorize: {text}, amount: {amount}"

        client = self._get_client()
        try:
            # Прямой await без asyncio.to_thread — неблокирующий вызов
            response = await client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=256
            )

            result = json.loads(response.choices[0].message.content)
            return {
                'category': result.get('category'),
                'confidence': result.get('confidence', 0.5),
            }

        except Exception as e:
            logger.error(f"AI categorization failed: {e}")
            return None

    async def aclose(self):
        """Закрытие httpx клиента при shutdown бота"""
        if self._http_client:
            await self._http_client.aclose()
```

### 3. Хендлер сообщения (упрощенный)

**Примечание:** Реальный хендлер в `bot/routers/expense.py` — 800+ строк с FSM, кешбэком, подписками, голосовыми сообщениями. Ниже — упрощенная суть:

```python
# bot/routers/expense.py (сильно упрощено для статьи)
@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_expense(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text

    await message.bot.send_chat_action(message.chat.id, "typing")

    result = await parse_expense_message(
        text=text,
        user_id=user_id,
        use_ai=True
    )

    if not result:
        return await handle_as_chat_message(message, state)

    expense = await create_expense(
        user_id=user_id,
        amount=result['amount'],
        category=result['category'],
        description=result['description'],
        ai_categorized=result['ai_categorized']
    )

    await message.answer(
        f"Добавлено: {result['description']}\n"
        f"Сумма: {result['amount']} руб\n"
        f"Категория: {result['category']}"
    )
```

---

## 7. Извлечение ключевых слов — самая боль

Когда AI определяет категорию, нужно сохранить слова из описания, чтобы в следующий раз не дергать AI. Звучит просто? Ха-ха.

### Проблема

Пользователи пишут по-разному:
- `"кофе 350"` → сохранить "кофе" ✅
- `"купил кофе в старбаксе"` → сохранить "кофе", "старбаксе" ✅
- `"купил хлеб молоко яйца масло сыр"` → сохранить? 🤔
- `"потратил 500р на обед"` → сохранить "обед" ✅

### Наивное решение (не работает)

```python
words = description.split()  # ["купил", "хлеб", "молоко", "яйца", "масло", "сыр"]
# Сохраняем все → категория засоряется мусором
```

**Проблемы:**
- Глаголы ("купил", "потратил") — мусор
- Списки покупок (5+ слов) — засоряют словарь
- Числа и валюта ("500", "р") — шум
- Предлоги ("в", "на", "за") — не нужны

### Реальное решение (3 функции)

**Шаг 1: Извлечение слов**
```python
def extract_words_from_description(description: str) -> List[str]:
    # 1. Удаляем числа и валюту
    text = re.sub(r'\d+', '', description)
    text = re.sub(r'[₽$€£¥\.,"\'!?;:\-\(\)]', ' ', text)

    # 2. Разбиваем на слова
    words = text.lower().split()

    # 3. Фильтруем стоп-слова
    stop_words = {
        'и', 'в', 'на', 'с', 'за', 'по', 'для', 'от', 'до', 'из',
        'купил', 'купила', 'купили', 'взял', 'взяла', 'взяли',
        'потратил', 'потратила', 'потратили', 'оплатил', 'оплатила',
        'рубль', 'рубля', 'рублей', 'руб', 'р', 'тыс', 'тысяч'
    }

    # 4. Минимум 3 буквы
    return [w for w in words if w and len(w) >= 3 and w not in stop_words]
```

**Шаг 2: Умная фильтрация**
```python
def filter_keywords_for_saving(words: List[str]) -> List[str]:
    # Правило 1: Более 4 слов → список покупок, НЕ сохраняем
    if len(words) > 4:
        return []  # "хлеб молоко яйца масло сыр" → []

    # Правило 2: Более 2 слов И есть глагол → берем 2 слова БЕЗ глагола
    verbs = {'купил', 'заказал', 'съел', 'сходил', ...}
    words_without_verbs = [w for w in words if w not in verbs]

    if len(words) > 2 and len(words_without_verbs) < len(words):
        return words_without_verbs[:2]  # "купил кофе круассан" → ["кофе", "круассан"]

    # Правило 3: В остальных случаях → максимум 3 слова
    return words[:3]  # "кофе капучино" → ["кофе", "капучино"]
```

**Шаг 3: Проверка орфографии (опционально)**
```python
# Если доступен spellchecker
corrected_words = []
for word in words:
    corrected = check_and_correct_text(word)  # "кофэ" → "кофе"
    if corrected and len(corrected) >= 3:
        corrected_words.append(corrected.lower())
```

### Примеры работы

| Ввод | Извлечено | Отфильтровано | Сохранено |
|------|-----------|---------------|-----------|
| `"кофе 350"` | `["кофе"]` | `["кофе"]` | ✅ `["кофе"]` |
| `"купил кофе в старбаксе"` | `["купил", "кофе", "старбаксе"]` | `["кофе", "старбаксе"]` | ✅ `["кофе", "старбаксе"]` |
| `"хлеб молоко яйца масло сыр"` | `["хлеб", "молоко", "яйца", "масло", "сыр"]` | `[]` (>4 слов) | ❌ `[]` |
| `"обед в макдональдсе"` | `["обед", "макдональдсе"]` | `["обед", "макдональдсе"]` | ✅ `["обед", "макдональдсе"]` |
| `"потратил 500р на такси"` | `["потратил", "такси"]` | `["такси"]` (глагол удален) | ✅ `["такси"]` |

### Уникальность слов

После фильтрации слова **удаляются из ВСЕХ категорий пользователя** и добавляются только в текущую:

```python
# Удаляем слово из всех категорий
for word in words:
    CategoryKeyword.objects.filter(
        category__profile=expense.profile,
        keyword=word
    ).delete()

# Добавляем в новую категорию
for word in words:
    CategoryKeyword.objects.get_or_create(
        category=category,
        keyword=word
    )
```

### Лимиты

- **Максимум 3 слова** за раз
- **Максимум 50 ключевых слов** на категорию (автоочистка старых)
- **Списки покупок (5+ слов)** игнорируются полностью

### Почему это сложно

Это заняло **несколько дней настройки**, потому что:
1. Изначально сохраняли всё → словарь засорялся за неделю
2. Потом добавили стоп-слова → глаголы всё равно проникали
3. Потом добавили правило "4+ слова = игнор" → списки покупок перестали мешать
4. Потом добавили умную фильтрацию глаголов → качество выросло
5. Потом добавили проверку орфографии → "кофэ" стал "кофе"

**Результат:** Теперь ~90% сохраненных слов реально полезны для категоризации.

---

## 8. Честные костыли и Workaround'ы

На Хабре любят честность — вот реальные "особенности" проекта:

### Костыль #1: Ограниченный Fallback (самый болезненный)

**Проблема:** Изначально при ошибке DeepSeek система перебирала ВСЮ цепочку fallback-провайдеров. Это занимало 30+ секунд.

**Решение (костыль):** Берем только ПЕРВОГО провайдера из fallback-цепочки с таймаутом 5 сек.

```python
# bot/utils/expense_parser.py
if fallback_chain:
    fallback_provider = fallback_chain[0]  # Только первый!
    # Timeout 5 сек для fallback (вместо 10 сек для основного)
```

**Почему не исправили "правильно":** 30 секунд — это смерть UX. Лучше быстро упасть на "Прочие расходы".

---

### Костыль #2: Throttling уведомлений админу

**Проблема:** При падении AI провайдера админ получал СОТНИ уведомлений в минуту.

**Решение:** Глобальные переменные (да, глобальные!) для rate limiting.

```python
# bot/services/monthly_insights.py
_last_fallback_notification = {}      # Глобальный state
_last_failure_notification = {}
NOTIFICATION_THROTTLE_HOURS = 1       # Максимум раз в час
```

**Почему глобальные переменные:** Celery worker'ы в отдельных процессах. Redis для этого — overkill.

---

### Костыль #3: Ротация API ключей с "воскрешением"

**Проблема:** API ключи временно блокируются (rate limit). Нужно пропускать "мертвые" ключи, но не навсегда.

**Решение:** 5-минутный cooldown.

```python
# bot/services/key_rotation_mixin.py
if not is_working:
    if datetime.now() - last_error_time < timedelta(minutes=5):
        continue  # Пропускаем "мертвый" ключ
    else:
        # Прошло 5 минут — пробуем снова
        logger.info(f"Retrying key #{current_index} after cooldown")
```

**Почему 5 минут:** Методом тыка.

---

### Костыль #4: Production bug с чужими категориями

**История:** В ноябре 2025 обнаружили, что траты пользователя A сохранялись с категориями пользователя B. Сотни пользователей затронуты.

**Причина:** Не было валидации что `category_id` принадлежит пользователю.

**Решение (после инцидента):**

```python
# bot/services/expense.py
if category_id is not None:
    category = ExpenseCategory.objects.get(id=category_id)

    if category.profile_id == profile.id:
        is_valid = True
    elif profile.household_id and category.profile.household_id == profile.household_id:
        is_valid = True  # Семейный бюджет
    else:
        raise ValueError("Нельзя использовать категорию другого пользователя")
```

**Урок:** Всегда валидируй FK на принадлежность пользователю.

---

### Костыль #5: Эмодзи с ZWJ (Zero Width Joiner)

**Проблема:** Простой regex не ловил составные эмодзи.

**Решение:** Централизованный regex с поддержкой ZWJ, используется в 15+ местах.

```python
# bot/utils/emoji_utils.py
EMOJI_PREFIX_RE = re.compile(
    r'^(?:'
    r'[\U0001F300-\U0001F9FF]'
    r'(?:\u200D[\U0001F300-\U0001F9FF])*'
    r'[\uFE0F\u200D]*'
    r')+\s*'
)
```

---

### Костыль #6: Celery health check — всегда True

```python
# expenses/views.py
def health_check(request):
    return JsonResponse({
        'status': 'ok',
        'celery_status': True,  # TODO: implement actual celery check
    })
```

**Почему не реализовали:** Мониторинг через Sentry. Health check для Kubernetes, которого нет.

---

## 9. Что ещё есть в коде, но не описано выше

### Прокси-fallback для OpenRouter
При недоступности SOCKS5 прокси — автоматический fallback на прямое соединение с уведомлением админа.

**Реализация:** Используется `httpx-socks` + `AsyncProxyTransport` для асинхронного SOCKS5. При ошибке прокси (`_is_proxy_error()`) повторяем запрос без `http_client`:

```python
# Упрощенная логика fallback
async def _make_api_call_with_proxy_fallback(self, create_call, operation):
    client = self._get_client(use_proxy=True)
    try:
        return await create_call(client)
    except Exception as e:
        if self._is_proxy_error(e):
            # Fallback на прямое соединение
            client_direct = self._get_client(use_proxy=False)
            asyncio.create_task(self._notify_admin_fallback(e))
            return await create_call(client_direct)
        raise
```

### Ротация ключей
`KeyRotationMixin` — автоматическая ротация API ключей с отслеживанием "мертвых" и их восстановлением через 5 минут.

### Голосовой пайплайн
Цепочка провайдеров для распознавания речи: Yandex SpeechKit -> OpenRouter/Gemini -> fallback.

### AsyncOpenAI миграция (январь 2026)
Полный переход с синхронного `OpenAI` на асинхронный `AsyncOpenAI`:

**До миграции:**
```python
from openai import OpenAI
client = OpenAI(api_key=...)
response = await asyncio.to_thread(client.chat.completions.create, ...)  # Блокировка потока!
```

**После миграции:**
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key=...)
response = await client.chat.completions.create(...)  # Чистый async, без блокировки
```

**Что изменилось:**
- Заменен `OpenAI` на `AsyncOpenAI` во всех сервисах
- Убраны все `asyncio.to_thread()` для AI вызовов (остались только для Django ORM)
- `httpx.Client` заменен на `httpx.AsyncClient` с `AsyncProxyTransport`
- Добавлены методы `aclose()` для корректного закрытия клиентов
- Shutdown handler в `bot/main.py` вызывает `aclose()` для всех AI сервисов

**Результат:** Устранение блокировки потоков при высокой конкуренции AI-запросов.

---

## Итоги

| Параметр | Значение |
|----------|----------|
| Язык | Python 3.11 |
| Telegram SDK | aiogram 3.13.1 |
| БД | PostgreSQL 15 + Django ORM |
| Кэш | Redis 7 |
| Контейнеризация | Docker Compose (6 сервисов) |
| AI SDK | **AsyncOpenAI** (полностью async) |
| AI категоризация | DeepSeek (`deepseek-chat`) |
| AI чат/голос | OpenRouter → Gemini (`gemini-3-flash-preview`) |
| AI insights | DeepSeek (`deepseek-reasoner`) |
| AI Fallback | OpenRouter (везде) |
| AI Прокси | `httpx-socks` + `AsyncProxyTransport` |
| OpenAI API | **НЕ используется** (только SDK) |
| Скорость (словарь) | ~5-15 мс (эмпирика) |
| Скорость (AI) | ~300-800 мс (эмпирика) |
| Стоимость/пользователь | $0.02-0.10/месяц (оценка) |
| % трат без AI | ~80% |
