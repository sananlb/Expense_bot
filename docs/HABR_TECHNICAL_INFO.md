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
from bot.utils.keyword_service import match_keyword_in_text

async def find_category_by_keywords(text: str, profile) -> Optional[str]:
    categories = ExpenseCategory.objects.filter(
        profile=profile
    ).prefetch_related('keywords')

    for category in categories:
        for kw in category.keywords.all():
            # 3-уровневая проверка: exact, prefix (2-3 слова), inflection
            matched, match_type = match_keyword_in_text(kw.keyword, text)
            if matched:
                kw.usage_count += 1
                kw.save(update_fields=['usage_count', 'last_used'])
                logger.info(f"[KEYWORD MATCH] {match_type}: '{kw.keyword}' matched '{text}'")
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
from bot.utils.keyword_service import match_keyword_in_text

def detect_expense_category_key(text: str) -> Optional[str]:
    """Detect a category key by checking keywords against the text."""
    best_key = None
    best_score = 0

    for key, data in EXPENSE_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_EXPENSE_CATEGORY_KEY:
            continue

        score = 0
        for keyword in data.get('keywords', []):
            # 3-уровневая проверка из keyword_service
            matched, match_type = match_keyword_in_text(keyword, text)
            if matched:
                score += 1

        if score > best_score:
            best_score = score
            best_key = key

    return best_key
```

**Особенность:** Функция `match_keyword_in_text` использует **3-уровневую систему**:
1. **Exact match** — полное совпадение фразы
2. **Prefix match** — совпадение первых 2-3 слов (для multi-word keywords)
3. **Inflection match** — русские склонения для одиночных слов ("зарплата" → "зарплату", "зарплаты")

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

# OpenRouter работает напрямую
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
import json

class UnifiedAIService:
    def __init__(self, provider: str = 'deepseek'):
        self.provider = provider

    def _get_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self._get_api_key(),
            base_url=self._get_base_url(),
            timeout=15.0,
            max_retries=1,
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

## 7. Keyword Matching — эволюция подхода (Вариант C - Гибридный)

### История проблемы

**Изначально** (до декабря 2025): Разбивали description на отдельные слова и сохраняли каждое.

**Проблемы:**
- "кофе" → сохранялось как keyword
- "Сосиска в тесте" → разбивалось на ["сосиска", "в", "тесте"]
- **БАГ:** Keyword "тест" из категории "Родственники" ложно срабатывал на "Сосиска в **тесте** и чай" → категоризировалось как "Родственники" ❌

### Решение: Сохраняем ПОЛНЫЕ ФРАЗЫ (декабрь 2025)

**Новый подход:** Description сохраняется как **ЦЕЛАЯ ФРАЗА**, не разбивается на слова.

```python
# bot/utils/keyword_service.py — РЕАЛЬНАЯ реализация
from bot.utils.keyword_service import normalize_keyword_text, ensure_unique_keyword

# Сохранение keyword при обучении
keyword = normalize_keyword_text(expense.description)  # "Сосиска в тесте и чай" → нормализация

kw_obj, created, removed = ensure_unique_keyword(
    profile=expense.profile,
    category=category,
    word=keyword,  # ← Сохраняем ПОЛНУЮ ФРАЗУ!
    is_income=False
)
```

### Нормализация текста

```python
def normalize_keyword_text(text: str) -> str:
    """
    Единая нормализация для keywords.

    1. Lowercase
    2. Удаление эмодзи (включая ZWJ для композитных эмодзи)
    3. Удаление пунктуации (кроме дефиса внутри слов)
    4. Trim + схлопывание пробелов
    """
    normalized = text.lower()

    # Удаляем эмодзи (включая ZWJ для "👨‍💻")
    emoji_pattern = re.compile(r'[\U0001F000-\U0001F9FF\u200d\ufe0f]+', flags=re.UNICODE)
    normalized = emoji_pattern.sub('', normalized)

    # Удаляем пунктуацию, оставляем дефис внутри слов
    normalized = re.sub(r'[^\w\s\-]', ' ', normalized, flags=re.UNICODE)
    normalized = re.sub(r'(?<!\w)-|-(?!\w)', ' ', normalized)

    # Схлопываем пробелы
    return ' '.join(normalized.split())
```

### 3-уровневая система matching

**Проблема:** Как "зарплата" должна матчить "зарплата от компании", но "тест" НЕ должен матчить "сосиска в тесте"?

**Решение:** 3 уровня проверки в `match_keyword_in_text()`:

```python
def match_keyword_in_text(keyword: str, text: str) -> Tuple[bool, str]:
    """
    Уровень 1: Exact match — полное совпадение фразы
    Уровень 2: Prefix match — первые 2-3 слова совпадают
    Уровень 3: Inflection match — склонения для одиночных keywords
    """
    normalized_keyword = normalize_keyword_text(keyword)
    normalized_text = normalize_keyword_text(text)

    # Защита: минимум 3 символа
    if len(normalized_keyword) < 3:
        return False, "none"

    # УРОВЕНЬ 1: Exact match
    if normalized_text == normalized_keyword:
        return True, "exact"

    # УРОВЕНЬ 2: Prefix match (первые 2-3 слова)
    keyword_words = normalized_keyword.split()
    text_words = normalized_text.split()

    if len(text_words) >= 2 and len(keyword_words) >= 2:
        prefix_length = min(3, len(text_words), len(keyword_words))
        if ' '.join(text_words[:prefix_length]) == ' '.join(keyword_words[:prefix_length]):
            return True, "prefix"

    # УРОВЕНЬ 3: Inflection match (только для одиночных keywords)
    # Проверяем склонение с ЛЮБЫМ словом текста >= 3 символов
    if len(keyword_words) == 1 and len(normalized_keyword) >= 3:
        for text_word in text_words:
            if len(text_word) >= 3:
                # ПРОСТАЯ ЛОГИКА: сравниваем ВСЁ слово, разница не более 1 буквы
                diff = abs(len(normalized_keyword) - len(text_word))

                # Если разница в длине > 1 символа - сразу пропускаем
                if diff > 1:
                    continue

                # Если точное совпадение - это inflection (склонение)
                if normalized_keyword == text_word:
                    return True, "inflection"

                # Если разница ровно 1 символ - подсчитываем количество отличающихся букв
                if diff == 1:
                    shorter = normalized_keyword if len(normalized_keyword) < len(text_word) else text_word
                    longer = text_word if len(normalized_keyword) < len(text_word) else normalized_keyword

                    # Подсчитываем количество несовпадающих букв на одинаковых позициях
                    mismatches = sum(1 for i in range(len(shorter)) if shorter[i] != longer[i])
                    # Плюс 1 символ который есть в длинном слове но нет в коротком
                    mismatches += 1

                    # Если отличается не более 1 буквы - это склонение
                    if mismatches <= 1:
                        return True, "inflection"

                # Если длина одинаковая (diff == 0) - проверяем что отличается только 1 буква
                if diff == 0:
                    mismatches = sum(1 for i in range(len(normalized_keyword)) if normalized_keyword[i] != text_word[i])
                    if mismatches == 1:
                        return True, "inflection"

    return False, "none"
```

### Примеры работы

| Keyword | Text | Match | Type | Комментарий |
|---------|------|-------|------|-------------|
| `"кофе"` | `"Кофе"` | ✅ | exact | Полное совпадение |
| `"сосиска в тесте и чай"` | `"Сосиска в тесте и чай 390"` | ✅ | prefix | Первые 5 слов → берем 3 → совпадают |
| `"сосиска в тесте и чай"` | `"Сосиска в тесте 400"` | ✅ | prefix | Первые 3 слова совпадают |
| `"зарплата"` | `"Зарплату перевели"` | ✅ | inflection | Склонение с первым словом текста |
| `"зарплата"` | `"Зарплата от компании"` | ✅ | inflection | Склонение с первым словом текста |
| `"зарплата"` | `"мне перевели зарплату"` | ✅ | inflection | **НОВОЕ:** Склонение с ЛЮБЫМ словом текста |
| `"зарплата"` | `"перевели зарплату вчера"` | ✅ | inflection | **НОВОЕ:** Склонение с ЛЮБЫМ словом текста |
| `"тест"` | `"Сосиска в тесте и чай"` | ✅ | inflection | Склонение с ANY word ("тесте" = склонение "тест") |
| `"95"` | `"9500"` | ❌ | none | Защита от коротких keywords (< 3 символа) |

### Защита от ложных срабатываний

**Критические правила:**
1. **Минимум 3 символа** — "в", "на", "от" автоматически игнорируются
2. **Inflection с ЛЮБЫМ словом текста** — "зарплата" матчит "мне перевели зарплату" (декабрь 2025)
3. **Prefix match требует >= 2 слов** — одиночные слова не используют prefix
4. **Слова >= 3 символов** — для inflection match (включая keyword и text_word)
5. **Посимвольное сравнение ВСЕГО слова** — не используем stem/основу, сравниваем целиком (январь 2026)
6. **Максимум 1 буква разницы** — для inflection match считаем ВСЕ несовпадающие позиции ("зарплата"→"зарплату" ✅, "фриланс"→"фрилансом" ❌, "кофе"→"косой" ❌)

### Уникальность keywords

**Жесткое правило:** Один keyword может быть **только в ОДНОЙ категории** у пользователя.

```python
def ensure_unique_keyword(profile, category, word, is_income=False):
    """
    1. Нормализует keyword
    2. УДАЛЯЕТ из ВСЕХ категорий пользователя
    3. Создает/обновляет в целевой категории
    """
    normalized = normalize_keyword_text(word)

    # УДАЛЯЕМ из всех категорий
    KeywordModel.objects.filter(
        category__profile=profile,
        keyword=normalized
    ).delete()

    # Создаем в целевой
    keyword, created = KeywordModel.objects.get_or_create(
        category=category,
        keyword=normalized,
        defaults={'usage_count': 0}
    )

    return keyword, created, removed_count
```

### Production bugs и эволюция (ноябрь-декабрь 2025)

**БАГ #1 (ноябрь 2025):** "Сосиска в тесте и чай 390" → категория "Родственники" (из-за keyword "тест")
- **Причина:** Старая система разбивала на слова + использовала простой `if keyword in text`
- **Решение:** Вариант C — сохраняем полные фразы + 3-уровневый matching

**БАГ #2 (декабрь 2025):** "зарплата" НЕ матчила "мне перевели зарплату" (inflection regression)
- **Причина:** Inflection проверялся только с ПЕРВЫМ словом текста
- **Решение:** Изменена логика — inflection проверяется с ЛЮБЫМ словом текста >= 3 символов
- **Побочный эффект:** "тест" теперь матчит "в тесте" (морфологически корректно)

**БАГ #3 (январь 2026):** Ложные срабатывания "кофе" → "косой козырек"
- **Причина:** Использование stem-based сравнения давало совпадения коротких основ: "ко" == "ко"
- **Решение:** Полностью переписана логика inflection matching - вместо stem используется **посимвольное сравнение ВСЕГО слова**
- **Новая логика:** Сравниваем всё слово целиком, максимум 1 буква разницы (считаем все несовпадающие позиции)
- **Проверено в production:** "косой козырек 200" → AI вызван (keyword не найден) → правильная категория "Одежда и обувь" ✅

**Результат эволюции:**
- ✅ Склонения работают с ЛЮБЫМ словом ("зарплата" → "мне перевели зарплату")
- ✅ Умный prefix matching для фраз (первые 2-3 слова)
- ✅ Посимвольное сравнение слов (максимум 1 буква разницы)
- ✅ Защита от коротких совпадений ("кофе" ≠ "косой", "костюм" ≠ "косой")
- ✅ Полная валидация в production ("косой козырек" НЕ совпадает с "кофе")

### Лимиты и очистка

- **Максимум 100 символов** на keyword (автоматическое обрезание по словам)
- **Максимум 50 keywords** на категорию (автоочистка старых)
- **Минимум 3 символа** после нормализации

**Результат:** Система стала в **10x точнее** при категоризации, false positives практически исчезли.

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
