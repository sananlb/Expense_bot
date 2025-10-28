"""
Улучшенный модуль для категоризации расходов с поддержкой множественного ввода
и исправления опечаток без использования ИИ
"""
import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from bot.utils.category_helpers import get_category_display_name

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
    'кафе и рестораны': {
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
        'parking': ['парковка', 'стоянка', 'паркинг'],
        'brands': ['яндекс', 'uber', 'gett', 'ситимобил', 'везет', 'bolt'],
        'keywords': ['транспорт', 'поездка', 'доехать', 'добраться', 'проезд']
    },
    'автомобиль': {
        'fuel': ['бензин', 'дизель', 'газ', 'заправка', 'азс', 'топливо'],
        'service': ['то', 'техобслуживание', 'ремонт', 'шиномонтаж', 'автосервис', 'сто', 'мойка'],
        'parts': ['масло', 'фильтр', 'тормоза', 'колодки', 'свечи', 'аккумулятор', 'шины'],
        'other': ['страховка', 'осаго', 'каско', 'налог', 'штраф'],
        'keywords': ['автомобиль', 'машина', 'авто', 'автомобиль']
    },
    'жилье': {
        'rent': ['аренда', 'квартплата', 'коммуналка', 'жкх'],
        'utilities': ['свет', 'электричество', 'вода', 'газ', 'отопление', 'домофон'],
        'household': ['ремонт', 'мебель', 'посуда', 'бытовая техника', 'уборка'],
        'keywords': ['жилье', 'дом', 'квартира', 'жилплощадь']
    },
    'аптеки': {
        'medical': ['аптека', 'лекарства', 'таблетки', 'витамины', 'бады', 'мазь', 'капли',
                   'сироп', 'антибиотик', 'обезболивающее', 'жаропонижающее'],
        'keywords': ['аптека', 'медикаменты', 'препараты']
    },
    'медицина': {
        'doctors': ['врач', 'доктор', 'поликлиника', 'больница', 'клиника', 'медцентр',
                   'стоматолог', 'окулист', 'терапевт', 'хирург', 'педиатр'],
        'procedures': ['анализы', 'узи', 'рентген', 'мрт', 'кт', 'осмотр', 'прием', 'консультация'],
        'keywords': ['медицина', 'лечение', 'болезнь', 'здоровье']
    },
    'красота': {
        'services': ['салон', 'парикмахерская', 'маникюр', 'педикюр', 'стрижка', 'окрашивание',
                    'укладка', 'массаж', 'косметолог', 'визажист', 'эпиляция'],
        'products': ['косметика', 'крем', 'шампунь', 'лак', 'помада', 'тушь', 'духи'],
        'keywords': ['красота', 'уход', 'бьюти']
    },
    'спорт и фитнес': {
        'activities': ['фитнес', 'спортзал', 'тренажерный зал', 'йога', 'бассейн', 'тренировка',
                      'пилатес', 'кроссфит', 'бокс', 'единоборства', 'танцы'],
        'equipment': ['спортивное питание', 'протеин', 'гантели', 'коврик', 'форма', 'кроссовки'],
        'keywords': ['спорт', 'фитнес', 'тренировка', 'зал']
    },
    'одежда и обувь': {
        'clothes': ['джинсы', 'футболка', 'рубашка', 'платье', 'юбка', 'брюки', 'шорты',
                   'куртка', 'пальто', 'свитер', 'кофта', 'костюм', 'пиджак'],
        'shoes': ['кроссовки', 'ботинки', 'туфли', 'сапоги', 'босоножки', 'кеды', 'тапки'],
        'accessories': ['сумка', 'рюкзак', 'ремень', 'шарф', 'шапка', 'перчатки', 'носки'],
        'brands': ['zara', 'hm', 'uniqlo', 'reserved', 'bershka', 'mango', 'nike', 'adidas'],
        'keywords': ['одежда', 'обувь', 'гардероб', 'шоппинг']
    },
    'развлечения': {
        'activities': ['кино', 'театр', 'концерт', 'выставка', 'музей', 'цирк', 'зоопарк'],
        'sports': ['боулинг', 'бильярд', 'каток', 'бассейн'],
        'nightlife': ['клуб', 'бар', 'караоке', 'дискотека'],
        'games': ['игры', 'квест', 'аттракционы', 'парк'],
        'keywords': ['развлечения', 'отдых', 'досуг', 'веселье']
    },
    'образование': {
        'institutions': ['школа', 'университет', 'институт', 'колледж', 'курсы', 'академия'],
        'materials': ['учебник', 'книга', 'тетрадь', 'ручка', 'карандаш', 'рюкзак'],
        'services': ['репетитор', 'обучение', 'курс', 'семинар', 'тренинг', 'мастер-класс'],
        'keywords': ['образование', 'учеба', 'обучение', 'курсы']
    },
    'подарки': {
        'occasions': ['день рождения', 'новый год', 'рождество', '8 марта', '23 февраля',
                     'свадьба', 'юбилей'],
        'items': ['подарок', 'сюрприз', 'букет', 'цветы', 'открытка', 'сувенир'],
        'keywords': ['подарки', 'праздник', 'поздравление']
    },
    'путешествия': {
        'transport': ['билет', 'авиабилет', 'поезд', 'самолет', 'автобус'],
        'accommodation': ['отель', 'гостиница', 'хостел', 'аренда', 'airbnb', 'booking'],
        'activities': ['экскурсия', 'тур', 'гид', 'музей', 'достопримечательность'],
        'keywords': ['путешествия', 'отпуск', 'поездка', 'туризм']
    },
    'коммунальные услуги и подписки': {
        'utilities': ['коммуналка', 'квартплата', 'жкх', 'свет', 'электричество', 'вода',
                     'газ', 'отопление', 'домофон'],
        'communication': ['интернет', 'телефон', 'мобильный', 'связь', 'тариф', 'пополнение'],
        'subscriptions': ['подписка', 'netflix', 'spotify', 'youtube', 'сервис', 'абонемент'],
        'brands': ['мтс', 'билайн', 'мегафон', 'теле2', 'yota', 'ростелеком'],
        'keywords': ['коммуналка', 'связь', 'подписка', 'услуги']
    }
}

# Английские категории расходов
CATEGORY_KEYWORDS_EN = {
    'groceries': {
        'products': ['bread', 'milk', 'eggs', 'meat', 'fish', 'chicken', 'cheese', 'butter',
                    'vegetables', 'fruits', 'potatoes', 'carrots', 'onions', 'tomatoes'],
        'drinks': ['water', 'juice', 'soda', 'beer', 'wine'],
        'stores': ['grocery', 'supermarket', 'store', 'market', 'walmart', 'target', 'costco'],
        'keywords': ['groceries', 'food', 'shopping']
    },
    'cafes and restaurants': {
        'drinks': ['coffee', 'tea', 'latte', 'cappuccino', 'espresso', 'americano'],
        'food': ['burger', 'pizza', 'sandwich', 'pasta', 'salad', 'soup', 'sushi'],
        'places': ['cafe', 'restaurant', 'bar', 'starbucks', 'mcdonalds', 'subway'],
        'keywords': ['breakfast', 'lunch', 'dinner', 'meal']
    },
    'transport': {
        'types': ['taxi', 'uber', 'lyft', 'bus', 'metro', 'subway', 'train', 'flight'],
        'parking': ['parking', 'park'],
        'keywords': ['transport', 'transportation', 'ride', 'trip']
    },
    'car': {
        'fuel': ['gas', 'gasoline', 'petrol', 'fuel', 'diesel', 'station'],
        'service': ['maintenance', 'repair', 'service', 'tire', 'oil change', 'car wash'],
        'parts': ['oil', 'filter', 'brakes', 'battery', 'tires'],
        'other': ['insurance', 'tax', 'fine', 'ticket'],
        'keywords': ['car', 'vehicle', 'automobile']
    },
    'housing': {
        'rent': ['rent', 'lease', 'mortgage'],
        'utilities': ['electricity', 'water', 'gas', 'heating'],
        'household': ['repair', 'furniture', 'appliance', 'cleaning'],
        'keywords': ['housing', 'home', 'apartment']
    },
    'pharmacies': {
        'medical': ['pharmacy', 'medicine', 'pills', 'vitamins', 'drugs', 'supplements',
                   'prescription', 'painkiller', 'antibiotic'],
        'keywords': ['pharmacy', 'drugstore', 'medications']
    },
    'medicine': {
        'doctors': ['doctor', 'hospital', 'clinic', 'dentist', 'physician', 'specialist'],
        'procedures': ['checkup', 'consultation', 'test', 'xray', 'mri', 'scan'],
        'keywords': ['medicine', 'medical', 'health', 'treatment']
    },
    'beauty': {
        'services': ['salon', 'haircut', 'manicure', 'pedicure', 'massage', 'spa',
                    'hairdresser', 'barber', 'styling', 'coloring'],
        'products': ['cosmetics', 'cream', 'shampoo', 'perfume', 'makeup'],
        'keywords': ['beauty', 'grooming', 'personal care']
    },
    'sports and fitness': {
        'activities': ['gym', 'fitness', 'yoga', 'swimming', 'workout', 'training',
                      'pilates', 'crossfit', 'boxing', 'martial arts', 'dance'],
        'equipment': ['protein', 'supplements', 'dumbbells', 'mat', 'sportswear'],
        'keywords': ['sports', 'fitness', 'workout', 'gym']
    },
    'clothes and shoes': {
        'clothes': ['jeans', 'shirt', 'dress', 'pants', 'shorts', 'jacket', 'coat',
                   'sweater', 'suit', 't-shirt'],
        'shoes': ['sneakers', 'boots', 'shoes', 'sandals', 'slippers'],
        'accessories': ['bag', 'backpack', 'belt', 'scarf', 'hat', 'gloves', 'socks'],
        'brands': ['zara', 'hm', 'uniqlo', 'nike', 'adidas', 'reserved'],
        'keywords': ['clothes', 'clothing', 'shoes', 'apparel', 'fashion']
    },
    'entertainment': {
        'activities': ['cinema', 'movie', 'theater', 'concert', 'museum', 'exhibition', 'zoo'],
        'sports': ['bowling', 'billiards', 'skating', 'pool'],
        'nightlife': ['club', 'bar', 'karaoke', 'disco'],
        'games': ['games', 'quest', 'park'],
        'keywords': ['entertainment', 'fun', 'leisure']
    },
    'education': {
        'institutions': ['school', 'university', 'college', 'courses', 'academy'],
        'materials': ['book', 'notebook', 'pen', 'pencil', 'backpack', 'textbook'],
        'services': ['tutor', 'course', 'training', 'seminar', 'workshop'],
        'keywords': ['education', 'learning', 'study', 'courses']
    },
    'gifts': {
        'occasions': ['birthday', 'christmas', 'wedding', 'anniversary', 'holiday'],
        'items': ['gift', 'present', 'flowers', 'bouquet', 'card', 'souvenir'],
        'keywords': ['gifts', 'presents', 'celebration']
    },
    'travel': {
        'transport': ['ticket', 'flight', 'train', 'bus'],
        'accommodation': ['hotel', 'hostel', 'airbnb', 'booking', 'rent'],
        'activities': ['tour', 'excursion', 'guide', 'museum', 'attraction'],
        'keywords': ['travel', 'trip', 'vacation', 'tourism']
    },
    'utilities and subscriptions': {
        'utilities': ['utilities', 'electricity', 'water', 'gas', 'heating'],
        'communication': ['internet', 'phone', 'mobile', 'plan', 'topup'],
        'subscriptions': ['subscription', 'netflix', 'spotify', 'youtube', 'service'],
        'keywords': ['utilities', 'bills', 'subscription', 'services']
    },
    'other expenses': {
        'keywords': ['other', 'misc', 'miscellaneous', 'various']
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
    from asgiref.sync import sync_to_async
    
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
            # Используем язык пользователя для отображения категории
            lang_code = user_profile.language_code if hasattr(user_profile, 'language_code') else 'ru'
            category_display_name = get_category_display_name(category, lang_code)
            category_scores[category_display_name] = score
    
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