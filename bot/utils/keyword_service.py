"""
Универсальный модуль для работы с keywords расходов и доходов.
Единый код для обучения, поиска и нормализации keywords.

Логика поиска:
- Уровень 1 (Exact): Точное совпадение полной фразы (±1 буква на всю фразу)
- Уровень 2 (Word): Поиск каждого слова текста в keywords (±1 буква на слово)

При сохранении и поиске из текста удаляются мусорные слова (STOP_WORDS).
"""
import re
import logging
from typing import Tuple, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# STOP_WORDS - мусорные слова, удаляемые при сохранении и поиске keywords
# =============================================================================

STOP_WORDS: Set[str] = {
    # === Предлоги и союзы (RU) ===
    'и', 'в', 'на', 'с', 'за', 'по', 'для', 'от', 'до', 'из',
    'или', 'но', 'а', 'к', 'у', 'о', 'об', 'под', 'над',
    'при', 'без', 'между', 'через', 'около', 'ради', 'вместо',

    # === Предлоги и союзы (EN) ===
    'and', 'or', 'to', 'for', 'from', 'with', 'at', 'by', 'in', 'on',
    'the', 'a', 'an', 'of', 'as', 'is', 'it', 'if', 'so',

    # === Глаголы действия (RU) ===
    'купил', 'купила', 'купили', 'купить',
    'взял', 'взяла', 'взяли', 'взять',
    'потратил', 'потратила', 'потратили', 'потратить',
    'оплатил', 'оплатила', 'оплатили', 'оплатить',
    'заплатил', 'заплатила', 'заплатили', 'заплатить',
    'заказал', 'заказала', 'заказали', 'заказать',
    'приобрел', 'приобрела', 'приобрели', 'приобрести',
    'съел', 'съела', 'съели', 'съесть',
    'выпил', 'выпила', 'выпили', 'выпить',
    'сходил', 'сходила', 'сходили', 'сходить',
    'отдал', 'отдала', 'отдали', 'отдать',
    'внес', 'внесла', 'внесли', 'внести',
    'перевел', 'перевела', 'перевели', 'перевести',
    'отправил', 'отправила', 'отправили', 'отправить',
    'положил', 'положила', 'положили', 'положить',
    'снял', 'сняла', 'сняли', 'снять',
    'получил', 'получила', 'получили', 'получить',

    # === Глаголы действия (EN) ===
    'bought', 'buy', 'paid', 'pay', 'spent', 'spend',
    'got', 'get', 'took', 'take', 'ordered', 'order',
    'had', 'have', 'made', 'make',

    # === Временные слова (RU) ===
    'вчера', 'сегодня', 'завтра', 'утром', 'вечером', 'днем', 'ночью',
    'позавчера', 'послезавтра', 'недавно', 'давно', 'после', 'перед', 'до',

    # === Временные слова (EN) ===
    'yesterday', 'today', 'tomorrow', 'morning', 'evening', 'night',
    'recently', 'ago',

    # === Местоимения (RU) ===
    'я', 'мне', 'мной', 'мой', 'моя', 'мое', 'мои',
    'себе', 'себя', 'собой',
    'он', 'она', 'оно', 'они', 'ему', 'ей', 'им',
    'мы', 'нам', 'нас', 'наш', 'наша', 'наши',

    # === Местоимения (EN) ===
    'i', 'me', 'my', 'myself', 'mine',
    'you', 'your', 'yourself', 'yours',
    'he', 'she', 'it', 'they', 'we', 'us', 'our',

    # === Валюты - коды (все доступные в боте) ===
    'rub', 'usd', 'eur', 'gbp', 'cny', 'chf', 'inr', 'try', 'jpy',
    'ars', 'cop', 'pen', 'clp', 'mxn', 'brl', 'aed',
    'kzt', 'uah', 'byn', 'byr', 'uzs', 'amd', 'azn', 'kgs', 'tjs', 'tmt', 'mdl', 'gel',

    # === Валюты - названия (RU) ===
    'рубль', 'рубля', 'рублей', 'руб',
    'доллар', 'доллара', 'долларов', 'долл',
    'евро',
    'фунт', 'фунта', 'фунтов',
    'юань', 'юаня', 'юаней',
    'франк', 'франка', 'франков',
    'рупия', 'рупии', 'рупий', 'рупи',
    'лира', 'лиры', 'лир',
    'йена', 'йены', 'йен', 'иена', 'иены', 'иен',
    'тенге', 'теньге', 'тнг', 'тг',
    'гривна', 'гривны', 'гривен', 'грн',
    'сум', 'сума', 'сумов',
    'драм', 'драма', 'драмов',
    'манат', 'маната', 'манатов', 'манаты',
    # 'сом' убран — конфликт с рыбой "сом"
    'сомони',
    'лей', 'лея', 'леев', 'леи',
    'лари',
    'дирхам', 'дирхама', 'дирхамов', 'дирхамы', 'дирхаме',
    'реал', 'реала', 'реалов', 'реалы',
    'песо',
    # 'соль' убран — конфликт с продуктом "соль"
    'солей',
    # Прилагательные стран (для «500 мексиканских» и т.п.)
    'аргентинских', 'аргентинское', 'аргентинский',
    'колумбийских', 'колумбийское', 'колумбийский',
    'перуанских', 'перуанское', 'перуанский',
    'чилийских', 'чилийское', 'чилийский',
    'мексиканских', 'мексиканское', 'мексиканский',
    'бразильских', 'бразильское', 'бразильский',

    # === Валюты - названия (EN) ===
    'dollar', 'dollars', 'buck', 'bucks',
    'euro', 'euros',
    'pound', 'pounds', 'sterling',
    'yuan', 'renminbi', 'rmb',
    'franc', 'francs',
    'rupee', 'rupees',
    'lira', 'liras',
    'yen',
    'peso', 'pesos',
    'real', 'reals',
    'tenge',
    'hryvnia', 'hryvnya',
    # 'som', 'soum' убраны — конфликт с рыбой
    'somoni',
    'manat',
    'dram',
    'lari',
    'lei',
    'dirham', 'dirhams',
    'sol',

    # === Числительные и единицы ===
    'тыс', 'тысяч', 'тысячи', 'тысячу',
    'млн', 'миллион', 'миллиона', 'миллионов',
    'thousand', 'million', 'billion',
    'шт', 'штук', 'штуки',
}


def normalize_keyword_text(text: str) -> str:
    """
    Базовая нормализация текста для keywords.
    НЕ удаляет stop words - это делает отдельная функция.

    Args:
        text: Исходный текст (description или поисковый запрос)

    Returns:
        Нормализованный текст (lowercase, trim, без пунктуации/эмодзи)

    Examples:
        >>> normalize_keyword_text("  Сосиска в ТЕСТЕ и чай  ")
        "сосиска в тесте и чай"
        >>> normalize_keyword_text("Кофе, чай")
        "кофе чай"
        >>> normalize_keyword_text("🍕 Пицца!")
        "пицца"
    """
    if not text:
        return ""

    # 1. Lowercase
    normalized = text.lower()

    # 2. Удаляем эмодзи
    emoji_pattern = re.compile(
        r'[\U0001F000-\U0001F9FF'  # Emoticons, symbols, pictographs
        r'\U00002600-\U000027BF'    # Miscellaneous Symbols
        r'\U0001F300-\U0001F64F'    # Miscellaneous Symbols and Pictographs
        r'\U0001F680-\U0001F6FF'    # Transport and Map Symbols
        r'\u2600-\u27BF'            # Miscellaneous Symbols (compact)
        r'\u2300-\u23FF'            # Miscellaneous Technical
        r'\u2B00-\u2BFF'            # Miscellaneous Symbols and Arrows
        r'\u26A0-\u26FF'            # Miscellaneous Symbols
        r'\uFE00-\uFE0F'            # Variation Selectors
        r'\U000E0100-\U000E01EF'    # Variation Selectors Supplement
        r'\u200d'                   # Zero-Width Joiner (ZWJ)
        r'\ufe0f'                   # Variation Selector-16
        r']+',
        flags=re.UNICODE
    )
    normalized = emoji_pattern.sub('', normalized)

    # 3. Удаляем пунктуацию и валютные символы
    # Оставляем буквы (кириллица + латиница), цифры, пробелы, дефис внутри слов
    # Числа НЕ удаляем — они могут быть частью названия ("бензин 95", "iPhone 15")
    normalized = re.sub(r'[^\w\s\-]', ' ', normalized, flags=re.UNICODE)
    # Удаляем дефисы на границах слов (оставляем только внутри)
    normalized = re.sub(r'(?<!\w)-|-(?!\w)', ' ', normalized)

    # 4. Trim + схлопывание пробелов
    normalized = ' '.join(normalized.split())

    return normalized


def remove_stop_words(text: str) -> str:
    """
    Удаляет мусорные слова из текста.

    Args:
        text: Нормализованный текст (lowercase)

    Returns:
        Текст без stop words

    Examples:
        >>> remove_stop_words("купил трухлявые консервы вчера")
        "трухлявые консервы"
        >>> remove_stop_words("я взял кофе за 200 рублей")
        "кофе 200"
    """
    if not text:
        return ""

    words = text.split()
    filtered = [w for w in words if w not in STOP_WORDS and len(w) >= 2]
    return ' '.join(filtered)


def prepare_keyword_for_save(text: str) -> str:
    """
    Подготавливает текст для сохранения как keyword.
    Нормализует, удаляет stop words, возвращает ФРАЗУ ЦЕЛИКОМ.

    Args:
        text: Исходный текст (description)

    Returns:
        Очищенный keyword для сохранения в БД.
        Пустая строка если фраза слишком длинная (>4 слов после очистки).

    Examples:
        >>> prepare_keyword_for_save("Вчера купил трухлявые консервы")
        "трухлявые консервы"
        >>> prepare_keyword_for_save("купил кофе в старбаксе")
        "кофе старбаксе"
        >>> prepare_keyword_for_save("играл с друзьями в КС после школы 300 рублей")
        ""  # Слишком длинная фраза — игнорируем
    """
    normalized = normalize_keyword_text(text)
    cleaned = remove_stop_words(normalized)

    # Длинные фразы (>4 слов) игнорируем — они слишком специфичны
    # и случайные слова ("друзьями", "школы") сломают логику
    words = cleaned.split()
    if len(words) > 4:
        return ""

    return cleaned


def words_match_with_inflection(word1: str, word2: str) -> bool:
    """
    Проверяет совпадение двух слов с учётом склонений (±1 буква).

    Args:
        word1: Первое слово
        word2: Второе слово

    Returns:
        True если слова совпадают или отличаются на 1 букву

    Examples:
        >>> words_match_with_inflection("зарплата", "зарплату")
        True
        >>> words_match_with_inflection("кофе", "кофе")
        True
        >>> words_match_with_inflection("кофе", "косой")
        False
        >>> words_match_with_inflection("кб", "кб")
        True  # 2-буквенные: только exact match
        >>> words_match_with_inflection("кб", "кв")
        False  # 2-буквенные: ±1 буква НЕ допускается
    """
    if word1 == word2:
        return True

    # Минимум 2 символа для сравнения
    if len(word1) < 2 or len(word2) < 2:
        return False

    # Для слов до 3 букв включительно — только exact match, без ±1 буквы
    # Это защита от ложных срабатываний: "лор" не должен матчить "лар", "кб" не должен матчить "кв" и т.д.
    if len(word1) <= 3 or len(word2) <= 3:
        return False  # Уже проверили exact match выше

    diff = abs(len(word1) - len(word2))

    # Если разница в длине > 1 символа - не совпадение
    if diff > 1:
        return False

    # Если длина одинаковая - считаем отличающиеся буквы
    if diff == 0:
        mismatches = sum(1 for a, b in zip(word1, word2) if a != b)
        return mismatches <= 1

    # Если разница ровно 1 символ
    shorter = word1 if len(word1) < len(word2) else word2
    longer = word2 if len(word1) < len(word2) else word1

    # Подсчитываем несовпадения на одинаковых позициях + 1 за лишний символ
    mismatches = sum(1 for i, c in enumerate(shorter) if c != longer[i]) + 1
    return mismatches <= 1


def match_keyword_in_text(
    keyword: str,
    text: str,
) -> Tuple[bool, str]:
    """
    Проверяет совпадение keyword с текстом (2 уровня).

    ВАЖНО: Keyword из БД сравнивается как есть (уже очищен при сохранении).
           Text очищается от stop words перед сравнением.

    Уровни проверки:
    1. Exact: Точное совпадение очищенной фразы (±1 буква на всю фразу)
    2. Word: Каждое слово очищенного текста ищем в keywords как отдельное слово (±1 буква)

    Args:
        keyword: Сохраненный keyword из БД (уже нормализованный и очищенный)
        text: Текст для проверки (будет нормализован и очищен от stop words)

    Returns:
        (matched, match_type):
            - matched: True если есть совпадение, False иначе
            - match_type: "exact", "word", или "none"

    Examples:
        >>> match_keyword_in_text("трухлявые консервы", "Купил трухлявые консервы вчера")
        (True, "exact")  # после очистки: "трухлявые консервы" == "трухлявые консервы"

        >>> match_keyword_in_text("консервы", "Купил трухлявые консервы вчера")
        (True, "word")  # keyword "консервы" найден как отдельное слово

        >>> match_keyword_in_text("зарплата", "Мне перевели зарплату")
        (True, "word")  # "зарплата" ~= "зарплату" (±1 буква)

        >>> match_keyword_in_text("трухлявые консервы", "Трухлявые просроченные консервы")
        (False, "none")  # фраза не совпадает, а "трухлявые консервы" != одному слову
    """
    # Нормализуем и очищаем keyword от stop words
    # (на случай если передан не из БД, например название категории "Кафе и рестораны")
    normalized_keyword = normalize_keyword_text(keyword)
    cleaned_keyword = remove_stop_words(normalized_keyword)

    # Нормализуем и очищаем текст от stop words
    normalized_text = normalize_keyword_text(text)
    cleaned_text = remove_stop_words(normalized_text)

    if not cleaned_keyword or not cleaned_text:
        return False, "none"

    # ЗАЩИТА: Минимум 2 символа для keyword (для кб, вв, зп и т.д.)
    # 2-буквенные keywords матчатся только exact, без ±1 буквы
    if len(cleaned_keyword) < 2:
        return False, "none"

    # =================================================================
    # УРОВЕНЬ 1: Exact - точное совпадение фразы (±1 буква на всю фразу)
    # =================================================================
    if cleaned_text == cleaned_keyword:
        return True, "exact"

    # Проверяем ±1 букву для всей фразы (для коротких фраз)
    if len(cleaned_keyword) <= 15:  # Для фраз до 15 символов
        if words_match_with_inflection(cleaned_text, cleaned_keyword):
            return True, "exact"

    # =================================================================
    # УРОВЕНЬ 2: Word - поиск keyword как отдельного слова в тексте
    # =================================================================
    # Применяется только для одиночных keywords (не фраз)
    keyword_words = cleaned_keyword.split()

    if len(keyword_words) == 1:
        # Keyword - одно слово, ищем его в любом месте текста
        text_words = cleaned_text.split()

        for text_word in text_words:
            if words_match_with_inflection(cleaned_keyword, text_word):
                return True, "word"

    return False, "none"


def ensure_unique_keyword(
    profile,  # Profile
    category,  # Union[ExpenseCategory, IncomeCategory]
    word: str,
    is_income: bool = False
) -> Tuple[Optional[object], bool, int]:
    """
    Универсальная функция для обеспечения уникальности keywords.
    Работает и для расходов (CategoryKeyword), и для доходов (IncomeCategoryKeyword).

    ВАЖНО: Одно слово может быть только в ОДНОЙ категории!

    Алгоритм:
    1. Нормализует и очищает слово от stop words
    2. УДАЛЯЕТ слово из ВСЕХ категорий пользователя (расходов или доходов)
    3. Создает/получает слово в целевой категории
    4. Возвращает (keyword, created, removed_count)

    Args:
        profile: Профиль пользователя
        category: Целевая категория (ExpenseCategory или IncomeCategory)
        word: Ключевое слово или фраза
        is_income: True для доходов, False для расходов

    Returns:
        (keyword, created, removed_count):
            - keyword: объект CategoryKeyword или IncomeCategoryKeyword (или None если слово короче 3 символов)
            - created: True если слово создано, False если существовало
            - removed_count: количество удаленных дубликатов

    Note:
        Поле 'language' игнорируется т.к. не используется в фильтрации.
        CategoryKeyword имеет это поле в схеме, но код его не проверяет.
        IncomeCategoryKeyword вообще не имеет поля language.
    """
    from expenses.models import CategoryKeyword, IncomeCategoryKeyword

    # Выбираем модель в зависимости от типа
    KeywordModel = IncomeCategoryKeyword if is_income else CategoryKeyword

    # Нормализуем и очищаем от stop words
    cleaned_word = prepare_keyword_for_save(word)

    if not cleaned_word or len(cleaned_word) < 3:
        # Слово слишком короткое после очистки
        logger.debug(f"Keyword too short after cleaning: '{word}' -> '{cleaned_word}', skipping")
        return None, False, 0

    # ОГРАНИЧЕНИЕ max_length=100 (CategoryKeyword.keyword / IncomeCategoryKeyword.keyword)
    # Обрезаем по словам, чтобы не разрывать слова посередине
    if len(cleaned_word) > 100:
        # Обрезаем до 100 символов
        truncated = cleaned_word[:100]
        # Находим последний пробел, чтобы не разрывать слово
        last_space = truncated.rfind(' ')
        if last_space > 0:
            cleaned_word = truncated[:last_space].strip()
        else:
            # Если нет пробелов - обрезаем жестко
            cleaned_word = truncated.strip()

        logger.debug(
            f"Keyword truncated from {len(word)} to {len(cleaned_word)} chars: "
            f"'{cleaned_word}...'"
        )

    # СТРОГАЯ УНИКАЛЬНОСТЬ: удаляем слово из ВСЕХ категорий пользователя
    # БЕЗ фильтрации по языку - т.к. поле не используется в production коде
    deleted = KeywordModel.objects.filter(
        category__profile=profile,
        keyword=cleaned_word
    ).delete()

    removed_count = deleted[0] if deleted else 0

    if removed_count > 0:
        logger.debug(
            f"Removed keyword '{cleaned_word}' from {removed_count} "
            f"{'income' if is_income else 'expense'} categories to maintain uniqueness"
        )

    # Создаем/получаем keyword в целевой категории
    # БЕЗ указания языка - поле не используется
    keyword, created = KeywordModel.objects.get_or_create(
        category=category,
        keyword=cleaned_word,
        defaults={'usage_count': 0}
    )

    return keyword, created, removed_count
