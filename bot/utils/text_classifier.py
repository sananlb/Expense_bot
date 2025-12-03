"""
Классификатор текстовых сообщений для определения типа: record (трата) или chat
"""
import re
from typing import Tuple, List
import pymorphy3

# Инициализируем морфологический анализатор
morph = pymorphy3.MorphAnalyzer()

# Паттерны для определения вопросов
QUESTION_PATTERNS = [
    r'\?$',  # Заканчивается вопросительным знаком
    r'^(что|как|где|когда|почему|зачем|кто|какой|какая|какие|сколько)\s',  # Вопросительные слова
    r'^(покаж|скаж|расскаж|объясн|помог|подскаж)',  # Глаголы-просьбы
]

# Слова-индикаторы чата (приветствия, обращения к боту)
CHAT_INDICATORS = [
    'привет', 'здравствуй', 'добрый день', 'добрый вечер', 'доброе утро',
    'спасибо', 'благодарю', 'пожалуйста',
    'помоги', 'подскажи', 'расскажи', 'объясни', 'покажи',
    'умеешь', 'можешь', 'знаешь',
    'бот', 'ассистент',
    'траты за', 'расходы за', 'траты вчера', 'траты сегодня',  # Запросы показа трат
    'покажи траты', 'покажи расходы', 'показать траты', 'показать расходы',
]

# Слова-индикаторы команд/запросов
# ВАЖНО: Не добавляем сюда "отчет", "статистика" - это могут быть описания трат
COMMAND_INDICATORS = [
    'настройки', 'настрой', 'измени', 'установи',
]

# Слова-индикаторы трат (глаголы покупки)
# Оставляем пустым - все глаголы покупки обычно используются в вопросах
EXPENSE_VERBS = [
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
    
    Returns:
        Tuple[str, float]: (тип сообщения, уверенность от 0 до 1)
    """
    text = text.strip()
    text_lower = text.lower()
    
    # 0. ПРИОРИТЕТ 1: Сначала проверяем вопросительный знак - это всегда чат
    if text.strip().endswith('?'):
        return 'chat', 1.0
    
    # 1. ПРИОРИТЕТ 2: Проверяем вопросительные слова и глаголы-просьбы
    for pattern in QUESTION_PATTERNS[1:]:  # Пропускаем первый паттерн (уже проверили)
        if re.search(pattern, text_lower):
            return 'chat', 0.95
    
    # 1. НОВОЕ: Затем используем специализированный модуль intent
    from .expense_intent import is_show_expenses_request, is_expense_record_request
    
    # Проверяем, является ли это запросом показа трат
    is_show, show_confidence = is_show_expenses_request(text)
    if is_show and show_confidence >= 0.7:
        return 'chat', show_confidence
    
    # Проверяем, является ли это записью траты
    is_record, record_confidence = is_expense_record_request(text)
    if is_record and record_confidence >= 0.7:
        return 'record', record_confidence
    
    # 2. Проверяем наличие чат-индикаторов
    for indicator in CHAT_INDICATORS:
        if indicator in text_lower:
            return 'chat', 0.9
    
    # 3. Проверяем наличие команд
    for command in COMMAND_INDICATORS:
        if command in text_lower:
            return 'chat', 0.85
    
    # 4. Проверяем наличие глаголов покупки - это точно трата
    for verb in EXPENSE_VERBS:
        if verb in text_lower:
            return 'record', 0.9
    
    # 5. Проверяем, содержит ли сообщение числа (возможно сумма)
    has_numbers = bool(re.search(r'\d+', text))
    if has_numbers:
        # Если есть числа, скорее всего это трата
        return 'record', 0.85
    
    # 6. Морфологический анализ - если это существительное или
    # фраза "прилагательное + существительное", то это трата
    if is_noun_phrase(text):
        # Исключаем слишком длинные фразы (скорее всего это предложения)
        if len(text.split()) <= 4:
            return 'record', 0.8
    
    # 7. Если текст очень короткий (1-2 слова) и не вопрос - скорее всего трата
    word_count = len(text.split())
    if word_count <= 2 and not text.endswith('?'):
        # Короткие фразы без контекста - это описания трат
        # Примеры: "Статистика", "Отчет", "Продукты", "Кофе"
        return 'record', 0.55  # Снижаем confidence для коротких фраз
    
    # 8. Длинные предложения без чисел - скорее всего чат
    if word_count > 5 and not has_numbers:
        return 'chat', 0.7
    
    # По умолчанию - не уверены, но склоняемся к record
    # (лучше попытаться записать трату, чем проигнорировать)
    return 'record', 0.5


def get_expense_indicators(text: str) -> List[str]:
    """
    Возвращает список индикаторов, указывающих на то, что это трата
    """
    indicators = []
    text_lower = text.lower()
    
    # Проверяем глаголы покупки
    for verb in EXPENSE_VERBS:
        if verb in text_lower:
            indicators.append(f"глагол покупки: {verb}")
    
    # Проверяем наличие чисел
    numbers = re.findall(r'\d+', text)
    if numbers:
        indicators.append(f"числа: {', '.join(numbers)}")
    
    # Проверяем тип фразы
    if is_noun_phrase(text):
        indicators.append("фраза-существительное")
    
    return indicators