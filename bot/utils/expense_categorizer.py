"""
Улучшенный модуль для категоризации расходов с поддержкой множественного ввода
и исправления опечаток без использования ИИ
"""
import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Попробуем импортировать spellchecker
try:
    from spellchecker import SpellChecker
    SPELLCHECKER_AVAILABLE = True
except ImportError:
    SPELLCHECKER_AVAILABLE = False
    print("Warning: pyspellchecker not installed. Using manual corrections only.")

# Словарь для исправления опечаток (расширяемый)
TYPO_CORRECTIONS = {
    # Еда и напитки
    'вада': 'вода',
    'вода': 'вода',
    'кофе': 'кофе',
    'кофэ': 'кофе',
    'кофи': 'кофе',
    'прадукты': 'продукты',
    'продукты': 'продукты',
    'чебурек': 'чебурек',
    'чибурек': 'чебурек',
    'чебуррек': 'чебурек',
    'хлеп': 'хлеб',
    'молако': 'молоко',
    'малоко': 'молоко',
    'колбоса': 'колбаса',
    'калбаса': 'колбаса',
    'пица': 'пицца',
    'пицца': 'пицца',
    
    # Транспорт
    'токси': 'такси',
    'таксі': 'такси',
    'метро': 'метро',
    'митро': 'метро',
    'автобус': 'автобус',
    'автобуз': 'автобус',
    'бинзин': 'бензин',
    'бензин': 'бензин',
    
    # Другие категории
    'оптека': 'аптека',
    'аптека': 'аптека',
    'ликарства': 'лекарства',
    'лекарства': 'лекарства',
    'магазин': 'магазин',
    'магазине': 'магазин',
    'магозин': 'магазин',
    'адежда': 'одежда',
    'одежда': 'одежда',
    'интирнет': 'интернет',
    'интернет': 'интернет',
    'телифон': 'телефон',
    'телефон': 'телефон',
}

# Расширенный словарь ключевых слов с точными словами
CATEGORY_KEYWORDS_EXACT = {
    'продукты': {
        'products': ['хлеб', 'молоко', 'яйца', 'мясо', 'рыба', 'курица', 'сыр', 'масло', 
                    'колбаса', 'сосиски', 'овощи', 'фрукты', 'картошка', 'морковь', 'лук',
                    'помидоры', 'огурцы', 'яблоки', 'бананы', 'апельсины', 'мандарины'],
        'drinks': ['вода', 'сок', 'молоко', 'кефир', 'йогурт', 'ряженка', 'пиво', 'вино'],
        'sweets': ['конфеты', 'шоколад', 'печенье', 'торт', 'пирожное', 'мороженое'],
        'grocery': ['крупа', 'макароны', 'рис', 'гречка', 'сахар', 'соль', 'мука', 'специи'],
        'stores': ['магазин', 'супермаркет', 'гипермаркет', 'пятерочка', 'перекресток', 
                  'дикси', 'магнит', 'лента', 'ашан', 'metro', 'spar', 'окей'],
        'keywords': ['продукты', 'еда', 'покушать', 'пища']
    },
    'кафе': {
        'drinks': ['кофе', 'чай', 'капучино', 'латте', 'эспрессо', 'американо', 'какао'],
        'fastfood': ['бургер', 'пицца', 'суши', 'роллы', 'шаурма', 'чебурек', 'беляш',
                    'самса', 'хачапури', 'блины', 'сэндвич'],
        'meals': ['завтрак', 'обед', 'ужин', 'ланч', 'бизнес-ланч', 'перекус'],
        'places': ['кафе', 'ресторан', 'бар', 'столовая', 'буфет', 'кофейня'],
        'brands': ['макдональдс', 'макдак', 'kfc', 'бургер кинг', 'subway', 'starbucks',
                  'кофемания', 'шоколадница', 'costa', 'вкусно и точка']
    },
    'транспорт': {
        'public': ['такси', 'метро', 'автобус', 'троллейбус', 'трамвай', 'маршрутка',
                  'электричка', 'поезд', 'самолет'],
        'fuel': ['бензин', 'дизель', 'газ', 'заправка', 'азс', 'топливо'],
        'parking': ['парковка', 'стоянка', 'паркинг'],
        'brands': ['яндекс', 'uber', 'gett', 'ситимобил', 'везет', 'bolt'],
        'keywords': ['транспорт', 'поездка', 'доехать', 'добраться', 'проезд']
    },
    'развлечения': {
        'activities': ['кино', 'театр', 'концерт', 'выставка', 'музей', 'цирк', 'зоопарк'],
        'sports': ['боулинг', 'бильярд', 'каток', 'бассейн', 'фитнес', 'спортзал', 'йога'],
        'nightlife': ['клуб', 'бар', 'караоке', 'дискотека'],
        'games': ['игры', 'квест', 'аттракционы', 'парк'],
        'keywords': ['развлечения', 'отдых', 'досуг', 'веселье']
    },
    'здоровье': {
        'medical': ['аптека', 'лекарства', 'таблетки', 'витамины', 'бады', 'мазь', 'капли'],
        'doctors': ['врач', 'доктор', 'поликлиника', 'больница', 'клиника', 'медцентр'],
        'procedures': ['анализы', 'узи', 'рентген', 'мрт', 'кт', 'осмотр', 'прием'],
        'keywords': ['здоровье', 'лечение', 'болезнь', 'медицина']
    },
    'одежда': {
        'clothes': ['джинсы', 'футболка', 'рубашка', 'платье', 'юбка', 'брюки', 'шорты',
                   'куртка', 'пальто', 'свитер', 'кофта', 'костюм', 'пиджак'],
        'shoes': ['кроссовки', 'ботинки', 'туфли', 'сапоги', 'босоножки', 'кеды', 'тапки'],
        'accessories': ['сумка', 'рюкзак', 'ремень', 'шарф', 'шапка', 'перчатки', 'носки'],
        'brands': ['zara', 'hm', 'uniqlo', 'reserved', 'bershka', 'mango', 'nike', 'adidas'],
        'keywords': ['одежда', 'обувь', 'гардероб', 'шоппинг']
    },
    'связь': {
        'services': ['интернет', 'телефон', 'мобильный', 'связь', 'тариф', 'пополнение'],
        'brands': ['мтс', 'билайн', 'мегафон', 'теле2', 'yota', 'ростелеком'],
        'keywords': ['связь', 'оплата связи', 'счет за телефон']
    },
    'дом': {
        'utilities': ['коммуналка', 'квартплата', 'жкх', 'свет', 'электричество', 'вода',
                     'газ', 'отопление', 'домофон', 'интернет'],
        'household': ['ремонт', 'мебель', 'посуда', 'бытовая техника', 'уборка'],
        'keywords': ['дом', 'квартира', 'жилье', 'коммунальные']
    },
    'подарки': {
        'occasions': ['день рождения', 'новый год', 'рождество', '8 марта', '23 февраля',
                     'свадьба', 'юбилей'],
        'items': ['подарок', 'сюрприз', 'букет', 'цветы', 'открытка'],
        'keywords': ['подарки', 'праздник', 'поздравление']
    }
}

# Английские категории расходов
CATEGORY_KEYWORDS_EN = {
    'groceries': {
        'products': ['bread', 'milk', 'eggs', 'meat', 'fish', 'chicken', 'cheese', 'butter',
                    'vegetables', 'fruits', 'potatoes', 'carrots', 'onions', 'tomatoes'],
        'drinks': ['water', 'juice', 'soda', 'beer', 'wine', 'coffee', 'tea'],
        'stores': ['grocery', 'supermarket', 'store', 'market', 'walmart', 'target', 'costco'],
        'keywords': ['groceries', 'food', 'shopping']
    },
    'cafe': {
        'drinks': ['coffee', 'tea', 'latte', 'cappuccino', 'espresso', 'americano'],
        'food': ['burger', 'pizza', 'sandwich', 'pasta', 'salad', 'soup'],
        'places': ['cafe', 'restaurant', 'bar', 'starbucks', 'mcdonalds', 'subway'],
        'keywords': ['breakfast', 'lunch', 'dinner', 'meal']
    },
    'transport': {
        'types': ['taxi', 'uber', 'lyft', 'bus', 'metro', 'subway', 'train', 'flight'],
        'fuel': ['gas', 'gasoline', 'petrol', 'fuel', 'diesel'],
        'keywords': ['transport', 'transportation', 'ride', 'trip']
    },
    'entertainment': {
        'activities': ['cinema', 'movie', 'theater', 'concert', 'museum', 'park'],
        'services': ['netflix', 'spotify', 'youtube', 'gaming', 'subscription'],
        'keywords': ['entertainment', 'fun', 'leisure']
    },
    'health': {
        'medical': ['pharmacy', 'medicine', 'pills', 'vitamins', 'drugs'],
        'services': ['doctor', 'hospital', 'clinic', 'dentist'],
        'keywords': ['health', 'medical', 'treatment']
    },
    'clothes': {
        'items': ['shirt', 'pants', 'dress', 'shoes', 'jacket', 'coat'],
        'stores': ['zara', 'hm', 'uniqlo', 'nike', 'adidas'],
        'keywords': ['clothes', 'clothing', 'apparel', 'shopping']
    },
    'utilities': {
        'services': ['internet', 'phone', 'electricity', 'water', 'gas', 'heating'],
        'keywords': ['utilities', 'bills', 'subscription']
    },
    'other': {
        'keywords': ['other', 'misc', 'miscellaneous']
    }
}

# Слова-разделители для множественного ввода
SEPARATORS = ['и', 'да', 'еще', 'ещё', 'плюс', 'также', 'тоже', ',', '+']
SEPARATORS_EN = ['and', 'plus', 'with', 'also', ',', '+', '&']

# Инициализируем spell checkers для разных языков если доступны
if SPELLCHECKER_AVAILABLE:
    # Русский spell checker
    spell_ru = SpellChecker(language='ru')
    # Добавляем специфичные слова которые должны быть правильными
    spell_ru.word_frequency.load_words([
        'кофе', 'чебурек', 'шаурма', 'латте', 'капучино', 'эспрессо',
        'такси', 'яндекс', 'uber', 'пятерочка', 'перекресток', 'магнит',
        'макдональдс', 'kfc', 'subway', 'starbucks', 'wifi', 'интернет',
        'бургер', 'пицца', 'суши', 'роллы', 'фастфуд', 'смузи',
        'коммуналка', 'жкх', 'квартплата'
    ])
    
    # Английский spell checker
    spell_en = SpellChecker(language='en')
    # Добавляем специфичные слова для английского
    spell_en.word_frequency.load_words([
        'uber', 'mcdonalds', 'starbucks', 'subway', 'wifi', 'latte',
        'cappuccino', 'espresso', 'burger', 'pizza', 'sushi', 'fastfood',
        'groceries', 'utilities', 'subscription', 'cashback', 'netflix',
        'spotify', 'youtube', 'amazon', 'iphone', 'android'
    ])
else:
    spell_ru = None
    spell_en = None


def detect_language(text: str) -> str:
    """
    Определяет язык текста (русский или английский)
    
    Args:
        text: Текст для анализа
    
    Returns:
        'ru' для русского, 'en' для английского
    """
    # Подсчитываем кириллические и латинские буквы
    cyrillic_count = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    latin_count = sum(1 for c in text if ('a' <= c <= 'z') or ('A' <= c <= 'Z'))
    
    # Возвращаем язык с большим количеством символов
    return 'ru' if cyrillic_count >= latin_count else 'en'


def correct_typos(text: str, language: str = None) -> str:
    """
    Исправляет опечатки в тексте используя spell checker и словарь
    
    Args:
        text: Исходный текст
        language: Язык текста ('ru' или 'en'). Если None, определяется автоматически
    
    Returns:
        Текст с исправленными опечатками
    """
    # Автоматически определяем язык если не указан
    if language is None:
        language = detect_language(text)
    words = text.lower().split()
    corrected_words = []
    
    for word in words:
        # Убираем знаки препинания с краев слова
        punctuation_start = ''
        punctuation_end = ''
        clean_word = word
        
        # Сохраняем пунктуацию в начале
        while clean_word and clean_word[0] in '.,!?;:()[]{}"\'-':
            punctuation_start += clean_word[0]
            clean_word = clean_word[1:]
        
        # Сохраняем пунктуацию в конце
        while clean_word and clean_word[-1] in '.,!?;:()[]{}"\'-':
            punctuation_end = clean_word[-1] + punctuation_end
            clean_word = clean_word[:-1]
        
        # Сначала проверяем наш словарь исправлений (для русского)
        if language == 'ru' and clean_word in TYPO_CORRECTIONS:
            corrected = TYPO_CORRECTIONS[clean_word]
        # Затем используем соответствующий spell checker если он доступен
        elif SPELLCHECKER_AVAILABLE and len(clean_word) > 2:
            # Выбираем правильный spell checker
            spell_checker = spell_ru if language == 'ru' else spell_en
            
            if spell_checker:
                # Получаем наиболее вероятное исправление
                correction = spell_checker.correction(clean_word)
                if correction and correction != clean_word:
                    # Проверяем что исправление разумное (не слишком отличается)
                    if len(set(clean_word) & set(correction)) >= len(clean_word) * 0.5:
                        corrected = correction
                    else:
                        corrected = clean_word
                else:
                    corrected = clean_word
            else:
                corrected = clean_word
        else:
            corrected = clean_word
        
        # Восстанавливаем слово с пунктуацией
        corrected_words.append(punctuation_start + corrected + punctuation_end)
    
    return ' '.join(corrected_words)


def split_multiple_items(text: str) -> List[str]:
    """
    Разбивает текст на отдельные элементы при множественном вводе
    
    Args:
        text: Текст для разбиения
    
    Returns:
        Список отдельных элементов
    """
    # Нормализуем текст
    text = text.lower().strip()
    
    # Создаем паттерн для разделителей
    separator_pattern = '|'.join([f'\\s+{sep}\\s+' for sep in SEPARATORS if sep.isalpha()])
    separator_pattern += '|[,+]'
    
    # Разбиваем текст
    items = re.split(separator_pattern, text)
    
    # Очищаем и фильтруем результаты
    cleaned_items = []
    for item in items:
        item = item.strip()
        if item and len(item) > 1:  # Игнорируем пустые и слишком короткие
            cleaned_items.append(item)
    
    return cleaned_items if len(cleaned_items) > 1 else [text]


def find_category_matches(word: str, category_keywords: Dict) -> int:
    """
    Подсчитывает количество совпадений слова с ключевыми словами категории
    
    Args:
        word: Слово для проверки
        category_keywords: Словарь ключевых слов категории
    
    Returns:
        Количество совпадений (с учетом весов)
    """
    score = 0
    word_lower = word.lower().strip()
    
    # Проверяем точные совпадения
    for group_name, keywords in category_keywords.items():
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Точное совпадение слова
            if word_lower == keyword_lower:
                # Даем больший вес определенным группам
                if group_name in ['keywords', 'products', 'drinks', 'fastfood']:
                    score += 3
                elif group_name in ['brands', 'stores', 'places']:
                    score += 2
                else:
                    score += 1
            
            # Частичное совпадение (слово содержится в ключевом слове или наоборот)
            elif len(word_lower) > 3 and (word_lower in keyword_lower or keyword_lower in word_lower):
                score += 0.5
    
    return score


def categorize_expense(text: str, amount: Optional[float] = None, language: str = None) -> Tuple[str, float, str]:
    """
    Определяет категорию расхода с улучшенной логикой
    
    Args:
        text: Описание расхода
        amount: Сумма расхода (опционально)
        language: Язык текста ('ru' или 'en'). Если None, определяется автоматически
    
    Returns:
        Кортеж (категория, уверенность, исправленный текст)
    """
    # Определяем язык если не указан
    if language is None:
        language = detect_language(text)
    
    # Исправляем опечатки
    corrected_text = correct_typos(text, language)
    
    # Разбиваем на отдельные элементы
    items = split_multiple_items(corrected_text)
    
    # Подсчитываем совпадения для каждой категории
    category_scores = defaultdict(float)
    
    for item in items:
        # Разбиваем элемент на слова
        words = item.split()
        
        for word in words:
            # Очищаем слово от знаков препинания
            clean_word = word.strip('.,!?;:()[]{}"\'-')
            if len(clean_word) < 2:
                continue
            
            # Выбираем правильный словарь категорий в зависимости от языка
            keywords_dict = CATEGORY_KEYWORDS_EXACT if language == 'ru' else CATEGORY_KEYWORDS_EN
            
            # Проверяем каждую категорию
            for category_name, category_keywords in keywords_dict.items():
                score = find_category_matches(clean_word, category_keywords)
                if score > 0:
                    category_scores[category_name] += score
    
    # Находим категорию с максимальным счетом
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1])
        category_name = best_category[0]
        score = best_category[1]
        
        # Вычисляем уверенность (нормализуем от 0 до 1)
        # Считаем что максимальная уверенность при score >= 5
        confidence = min(score / 5.0, 1.0)
        
        # Если уверенность слишком низкая, возвращаем "другое"
        if confidence < 0.2:
            return 'другое', 0.1, corrected_text
        
        return category_name, confidence, corrected_text
    
    # Если не нашли совпадений
    return 'другое', 0.1, corrected_text


def get_category_suggestions(text: str) -> List[Tuple[str, float]]:
    """
    Возвращает топ-3 наиболее вероятных категорий
    
    Args:
        text: Описание расхода
    
    Returns:
        Список кортежей (категория, уверенность)
    """
    # Исправляем опечатки
    corrected_text = correct_typos(text)
    
    # Разбиваем на отдельные элементы
    items = split_multiple_items(corrected_text)
    
    # Подсчитываем совпадения для каждой категории
    category_scores = defaultdict(float)
    
    for item in items:
        words = item.split()
        
        for word in words:
            clean_word = word.strip('.,!?;:()[]{}"\'-')
            if len(clean_word) < 2:
                continue
            
            for category_name, category_keywords in CATEGORY_KEYWORDS_EXACT.items():
                score = find_category_matches(clean_word, category_keywords)
                if score > 0:
                    category_scores[category_name] += score
    
    # Сортируем по убыванию счета
    sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Возвращаем топ-3 с нормализованной уверенностью
    result = []
    for category, score in sorted_categories[:3]:
        confidence = min(score / 5.0, 1.0)
        if confidence >= 0.1:
            result.append((category, confidence))
    
    # Если нет подходящих категорий, добавляем "другое"
    if not result:
        result.append(('другое', 0.1))
    
    return result


# Тестовая функция
def categorize_expense_with_weights(text: str, user_profile) -> Tuple[str, float, str]:
    """
    Категоризация расхода с использованием персональных весов из БД
    
    Args:
        text: Описание расхода
        user_profile: Профиль пользователя из БД
    
    Returns:
        Кортеж (категория, уверенность, исправленный текст)
    """
    import math
    from expenses.models import CategoryKeyword, ExpenseCategory
    
    # Исправляем опечатки
    language = detect_language(text)
    corrected_text = correct_typos(text, language)
    
    # Разбиваем на отдельные элементы и слова
    items = split_multiple_items(corrected_text)
    
    # Получаем все категории пользователя
    user_categories = ExpenseCategory.objects.filter(profile=user_profile)
    
    # Подсчитываем очки для каждой категории
    category_scores = {}
    
    for category in user_categories:
        score = 0.0
        
        # Получаем ключевые слова категории с весами
        keywords = CategoryKeyword.objects.filter(category=category)
        
        for item in items:
            words = item.lower().split()
            
            for word in words:
                # Очищаем слово
                clean_word = re.sub(r'[^\w\s]', '', word).strip()
                if len(clean_word) < 3:
                    continue
                
                # Ищем совпадения в ключевых словах
                for keyword in keywords:
                    if keyword.keyword.lower() == clean_word:
                        # Точное совпадение - используем нормализованный вес
                        score += keyword.normalized_weight * 3
                    elif clean_word.startswith(keyword.keyword.lower()):
                        # Слово начинается с ключевого
                        score += keyword.normalized_weight * 2
                    elif keyword.keyword.lower() in clean_word:
                        # Ключевое слово входит в слово
                        score += keyword.normalized_weight * 1
        
        if score > 0:
            category_scores[category.name] = score
    
    # Если нашли совпадения
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1])
        category_name = best_category[0]
        score = best_category[1]
        
        # Вычисляем уверенность (используем логарифмическую шкалу)
        # score = 1 -> confidence = 0.5
        # score = 5 -> confidence = 0.85
        # score = 10 -> confidence = 0.95
        confidence = 1 - math.exp(-score * 0.3)
        confidence = min(max(confidence, 0.1), 1.0)
        
        return category_name, confidence, corrected_text
    
    # Если не нашли в персональных весах, используем старую логику
    return categorize_expense(text, language=language)


def categorize_expense_smart(text: str, user_profile=None) -> Tuple[str, float, str]:
    """
    Умная категоризация: использует веса из БД если есть профиль,
    иначе использует статические правила
    
    Args:
        text: Описание расхода
        user_profile: Профиль пользователя (опционально)
    
    Returns:
        Кортеж (категория, уверенность, исправленный текст)
    """
    if user_profile:
        try:
            # Пробуем использовать веса из БД
            return categorize_expense_with_weights(text, user_profile)
        except Exception as e:
            # Если что-то пошло не так, используем старую логику
            print(f"Error in weighted categorization: {e}")
    
    # Используем статическую категоризацию
    return categorize_expense(text)


if __name__ == "__main__":
    test_cases = [
        "кофе вода и чебурек",
        "вада и кофе",
        "такси до дома",
        "продукты в магазине",
        "обед в кафе",
        "бензин на заправке",
        "лекарства в аптеке",
        "коммуналка за месяц",
        "подарок на день рождения"
    ]
    
    for test in test_cases:
        category, confidence, corrected = categorize_expense(test)
        print(f"Текст: {test}")
        print(f"Исправлено: {corrected}")
        print(f"Категория: {category} (уверенность: {confidence:.2f})")
        print(f"Альтернативы: {get_category_suggestions(test)}")
        print("-" * 50)