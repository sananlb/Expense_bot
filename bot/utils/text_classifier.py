"""
Классификатор текстовых сообщений для определения типа: record (трата) или chat
"""
import re
from typing import Tuple, List
import pymorphy3

# Инициализируем морфологический анализатор
morph = pymorphy3.MorphAnalyzer()

# Вопросительные слова в начале предложения - это чат
QUESTION_WORDS = ['что', 'как', 'где', 'когда', 'почему', 'зачем', 'кто', 'какой', 'какая', 'какие', 'сколько']

# Слова-глаголы которые делают сообщение запросом (чат)
CHAT_ACTION_WORDS = [
    'покажи', 'найди', 'выведи', 'сравни',
    'покаж', 'найд', 'вывед', 'сравн'
]

# Предлоги и союзы для фильтрации
STOP_WORDS = [
    'и', 'в', 'на', 'с', 'у', 'к', 'за', 'из', 'от', 'до', 'по', 'о', 'об',
    'а', 'но', 'да', 'или', 'либо', 'то', 'не', 'ни',
    'это', 'эта', 'эти', 'тот', 'та', 'те',
]


def is_noun_phrase(text: str) -> bool:
    """
    Проверяет, является ли текст существительным или 
    фразой "прилагательное + существительное"
    """
    words = text.split()
    
    # Убираем стоп-слова
    meaningful_words = [w for w in words if w.lower() not in STOP_WORDS]
    
    if not meaningful_words:
        return False
    
    # Анализируем части речи
    parsed_words = []
    for word in meaningful_words:
        parsed = morph.parse(word)[0]
        parsed_words.append(parsed)
    
    # Одно слово - проверяем, существительное ли
    if len(parsed_words) == 1:
        pos = parsed_words[0].tag.POS
        return pos == 'NOUN'  # Существительное
    
    # Два слова - проверяем паттерн "прилагательное + существительное"
    if len(parsed_words) == 2:
        first_pos = parsed_words[0].tag.POS
        second_pos = parsed_words[1].tag.POS
        
        # Прилагательное + существительное
        if first_pos in ['ADJF', 'ADJS', 'PRTF', 'PRTS'] and second_pos == 'NOUN':
            return True
        # Существительное + существительное (например, "кофе латте")
        if first_pos == 'NOUN' and second_pos == 'NOUN':
            return True
        # Существительное + число (например, "бензин 95")
        if first_pos == 'NOUN' and second_pos == 'NUMR':
            return True
    
    # Три слова - может быть "прилагательное + прилагательное + существительное"
    if len(parsed_words) == 3:
        # Проверяем, что последнее слово - существительное
        if parsed_words[-1].tag.POS == 'NOUN':
            # И хотя бы одно из первых - прилагательное
            if any(p.tag.POS in ['ADJF', 'ADJS', 'PRTF', 'PRTS'] for p in parsed_words[:-1]):
                return True
    
    return False


def classify_message(text: str) -> Tuple[str, float]:
    """
    Классифицирует сообщение как 'record' (трата) или 'chat'

    Новая упрощенная логика:
    1. Если есть '?' → chat
    2. Если начинается с вопросительного слова (что, как, где...) → chat
    3. Если есть слова-действия (покажи, найди, выведи) → chat
    4. Иначе → record (трата)

    Returns:
        Tuple[str, float]: (тип сообщения, уверенность от 0 до 1)
    """
    text = text.strip()
    text_lower = text.lower()

    # 1. ПРИОРИТЕТ: Вопросительный знак → всегда чат
    if text.endswith('?'):
        return 'chat', 1.0

    # 2. Проверяем первое слово - вопросительное слово?
    words = text_lower.split()
    if words and words[0] in QUESTION_WORDS:
        return 'chat', 0.95

    # 3. Проверяем наличие слов-действий (покажи, найди, выведи)
    for action_word in CHAT_ACTION_WORDS:
        if action_word in text_lower:
            return 'chat', 0.9

    # 4. ВСЕ ОСТАЛЬНОЕ → record (трата)
    # Примеры: "Статистика", "Отчет", "Продукты 500", "Кофе", "Бензин"
    return 'record', 0.8


def get_expense_indicators(text: str) -> List[str]:
    """
    Возвращает список индикаторов, указывающих на то, что это трата
    """
    indicators = []

    # Проверяем наличие чисел
    numbers = re.findall(r'\d+', text)
    if numbers:
        indicators.append(f"числа: {', '.join(numbers)}")

    # Проверяем тип фразы
    if is_noun_phrase(text):
        indicators.append("фраза-существительное")

    return indicators