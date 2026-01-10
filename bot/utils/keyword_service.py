"""
Универсальный модуль для работы с keywords расходов и доходов.
Единый код для обучения, поиска и нормализации keywords.

Этот модуль решает проблему ложных срабатываний при keyword matching:
- Вместо поиска отдельных слов ("тест" в "в тесте") используется сопоставление полных фраз
- Поддерживается 2 уровня проверки: точное совпадение + совпадение начала фразы
- Единая нормализация для расходов и доходов
"""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def normalize_keyword_text(text: str) -> str:
    """
    Единая нормализация текста для keywords.
    Используется при сохранении И при поиске.

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

    # 2. Удаляем эмодзи (используем готовую утилиту из проекта)
    try:
        from bot.utils.emoji_utils import EMOJI_PREFIX_RE
        # EMOJI_PREFIX_RE только для начала строки, поэтому удаляем все эмодзи универсально
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
    except ImportError:
        # Fallback: простое удаление эмодзи через базовый regex
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # эмоции
            "\U0001F300-\U0001F5FF"  # символы
            "\U0001F680-\U0001F6FF"  # транспорт
            "\U0001F1E0-\U0001F1FF"  # флаги
            "\U00002700-\U000027BF"  # разное
            "]+",
            flags=re.UNICODE
        )
        normalized = emoji_pattern.sub('', normalized)

    # 3. Удаляем пунктуацию (кроме дефиса внутри слов)
    # Оставляем буквы (кириллица + латиница), цифры, пробелы, дефис
    normalized = re.sub(r'[^\w\s\-]', ' ', normalized, flags=re.UNICODE)
    # Удаляем дефисы на границах слов (оставляем только внутри)
    normalized = re.sub(r'(?<!\w)-|-(?!\w)', ' ', normalized)

    # 4. Trim + схлопывание пробелов
    normalized = ' '.join(normalized.split())

    return normalized


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
    1. Нормализует слово
    2. УДАЛЯЕТ слово из ВСЕХ категорий пользователя (расходов или доходов)
    3. Создает/получает слово в целевой категории
    4. Возвращает (keyword, created, removed_count)

    Args:
        profile: Профиль пользователя
        category: Целевая категория (ExpenseCategory или IncomeCategory)
        word: Ключевое слово
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

    # Нормализуем слово
    normalized_word = normalize_keyword_text(word)

    if not normalized_word or len(normalized_word) < 3:
        # Создаем пустой объект для совместимости (не сохраняем в БД)
        logger.debug(f"Keyword too short: '{normalized_word}', skipping")
        return None, False, 0

    # ОГРАНИЧЕНИЕ max_length=100 (CategoryKeyword.keyword / IncomeCategoryKeyword.keyword)
    # Обрезаем по словам, чтобы не разрывать слова посередине
    if len(normalized_word) > 100:
        # Обрезаем до 100 символов
        truncated = normalized_word[:100]
        # Находим последний пробел, чтобы не разрывать слово
        last_space = truncated.rfind(' ')
        if last_space > 0:
            normalized_word = truncated[:last_space].strip()
        else:
            # Если нет пробелов - обрезаем жестко
            normalized_word = truncated.strip()

        logger.debug(
            f"Keyword truncated from {len(word)} to {len(normalized_word)} chars: "
            f"'{normalized_word}...'"
        )

    # СТРОГАЯ УНИКАЛЬНОСТЬ: удаляем слово из ВСЕХ категорий пользователя
    # БЕЗ фильтрации по языку - т.к. поле не используется в production коде
    deleted = KeywordModel.objects.filter(
        category__profile=profile,
        keyword=normalized_word
    ).delete()

    removed_count = deleted[0] if deleted else 0

    if removed_count > 0:
        logger.debug(
            f"Removed keyword '{normalized_word}' from {removed_count} "
            f"{'income' if is_income else 'expense'} categories to maintain uniqueness"
        )

    # Создаем/получаем keyword в целевой категории
    # БЕЗ указания языка - поле не используется
    keyword, created = KeywordModel.objects.get_or_create(
        category=category,
        keyword=normalized_word,
        defaults={'usage_count': 0}
    )

    return keyword, created, removed_count


def match_keyword_in_text(
    keyword: str,
    text: str,
    min_words: int = 2,
    max_prefix_words: int = 3
) -> Tuple[bool, str]:
    """
    Проверяет совпадение keyword с текстом (3 уровня).

    Уровни проверки:
    1. Точное совпадение полной фразы
    2. Совпадение начала фразы (первые 2-3 слова, если >= 2 слов)
    3. Совпадение со склонениями (для одиночных keywords >= 4 символов с первым словом текста)

    Args:
        keyword: Сохраненный keyword (нормализованный)
        text: Текст для проверки (будет нормализован)
        min_words: Минимум слов для prefix matching (по умолчанию 2)
        max_prefix_words: Максимум слов для prefix (по умолчанию 3)

    Returns:
        (matched, match_type):
            - matched: True если есть совпадение, False иначе
            - match_type: "exact", "prefix", "inflection", или "none"

    Examples:
        >>> match_keyword_in_text("сосиска в тесте и чай", "Сосиска в тесте и чай 390")
        (True, "prefix")  # текст содержит "390" в конце, поэтому это prefix совпадение
        >>> match_keyword_in_text("сосиска в тесте и чай", "сосиска в тесте и чай")
        (True, "exact")  # полное совпадение без дополнительных слов
        >>> match_keyword_in_text("зарплата", "Зарплату перевели")
        (True, "inflection")  # склонение одиночного keyword с первым словом текста
        >>> match_keyword_in_text("зарплата", "Зарплата от компании")
        (True, "inflection")  # одиночный keyword матчит первое слово фразы
        >>> match_keyword_in_text("долг за тест", "Тест 500")
        (False, "none")  # начало НЕ совпадает
    """
    # Нормализуем оба текста
    normalized_keyword = normalize_keyword_text(keyword)
    normalized_text = normalize_keyword_text(text)

    if not normalized_keyword or not normalized_text:
        return False, "none"

    # ЗАЩИТА: Минимум 3 символа для keyword (предотвращает "в", "на")
    if len(normalized_keyword) < 3:
        return False, "none"

    # УРОВЕНЬ 1: Точное совпадение полной фразы
    if normalized_text == normalized_keyword:
        return True, "exact"

    text_words = normalized_text.split()
    keyword_words = normalized_keyword.split()

    # УРОВЕНЬ 2: Совпадение начала фразы (первые 2-3 слова)
    # Проверяем только если в тексте >= min_words слов
    if len(text_words) >= min_words and len(keyword_words) >= min_words:
        # Берем первые N слов (2-3)
        prefix_length = min(max_prefix_words, len(text_words), len(keyword_words))
        text_prefix = ' '.join(text_words[:prefix_length])
        keyword_prefix = ' '.join(keyword_words[:prefix_length])

        # Защита от коротких слов (< 3 символа)
        if len(text_prefix) >= 3 and text_prefix == keyword_prefix:
            return True, "prefix"

    # УРОВЕНЬ 3: Совпадение со склонениями (для одиночных keywords)
    # Применяется ТОЛЬКО если keyword = одно слово >= 4 символов
    # Проверяем склонение с ЛЮБЫМ словом текста >= 4 символов
    # Это позволяет "зарплата" матчить "перевели зарплату" или "зарплата от компании"
    if len(keyword_words) == 1 and len(normalized_keyword) >= 4:
        for text_word in text_words:
            if len(text_word) >= 4:
                # Берем ОСНОВУ слова (без окончания) - убираем последние 2 символа от меньшего слова
                min_len = min(len(normalized_keyword), len(text_word))
                # Основа = минимум минус 2 символа (окончание), но не меньше 4
                stem_len = max(4, min_len - 2)

                # Проверяем что основы совпадают
                keyword_stem = normalized_keyword[:stem_len]
                text_stem = text_word[:stem_len]

                if keyword_stem == text_stem:
                    # Разница в длине не больше 2 символов (окончание)
                    diff = abs(len(normalized_keyword) - len(text_word))
                    if diff <= 2:
                        return True, "inflection"

    return False, "none"
