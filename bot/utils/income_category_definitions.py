"""
Shared definitions and helpers for income categories.
"""
import re
from typing import Optional, Dict

# ВАЖНО: Импортируем из централизованного модуля (включает ZWJ для композитных эмодзи)
from bot.utils.emoji_utils import strip_leading_emoji


def _keyword_matches_in_text(keyword: str, text: str) -> bool:
    """
    Проверяет есть ли ключевое слово в тексте как ЦЕЛОЕ СЛОВО с учетом склонений.
    Локальная копия функции для избежания циклического импорта.

    Защита от ложных срабатываний:
    - "95" НЕ совпадёт с "9500"
    - "зп" НЕ совпадёт с "инвестзп"
    - "зарплата" совпадёт с "зарплату", "зарплаты" (окончание <= 2 символа)
    """
    if not keyword or not text:
        return False
    keyword_lower = keyword.lower().strip()
    text_lower = text.lower()
    text_words = re.findall(r'[\wа-яёА-ЯЁ\-]+', text_lower)
    for word in text_words:
        if word == keyword_lower:
            return True
        if word.startswith(keyword_lower):
            ending_length = len(word) - len(keyword_lower)
            if ending_length <= 2:
                return True
    return False


INCOME_CATEGORY_DEFINITIONS: Dict[str, Dict[str, object]] = {
    'salary': {
        'name_ru': '💼 Зарплата',
        'name_en': '💼 Salary',
        'keywords': ['зарплата', 'зп', 'salary', 'payroll', 'paycheck', 'wage', 'wages', 'salary payment'],
        'aliases': ['зарплата', 'salary', 'payroll', 'pay check', 'wage'],
    },
    'bonus': {
        'name_ru': '🎁 Премии и бонусы',
        'name_en': '🎁 Bonuses',
        'keywords': ['премия', 'бонус', 'bonus', 'premia', 'award', 'надбавка', 'премиальные'],
        'aliases': ['премия', 'премии', 'bonus', 'bonuses', 'award'],
    },
    'freelance': {
        'name_ru': '💻 Фриланс',
        'name_en': '💻 Freelance',
        'keywords': ['фриланс', 'freelance', 'gig', 'contract', 'upwork', 'подработка', 'project', 'commission'],
        'aliases': ['фриланс', 'freelance', 'gig work', 'contract job'],
    },
    'investment': {
        'name_ru': '📈 Инвестиции',
        'name_en': '📈 Investments',
        'keywords': ['инвест', 'дивиденд', 'investment', 'investments', 'stock', 'shares', 'crypto', 'capital gain'],
        'aliases': ['инвестиции', 'investments', 'dividends', 'dividend', 'capital gains'],
    },
    'interest': {
        'name_ru': '🏦 Проценты по вкладам',
        'name_en': '🏦 Bank Interest',
        'keywords': ['процент', 'проценты', 'interest', 'bank interest', 'deposit interest', 'savings interest'],
        'aliases': ['проценты', 'interest', 'deposit interest', 'bank interest'],
    },
    'rent': {
        'name_ru': '🏠 Аренда недвижимости',
        'name_en': '🏠 Rent Income',
        'keywords': ['аренда', 'сдача', 'rent', 'rental', 'tenant', 'landlord', 'lease'],
        'aliases': ['аренда', 'rent', 'rental income', 'rent income'],
    },
    'refund': {
        'name_ru': '💸 Возвраты и компенсации',
        'name_en': '💸 Refunds',
        'keywords': ['возврат', 'компенсация', 'refund', 'reimbursement', 'compensation', 'кешбек', 'кешбэк', 'cashback', 'cash back', 'rebate'],
        'aliases': ['возврат', 'refund', 'reimbursement', 'compensation', 'cashback', 'cash back', 'кешбэк', 'кешбек'],
    },
    'gift': {
        'name_ru': '🎉 Подарки',
        'name_en': '🎉 Gifts',
        'keywords': ['подарок', 'подарили', 'gift', 'present', 'donation'],
        'aliases': ['подарок', 'gift', 'present'],
    },
    'other': {
        'name_ru': '💰 Прочие доходы',
        'name_en': '💰 Other Income',
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

    ВАЖНО: Используем проверку целого слова вместо подстроки,
    чтобы "95" не совпадало с "9500" и т.п.
    """
    for key, data in INCOME_CATEGORY_DEFINITIONS.items():
        if key == DEFAULT_INCOME_CATEGORY_KEY:
            continue
        for keyword in data.get('keywords', []):
            if _keyword_matches_in_text(keyword, text):
                return key
    return None
