"""
FAQ data for the bot.
Structured as TypedDict for predictable fields and linting hints.
"""
from __future__ import annotations

from typing import List, TypedDict


class FAQEntry(TypedDict):
    id: str
    category: str
    questions_ru: List[str]
    questions_en: List[str]
    keywords: List[str]
    answer_ru: str
    answer_en: str


FAQ_DATA: List[FAQEntry] = [
    {
        "id": "capabilities",
        "category": "general",
        "questions_ru": [
            "что ты умеешь",
            "что ты можешь",
            "чем занимаешься",
            "кто ты",
            "help",
            "помощь",
        ],
        "questions_en": [
            "what can you do",
            "what are your features",
            "what is this bot",
            "help",
            "capabilities",
        ],
        "keywords": ["помощь", "функции", "возможности", "help", "capabilities"],
        "answer_ru": "__WELCOME_MESSAGE__",
        "answer_en": "__WELCOME_MESSAGE__",
    },
    {
        "id": "add_expense",
        "category": "transactions",
        "questions_ru": [
            "как добавить трату",
            "как записать расход",
            "как добавить расход",
            "как внести трату",
        ],
        "questions_en": [
            "how to add expense",
            "how to record expense",
            "how to add spending",
        ],
        "keywords": ["добавить", "записать", "расход", "трата", "expense", "record"],
        "answer_ru": (
            "Просто отправьте сумму и описание: \"500 кофе\", \"такси 450\". "
            "Можно указать валюту: \"50 usd ужин\". "
            "Запись задним числом: \"12.11 продукты 1200\" (формат ДД.ММ). "
            "Категорию предложу сам, исправления запоминаю. "
            "Голосовой ввод доступен с подпиской/триалом."
        ),
        "answer_en": (
            "Send amount with description: \"500 coffee\", \"taxi 450\". "
            "You can add currency: \"50 usd lunch\". "
            "Backdate entry: \"12.11 groceries 1200\" (DD.MM format). "
            "I auto-assign category and remember your corrections. "
            "Voice input is available with subscription/trial."
        ),
    },
    {
        "id": "add_income",
        "category": "transactions",
        "questions_ru": [
            "как добавить доход",
            "как записать доход",
            "как учитывать доход",
        ],
        "questions_en": [
            "how to add income",
            "how to record income",
            "income tracking",
        ],
        "keywords": ["доход", "income", "прибыль", "зарплата", "record income"],
        "answer_ru": (
            "Используйте знак \"+\": \"+50000 зарплата\", \"+1200 кешбэк\". "
            "Запись задним числом: \"25.11 +50000 зарплата\" (формат ДД.ММ). "
            "Категорию подберу автоматически, можно отредактировать после добавления. "
            "Учет доходов доступен только с активной подпиской или триалом."
        ),
        "answer_en": (
            "Use a \"+\" sign: \"+50000 salary\", \"+1200 cashback\". "
            "Backdate entry: \"25.11 +50000 salary\" (DD.MM format). "
            "I auto-select category; you can edit it after. "
            "Income tracking is available only with an active subscription or trial."
        ),
    },
    {
        "id": "view_reports",
        "category": "reports",
        "questions_ru": [
            "как посмотреть статистику",
            "как посмотреть расходы",
            "покажи траты",
            "отчет",
            "как получить отчет",
        ],
        "questions_en": [
            "how to view reports",
            "show expenses",
            "statistics",
            "report",
        ],
        "keywords": ["отчет", "статистика", "траты", "expenses", "report", "analytics"],
        "answer_ru": (
            "Статистика доступна в меню \"Бюджет\": траты за сегодня, по месяцам, дневник операций. "
            "Там же можно сгенерировать PDF/Excel отчёт с графиками. "
            "Команда /report — быстрый доступ к отчётам."
        ),
        "answer_en": (
            "Statistics available in \"Budget\" menu: today's expenses, monthly view, transaction diary. "
            "You can also generate PDF/Excel reports with charts there. "
            "/report command — quick access to reports."
        ),
    },
    {
        "id": "categories_manage",
        "category": "categories",
        "questions_ru": [
            "как управлять категориями",
            "как добавить категорию",
            "как изменить категорию",
            "как удалить категорию",
            "зачем категории",
        ],
        "questions_en": [
            "how to manage categories",
            "how to add category",
            "how to edit category",
            "delete category",
            "why categories",
        ],
        "keywords": ["категория", "категории", "category", "categories", "иконка"],
        "answer_ru": (
            "Управление в меню \"Категории\": отдельно категории расходов и доходов. "
            "Настройте под себя сразу — это важно для будущей аналитики. "
            "Редактируйте категорию только на похожую по смыслу (система ищет по ключевым словам). "
            "Нужна другая по смыслу — создайте новую. "
            "Исправления после добавления записи тоже обучают автокатегоризацию."
        ),
        "answer_en": (
            "Manage in \"Categories\" menu: separate expense and income categories. "
            "Set them up right away — important for future analytics. "
            "Edit category only to similar meaning (system searches by keywords). "
            "Need different meaning — create a new one. "
            "Your corrections after adding a record also improve detection."
        ),
    },
    {
        "id": "category_keywords",
        "category": "categories",
        "questions_ru": [
            "как настроить автокатегории",
            "как добавить ключевые слова",
            "бот ошибается с категорией",
        ],
        "questions_en": [
            "how to add keyword",
            "auto category not working",
            "wrong category",
        ],
        "keywords": ["ключевые", "слова", "keywords", "авто", "категория"],
        "answer_ru": (
            "Категория определяется автоматически: по ключевым словам или вашей истории. "
            "Если совпадений нет — ИИ подберёт категорию. "
            "Результат не устроил? Отредактируйте запись, выбрав правильную категорию — система запомнит и в следующий раз определит верно."
        ),
        "answer_en": (
            "Category is detected automatically: by keywords or your history. "
            "If no match — AI will pick the category. "
            "Not satisfied? Edit the record with correct category — system will remember and detect correctly next time."
        ),
    },
    {
        "id": "cashback",
        "category": "cashback",
        "questions_ru": [
            "как работает кешбэк",
            "как добавить кешбэк",
            "как учитывать кешбэк",
        ],
        "questions_en": [
            "how cashback works",
            "add cashback",
            "track cashback",
        ],
        "keywords": ["кешбэк", "cashback", "cash back", "бонусы"],
        "answer_ru": (
            "Добавьте кешбэк в меню \"Кешбэк\". После этого все записи с категорией, на которую добавлен кешбэк, "
            "будут отображаться с кешбэком. Также есть учёт кешбэка как дохода в отчётах. "
            "Закрепите сообщение кешбэк в чате с ботом, чтобы оно всегда было под рукой."
        ),
        "answer_en": (
            "Add cashback in \"Cashback\" menu. After that, all records with categories that have cashback "
            "will display with cashback. Cashback is also tracked as income in reports. "
            "Pin the cashback message in chat so it's always at hand."
        ),
    },
    {
        "id": "recurring",
        "category": "recurring",
        "questions_ru": [
            "как добавить регулярный платеж",
            "повторяющиеся платежи",
            "подписка на платежи",
            "автоматические расходы",
        ],
        "questions_en": [
            "how to add recurring payment",
            "recurring payments",
            "automatic expenses",
        ],
        "keywords": ["регулярный", "повтор", "ежемесячный", "recurring", "automatic"],
        "answer_ru": (
            "Меню \"Ежемесячные операции\": задайте описание, сумму, категорию и день месяца. "
            "Можно редактировать или ставить на паузу. "
            "Запись о ежемесячной операции появится в чате как все другие записи в выбранный день в 12:00, её можно будет отредактировать."
        ),
        "answer_en": (
            "\"Monthly operations\" menu: set description, amount, category, and day of month. "
            "You can edit or pause them. "
            "The recurring record will appear in chat like any other record on the chosen day at 12:00, and you can edit it."
        ),
    },
    {
        "id": "settings",
        "category": "settings",
        "questions_ru": [
            "как сменить язык",
            "как сменить валюту",
            "настройки",
            "как изменить часовой пояс",
        ],
        "questions_en": [
            "how to change language",
            "how to change currency",
            "settings",
            "timezone",
        ],
        "keywords": ["настройки", "settings", "валюта", "язык", "timezone", "часовой"],
        "answer_ru": (
            "Откройте /settings: можно сменить язык (ru/en), валюту, часовой пояс, включить/выключить кешбэк "
            "и другие опции."
        ),
        "answer_en": (
            "Open /settings: change language (ru/en), currency, timezone, toggle cashback, and other options."
        ),
    },
    {
        "id": "subscription",
        "category": "subscription",
        "questions_ru": [
            "что дает подписка",
            "зачем подписка",
            "подписка",
            "премиум",
        ],
        "questions_en": [
            "what does subscription give",
            "why subscription",
            "premium features",
        ],
        "keywords": ["подписка", "премиум", "premium", "subscription"],
        "answer_ru": (
            "Большинство функций доступны бесплатно! С подпиской (есть триал для новых): "
            "AI-ассистент — вопросы по статистике естественным языком (\"сколько потратил на еду в ноябре?\", \"какая самая большая трата?\"); "
            "учёт доходов; голосовой ввод; учёт кешбэка; семейный бюджет. "
            "Отчёты: с подпиской — в любое время, без подписки — приходят 1-го числа за прошлый месяц. "
            "/subscription — статус и оплата."
        ),
        "answer_en": (
            "Most features are free! Subscription (trial for new users) adds: "
            "AI assistant — ask about your stats naturally (\"how much did I spend on food in November?\", \"what's my biggest expense?\"); "
            "income tracking; voice input; cashback tracking; family budget. "
            "Reports: with subscription — anytime, without — sent on 1st of each month for previous month. "
            "/subscription — status and payment."
        ),
    },
    {
        "id": "limits",
        "category": "limits",
        "questions_ru": [
            "как установить лимит",
            "как поставить бюджет",
            "лимиты по категориям",
            "бюджет",
            "баланс",
        ],
        "questions_en": [
            "how to set limit",
            "how to set budget",
            "category limit",
            "spending cap",
            "balance",
        ],
        "keywords": ["лимит", "бюджет", "limit", "budget", "баланс", "balance"],
        "answer_ru": (
            "Лимиты пока не реализованы как отдельная функция. "
            "Но вы можете внести баланс или бюджет как доход: \"+40000 бюджет\". "
            "Тогда все расходы будут вычитаться и вы увидите текущий баланс в статистике."
        ),
        "answer_en": (
            "Limits are not yet implemented as a separate feature. "
            "But you can add balance or budget as income: \"+40000 budget\". "
            "All expenses will be subtracted and you'll see current balance in statistics."
        ),
    },
]


def get_faq_for_ai_context() -> str:
    """
    Build a compact FAQ snippet for AI prompts (English, trimmed).
    """
    lines: List[str] = ["BOT FAQ (short answers, respond in user's language):"]
    for entry in FAQ_DATA:
        question = entry["questions_en"][0] if entry["questions_en"] else entry["questions_ru"][0]
        answer = entry["answer_en"].replace("\n", " ")
        if len(answer) > 220:
            answer = answer[:220] + "..."
        lines.append(f"Q: {question}")
        lines.append(f"A: {answer}")
        lines.append("")
    return "\n".join(lines)
