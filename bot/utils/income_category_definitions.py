"""
Shared definitions and helpers for income categories.
"""
from typing import Optional, Dict
import re

EMOJI_PREFIX_RE = re.compile(
    r'^[\U0001F000-\U0001F9FF'
    r'\U00002600-\U000027BF'
    r'\U0001F300-\U0001F64F'
    r'\U0001F680-\U0001F6FF'
    r'\u2600-\u27BF'
    r'\u2300-\u23FF'
    r'\u2B00-\u2BFF'
    r'\u26A0-\u26FF'
    r']+\s*',
    re.UNICODE
)


def strip_leading_emoji(value: Optional[str]) -> str:
    """Remove leading emoji characters from a category label."""
    if not value:
        return ''
    return EMOJI_PREFIX_RE.sub('', value).strip()


INCOME_CATEGORY_DEFINITIONS: Dict[str, Dict[str, object]] = {
    'salary': {
        'name_ru': '💼 Зарплата',
        'name_en': '💼 Salary',
        'keywords': ['зарплата', 'зп', 'salary', 'payroll', 'paycheck', 'wage', 'wages', 'salary payment'],
        'aliases': ['зарплата', 'salary', 'payroll', 'pay check', 'wage'],
        'income_type': 'salary',
    },
    'bonus': {
        'name_ru': '🎁 Премии и бонусы',
        'name_en': '🎁 Bonuses',
        'keywords': ['премия', 'бонус', 'bonus', 'premia', 'award', 'надбавка', 'премиальные'],
        'aliases': ['премия', 'премии', 'bonus', 'bonuses', 'award'],
        'income_type': 'bonus',
    },
    'freelance': {
        'name_ru': '💻 Фриланс',
        'name_en': '💻 Freelance',
        'keywords': ['фриланс', 'freelance', 'gig', 'contract', 'upwork', 'подработка', 'project', 'commission'],
        'aliases': ['фриланс', 'freelance', 'gig work', 'contract job'],
        'income_type': 'freelance',
    },
    'investment': {
        'name_ru': '📈 Инвестиции',
        'name_en': '📈 Investments',
        'keywords': ['инвест', 'дивиденд', 'investment', 'investments', 'stock', 'shares', 'crypto', 'capital gain'],
        'aliases': ['инвестиции', 'investments', 'dividends', 'dividend', 'capital gains'],
        'income_type': 'investment',
    },
    'interest': {
        'name_ru': '🏦 Проценты по вкладам',
        'name_en': '🏦 Bank Interest',
        'keywords': ['процент', 'проценты', 'interest', 'bank interest', 'deposit interest', 'savings interest'],
        'aliases': ['проценты', 'interest', 'deposit interest', 'bank interest'],
        'income_type': 'interest',
    },
    'rent': {
        'name_ru': '🏠 Аренда недвижимости',
        'name_en': '🏠 Rent Income',
        'keywords': ['аренда', 'сдача', 'rent', 'rental', 'tenant', 'landlord', 'lease'],
        'aliases': ['аренда', 'rent', 'rental income', 'rent income'],
        'income_type': 'other',
    },
    'refund': {
        'name_ru': '💸 Возвраты и компенсации',
        'name_en': '💸 Refunds',
        'keywords': ['возврат', 'компенсация', 'refund', 'reimbursement', 'compensation'],
        'aliases': ['возврат', 'refund', 'reimbursement', 'compensation'],
        'income_type': 'refund',
    },
    'cashback': {
        'name_ru': '💳 Кешбэк',
        'name_en': '💳 Cashback',
        'keywords': ['кешбек', 'кешбэк', 'cashback', 'cash back', 'rebate'],
        'aliases': ['cashback', 'cash back', 'кешбэк', 'кешбек'],
        'income_type': 'cashback',
    },
    'gift': {
        'name_ru': '🎉 Подарки',
        'name_en': '🎉 Gifts',
        'keywords': ['подарок', 'подарили', 'gift', 'present', 'donation'],
        'aliases': ['подарок', 'gift', 'present'],
        'income_type': 'gift',
    },
    'other': {
        'name_ru': '💰 Прочие доходы',
        'name_en': '💰 Other Income',
        'keywords': ['доход', 'получил', 'поступление', 'income', 'other income', 'received', 'plus'],
        'aliases': ['other', 'прочие доходы', 'other income', 'income'],
        'income_type': 'other',
    },
}

DEFAULT_INCOME_CATEGORY_KEY = 'other'


def get_income_category_display_name(category_key: str, language_code: str = 'ru') -> str:
    """Return the localized category name (with emoji) for the given key."""
    data = INCOME_CATEGORY_DEFINITIONS.get(category_key) or INCOME_CATEGORY_DEFINITIONS[DEFAULT_INCOME_CATEGORY_KEY]
    if language_code.lower().startswith('en'):
        return data['name_en']  # type: ignore[index]
    return data['name_ru']  # type: ignore[index]


def get_income_type(category_key: Optional[str]) -> str:
    """Return the income type associated with the category key."""
    if not category_key:
        return INCOME_CATEGORY_DEFINITIONS[DEFAULT_INCOME_CATEGORY_KEY]['income_type']  # type: ignore[index]
    data = INCOME_CATEGORY_DEFINITIONS.get(category_key)
    if not data:
        return INCOME_CATEGORY_DEFINITIONS[DEFAULT_INCOME_CATEGORY_KEY]['income_type']  # type: ignore[index]
    return data['income_type']  # type: ignore[index]


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
    """Detect a category key by checking keywords against the text."""
    text_lower = text.lower()
    for key, data in INCOME_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_INCOME_CATEGORY_KEY:
            continue
        for keyword in data.get('keywords', []):
            if keyword in text_lower:
                return key
    return None
