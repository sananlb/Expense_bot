"""
Shared definitions and helpers for income categories.
"""
from typing import Optional, Dict

# ВАЖНО: Импортируем из централизованного модуля (включает ZWJ для композитных эмодзи)
from bot.utils.emoji_utils import strip_leading_emoji
# НОВАЯ СИСТЕМА: Импортируем централизованную функцию матчинга
from bot.utils.keyword_service import match_keyword_in_text


# ВАЖНО: Поле 'description' — краткое СМЫСЛОВОЕ описание границ категории (на английском,
# т.к. инструкции AI-промпта на английском). Оно попадает в промпт AI-категоризации.
# Не перечисляйте здесь примеры — для этого есть 'keywords'.
INCOME_CATEGORY_DEFINITIONS: Dict[str, Dict[str, object]] = {
    'salary': {
        'name_ru': '💼 Зарплата',
        'name_en': '💼 Salary',
        'description': 'Regular pay from the main job.',
        'keywords': ['зарплата', 'зп', 'salary', 'payroll', 'paycheck', 'wage', 'wages', 'salary payment'],
        'aliases': ['зарплата', 'salary', 'payroll', 'pay check', 'wage'],
    },
    'bonus': {
        'name_ru': '🎁 Премии и бонусы',
        'name_en': '🎁 Bonuses',
        'description': 'Extra payments from an employer on top of the regular salary.',
        'keywords': ['премия', 'бонус', 'bonus', 'premia', 'award', 'надбавка', 'премиальные'],
        'aliases': ['премия', 'премии', 'bonus', 'bonuses', 'award'],
    },
    'freelance': {
        'name_ru': '💻 Фриланс',
        'name_en': '💻 Freelance',
        'description': 'Money earned from side jobs, one-off projects or self-employment.',
        'keywords': ['фриланс', 'freelance', 'gig', 'contract', 'upwork', 'подработка', 'project', 'commission'],
        'aliases': ['фриланс', 'freelance', 'gig work', 'contract job'],
    },
    'investment': {
        'name_ru': '📈 Инвестиции',
        'name_en': '📈 Investments',
        'description': 'Returns from investments and financial assets.',
        'keywords': ['инвест', 'дивиденд', 'investment', 'investments', 'stock', 'shares', 'crypto', 'capital gain'],
        'aliases': ['инвестиции', 'investments', 'dividends', 'dividend', 'capital gains'],
    },
    'interest': {
        'name_ru': '🏦 Проценты по вкладам',
        'name_en': '🏦 Bank Interest',
        'description': 'Interest earned on bank deposits and savings accounts.',
        'keywords': ['процент', 'проценты', 'interest', 'bank interest', 'deposit interest', 'savings interest'],
        'aliases': ['проценты', 'interest', 'deposit interest', 'bank interest'],
    },
    'rent': {
        'name_ru': '🏠 Аренда недвижимости',
        'name_en': '🏠 Rent Income',
        'description': 'Money received from renting out property.',
        'keywords': ['аренда', 'сдача', 'rent', 'rental', 'tenant', 'landlord', 'lease'],
        'aliases': ['аренда', 'rent', 'rental income', 'rent income'],
    },
    'refund': {
        'name_ru': '💸 Возвраты и компенсации',
        'name_en': '💸 Refunds',
        'description': 'Money returned to the user: refunds, compensations, cashback.',
        'keywords': ['возврат', 'компенсация', 'refund', 'reimbursement', 'compensation', 'кешбек', 'кешбэк', 'cashback', 'cash back', 'rebate'],
        'aliases': ['возврат', 'refund', 'reimbursement', 'compensation', 'cashback', 'cash back', 'кешбэк', 'кешбек'],
    },
    'gift': {
        'name_ru': '🎉 Подарки',
        'name_en': '🎉 Gifts',
        'description': 'Money received as a gift.',
        'keywords': ['подарок', 'подарили', 'gift', 'present', 'donation'],
        'aliases': ['подарок', 'gift', 'present'],
    },
    'other': {
        'name_ru': '💰 Прочие доходы',
        'name_en': '💰 Other Income',
        'description': 'Use only when the income clearly fits no other category.',
        'keywords': ['доход', 'получил', 'поступление', 'income', 'other income', 'received', 'plus',
                     'баланс', 'бюджет', 'лимит', 'balance', 'budget', 'limit'],
        'aliases': ['other', 'прочие доходы', 'other income', 'income'],
    },
}

DEFAULT_INCOME_CATEGORY_KEY = 'other'


def get_income_category_display_name(category_key: str, language_code: str = 'ru') -> str:
    """Return the localized category name (with emoji) for the given key."""
    data = INCOME_CATEGORY_DEFINITIONS.get(category_key) or INCOME_CATEGORY_DEFINITIONS[DEFAULT_INCOME_CATEGORY_KEY]
    if language_code.lower().startswith('en'):
        return data['name_en']  # type: ignore[index]
    return data['name_ru']  # type: ignore[index]


def get_income_category_description(label: Optional[str]) -> Optional[str]:
    """Return the semantic description for a category label (for AI prompts).

    Матчинг намеренно консервативный — только точные имена и aliases, БЕЗ keywords:
    для кастомной категории неверное описание хуже, чем его отсутствие.
    """
    if not label:
        return None
    cleaned = strip_leading_emoji(label).lower()
    if not cleaned:
        return None

    for data in INCOME_CATEGORY_DEFINITIONS.values():
        potential_matches = {
            strip_leading_emoji(data['name_ru']).lower(),  # type: ignore[arg-type]
            strip_leading_emoji(data['name_en']).lower(),  # type: ignore[arg-type]
        }
        if cleaned in potential_matches:
            return data.get('description')  # type: ignore[return-value]

        for alias in data.get('aliases', []):  # type: ignore[union-attr]
            alias_lower = alias.lower()
            if alias_lower and (alias_lower == cleaned or alias_lower in cleaned or cleaned in alias_lower):
                return data.get('description')  # type: ignore[return-value]

    return None


def normalize_income_category_key(label: Optional[str]) -> Optional[str]:
    """Map a raw category label to a canonical category key."""
    if not label:
        return None
    cleaned = strip_leading_emoji(label).lower()
    if not cleaned:
        return None

    for key, data in INCOME_CATEGORY_DEFINITIONS.items():
        potential_matches = {
            strip_leading_emoji(data['name_ru']).lower(),
            strip_leading_emoji(data['name_en']).lower(),
        }

        if cleaned in potential_matches:
            return key

        for alias in data.get('aliases', []):
            alias_lower = alias.lower()
            if alias_lower and (alias_lower == cleaned or alias_lower in cleaned or cleaned in alias_lower):
                return key

        for keyword in data.get('keywords', []):
            keyword_lower = keyword.lower()
            if keyword_lower and (keyword_lower == cleaned or keyword_lower in cleaned or cleaned in keyword_lower):
                return key

    return None


def detect_income_category_key(text: str) -> Optional[str]:
    """Detect a category key by checking keywords against the text.

    2-уровневая проверка: exact (фраза целиком ±1 буква) + word (одиночное слово ±1 буква).
    Stop-words удаляются из keyword и text перед сравнением.
    Поддерживает склонения ("зарплата" совпадет с "зарплату", "зарплаты").
    """
    for key, data in INCOME_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_INCOME_CATEGORY_KEY:
            continue
        for keyword in data.get('keywords', []):
            matched, match_type = match_keyword_in_text(keyword, text)
            if matched:
                return key
    return None
