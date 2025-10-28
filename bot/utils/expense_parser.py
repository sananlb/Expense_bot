"""
Парсер для извлечения информации о расходах и доходах из текстовых сообщений
"""
import re
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, time
from dateutil import parser as date_parser
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Вспомогательная функция для безопасного использования sync_to_async с Django ORM
def make_sync_to_async(func):
    """Создает обертку для синхронной функции для использования в асинхронном контексте"""
    return sync_to_async(func)

# Паттерны для извлечения даты
DATE_PATTERNS = [
    r'(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})',  # дд.мм.гггг или дд/мм/гггг
    r'(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{2})',    # дд.мм.гг или дд/мм/гг
    r'(\d{1,2})[.\/-](\d{1,2})(?:\s|$)',        # дд.мм (текущий год) - пробел или конец строки
]

# Паттерны для извлечения суммы
AMOUNT_PATTERNS = [
    r'(\d+(?:[.,]\d+)?)\s*(?:руб|рублей|р|₽)',  # 100 руб, 100.50 р
    r'(\d+(?:[.,]\d+)?)\s*(?:usd|\$|долл|доллар)',  # 100 USD, $100
    r'(\d+(?:[.,]\d+)?)\s*(?:eur|€|евро)',  # 100 EUR, €100
    r'(\d+(?:[.,]\d+)?)\s*(?:cny|¥|юан|юаней)',  # 100 CNY
    # Latin American currencies
    r'(\d+(?:[.,]\d+)?)\s*(?:ars|песо|аргентинских?)',  # 100 ARS, Argentine Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:cop|колумбийских?)',  # 100 COP, Colombian Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:pen|солей?|перуанских?)',  # 100 PEN, Peruvian Sol
    r'(\d+(?:[.,]\d+)?)\s*(?:clp|чилийских?)',  # 100 CLP, Chilean Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:mxn|мексиканских?)',  # 100 MXN, Mexican Peso
    r'(\d+(?:[.,]\d+)?)\s*(?:brl|реалов?|бразильских?)',  # 100 BRL, Brazilian Real
    r'(\d+(?:[.,]\d+)?)\s*$',  # просто число в конце
    r'^(\d+(?:[.,]\d+)?)\s',  # число в начале
    r'\s(\d+(?:[.,]\d+)?)\s',  # число в середине
]

# Паттерны для определения валюты
CURRENCY_PATTERNS = {
    # Major world currencies
    'USD': [r'\$', r'\busd\b', r'\bдолл', r'\bдоллар', r'\bdollars?\b'],
    'EUR': [r'€', r'\beur\b', r'\bевро', r'\beuro'],
    'GBP': [r'£', r'\bgbp\b', r'\bфунт', r'\bsterling', r'\bpounds?\b'],
    'CNY': [r'¥', r'\bcny\b', r'\bюан', r'\byuan', r'\brenminbi', r'\brmb\b'],
    'CHF': [r'\bchf\b', r'₣', r'\bфранк(?:ов|а)?\b', r'\bswiss\s+franc', r'\bfrancs?\b'],
    'INR': [r'\binr\b', r'₹', r'\bрупи[йяею]', r'\bиндийск.*руп'],
    'TRY': [r'\btry\b', r'₺', r'\bлир[аиы]?\b', r'\bтурец.*лир'],

    # Local currencies (CIS and nearby)
    'KZT': [r'\bkzt\b', r'₸', r'\bтенге', r'\bтеньге', r'\bтенг[еиия]', r'\bтнг', r'\btenge'],
    'UAH': [r'\buah\b', r'\bгрн', r'\bгривн[а-я]*', r'\bгривен', r'\bhryvni?a', r'\bhryvnya'],
    'BYN': [r'\bbyn\b', r'\bbyr\b', r'\bбел[ао]рус.*руб', r'\bbelarus.*rubl', r'\bbelarusian\s+ruble'],
    'RUB': [r'₽', r'\brub\b', r'\bруб', r'\bрубл'],
    'UZS': [r'\buzs\b', r"\bso['']m", r'\bсум(?:ов|ы|у)?\b', r'\bузбек.*сум', r'\buzbek.*som'],
    'AMD': [r'\bamd\b', r'\bдрам', r'\bdram'],
    'TMT': [r'\btmt\b', r'\bтуркмен.*манат', r'\bturkmen.*manat'],
    'AZN': [r'\bazn\b', r'\bазер.*манат', r'\bazer.*manat', r'\bманат(?:ов|ы)?\b'],
    'KGS': [r'\bkgs\b', r'\bkgz\b', r'\bсом(?:ов|ы|у)?\b', r'\bкиргиз.*сом', r'\bкырг.*сом'],
    'TJS': [r'\btjs\b', r'\bсомон[ия]?\b', r'\bтаджик.*сом', r'\btajik.*somoni'],
    'MDL': [r'\bmdl\b', r'\bлей(?:ев|я|и|ем|ями)?\b', r'\bмолдав.*лей', r'\bmoldov.*le[ui]'],
    'GEL': [r'\bgel\b', r'\bлари\b', r'\blari\b', r'\bgruzi.*lari'],

    # Latin American currencies
    'ARS': [r'\bars\b', r'\bаргентинских?', r'\bаргентинское', r'\bаргентинский', r'\bargentin[ea].*peso', r'\bпесо'],
    'COP': [r'\bcop\b', r'\bколумбийских?', r'\bколумбийское', r'\bколумбийский', r'\bcolombian.*peso'],
    'PEN': [r'\bpen\b', r'\bсолей?', r'\bперуанских?', r'\bперуанское', r'\bперуанский', r'\bperuvian\s+sol'],
    'CLP': [r'\bclp\b', r'\bчилийских?', r'\bчилийское', r'\bчилийский', r'\bchilean.*peso'],
    'MXN': [r'\bmxn\b', r'\bмексиканских?', r'\bмексиканское', r'\bмексиканский', r'\bmexican.*peso'],
    'BRL': [r'\bbrl\b', r'\bреал(?:ов|ы)?', r'\bбразильских?', r'\bбразильское', r'\bбразильский', r'\bbrazilian\s+real'],
}


# Паттерны для определения дохода - знак + или слово "плюс"
INCOME_PATTERNS = [
    r'^\+',  # Начинается с +
    r'^\+\d',  # Начинается с + и сразу цифра (+35000)
    r'\s\+\d',  # Пробел, затем + и цифры (долг +1200)
    r'\+\s*\d',  # + и цифры с возможным пробелом
    r'^плюс\s+\d',  # Начинается со слова "плюс" и цифра (плюс 5000)
    r'\sплюс\s+\d',  # Пробел, затем "плюс" и цифры (зарплата плюс 1200)
    r'^плюс\s*\d',  # "плюс" и цифры с возможным пробелом
]

# Паттерны для явного определения траты - знак - или слово "минус"
EXPENSE_PATTERNS = [
    r'^\-',  # Начинается с -
    r'^\-\d',  # Начинается с - и сразу цифра (-500)
    r'\s\-\d',  # Пробел, затем - и цифры (кофе -200)
    r'\-\s*\d',  # - и цифры с возможным пробелом
    r'^минус\s+\d',  # Начинается со слова "минус" и цифра (минус 5000)
    r'\sминус\s+\d',  # Пробел, затем "минус" и цифры (кофе минус 200)
    r'^минус\s*\d',  # "минус" и цифры с возможным пробелом
]

# Импортируем словарь ключевых слов из models
from expenses.models import CATEGORY_KEYWORDS as MODEL_CATEGORY_KEYWORDS

# Импортируем helper функцию для работы с категориями
from bot.utils.category_helpers import get_category_display_name
from bot.utils.income_category_definitions import (
    DEFAULT_INCOME_CATEGORY_KEY,
    detect_income_category_key,
    get_income_category_display_name as get_income_category_display_for_key,
    get_income_type,
    normalize_income_category_key,
)

def extract_date_from_text(text: str) -> Tuple[Optional[date], str]:
    """
    Извлекает дату из текста и возвращает кортеж (дата, текст_без_даты)
    Поддерживает только числовые даты в форматах: дд.мм.гггг, дд.мм.гг, дд.мм
    
    Примеры:
    - "Кофе 200 15.03.2024" -> (date(2024, 3, 15), "Кофе 200")
    - "25.12.2023 подарки 5000" -> (date(2023, 12, 25), "подарки 5000")
    - "Продукты 1500 08.09" -> (date(current_year, 9, 8), "Продукты 1500")
    - "Продукты 1500" -> (None, "Продукты 1500")
    """
    # Проверяем числовые даты
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                if len(match.groups()) == 3:
                    # Полная дата дд.мм.гггг или дд.мм.гг
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year_str = match.group(3)
                    
                    # Обработка двузначного года
                    if len(year_str) == 2:
                        year = 2000 + int(year_str)
                    else:
                        year = int(year_str)
                    
                    # Валидация даты
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        expense_date = date(year, month, day)
                        
                        # Убираем дату из текста
                        text_without_date = text[:match.start()] + text[match.end():]
                        text_without_date = ' '.join(text_without_date.split())  # Убираем лишние пробелы
                        
                        return expense_date, text_without_date
                        
                elif len(match.groups()) == 2:
                    # Короткая дата дд.мм (используем текущий год)
                    day = int(match.group(1))
                    month = int(match.group(2))
                    
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        current_year = datetime.now().year
                        expense_date = date(current_year, month, day)
                        
                        # Убираем дату из текста
                        text_without_date = text[:match.start()] + text[match.end():]
                        text_without_date = ' '.join(text_without_date.split())
                        
                        return expense_date, text_without_date
                        
            except (ValueError, TypeError) as e:
                logger.debug(f"Ошибка при парсинге даты из текста '{text}': {e}")
                continue
    
    # Если дата не найдена, возвращаем None и оригинальный текст
    return None, text

# Старый словарь для обратной совместимости
OLD_CATEGORY_KEYWORDS = {
    'азс': [
        # Основные слова
        'азс', 'заправка', 'бензин', 'дизель', 'солярка', 'топливо', 'горючее',
        # Бренды АЗС
        'лукойл', 'роснефть', 'газпромнефть', 'газпром', 'shell', 'bp', 'esso', 'татнефть',
        # Типы топлива
        '95', '92', '98', '100', 'дт', 'аи-95', 'аи-92', 'аи-98',
        # Дополнительные
        'колонка', 'литр', 'литров', 'залил', 'заправился', 'заправилась'
    ],
    'супермаркеты': [
        # Основные сети
        'супермаркет', 'пятерочка', 'пятёрочка', 'перекресток', 'перекрёсток', 'дикси', 'магнит',
        'лента', 'ашан', 'атак', 'metro', 'spar', 'окей', 'глобус', 'карусель',
        # Локальные сети
        'верный', 'авоська', 'монетка', 'призма', 'семишагофф', 'фасоль', 'вкусвилл',
        # Онлайн супермаркеты
        'самокат', 'яндекс.лавка', 'сбермаркет', 'впрок', 'деливери клаб'
    ],
    'продукты': [
        # Основные продукты
        'продукты', 'еда', 'молоко', 'хлеб', 'мясо', 'овощи', 'фрукты', 'рыба', 'курица',
        'яйца', 'масло', 'сыр', 'колбаса', 'сосиски', 'крупа', 'макароны', 'сахар',
        # Места покупки
        'рынок', 'базар', 'ярмарка', 'мясная лавка', 'булочная', 'пекарня',
        # Специализированные
        'вкусвилл', 'азбука вкуса', 'мираторг'
    ],
    'кафе и рестораны': [
        # Основные
        'ресторан', 'кафе', 'кофе', 'обед', 'завтрак', 'ужин', 'перекус', 'ланч', 'бизнес-ланч',
        # Блюда
        'пицца', 'суши', 'роллы', 'бургер', 'шаурма', 'паста', 'салат', 'суп', 'десерт', 'мороженое',
        # Напитки
        'капучино', 'латте', 'эспрессо', 'американо', 'раф', 'флэт уайт', 'макиато', 'чай', 'какао',
        'фраппе', 'гляссе', 'мокко', 'доппио', 'ристретто', 'лунго', 'кортадо',
        # Фастфуд
        'макдональдс', 'макдак', 'мак', 'kfc', 'кфс', 'бургер кинг', 'burger king', 'вкусно и точка',
        # Кафе и кофейни
        'старбакс', 'starbucks', 'шоколадница', 'кофемания', 'costa', 'кофе хауз', 'кофейня',
        'one price coffee', 'даблби', 'surf coffee', 'правда кофе', 'кооператив черный',
        # Доставка еды
        'доставка', 'яндекс.еда', 'delivery club', 'деливери', 'суши', 'пицца', 'роллы',
        # Дополнительные
        'столовая', 'бар', 'паб', 'ресторация', 'чаевые', 'кулинария', 'бистро', 'пекарня', 'кондитерская'
    ],
    'транспорт': [
        # Такси
        'такси', 'яндекс', 'яндекс.такси', 'uber', 'убер', 'gett', 'гетт', 'ситимобил', 'везет',
        # Общественный транспорт
        'метро', 'автобус', 'троллейбус', 'трамвай', 'маршрутка', 'электричка', 'проездной',
        'тройка', 'единый', 'транспортная карта', 'мцд',
        # Каршеринг
        'каршеринг', 'делимобиль', 'белкакар', 'яндекс.драйв', 'ситидрайв',
        # Самокаты
        'самокат', 'кикшеринг', 'юрент'
    ],
    'здоровье': [
        # Аптеки
        'аптека', 'лекарства', 'таблетки', 'витамины', 'бады', 'медикаменты', 'препараты',
        # Медицинские услуги
        'врач', 'доктор', 'клиника', 'больница', 'поликлиника', 'анализы', 'узи', 'мрт',
        'стоматолог', 'зубной', 'терапевт', 'окулист', 'массаж',
        # Сети аптек
        'ригла', 'асна', '36.6', 'горздрав', 'столички', 'неофарм',
        # Медицинские центры
        'инвитро', 'медси', 'см-клиника'
    ],
    'одежда и обувь': [
        # Основные типы
        'одежда', 'обувь', 'джинсы', 'футболка', 'куртка', 'платье', 'ботинки', 'туфли',
        'кроссовки', 'рубашка', 'штаны', 'юбка', 'брюки', 'костюм', 'пальто',
        # Бренды
        'zara', 'h&m', 'hm', 'uniqlo', 'mango', 'bershka', 'pull&bear', 'massimo dutti',
        'reserved', 'colin\'s', 'gloria jeans', 'спортмастер', 'декатлон',
        # Магазины
        'ламода', 'центробувь', 'экко', 'рандеву', 'вещевой рынок'
    ],
    'развлечения': [
        # Основные
        'кино', 'театр', 'концерт', 'клуб', 'бар', 'паб', 'игры', 'боулинг', 'квест',
        'караоке', 'бильярд', 'картинг', 'пейнтбол', 'лазертаг',
        # Кинотеатры
        'кинотеатр', 'каро', 'формула кино', 'синема парк', 'imax', 'киномакс',
        # Спорт
        'фитнес', 'тренажерный зал', 'тренажерка', 'бассейн', 'йога', 'танцы', 'секция',
        'спортзал', 'фитнес-клуб', 'каток', 'лыжи', 'коньки'
    ],
    'дом и жкх': [
        # Основные платежи
        'жилье', 'квартира', 'дом', 'коммуналка', 'квартплата', 'жкх', 'свет', 'вода',
        'газ', 'отопление', 'электричество', 'канализация', 'водоотведение',
        # Аренда и ипотека
        'аренда', 'ипотека', 'наем', 'съем',
        # Ремонт и обслуживание
        'ремонт', 'сантехник', 'электрик', 'клининг', 'уборка', 'домофон',
        # Мебель и товары для дома
        'мебель', 'ikea', 'икея', 'леруа мерлен', 'obi', 'стройматериалы'
    ],
    'связь и интернет': [
        # Основные услуги
        'связь', 'интернет', 'телефон', 'мобильный', 'сотовая',
        # Операторы
        'мтс', 'билайн', 'мегафон', 'теледва', 'теле2', 'ростелеком', 'йота',
        # Услуги
        'тариф', 'пополнение', 'роуминг', 'сим-карта', 'sim'
    ],
    'образование': [
        # Основные
        'образование', 'курсы', 'школа', 'университет', 'репетитор', 'учебники',
        'обучение', 'тренинг', 'семинар', 'вебинар', 'конференция',
        # Онлайн платформы
        'coursera', 'udemy', 'skillbox', 'geekbrains', 'нетология', 'яндекс.практикум',
        # Языковые курсы
        'английский', 'english', 'skyeng', 'инглекс'
    ],
    'автомобиль': [
        # Основные расходы
        'автомобиль', 'машина', 'сто', 'ремонт', 'запчасти', 'мойка', 'парковка',
        'штраф', 'страховка', 'каско', 'осаго', 'техосмотр', 'шиномонтаж',
        # Расходные материалы
        'масло', 'фильтр', 'антифриз', 'тормозная жидкость', 'аккумулятор',
        # Услуги
        'шины', 'резина', 'диски', 'покраска', 'полировка'
    ],
    'подарки': [
        # Основные
        'подарок', 'подарки', 'день рождения', 'др', 'праздник', 'сувенир',
        'цветы', 'букет', 'роза', 'тюльпан', 'цветочный', 'открытка',
        # Праздники
        'новый год', '8 марта', '23 февраля', '14 февраля', 'рождество', 'свадьба'
    ],
    'путешествия': [
        # Основные
        'путешествие', 'отпуск', 'билет', 'отель', 'гостиница', 'хостел',
        'самолет', 'поезд', 'виза', 'тур', 'экскурсия', 'бронь',
        # Транспорт
        'аэропорт', 'вокзал', 'ржд', 'аэрофлот', 'победа', 's7',
        # Бронирование
        'booking', 'airbnb', 'островок', 'туту.ru', 'яндекс.путешествия'
    ],
    'прочее': ['прочее', 'другое', 'разное']
}


def detect_income_intent(text: str) -> bool:
    """
    Определяет, является ли текст доходом по знаку + или слову "плюс"

    Примеры:
    - "+5000" -> True
    - "+5000 зарплата" -> True
    - "долг +1200" -> True
    - "плюс 5000" -> True
    - "зарплата плюс 3000" -> True
    - "плюс 1000 долг" -> True
    - "зарплата 100000" -> False (нет знака + или слова "плюс")
    - "получил 5000" -> False (нет знака + или слова "плюс")
    - "заработал 3000" -> False (нет знака + или слова "плюс")
    - "кофе 200" -> False
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Проверяем наличие знака + перед числом
    for pattern in INCOME_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    
    return False


def detect_currency(text: str, user_currency: str = 'RUB') -> str:
    """Detect currency from text"""
    text_lower = text.lower()
    
    for currency, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return currency
    
    return (user_currency or 'RUB').upper()  # Default to user's currency in uppercase


async def parse_expense_message(text: str, user_id: Optional[int] = None, profile=None, use_ai: bool = True) -> Optional[Dict[str, Any]]:
    """
    Парсит текстовое сообщение и извлекает информацию о расходе

    Примеры:
    - "Кофе 200" -> {'amount': 200, 'description': 'Кофе', 'category': 'кафе'}
    - "-200 кофе" -> {'amount': 200, 'description': 'кофе', 'category': 'кафе'}
    - "минус 500 обед" -> {'amount': 500, 'description': 'обед', 'category': 'кафе'}
    - "Дизель 4095 АЗС" -> {'amount': 4095, 'description': 'Дизель АЗС', 'category': 'транспорт'}
    - "Продукты в пятерочке 1500" -> {'amount': 1500, 'description': 'Продукты в пятерочке', 'category': 'продукты'}
    - "Кофе 200 15.03.2024" -> {'amount': 200, 'description': 'Кофе', 'expense_date': date(2024, 3, 15)}
    - "25.12.2023 подарки 5000" -> {'amount': 5000, 'description': 'подарки', 'expense_date': date(2023, 12, 25)}
    """
    if not text:
        return None

    # Сохраняем оригинальный текст
    original_text = text.strip()

    # Удаляем знак минус или слово "минус" из начала текста, если они есть
    # Это нужно для корректного парсинга суммы
    text_cleaned = original_text
    for pattern in EXPENSE_PATTERNS:
        match = re.search(pattern, text_cleaned.lower())
        if match:
            # Удаляем знак минус или слово "минус"
            if text_cleaned.lower().startswith('минус'):
                text_cleaned = text_cleaned[5:].strip()
            elif text_cleaned.startswith('-'):
                text_cleaned = text_cleaned[1:].strip()
            break

    # Сначала извлекаем дату, если она есть
    expense_date, text_without_date = extract_date_from_text(text_cleaned)

    # Используем текст без даты для дальнейшего парсинга
    text_to_parse = text_without_date
    
    # Ищем сумму
    amount = None
    amount_str = None
    text_without_amount = None
    
    for pattern in AMOUNT_PATTERNS:
        # Ищем в тексте без даты (не в lowercase, чтобы позиции совпадали)
        match = re.search(pattern, text_to_parse, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = Decimal(amount_str)
                # Убираем найденную сумму из текста без даты для получения описания
                # Находим позицию совпадения в тексте без даты
                match_start = match.start()
                match_end = match.end()
                text_without_amount = (text_to_parse[:match_start] + ' ' + text_to_parse[match_end:]).strip()
                break
            except (ValueError, InvalidOperation) as e:
                logger.debug(f"Ошибка при парсинге суммы '{amount_str}': {e}")
                continue
    
    # Если не нашли сумму, пытаемся найти последнюю трату с таким же названием
    if not amount or amount <= 0:
        if user_id:
            from bot.services.expense import get_last_expense_by_description
            # Пытаемся найти последнюю трату с похожим описанием
            last_expense = await get_last_expense_by_description(user_id, original_text)
            if last_expense:
                # Используем сумму и категорию из найденной траты
                amount = last_expense.amount
                category_id = last_expense.category_id
                category_name = None
                
                # Безопасно получаем имя категории (уже должно быть загружено через select_related)
                try:
                    if last_expense.category:
                        # Используем язык пользователя для отображения категории
                        lang_code = profile.language_code if profile and hasattr(profile, 'language_code') else 'ru'
                        category_name = get_category_display_name(last_expense.category, lang_code)
                except (AttributeError, TypeError) as e:
                    logger.debug(f"Error getting category name: {e}")
                    pass
                    
                # Используем текст без даты для описания
                desc_text = text_without_date if text_without_date else original_text
                # Сохраняем описание с капитализацией первой буквы
                description = desc_text[0].upper() + desc_text[1:] if len(desc_text) > 1 else desc_text.upper() if desc_text else 'Расход'
                
                result = {
                    'amount': float(amount),
                    'description': description,
                    'category': category_name,
                    'category_id': category_id,
                    'currency': last_expense.currency or 'RUB',
                    'confidence': 0.8,  # Высокая уверенность, так как нашли похожую трату
                    'reused_from_last': True,  # Флаг, что данные взяты из предыдущей траты
                    'expense_date': expense_date  # Добавляем дату, если она была указана
                }
                
                logger.info(f"Нашли похожую трату '{last_expense.description}' с суммой {amount}")
                return result
        
        # Если не нашли похожую трату, возвращаем None
        return None
    
    # Определяем категорию
    category = None
    max_score = 0
    text_lower = text_to_parse.lower()  # Создаем text_lower для поиска категорий
    
    # Сначала проверяем пользовательские категории, если есть профиль
    if profile:
        from expenses.models import ExpenseCategory, CategoryKeyword
        from asgiref.sync import sync_to_async
        
        # Получаем категории пользователя с их ключевыми словами
        @sync_to_async
        def get_user_categories():
            return list(ExpenseCategory.objects.filter(profile=profile).prefetch_related('keywords'))
        
        user_categories = await get_user_categories()
        
        # Проверяем каждую категорию пользователя
        for user_cat in user_categories:
            user_cat_lower = user_cat.name.lower()
            
            # Проверяем прямое вхождение названия категории в текст
            if user_cat_lower in text_lower:
                # Используем язык пользователя для отображения категории
                lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                category = get_category_display_name(user_cat, lang_code)
                max_score = 100  # Максимальный приоритет для пользовательских категорий
                break
            
            # Проверяем ключевые слова пользовательской категории
            @sync_to_async
            def get_keywords():
                return list(user_cat.keywords.all())
            
            keywords = await get_keywords()
            for kw in keywords:
                if kw.keyword.lower() in text_lower:
                    # Используем язык пользователя для отображения категории
                    lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                    category = get_category_display_name(user_cat, lang_code)
                    max_score = 100
                    break
            
            if category:
                break
    
    # Если не нашли в пользовательских, ищем в стандартных
    if not category:
        for cat_name, keywords in MODEL_CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if score > max_score:
                max_score = score
                category = cat_name
    
    # Формируем описание (текст без суммы и без даты)
    description = text_without_amount if text_without_amount is not None else text_without_date
    
    # Убираем слова-маркеры времени из описания, даже если они не были обработаны как даты
    time_words = ['вчера', 'позавчера', 'сегодня', 'завтра']
    for word in time_words:
        description = re.sub(r'\b' + word + r'\b', '', description, flags=re.IGNORECASE)
    
    # Убираем лишние пробелы
    description = ' '.join(description.split())
    
    # Капитализируем только первую букву, не меняя регистр остальных
    if description and len(description) > 0:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Определяем валюту
    user_currency = (profile.currency if profile else 'RUB') or 'RUB'
    user_currency = user_currency.upper()
    currency = detect_currency(original_text, user_currency)
    
    # Базовый результат (НЕ заполняем category если не найдена)
    result = {
        'amount': float(amount),
        'description': description or 'Расход',
        'category': category,  # Оставляем None если не найдено
        'currency': currency,
        'confidence': 0.5 if category else 0.2,
        'expense_date': expense_date  # Добавляем дату, если она была указана
    }
    
    # Попробуем улучшить с помощью AI, если:
    # 1. Не нашли категорию по ключевым словам
    # 2. Или нашли, но её нет у пользователя
    if use_ai and user_id and profile:
        should_use_ai = False
        
        # Проверяем, нужно ли использовать AI
        if not category:
            should_use_ai = True
            logger.info(f"No category found by keywords for '{text}', will use AI")
        else:
            # Проверяем, есть ли такая категория у пользователя
            from expenses.models import ExpenseCategory
            from asgiref.sync import sync_to_async
            @sync_to_async
            def get_user_category_names():
                return list(ExpenseCategory.objects.filter(profile=profile).values_list('name', flat=True))
            
            user_categories = await get_user_category_names()
            
            # Проверяем точное и частичное совпадение
            category_exists = any(
                category.lower() in cat.lower() or cat.lower() in category.lower() 
                for cat in user_categories
            )
            
            if not category_exists:
                should_use_ai = True
                logger.info(f"Category '{category}' not found in user categories, will use AI")
        
        if should_use_ai:
            try:
                from bot.services.ai_selector import get_service
                
                # Получаем категории пользователя
                @sync_to_async
                def get_profile_categories():
                    return list(ExpenseCategory.objects.filter(profile=profile).values_list('name', flat=True))
                
                user_categories = await get_profile_categories()
                
                if user_categories:
                    # Получаем контекст пользователя (недавние категории)
                    user_context = {}
                    @sync_to_async
                    def get_recent_expenses():
                        return list(
                            profile.expenses.select_related('category')
                            .order_by('-created_at')[:10]
                        )
                    
                    recent_expenses = await get_recent_expenses()
                    if recent_expenses:
                        # Используем язык пользователя для отображения категорий
                        lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                        recent_categories = list(set([
                            get_category_display_name(exp.category, lang_code) for exp in recent_expenses 
                            if exp.category
                        ]))[:3]
                        if recent_categories:
                            user_context['recent_categories'] = recent_categories
                    
                    # Пробуем сначала основной AI сервис с таймаутом
                    try:
                        logger.info(f"Getting AI service for categorization...")
                        ai_service = get_service('categorization')
                        logger.info(f"AI service obtained: {type(ai_service).__name__}")
                        logger.info(f"Calling categorize_expense with timeout=15s...")
                        ai_result = await asyncio.wait_for(
                            ai_service.categorize_expense(
                                text=text_without_date,  # Отправляем текст без даты
                                amount=amount,
                                currency=currency,
                                categories=user_categories,
                                user_context=user_context
                            ),
                            timeout=15.0  # 15 секунд общий таймаут для изолированного процесса
                        )
                        logger.info(f"AI categorization completed")
                    except asyncio.TimeoutError:
                        logger.warning(f"AI categorization timeout for '{original_text}'")
                        ai_result = None
                    except Exception as e:
                        logger.error(f"AI categorization error: {e}")
                        ai_result = None
                    
                    # Если Google AI не сработал, пробуем OpenAI
                    if not ai_result:
                        logger.warning(f"Primary AI failed, trying fallback to OpenAI")
                        from bot.services.ai_selector import AISelector
                        try:
                            openai_service = AISelector('openai')
                            ai_result = await asyncio.wait_for(
                                openai_service.categorize_expense(
                                    text=text_without_date,  # Отправляем текст без даты
                                    amount=amount,
                                    currency=currency,
                                    categories=user_categories,
                                    user_context=user_context
                                ),
                                timeout=5.0  # 5 секунд таймаут для fallback
                            )
                            if ai_result:
                                logger.info(f"OpenAI fallback successful")
                        except asyncio.TimeoutError:
                            logger.error(f"OpenAI fallback timeout")
                        except Exception as e:
                            logger.error(f"OpenAI fallback failed: {e}")
                    
                    if ai_result:
                        # Обновляем только категорию из AI
                        result['category'] = ai_result.get('category', result['category'])
                        result['confidence'] = ai_result.get('confidence', result['confidence'])
                        result['ai_enhanced'] = True
                        result['ai_provider'] = ai_result.get('provider', 'unknown')
                        
                        # Безопасное логирование без Unicode
                        try:
                            # Оставляем эмодзи но убираем их из лога
                            if result['category']:
                                cat_clean = ''.join(c for c in result['category'] if ord(c) < 128).strip()
                                if not cat_clean and result['category']:
                                    cat_clean = 'category with emoji'
                                logger.info(f"AI enhanced result for user {user_id}: category='{cat_clean}', confidence={result['confidence']}, provider={result['ai_provider']}")
                        except (AttributeError, KeyError, TypeError) as e:
                            logger.debug(f"Error logging AI result: {e}")
                            pass
                    
            except Exception as e:
                logger.error(f"AI categorization failed: {e}")
    
    # Финальный fallback - если категория все еще не определена
    if not result['category']:
        result['category'] = 'Прочие расходы'
        logger.info(f"Using default category 'Прочие расходы' for '{original_text}'")
    
    return result


async def parse_income_message(text: str, user_id: Optional[int] = None, profile=None, use_ai: bool = True) -> Optional[Dict[str, Any]]:
    """
    Парсит текстовое сообщение и извлекает информацию о доходе
    
    Примеры:
    - "+5000" -> {'amount': 5000, 'description': 'Доход', 'is_income': True}
    - "зарплата 100000" -> {'amount': 100000, 'description': 'Зарплата', 'category': '💼 Зарплата'}
    - "получил премию 50000" -> {'amount': 50000, 'description': 'Получил премию', 'category': '🎁 Премии и бонусы'}
    """
    if not text:
        return None
    
    # Сохраняем оригинальный текст
    original_text = text.strip()
    
    # Убираем символ + в начале для парсинга суммы
    text_for_parsing = original_text
    if text_for_parsing.startswith('+'):
        text_for_parsing = text_for_parsing[1:].strip()
    
    # Сначала извлекаем дату, если она есть
    expense_date, text_without_date = extract_date_from_text(text_for_parsing)
    
    # Используем текст без даты для дальнейшего парсинга
    text_to_parse = text_without_date
    text_lower = text_to_parse.lower()
    
    # Ищем сумму
    amount = None
    amount_str = None
    text_without_amount = None
    
    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = Decimal(amount_str)
                # Убираем найденную сумму из текста для получения описания
                match_start = match.start()
                match_end = match.end()
                text_without_amount = (text_to_parse[:match_start] + ' ' + text_to_parse[match_end:]).strip()
                break
            except (ValueError, InvalidOperation) as e:
                logger.debug(f"Ошибка при парсинге суммы дохода '{amount_str}': {e}")
                continue
    
    # Если не нашли сумму, пытаемся найти последний доход с таким же названием
    if not amount or amount <= 0:
        if user_id:
            from bot.services.income import get_last_income_by_description
            # Пытаемся найти последний доход с похожим описанием
            last_income = await get_last_income_by_description(user_id, original_text)
            if last_income:
                amount = last_income.amount
                # Используем язык пользователя для отображения категории дохода
                if last_income.category:
                    lang_code = profile.language_code if profile and hasattr(profile, 'language_code') else 'ru'
                    category = get_category_display_name(last_income.category, lang_code)
                else:
                    category = None
                # Используем текст без даты как описание
                description = text_without_date if text_without_date else original_text
                
                # Убираем символ + из описания если он есть
                if description and description.startswith('+'):
                    description = description[1:].strip()
                
                result = {
                    'amount': float(amount),
                    'description': description,
                    'income_date': expense_date or date.today(),
                    'income_type': last_income.income_type if hasattr(last_income, 'income_type') else 'other',
                    'currency': last_income.currency or 'RUB',
                    'is_income': True,
                    'similar_income': True,
                    'ai_enhanced': False,
                    'category_key': normalize_income_category_key(category) if category else None
                }
                if category:
                    result['category'] = category
                
                logger.info(f"Found similar income for '{original_text}': amount={amount}, category={category}")
                return result
        
        # Если не нашли похожий доход, возвращаем None
        return None
    
    # Определяем категорию дохода
    category = None
    category_key = None
    income_type = 'other'
    ai_categorized = False
    ai_confidence = None

    # Определяем язык пользователя для отображения категорий
    lang_code = 'ru'
    if profile and hasattr(profile, 'language_code') and profile.language_code:
        candidate_lang = profile.language_code.lower()
        if candidate_lang in ('ru', 'en'):
            lang_code = candidate_lang

    # Пытаемся определить категорию по встроенным ключевым словам
    detected_key = detect_income_category_key(text_lower)
    if detected_key:
        category_key = detected_key
        category = get_income_category_display_for_key(category_key, lang_code)
        income_type = get_income_type(category_key)

    # Если категорию не нашли, пытаемся определить через AI
    if not category and profile and use_ai:
        from bot.services.income_categorization import categorize_income

        ai_result = await categorize_income(text_without_date if text_without_date else original_text, user_id, profile)

        if ai_result:
            ai_category_label = ai_result.get('category')
            ai_category_key = normalize_income_category_key(ai_category_label)
            if ai_category_key:
                category_key = ai_category_key
                category = get_income_category_display_for_key(ai_category_key, lang_code)
                income_type = get_income_type(ai_category_key)
            elif ai_category_label:
                category = ai_category_label

            if ai_result.get('description'):
                description = ai_result['description']
            if not amount and ai_result.get('amount'):
                amount = Decimal(str(ai_result['amount']))

            ai_categorized = True
            ai_confidence = ai_result.get('confidence', 0.5)

    # Если AI не сработал, пытаемся найти по ключевым словам пользователя
    if not category and profile:
        from expenses.models import IncomeCategory, IncomeCategoryKeyword
        from asgiref.sync import sync_to_async

        try:
            @sync_to_async
            def get_income_keywords():
                return list(
                    IncomeCategoryKeyword.objects.filter(
                        category__profile=profile,
                        category__is_active=True
                    ).select_related('category')
                )

            keywords = await get_income_keywords()

            best_match = None
            best_weight = 0

            for keyword_obj in keywords:
                if keyword_obj.keyword.lower() in text_lower and keyword_obj.normalized_weight > best_weight:
                    best_match = keyword_obj.category
                    best_weight = keyword_obj.normalized_weight

            if best_match:
                category = get_category_display_name(best_match, lang_code)
                normalized_key = normalize_income_category_key(category)
                if normalized_key:
                    category_key = normalized_key
                    income_type = get_income_type(category_key)
        except Exception as e:
            logger.warning(f"Error checking income keywords: {e}")

        if not category:
            @sync_to_async
            def get_income_category_names():
                return list(IncomeCategory.objects.filter(profile=profile).values_list('name', flat=True))

            user_income_categories = await get_income_category_names()

            for user_cat in user_income_categories:
                lowered = user_cat.lower()
                if lowered in text_lower or any(word in lowered for word in text_lower.split()):
                    category = user_cat
                    normalized_key = normalize_income_category_key(user_cat)
                    if normalized_key:
                        category_key = normalized_key
                        category = get_income_category_display_for_key(category_key, lang_code)
                        income_type = get_income_type(category_key)
                    break

    # Финальные сопряжения
    if category and not category_key:
        normalized_key = normalize_income_category_key(category)
        if normalized_key:
            category_key = normalized_key
            category = get_income_category_display_for_key(category_key, lang_code)
            income_type = get_income_type(category_key)

    if not category:
        category_key = category_key or DEFAULT_INCOME_CATEGORY_KEY
        category = get_income_category_display_for_key(category_key, lang_code)
        income_type = get_income_type(category_key)

    # Формируем описание (используем текст без даты и без суммы)
    description = text_without_amount if text_without_amount else (text_without_date if text_without_date else 'Доход')
    
    # Убираем знак "+" из описания
    if description:
        description = description.replace('+', '').strip()
    
    # Убираем лишние пробелы и капитализируем
    description = ' '.join(description.split())
    if description and len(description) > 0:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Если описание пустое или слишком короткое, используем категорию или тип дохода
    if not description or len(description) < 2:
        if category:
            # Убираем эмодзи из категории для описания
            description = re.sub(r'[^\w\s]', '', category).strip()
        elif income_type != 'other':
            type_descriptions = {
                'ru': {
                    'salary': 'Зарплата',
                    'bonus': 'Премия',
                    'freelance': 'Фриланс',
                    'investment': 'Инвестиции',
                    'interest': 'Проценты',
                    'refund': 'Возврат',
                    'cashback': 'Кешбэк',
                    'gift': 'Подарок',
                    'other': 'Доход',
                },
                'en': {
                    'salary': 'Salary',
                    'bonus': 'Bonus',
                    'freelance': 'Freelance',
                    'investment': 'Investments',
                    'interest': 'Interest',
                    'refund': 'Refund',
                    'cashback': 'Cashback',
                    'gift': 'Gift',
                    'other': 'Income',
                },
            }
            localized_map = type_descriptions['en'] if lang_code == 'en' else type_descriptions['ru']
            description = localized_map.get(income_type, localized_map['other'])
        else:
            description = 'Income' if lang_code == 'en' else 'Доход'
    
    # Определяем валюту
    user_currency = (profile.currency if profile else 'RUB') or 'RUB'
    user_currency = user_currency.upper()
    currency = detect_currency(original_text, user_currency)
    
    # Формируем результат
    result = {
        'amount': float(amount),
        'description': description,
        'category_key': category_key,
        'category': category,
        'income_type': income_type,
        'currency': currency,
        'confidence': ai_confidence if ai_confidence else (0.8 if category else 0.5),
        'income_date': expense_date,
        'is_income': True,  # Флаг, что это доход
        'ai_categorized': ai_categorized,
        'ai_confidence': ai_confidence
    }
    
    return result


async def extract_amount_from_text(text: str) -> Optional[float]:
    """
    Извлекает только сумму из текста
    """
    parsed = await parse_expense_message(text, use_ai=False)
    return parsed['amount'] if parsed else None


def suggest_category(description: str) -> str:
    """
    Предлагает категорию на основе описания
    """
    description_lower = description.lower()
    
    # Используем новые категории из models.py
    for category, keywords in MODEL_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in description_lower:
                return category
    
    return 'Прочие расходы'
