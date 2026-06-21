# План внедрения FAQ системы

## Цель

Создать FAQ систему, которая:
1. Отвечает на частые вопросы пользователей **без вызова AI** (экономия токенов, мгновенный ответ)
2. При fuzzy совпадении вопроса — возвращает готовый ответ из FAQ
3. При отсутствии совпадения — передаёт FAQ как контекст для AI

## Архитектура

```
Сообщение (тип: chat)
    ↓
┌─────────────────────────────────┐
│  FAQ Matcher                    │
│  - Точное совпадение вопросов   │
│  - Fuzzy match (cutoff=0.75)    │
│  - Keyword match                │
└─────────────────────────────────┘
    ↓
├─ confidence >= 0.85 → Ответ из FAQ (без AI)
│
├─ confidence 0.6-0.85 → FAQ ответ + "Уточните, если не то"
│
└─ confidence < 0.6 → AI с FAQ контекстом
    ↓
┌─────────────────────────────────┐
│  AI Chat                        │
│  - System prompt + FAQ (EN)     │
│  - Инструкция отвечать на       │
│    языке пользователя           │
└─────────────────────────────────┘
```

## Структура файлов

```
bot/
├── data/
│   ├── __init__.py
│   └── faq.py              # FAQ данные (Python dict)
├── services/
│   └── faq_service.py      # Логика поиска и матчинга
└── routers/
    └── chat.py             # Интеграция FAQ в обработчик
```

## 1. Структура FAQ данных

**Файл:** `bot/data/faq.py`

```python
"""
FAQ данные для бота.
Хранятся в коде для простоты редактирования и деплоя.
"""

from typing import List, Dict, TypedDict

class FAQEntry(TypedDict):
    id: str                    # Уникальный ID записи
    category: str              # Категория: general, expenses, income, reports, settings, subscription
    questions_ru: List[str]    # Варианты вопросов на русском (для fuzzy match)
    questions_en: List[str]    # Варианты вопросов на английском
    keywords: List[str]        # Ключевые слова (оба языка)
    answer_ru: str             # Ответ на русском
    answer_en: str             # Ответ на английском

FAQ_DATA: List[FAQEntry] = [
    # === GENERAL ===
    {
        "id": "capabilities",
        "category": "general",
        "questions_ru": [
            "что ты умеешь",
            "что ты можешь",
            "какие у тебя функции",
            "что умеет бот",
            "расскажи о себе",
            "помощь",
            "help"
        ],
        "questions_en": [
            "what can you do",
            "what are your features",
            "what is this bot",
            "help",
            "capabilities"
        ],
        "keywords": ["умеешь", "можешь", "функции", "возможности", "help", "capabilities"],
        "answer_ru": """Я помогаю вести учёт финансов! Вот что я умею:

📝 <b>Учёт операций</b>
• Записать трату: просто напиши "500 кофе" или "такси 350"
• Записать доход: "+50000 зарплата" или "получил 1000"
• Я запоминаю категории и в следующий раз подставлю автоматически

📊 <b>Отчёты и аналитика</b>
• "Покажи траты за сегодня/неделю/месяц"
• "Сколько потратил в ноябре?"
• Меню "Бюджет": сводки и PDF/Excel отчёты по месяцам

⚙️ <b>Настройки</b>
• /settings — язык, валюта, часовой пояс
• /categories — управление категориями

💡 Просто пиши как удобно — я пойму!""",
        "answer_en": """I help you track your finances! Here's what I can do:

📝 <b>Track transactions</b>
• Record expense: just type "500 coffee" or "taxi 350"
• Record income: "+50000 salary" or "received 1000"
• I remember categories and will auto-assign them next time

📊 <b>Reports & Analytics</b>
• "Show expenses for today/week/month"
• "How much did I spend in November?"
• "Budget" menu: summaries and PDF/Excel reports by month

⚙️ <b>Settings</b>
• /settings — language, currency, timezone
• /categories — manage categories

💡 Just write naturally — I'll understand!"""
    },

    # === TRANSACTIONS (траты и доходы) ===
    {
        "id": "how_to_add_transaction",
        "category": "transactions",
        "questions_ru": [
            "как добавить трату",
            "как записать расход",
            "как внести трату",
            "как добавить доход",
            "как записать доход",
            "как вести учёт"
        ],
        "questions_en": [
            "how to add expense",
            "how to record expense",
            "how to add income",
            "how to record income",
            "how to track finances"
        ],
        "keywords": ["добавить", "записать", "внести", "трату", "расход", "доход", "add", "record", "expense", "income"],
        "answer_ru": """<b>Как записывать операции:</b>

💸 <b>Трата</b> — просто напиши сумму и описание:
• "500 кофе"
• "такси 350"
• "продукты 2500"

💵 <b>Доход</b> — добавь знак "+" перед суммой:
• "+50000 зарплата"
• "+1000 кэшбэк"

Я автоматически определю категорию. Если ошибусь — нажми ✏️, выбери правильную категорию, и я запомню!

💡 <b>Дополнительно:</b>
• Дата: "вчера кофе 200"
• Валюта: "50 usd обед\"""",
        "answer_en": """<b>How to record transactions:</b>

💸 <b>Expense</b> — just write amount and description:
• "500 coffee"
• "taxi 350"
• "groceries 2500"

💵 <b>Income</b> — add "+" sign before amount:
• "+50000 salary"
• "+1000 cashback"

I'll auto-detect the category. If wrong — tap ✏️, select correct category, and I'll remember!

💡 <b>Tips:</b>
• Date: "yesterday coffee 200"
• Currency: "50 usd lunch\""""
    },
    {
        "id": "how_to_edit_transaction",
        "category": "transactions",
        "questions_ru": [
            "как изменить трату",
            "как редактировать трату",
            "как исправить трату",
            "как удалить трату",
            "как изменить доход"
        ],
        "questions_en": [
            "how to edit expense",
            "how to change expense",
            "how to delete expense",
            "how to edit income"
        ],
        "keywords": ["изменить", "редактировать", "исправить", "удалить", "edit", "change", "delete"],
        "answer_ru": """<b>Как изменить запись:</b>

После добавления появляется сообщение с кнопкой "✏️ Редактировать".

Можно изменить:
• 📝 Сумму
• 🏷 Категорию
• 📅 Дату
• 🗑 Удалить запись

Также можно найти запись через "Покажи траты за сегодня" или в меню 'Бюджет'""",
        "answer_en": """<b>How to edit a record:</b>

After adding, you'll see a message with "✏️ Edit" button.

You can change:
• 📝 Amount
• 🏷 Category
• 📅 Date
• 🗑 Delete record

You can also find records via "Show today's expenses" or via the "Budget" menu"""
    },

    # === REPORTS ===
    {
        "id": "how_to_view_reports",
        "category": "reports",
        "questions_ru": [
            "как посмотреть отчёт",
            "как увидеть статистику",
            "где посмотреть траты",
            "покажи аналитику"
        ],
        "questions_en": [
            "how to view reports",
            "how to see statistics",
            "where to see expenses",
            "show analytics"
        ],
        "keywords": ["отчёт", "статистика", "аналитика", "report", "statistics", "analytics"],
        "answer_ru": """<b>Как посмотреть отчёты:</b>

📊 <b>Быстрые отчёты</b> — просто спроси:
• "Траты за сегодня"
• "Сколько потратил за неделю?"
• "Покажи расходы за ноябрь"

📈 <b>Детальный отчёт</b> — в меню "Бюджет"
• Выбери период (неделя/месяц/год)
• Получи PDF или Excel с графиками

📋 <b>Дневник трат</b> — кнопка "💸 Траты" в /start""",
        "answer_en": """<b>How to view reports:</b>

📊 <b>Quick reports</b> — just ask:
• "Expenses for today"
• "How much did I spend this week?"
• "Show expenses for November"

📈 <b>Detailed report</b> — in the "Budget" menu
• Choose period (week/month/year)
• Get PDF or Excel with charts

📋 <b>Expense diary</b> — "💸 Expenses" button in /start"""
    },

    # === CATEGORIES ===
    {
        "id": "how_to_manage_categories",
        "category": "categories",
        "questions_ru": [
            "как добавить категорию",
            "как создать категорию",
            "как изменить категории",
            "как настроить категории",
            "как работают категории",
            "что такое категории"
        ],
        "questions_en": [
            "how to add category",
            "how to create category",
            "how to manage categories",
            "how categories work",
            "what are categories"
        ],
        "keywords": ["категория", "категории", "category", "categories"],
        "answer_ru": """<b>Категории:</b>

Категории помогают группировать траты и доходы для аналитики.

📂 <b>Команда /categories</b> — управление категориями

➕ <b>Добавить</b>
• Нажми "Добавить" → введи название → выбери иконку

✏️ <b>Редактировать</b>
• Нажми на категорию → измени название/иконку
• Добавь ключевые слова для автоопределения

🗑 <b>Удалить</b>
• Нажми на категорию → Удалить
• Траты переместятся в "Прочие расходы"

💡 <b>Автоопределение:</b>
Бот запоминает твои исправления и учится определять категории автоматически!""",
        "answer_en": """<b>Categories:</b>

Categories help group expenses and income for analytics.

📂 <b>/categories command</b> — manage categories

➕ <b>Add</b>
• Tap "Add" → enter name → choose icon

✏️ <b>Edit</b>
• Tap category → change name/icon
• Add keywords for auto-detection

🗑 <b>Delete</b>
• Tap category → Delete
• Expenses will move to "Other"

💡 <b>Auto-detection:</b>
Bot remembers your corrections and learns to detect categories automatically!"""
    },
    {
        "id": "category_keywords",
        "category": "categories",
        "questions_ru": [
            "как добавить ключевое слово",
            "что такое ключевые слова",
            "как настроить автоопределение категории",
            "почему бот неправильно определяет категорию"
        ],
        "questions_en": [
            "how to add keyword",
            "what are keywords",
            "how to set up auto-detection",
            "why bot detects wrong category"
        ],
        "keywords": ["ключевое", "ключевые", "слово", "слова", "keyword", "keywords", "автоопределение"],
        "answer_ru": """<b>Ключевые слова категорий:</b>

Ключевые слова помогают боту автоматически определять категорию.

📝 <b>Как добавить:</b>
1. /categories → выбери категорию
2. Нажми "Ключевые слова"
3. Добавь слова, по которым бот узнает категорию

📌 <b>Пример:</b>
Категория "🍕 Еда" — ключевые слова: кофе, обед, ужин, ресторан, кафе

💡 <b>Совет:</b>
Проще всего — просто исправь категорию после записи траты. Бот запомнит и в следующий раз определит правильно!""",
        "answer_en": """<b>Category keywords:</b>

Keywords help bot automatically detect the category.

📝 <b>How to add:</b>
1. /categories → select category
2. Tap "Keywords"
3. Add words that identify this category

📌 <b>Example:</b>
Category "🍕 Food" — keywords: coffee, lunch, dinner, restaurant, cafe

💡 <b>Tip:</b>
Easiest way — just correct category after recording. Bot will remember and detect correctly next time!"""
    },

    # === CASHBACK ===
    {
        "id": "cashback_feature",
        "category": "cashback",
        "questions_ru": [
            "как работает кэшбэк",
            "что такое кэшбэк",
            "как добавить кэшбэк",
            "как учитывать кэшбэк",
            "как включить кэшбэк"
        ],
        "questions_en": [
            "how cashback works",
            "what is cashback",
            "how to add cashback",
            "how to track cashback",
            "how to enable cashback"
        ],
        "keywords": ["кэшбэк", "cashback", "кешбек", "кешбэк"],
        "answer_ru": """<b>Учёт кэшбэка:</b>

Бот умеет учитывать кэшбэк с покупок!

⚙️ <b>Включить:</b>
/settings → Кэшбэк → Включить

💰 <b>Как записывать:</b>
После добавления траты появится кнопка "💰 Кэшбэк".
Нажми и введи процент или сумму кэшбэка.

📊 <b>В отчётах:</b>
Кэшбэк отображается отдельной строкой и учитывается в общей статистике.

💡 <b>Пример:</b>
Трата: "1000 продукты"
Кэшбэк: 5% → бот запишёт +50₽ кэшбэка""",
        "answer_en": """<b>Cashback tracking:</b>

Bot can track cashback from purchases!

⚙️ <b>Enable:</b>
/settings → Cashback → Enable

💰 <b>How to record:</b>
After adding expense, "💰 Cashback" button appears.
Tap and enter cashback percentage or amount.

📊 <b>In reports:</b>
Cashback is shown separately and included in total statistics.

💡 <b>Example:</b>
Expense: "1000 groceries"
Cashback: 5% → bot records +50 cashback"""
    },

    # === RECURRING PAYMENTS ===
    {
        "id": "recurring_payments",
        "category": "recurring",
        "questions_ru": [
            "как добавить регулярный платёж",
            "как настроить ежемесячный платёж",
            "повторяющиеся платежи",
            "автоматические траты",
            "регулярные операции",
            "ежемесячные платежи"
        ],
        "questions_en": [
            "how to add recurring payment",
            "how to set up monthly payment",
            "repeating payments",
            "automatic expenses",
            "recurring operations",
            "monthly payments"
        ],
        "keywords": ["регулярный", "ежемесячный", "повторяющийся", "автоматический", "recurring", "monthly", "automatic", "repeating"],
        "answer_ru": """<b>Регулярные платежи:</b>

Для повторяющихся трат и доходов (аренда, подписки, зарплата).

📋 <b>Команда /recurring</b> — управление

➕ <b>Добавить:</b>
• Укажи сумму и описание
• Выбери категорию
• Установи день месяца (1-28)

⚙️ <b>Как работает:</b>
• Бот автоматически создаёт запись каждый месяц
• Ты получишь уведомление
• Можно отредактировать или пропустить

📌 <b>Примеры:</b>
• Аренда квартиры — 1 числа
• Netflix подписка — 15 числа
• Зарплата — 10 и 25 числа""",
        "answer_en": """<b>Recurring payments:</b>

For repeating expenses and income (rent, subscriptions, salary).

📋 <b>/recurring command</b> — management

➕ <b>Add:</b>
• Enter amount and description
• Choose category
• Set day of month (1-28)

⚙️ <b>How it works:</b>
• Bot automatically creates record each month
• You'll get a notification
• Can edit or skip

📌 <b>Examples:</b>
• Rent — 1st of month
• Netflix subscription — 15th
• Salary — 10th and 25th"""
    },

    # === SETTINGS ===
    {
        "id": "how_to_change_settings",
        "category": "settings",
        "questions_ru": [
            "как изменить настройки",
            "как поменять язык",
            "как изменить валюту",
            "настройки бота"
        ],
        "questions_en": [
            "how to change settings",
            "how to change language",
            "how to change currency",
            "bot settings"
        ],
        "keywords": ["настройки", "язык", "валюта", "settings", "language", "currency"],
        "answer_ru": """<b>Настройки бота:</b>

Команда /settings позволяет изменить:

🌍 <b>Язык</b> — русский или английский
💵 <b>Валюта</b> — RUB, USD, EUR и другие
🕐 <b>Часовой пояс</b> — для корректного учёта дат
💰 <b>Кэшбэк</b> — включить/выключить учёт кэшбэка""",
        "answer_en": """<b>Bot settings:</b>

/settings command allows you to change:

🌍 <b>Language</b> — Russian or English
💵 <b>Currency</b> — RUB, USD, EUR and others
🕐 <b>Timezone</b> — for correct date tracking
💰 <b>Cashback</b> — enable/disable cashback tracking"""
    },

    # === SUBSCRIPTION ===
    {
        "id": "subscription_info",
        "category": "subscription",
        "questions_ru": [
            "что даёт подписка",
            "зачем нужна подписка",
            "какие преимущества подписки",
            "что входит в подписку"
        ],
        "questions_en": [
            "what does subscription give",
            "why do i need subscription",
            "subscription benefits",
            "what's included in subscription"
        ],
        "keywords": ["подписка", "subscription", "premium", "преимущества"],
        "answer_ru": """<b>Что даёт подписка:</b>

🤖 <b>AI-ассистент</b>
• Умный анализ трат
• Ответы на вопросы о финансах
• Рекомендации по экономии

📊 <b>Расширенная аналитика</b>
• Детальные отчёты PDF/Excel
• Графики и диаграммы
• Сравнение периодов

🎁 <b>Пробный период</b>
• 30 дней бесплатно для новых пользователей

Команда /subscription — управление подпиской""",
        "answer_en": """<b>What subscription gives:</b>

🤖 <b>AI assistant</b>
• Smart expense analysis
• Answers about your finances
• Savings recommendations

📊 <b>Advanced analytics</b>
• Detailed PDF/Excel reports
• Charts and diagrams
• Period comparison

🎁 <b>Trial period</b>
• 30 days free for new users

/subscription command — manage subscription"""
    },

    # === LIMITS/BUDGETS (будущая функция) ===
    {
        "id": "limits_not_available",
        "category": "settings",
        "questions_ru": [
            "как установить лимит",
            "как задать бюджет",
            "как ограничить траты",
            "лимит на категорию"
        ],
        "questions_en": [
            "how to set limit",
            "how to set budget",
            "how to limit spending",
            "category limit"
        ],
        "keywords": ["лимит", "бюджет", "ограничение", "limit", "budget"],
        "answer_ru": """<b>Лимиты и бюджеты</b>

🚧 Эта функция находится в разработке и будет доступна в ближайших обновлениях!

Планируется:
• Установка лимитов по категориям
• Уведомления при приближении к лимиту
• Отслеживание выполнения бюджета

Пока отслеживай траты через меню "Бюджет" (кнопки без команды)""",
        "answer_en": """<b>Limits and budgets</b>

🚧 This feature is under development and will be available in upcoming updates!

Planned features:
• Category spending limits
• Notifications when approaching limit
• Budget tracking

For now, track expenses via the "Budget" menu (buttons, no command)"""
    },

]

# Функция для получения FAQ в формате для AI
def get_faq_for_ai_context() -> str:
    """
    Возвращает FAQ в компактном формате на английском для передачи в AI.
    """
    lines = ["BOT FAQ (answer in user's language):"]
    for entry in FAQ_DATA:
        q = entry["questions_en"][0] if entry["questions_en"] else entry["questions_ru"][0]
        # Берём английский ответ и сокращаем
        a = entry["answer_en"].replace("\n", " ").replace("<b>", "").replace("</b>", "")
        if len(a) > 200:
            a = a[:200] + "..."
        lines.append(f"Q: {q}")
        lines.append(f"A: {a}")
        lines.append("")
    return "\n".join(lines)
```

## 2. FAQ Service

**Файл:** `bot/services/faq_service.py`

```python
"""
Сервис для поиска ответов в FAQ.
Использует fuzzy matching (difflib.get_close_matches) для поиска похожих вопросов.
"""

import logging
from typing import Optional, Tuple, List
from difflib import get_close_matches, SequenceMatcher

from bot.data.faq import FAQ_DATA, FAQEntry, get_faq_for_ai_context

logger = logging.getLogger(__name__)


class FAQMatcher:
    """Класс для поиска ответов в FAQ"""

    # Пороги уверенности
    HIGH_CONFIDENCE_THRESHOLD = 0.85    # Точный ответ без AI
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60  # Ответ + "уточните"
    FUZZY_CUTOFF = 0.72                 # Порог для fuzzy matching (как в category.py)

    def __init__(self):
        self._build_index()

    def _build_index(self):
        """Построить индексы для быстрого поиска"""
        # Индекс вопросов -> entry
        self._questions_ru: dict[str, FAQEntry] = {}
        self._questions_en: dict[str, FAQEntry] = {}
        self._keywords: dict[str, List[FAQEntry]] = {}

        for entry in FAQ_DATA:
            # Индексируем вопросы
            for q in entry.get("questions_ru", []):
                self._questions_ru[q.lower().strip()] = entry
            for q in entry.get("questions_en", []):
                self._questions_en[q.lower().strip()] = entry

            # Индексируем ключевые слова
            for kw in entry.get("keywords", []):
                kw_lower = kw.lower()
                if kw_lower not in self._keywords:
                    self._keywords[kw_lower] = []
                self._keywords[kw_lower].append(entry)

    def find_answer(self, text: str, lang: str = 'ru') -> Tuple[Optional[str], float, Optional[str]]:
        """
        Найти ответ на вопрос в FAQ.

        Args:
            text: Текст вопроса пользователя
            lang: Язык пользователя ('ru' или 'en')

        Returns:
            Tuple[answer, confidence, faq_id]:
            - answer: Текст ответа или None
            - confidence: Уверенность (0.0 - 1.0)
            - faq_id: ID записи FAQ или None
        """
        text_lower = text.lower().strip()

        # Убираем знак вопроса для поиска
        text_clean = text_lower.rstrip('?').strip()

        # 1. Точное совпадение вопроса
        questions_index = self._questions_ru if lang == 'ru' else self._questions_en
        if text_clean in questions_index:
            entry = questions_index[text_clean]
            answer = entry.get(f"answer_{lang}") or entry.get("answer_ru")
            logger.info(f"FAQ exact match: '{text_clean}' -> {entry['id']}")
            return answer, 1.0, entry["id"]

        # 2. Fuzzy matching по вопросам
        all_questions = list(questions_index.keys())
        close_matches = get_close_matches(text_clean, all_questions, n=1, cutoff=self.FUZZY_CUTOFF)

        if close_matches:
            matched_q = close_matches[0]
            entry = questions_index[matched_q]
            # Вычисляем точную уверенность
            ratio = SequenceMatcher(None, text_clean, matched_q).ratio()
            answer = entry.get(f"answer_{lang}") or entry.get("answer_ru")
            logger.info(f"FAQ fuzzy match: '{text_clean}' -> '{matched_q}' (ratio={ratio:.2f})")
            return answer, ratio, entry["id"]

        # 3. Поиск по ключевым словам
        text_words = set(text_clean.split())
        best_match: Optional[FAQEntry] = None
        best_keyword_count = 0

        for word in text_words:
            if word in self._keywords:
                for entry in self._keywords[word]:
                    # Считаем сколько ключевых слов совпало
                    entry_keywords = set(kw.lower() for kw in entry.get("keywords", []))
                    match_count = len(text_words & entry_keywords)
                    if match_count > best_keyword_count:
                        best_keyword_count = match_count
                        best_match = entry

        if best_match and best_keyword_count >= 2:
            # Как минимум 2 ключевых слова должны совпасть
            answer = best_match.get(f"answer_{lang}") or best_match.get("answer_ru")
            confidence = min(0.7, 0.4 + best_keyword_count * 0.15)
            logger.info(f"FAQ keyword match: '{text_clean}' -> {best_match['id']} (keywords={best_keyword_count})")
            return answer, confidence, best_match["id"]

        # 4. Не найдено
        logger.info(f"FAQ no match for: '{text_clean}'")
        return None, 0.0, None

    def get_faq_context_for_ai(self) -> str:
        """Получить FAQ в формате для передачи в AI"""
        return get_faq_for_ai_context()


# Singleton instance
_faq_matcher: Optional[FAQMatcher] = None

def get_faq_matcher() -> FAQMatcher:
    """Получить singleton экземпляр FAQMatcher"""
    global _faq_matcher
    if _faq_matcher is None:
        _faq_matcher = FAQMatcher()
    return _faq_matcher


async def find_faq_answer(text: str, lang: str = 'ru') -> Tuple[Optional[str], float, Optional[str]]:
    """
    Асинхронная обёртка для поиска ответа в FAQ.

    Returns:
        Tuple[answer, confidence, faq_id]
    """
    matcher = get_faq_matcher()
    return matcher.find_answer(text, lang)
```

## 3. Интеграция в chat.py

**Изменения в:** `bot/routers/chat.py`

### 3.1 Импорты

```python
from bot.services.faq_service import find_faq_answer, get_faq_matcher
```

### 3.2 Модификация process_chat_message

```python
async def process_chat_message(message: types.Message, state: FSMContext, text: str, use_ai: bool = True, skip_typing: bool = False):
    """Обработать сообщение как чат"""
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    # 1. Проверяем приветствия - отвечаем мгновенно
    if is_greeting(text):
        response = get_greeting_response(lang)
        await send_message_with_cleanup(message, state, response, parse_mode="HTML")
        return

    # 2. NEW: Проверяем FAQ
    faq_answer, faq_confidence, faq_id = await find_faq_answer(text, lang)

    if faq_confidence >= 0.85:
        # Высокая уверенность — отвечаем из FAQ без AI
        logger.info(f"[Chat] FAQ high confidence answer for user {user_id}: {faq_id}")
        await send_message_with_cleanup(message, state, faq_answer, parse_mode="HTML")
        return

    if faq_confidence >= 0.60:
        # Средняя уверенность — отвечаем из FAQ + предлагаем уточнить
        logger.info(f"[Chat] FAQ medium confidence answer for user {user_id}: {faq_id}")
        clarification = "\n\n💡 Если это не то, что вы искали — уточните вопрос." if lang == 'ru' else "\n\n💡 If this isn't what you were looking for — please clarify your question."
        await send_message_with_cleanup(message, state, faq_answer + clarification, parse_mode="HTML")
        return

    # 3. Если FAQ не нашёл ответ — идём в AI с FAQ контекстом
    # ... существующий код AI чата с добавлением FAQ контекста
```

### 3.3 Передача FAQ в AI

Модифицировать системный промпт в `unified_ai_service.py`:

```python
# В методе chat(), когда нет FUNCTION_CALL:
faq_context = get_faq_matcher().get_faq_context_for_ai()

messages = [
    {
        "role": "system",
        "content": f"""You are a helpful assistant for a personal finance tracking bot.
Answer in the user's language ({user_language}).

{faq_context}

If the user's question matches a FAQ topic, use the FAQ answer as a base.
If not, provide a helpful response based on your knowledge of personal finance."""
    }
]
```

## 4. План реализации

### Этап 1: Создание структуры (30 мин)
- [ ] Создать `bot/data/__init__.py`
- [ ] Создать `bot/data/faq.py` с базовыми FAQ записями
- [ ] Создать `bot/services/faq_service.py`

### Этап 2: Интеграция (45 мин)
- [ ] Модифицировать `bot/routers/chat.py` — добавить проверку FAQ
- [ ] Модифицировать `bot/services/unified_ai_service.py` — добавить FAQ контекст

### Этап 3: Тестирование (30 мин)
- [ ] Проверить точное совпадение вопросов
- [ ] Проверить fuzzy matching
- [ ] Проверить fallback на AI с FAQ контекстом
- [ ] Проверить оба языка (ru/en)

### Этап 4: Расширение FAQ (по необходимости)
- [ ] Добавить больше вопросов по мере поступления от пользователей
- [ ] Анализ логов — какие вопросы чаще всего уходят в AI

## 5. Метрики успеха

1. **Снижение нагрузки на AI** — % вопросов, отвеченных из FAQ
2. **Время ответа** — FAQ ответы должны быть < 100ms
3. **Качество ответов** — отсутствие ошибок Pydantic/выдуманных функций
4. **Покрытие** — добавлять новые FAQ на основе частых вопросов

## 6. Категории FAQ (текущие)

| Категория | Описание | Кол-во записей |
|-----------|----------|----------------|
| `general` | Общие вопросы о боте, возможности | 1 |
| `transactions` | Добавление/редактирование трат и доходов | 2 |
| `reports` | Отчёты и аналитика | 1 |
| `categories` | Управление категориями, ключевые слова | 2 |
| `cashback` | Учёт кэшбэка | 1 |
| `recurring` | Регулярные/ежемесячные платежи | 1 |
| `settings` | Настройки бота (язык, валюта, часовой пояс) | 1 |
| `subscription` | Подписка и преимущества | 1 |
| `limits` | Лимиты и бюджеты (будущая функция) | 1 |

**Всего:** 11 записей (можно расширять)
