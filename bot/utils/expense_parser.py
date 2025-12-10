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
from bot.utils.language import get_text
from bot.utils.emoji_utils import strip_leading_emoji

logger = logging.getLogger(__name__)

# Словарь для конвертации чисел словами в цифры
WORD_TO_NUMBER = {
    # Английский - units, teens, tens
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100,
    # Русский - units, teens, tens
    'ноль': 0, 'нуль': 0,
    'один': 1, 'одна': 1, 'одно': 1, 'одну': 1,
    'два': 2, 'две': 2, 'двух': 2,
    'три': 3, 'трех': 3, 'трёх': 3,
    'четыре': 4, 'четырех': 4, 'четырёх': 4,
    'пять': 5, 'пяти': 5,
    'шесть': 6, 'шести': 6,
    'семь': 7, 'семи': 7,
    'восемь': 8, 'восьми': 8,
    'девять': 9, 'девяти': 9,
    'десять': 10, 'десяти': 10,
    # Русский - teens
    'одиннадцать': 11, 'двенадцать': 12, 'тринадцать': 13, 'четырнадцать': 14,
    'пятнадцать': 15, 'шестнадцать': 16, 'семнадцать': 17, 'восемнадцать': 18,
    'девятнадцать': 19,
    # Русский - tens
    'двадцать': 20, 'тридцать': 30, 'сорок': 40, 'пятьдесят': 50,
    'шестьдесят': 60, 'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90,
    # Русский - hundreds
    'сто': 100, 'ста': 100,
    'двести': 200, 'триста': 300, 'четыреста': 400,
    'пятьсот': 500, 'шестьсот': 600, 'семьсот': 700,
    'восемьсот': 800, 'девятьсот': 900,
}

# Словарь множителей для сумм
AMOUNT_MULTIPLIERS = {
    # Русский
    'тысяч': 1000,
    'тысячи': 1000,
    'тысяча': 1000,
    'тыс': 1000,
    'к': 1000,  # 10к
    'миллион': 1000000,
    'миллиона': 1000000,
    'миллионов': 1000000,
    'млн': 1000000,
    'м': 1000000,  # 2м
    # English
    'thousand': 1000,
    'thousands': 1000,
    'k': 1000,  # 10k
    'million': 1000000,
    'millions': 1000000,
    'm': 1000000,  # 2m
}

MULTIPLIERS = AMOUNT_MULTIPLIERS
NEGATIVE_WORDS = {'минус', 'minus'}

def keyword_matches_in_text(keyword: str, text: str) -> bool:
    """
    Проверяет есть ли ключевое слово в тексте как ЦЕЛОЕ СЛОВО с учетом склонений.
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

def convert_words_to_numbers(text: str) -> str:
    """
    Конвертирует числа словами в цифры, поддерживая составные числа.
    Также обрабатывает комбинации цифр + множитель (50 тыс -> 50000).
    Примеры:
    - "two hundred" -> "200"
    - "twenty five thousand" -> "25000"
    - "Apple minus two" -> "Apple -2"
    - "двести пятьдесят" -> "250"
    - "50 тыс" -> "50000"
    - "10к" -> "10000"
    """
    if not text:
        return text

    # Сначала обрабатываем комбинации "число + множитель" (50 тыс, 10к, 5 млн)
    # Это нужно делать ДО разбиения на слова

    # Паттерн: число (с возможной десятичной частью) + пробел? + множитель
    # Примеры: "50 тыс", "10к", "5.5 млн", "100 тысяч"
    for mult_word, mult_value in sorted(AMOUNT_MULTIPLIERS.items(), key=lambda x: -len(x[0])):
        # Паттерн для числа с пробелом перед множителем: "50 тыс"
        pattern_with_space = rf'(\d+(?:[.,]\d+)?)\s+{re.escape(mult_word)}\b'
        match = re.search(pattern_with_space, text, re.IGNORECASE)
        if match:
            num = float(match.group(1).replace(',', '.'))
            result = int(num * mult_value) if num * mult_value == int(num * mult_value) else num * mult_value
            text = text[:match.start()] + str(result) + text[match.end():]
            # Продолжаем искать другие комбинации
            continue

        # Паттерн для слитного написания: "10к", "5млн" (только для коротких множителей)
        if len(mult_word) <= 3:  # к, k, м, m, тыс, млн
            pattern_no_space = rf'(\d+(?:[.,]\d+)?){re.escape(mult_word)}\b'
            match = re.search(pattern_no_space, text, re.IGNORECASE)
            if match:
                num = float(match.group(1).replace(',', '.'))
                result = int(num * mult_value) if num * mult_value == int(num * mult_value) else num * mult_value
                text = text[:match.start()] + str(result) + text[match.end():]

    processed_text = text.replace('-', ' ')
    words = processed_text.split()
    result_words = []
    current_number_chunk = 0
    current_total = 0
    is_negative = False
    number_sequence_started = False
    last_was_hundred = False  # Track if last word was 'hundred' to prevent repeated multiplication
    trailing_punctuation = ""  # Store punctuation from the last number word

    i = 0
    while i < len(words):
        original_word = words[i]
        # Extract trailing punctuation
        clean_word = original_word.rstrip('.,!?;:()')
        word_punctuation = original_word[len(clean_word):]
        clean_word = clean_word.lower()

        # Skip 'and' within number sequences
        if clean_word == 'and' and number_sequence_started:
            if i + 1 < len(words):
                next_word = words[i+1].rstrip('.,!?;:()').lower()
                if next_word in WORD_TO_NUMBER or next_word in MULTIPLIERS:
                    i += 1
                    continue

        # Handle negative words (minus/минус)
        if clean_word in NEGATIVE_WORDS:
            if i + 1 < len(words):
                next_word = words[i+1].rstrip('.,!?;:()').lower()
                if next_word in WORD_TO_NUMBER or next_word in MULTIPLIERS:
                    is_negative = True
                    i += 1
                    continue

        # Process number words
        if clean_word in WORD_TO_NUMBER:
            number_sequence_started = True
            val = WORD_TO_NUMBER[clean_word]

            if val == 100:
                # Validate: prevent repeated 'hundred' (e.g., "hundred hundred")
                if last_was_hundred:
                    # Emit previous chunk and start fresh
                    if current_number_chunk > 0:
                        result_words.append(str(current_number_chunk) + trailing_punctuation)
                        trailing_punctuation = ""
                    current_number_chunk = 100
                elif current_number_chunk > 0:
                    current_number_chunk *= 100
                else:
                    current_number_chunk = 100
                last_was_hundred = True
            else:
                current_number_chunk += val
                last_was_hundred = False

            # Save punctuation from this word
            trailing_punctuation = word_punctuation

        elif clean_word in MULTIPLIERS:
            number_sequence_started = True
            multiplier = MULTIPLIERS[clean_word]

            if current_number_chunk > 0:
                current_total += current_number_chunk * multiplier
            else:
                # Handle standalone multiplier (e.g., "thousand" -> 1000)
                current_total += multiplier

            current_number_chunk = 0
            last_was_hundred = False
            trailing_punctuation = word_punctuation

        else:
            # Non-number word: emit accumulated number if any
            if number_sequence_started:
                final_number = current_total + current_number_chunk
                if is_negative:
                    final_number = -final_number
                    is_negative = False

                result_words.append(str(final_number) + trailing_punctuation)
                trailing_punctuation = ""
                current_total = 0
                current_number_chunk = 0
                number_sequence_started = False
                last_was_hundred = False

            # Handle hanging negative
            if is_negative:
                result_words.append("минус")
                is_negative = False

            result_words.append(original_word)

        i += 1

    # Emit final number if sequence ended with a number
    if number_sequence_started:
        final_number = current_total + current_number_chunk
        if is_negative:
            final_number = -final_number
        result_words.append(str(final_number) + trailing_punctuation)

    return ' '.join(result_words)

def make_sync_to_async(func):
    """Создает обертку для синхронной функции для использования в асинхронном контексте"""
    return sync_to_async(func)

# Паттерны для извлечения даты
DATE_PATTERNS = [
    r'(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})',  # дд.мм.гггг или дд/мм/гггг
    r'(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{2})',    # дд.мм.гг или дд/мм/гг
]

# Паттерны для извлечения суммы
AMOUNT_PATTERNS = [
    # Числа с точкой-разделителем тысяч (10.000.000 сум) - ВЫСШИЙ ПРИОРИТЕТ!
    # Точка как разделитель тысяч: ровно 3 цифры после каждой точки
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:рублей|rub+les?|руб|₽|р)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:доллар(?:ов)?|dollars?|долл|usd|\$)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:euros?|евро|eur|€)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:pounds?|фунт(?:ов)?|gbp|£)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:юаней|yuan|юан|cny|¥)\b',
    r"(\d{1,3}(?:\.\d{3})+)\s*(?:сум(?:ов)?|so['\']m|uzs|uzbek\S*\s+so['\']m)\b",
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:тенге|теньге|тнг|kzt|tenge)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:гривен|гривн[а-я]*|грн|uah)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*(?:лари|lari|gel)\b',
    r'(\d{1,3}(?:\.\d{3})+)\s*$',
    r'^(\d{1,3}(?:\.\d{3})+)\s',
    # Числа с пробелами-разделителями тысяч (ПРИОРИТЕТ!)
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:рублей|rub+les?|руб|₽|р)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:доллар(?:ов)?|dollars?|долл|usd|\$)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:euros?|евро|eur|€)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:pounds?|фунт(?:ов)?|gbp|£)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:юаней|yuan|юан|cny|¥)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:аргентинских?|pesos?|песо|ars)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:колумбийских?|cop)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:перуанских?|soles?|солей?|pen)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:чилийских?|clp)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:мексиканских?|mxn)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:бразильских?|reais?|реалов?|brl)\b',
    # CIS currencies
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лари|lari|gel|georgian\s+lari)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:тенге|теньге|тнг|kzt|tenge|kazakh\S*\s+tenge)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:гривен|гривн[а-я]*|грн|uah|hryvnia|hryvnya|ukrainian\s+hryvnia)\b',
    r"(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сум(?:ов)?|so['\']m|uzs|uzbek\S*\s+so['\']m)\b",
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:драм(?:ов)?|dram|amd|armenian\s+dram)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:манат(?:ов)?|manat|azn|azerbaijani\s+manat)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сом(?:ов)?|kgs|kyrgyz\S*\s+som)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сомони|somoni|tjs|tajik\S*\s+somoni)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лей|леев|лея|mdl|lei|moldovan\s+lei?)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:бел[ао]рус\S*\s+руб\S*|byn|byr|belarusian\s+ruble?)\b',
    # Other world currencies
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:франк(?:ов|а)?|francs?|chf|swiss\s+francs?)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:рупи[йяею]|rupees?|inr|indian\s+rupees?)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лир[аы]?|liras?|try|turkish\s+liras?)\b',
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*$',
    r'^(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s',
    # Fallback
    r'(\d+(?:[.,]\d+)?)\s*(?:рублей|rub+les?|руб|₽|р)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:доллар(?:ов)?|dollars?|долл|usd|\$)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:euros?|евро|eur|€)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:pounds?|фунт(?:ов)?|gbp|£)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:юаней|yuan|юан|cny|¥)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:аргентинских?|pesos?|песо|ars)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:колумбийских?|cop)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:перуанских?|soles?|солей?|pen)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:чилийских?|clp)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:мексиканских?|mxn)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:бразильских?|reais?|реалов?|brl)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:лари|lari|gel)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:тенге|теньге|тнг|kzt|tenge)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:гривен|гривн[а-я]*|грн|uah|hryvnia|hryvnya|uah)\b',
    r"(\d+(?:[.,]\d+)?)\s*(?:сум(?:ов)?|so['\']m|uzs)\b",
    r'(\d+(?:[.,]\d+)?)\s*(?:драм(?:ов)?|dram|amd)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:манат(?:ов)?|manat|azn)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:сом(?:ов)?|som|kgs)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:сомони|somoni|tjs)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:лей|леев|лея|mdl|lei)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:бел[ао]рус\S*\s+руб\S*|byn|byr|belarusian\s+ruble?)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:франк(?:ов|а)?|francs?|chf)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:рупи[йяею]|rupees?|inr)\b',
    r'(\d+(?:[.,]\d+)?)\s*(?:лир[аы]?|liras?|try)\b',
    r'(\d+(?:[.,]\d+)?)\s*$',
    r'^(\d+(?:[.,]\d+)?)\s',
    r'\s(\d+(?:[.,]\d+)?)\s',
]

# Паттерны для определения валюты
# ВАЖНО: Используем (?<![а-яА-Яa-zA-Z]) вместо \b в начале чтобы работало
# для слитного написания с числом (100лари, 500руб, etc)
CURRENCY_PATTERNS = {
    # Major world currencies
    'USD': [r'\$', r'\busd\b', r'(?<![а-яА-Я])долл', r'(?<![а-яА-Я])доллар', r'\bdollars?\b'],
    'EUR': [r'€', r'\beur\b', r'(?<![а-яА-Я])евро', r'\beuro'],
    'GBP': [r'£', r'\bgbp\b', r'(?<![а-яА-Я])фунт', r'\bsterling', r'\bpounds?\b'],
    'CNY': [r'¥', r'\bcny\b', r'(?<![а-яА-Я])юан', r'\byuan', r'\brenminbi', r'\brmb\b'],
    'CHF': [r'\bchf\b', r'₣', r'(?<![а-яА-Я])франк(?:ов|а)?\b', r'\bswiss\s+franc', r'\bfrancs?\b'],
    'INR': [r'\binr\b', r'₹', r'(?<![а-яА-Я])рупи[йяею]', r'(?<![а-яА-Я])индийск.*руп', r'\brupees?\b'],
    'TRY': [r'\btry\b', r'₺', r'(?<![а-яА-Я])лир[аиы]?\b', r'(?<![а-яА-Я])турец.*лир', r'\bliras?\b'],

    # Local currencies (CIS and nearby) - только рядом с числами
    'KZT': [r'\bkzt\b', r'₸', r'(?<![а-яА-Я])тенге\b', r'(?<![а-яА-Я])теньге\b', r'(?<![а-яА-Я])тнг\b', r'\btenge\b'],
    'UAH': [r'\buah\b', r'(?<![а-яА-Я])грн\b', r'(?<![а-яА-Я])гривн[а-я]*\b', r'(?<![а-яА-Я])гривен\b', r'\bhryvni?a\b'],
    'BYN': [r'\bbyn\b', r'\bbyr\b', r'(?<![а-яА-Я])бел[ао]рус\S*\s+руб', r'\bbelarusian\s+ruble'],
    'RUB': [r'₽', r'\brub\b', r'(?<![а-яА-Я])руб', r'(?<![а-яА-Я])рубл', r'\brubles?\b', r'\brubbles?\b'],
    'UZS': [r'\buzs\b', r"(?<![а-яА-Я])so['\']m\b", r'(?<![а-яА-Я])сум(?:ов|ы|у)?\b'],  # so'm с апострофом обязателен - узбекский
    'AMD': [r'\bamd\b', r'(?<![а-яА-Я])драм(?:ов)?\b', r'\bdram\b'],
    'TMT': [r'\btmt\b', r'(?<![а-яА-Я])туркмен\S*\s+манат', r'\bturkmen\S*\s+manat'],
    'AZN': [r'\bazn\b', r'(?<![а-яА-Я])манат(?:ов|ы)?\b', r'\bmanat\b'],
    'KGS': [r'\bkgs\b', r'(?<![а-яА-Я])сом(?:ов|ы|у)?\b', r'(?<![а-яА-Я])som\b'],  # som без апострофа - киргизский
    'TJS': [r'\btjs\b', r'(?<![а-яА-Я])сомон[ия]?\b', r'\bsomoni\b'],
    'MDL': [r'\bmdl\b', r'(?<![а-яА-Я])лей(?:ев|я|и)?\b', r'\blei\b'],
    'GEL': [r'\bgel\b', r'(?<![а-яА-Я])лари\b', r'(?<![а-яА-Я])lari\b'],

    # Latin American currencies
    'ARS': [r'\bars\b', r'(?<![а-яА-Я])аргентинских?', r'(?<![а-яА-Я])аргентинское', r'(?<![а-яА-Я])аргентинский', r'\bargentin[ea].*peso', r'(?<![а-яА-Я])песо'],
    'COP': [r'\bcop\b', r'(?<![а-яА-Я])колумбийских?', r'(?<![а-яА-Я])колумбийское', r'(?<![а-яА-Я])колумбийский', r'\bcolombian.*peso'],
    'PEN': [r'\bpen\b', r'(?<![а-яА-Я])солей?', r'(?<![а-яА-Я])перуанских?', r'(?<![а-яА-Я])перуанское', r'(?<![а-яА-Я])перуанский', r'\bperuvian\s+sol'],
    'CLP': [r'\bclp\b', r'(?<![а-яА-Я])чилийских?', r'(?<![а-яА-Я])чилийское', r'(?<![а-яА-Я])чилийский', r'\bchilean.*peso'],
    'MXN': [r'\bmxn\b', r'(?<![а-яА-Я])мексиканских?', r'(?<![а-яА-Я])мексиканское', r'(?<![а-яА-Я])мексиканский', r'\bmexican.*peso'],
    'BRL': [r'\bbrl\b', r'(?<![а-яА-Я])реал(?:ов|ы)?', r'(?<![а-яА-Я])бразильских?', r'(?<![а-яА-Я])бразильское', r'(?<![а-яА-Я])бразильский', r'\bbrazilian\s+real'],
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
    r'^plus\s+\d',  # Начинается со слова "plus" и цифра (plus 5000)
    r'\splus\s+\d',  # Пробел, затем "plus" и цифры (bonus plus 1200)
    r'^plus\s*\d',  # "plus" и цифры с возможным пробелом
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
    r'^minus\s+\d',  # Начинается со слова "minus" и цифра (minus 5000)
    r'\sminus\s+\d',  # Пробел, затем "minus" и цифры (coffee minus 200)
    r'^minus\s*\d',  # "minus" и цифры с возможным пробелом
]

# Импортируем helper функции для работы с категориями
from bot.utils.category_helpers import get_category_display_name
from bot.utils.expense_category_definitions import (
    DEFAULT_EXPENSE_CATEGORY_KEY,
    detect_expense_category_key,
    get_expense_category_display_name as get_expense_category_display_for_key,
    normalize_expense_category_key,
)
from bot.utils.income_category_definitions import (
    DEFAULT_INCOME_CATEGORY_KEY,
    detect_income_category_key,
    get_income_category_display_name as get_income_category_display_for_key,
    normalize_income_category_key,
)

def extract_date_from_text(text: str) -> Tuple[Optional[date], str]:
    """
    Извлекает дату из текста и возвращает кортеж (дата, текст_без_даты)
    Поддерживает только числовые даты в форматах: дд.мм.гггг или дд.мм.гг
    
    Примеры:
    - "Кофе 200 15.03.2024" -> (date(2024, 3, 15), "Кофе 200")
    - "25.12.2023 подарки 5000" -> (date(2023, 12, 25), "подарки 5000")
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
                        
            except (ValueError, TypeError) as e:
                logger.debug(f"Ошибка при парсинге даты из текста '{text}': {e}")
                continue
    
    # Если дата не найдена, возвращаем None и оригинальный текст
    return None, text


def extract_amount_from_patterns(text: str) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Извлекает сумму из текста, используя набор паттернов, и возвращает кортеж
    (сумма, текст_без_суммы). Если сумму найти не удалось, возвращает (None, None).
    """
    if not text:
        return None, None

    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        # Удаляем пробелы и обрабатываем разделители
        amount_str = match.group(1).replace(' ', '')

        # Определяем как обрабатывать точки:
        # - 2+ точки = разделители тысяч (10.000.000 -> 10000000)
        # - 1 точка = десятичный разделитель (500.50 -> 500.50)
        dot_count = amount_str.count('.')
        if dot_count >= 2:
            # Точки как разделители тысяч - удаляем их
            amount_str = amount_str.replace('.', '')
        # Заменяем запятые на точки для десятичной части
        amount_str = amount_str.replace(',', '.')

        try:
            amount = Decimal(amount_str)
        except (ValueError, InvalidOperation):
            logger.debug(f"Ошибка при парсинге суммы '{amount_str}' с паттерном '{pattern}'")
            continue

        match_start = match.start()
        match_end = match.end()

        # Проверяем есть ли множитель сразу после суммы (тысяч, млн и т.д.)
        text_after_amount = text[match_end:].strip()
        multiplier = None
        multiplier_match = None

        # Ищем множитель сразу после суммы
        for mult_word, mult_value in AMOUNT_MULTIPLIERS.items():
            # Ищем множитель как отдельное слово (с границами слова)
            mult_pattern = rf'^\s*{re.escape(mult_word)}\b'
            mult_match = re.search(mult_pattern, text_after_amount, re.IGNORECASE)
            if mult_match:
                multiplier = mult_value
                multiplier_match = mult_match
                logger.info(f"Найден множитель '{mult_word}' ({mult_value}x) для суммы {amount}")
                break

        # Если нашли множитель - применяем его и удаляем из текста
        if multiplier and multiplier_match:
            amount = amount * multiplier
            # Удаляем и сумму и множитель из текста
            mult_end = match_end + multiplier_match.end()
            text_without_amount = (text[:match_start] + ' ' + text[mult_end:]).strip()
            logger.info(f"Сумма после применения множителя: {amount}")
        else:
            text_without_amount = (text[:match_start] + ' ' + text[match_end:]).strip()

        return amount, text_without_amount

    # Fallback: Если не нашли по паттернам, ищем единственное число В СЕРЕДИНЕ текста С ПРОБЕЛАМИ
    # Примеры: "купил кофе 300 на работе", "coffee 10 000 at work"
    # НЕ срабатывает для чисел без пробелов: "купилкофе300наработе"
    # ВАЖНО: Число должно быть окружено пробелами с обеих сторон
    # Поддерживает числа с разделителями тысяч: 10 000, 1 000 000
    number_match = re.search(r'\s(\d{1,3}(?:[\s,]\d{3})*(?:[.,]\d+)?)\s', text)
    if number_match:
        # Извлекаем найденное число
        amount_str = number_match.group(1).replace(' ', '').replace(',', '.')

        # Проверяем что это единственное число в тексте
        # Удаляем найденное число и проверяем что в остатке нет других цифр
        text_without_this_number = text[:number_match.start()] + ' ' + text[number_match.end():]
        other_numbers = re.findall(r'\d', text_without_this_number)

        # Если в тексте нет других цифр - число единственное
        if len(other_numbers) == 0:
            try:
                amount = Decimal(amount_str)
                # Проверяем что число положительное и разумное (не ноль, меньше 10 млн)
                if amount > 0 and amount < 10_000_000:
                    # Удаляем это число из текста (с окружающими пробелами)
                    text_without_amount = text_without_this_number.strip()
                    # Убираем лишние пробелы
                    text_without_amount = ' '.join(text_without_amount.split())
                    logger.info(f"Fallback: найдено единственное число {amount} в середине текста '{text}'")
                    return amount, text_without_amount
            except (ValueError, InvalidOperation):
                pass

    return None, None


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


def is_number_only(text: str) -> bool:
    """
    Проверяет, содержит ли текст только число (с опциональным знаком +/- и валютой).

    Примеры:
    - "10000" -> True
    - "+10000" -> True
    - "-400" -> True
    - "2500" -> True
    - "+10000 рублей" -> True (число + валюта)
    - "10к" -> True (сокращения)
    - "+5 тыс" -> True
    - "5 тыс руб" -> True (множитель + валюта)
    - "10k usd" -> True (множитель + валюта)
    - "кофе 200" -> False (есть описание)
    - "+5000 зарплата" -> False (есть описание)
    - "200 продукты" -> False (есть описание)
    """
    if not text:
        return False

    text_clean = text.strip()

    # Паттерн для числа с опциональным знаком, множителем и валютой
    # Поддерживаем комбинации: +10000, -400, 2500, 10к, 5 тыс, 10000 рублей, $100, 100$
    # А также: 5 тыс руб, 10k usd, +3к рублей

    # Множители (к, k, т, тыс, тысяч)
    multiplier = r'(?:к|k|т|тыс|тысяч)?'

    # Валюты (руб, рублей, р, ₽, $, €, £, usd, eur, rub, kzt, тенге, тг)
    currency = r'(?:руб|рублей|р|₽|\$|€|£|usd|eur|rub|kzt|тенге|тг)?'

    # Полный паттерн: знак? валюта? число множитель? валюта?
    # Примеры: +5 тыс руб, $100, 10k usd, -400р
    number_only_pattern = (
        r'^[+\-]?\s*'           # опциональный знак
        r'(?:\$|€|£)?\s*'       # опциональная валюта перед числом ($100)
        r'\d+(?:[.,]\d+)?\s*'   # число (обязательно)
        + multiplier + r'\s*'   # опциональный множитель (к, тыс)
        + currency +            # опциональная валюта после числа (руб, usd)
        r'\.?\s*$'              # опциональная точка в конце
    )

    return bool(re.match(number_only_pattern, text_clean, re.IGNORECASE))


def detect_currency(text: str, user_currency: str = 'RUB') -> str:
    """
    Detect currency from text.
    Currency word must be adjacent to a number (before or after).
    """
    text_lower = text.lower()

    # Паттерн для проверки что валюта рядом с числом: "число валюта" или "валюта число"
    # Примеры: "100 лари", "100лари", "$100", "100$"
    for currency, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                start, end = match.start(), match.end()
                # Проверяем есть ли число рядом (до или после совпадения)
                # Число перед: смотрим на текст до совпадения
                text_before = text_lower[:start].rstrip()
                text_after = text_lower[end:].lstrip()

                # Символы валют ($, €, ₽ и т.д.) не требуют проверки близости к числу
                if pattern in [r'\$', r'€', r'£', r'¥', r'₽', r'₸', r'₣', r'₹', r'₺']:
                    return currency

                # Проверяем число непосредственно перед валютой
                if re.search(r'\d\s*$', text_before):
                    return currency

                # Проверяем число непосредственно после валюты
                if re.search(r'^\s*\d', text_after):
                    return currency

    return (user_currency or 'RUB').upper()  # Default to user's currency in uppercase


def find_user_category_by_key(user_categories_objects: list, category_key: str, lang_code: str = 'ru') -> Optional[str]:
    """
    Находит категорию пользователя по category_key из уже загруженного списка.

    Args:
        user_categories_objects: Список объектов ExpenseCategory (УЖЕ загружены из БД)
        category_key: Ключ категории (например, "utilities_subscriptions")
        lang_code: Код языка для отображения

    Returns:
        Название категории пользователя или None
    """
    for cat in user_categories_objects:
        # Проверяем name_ru
        cat_key_ru = normalize_expense_category_key(cat.name_ru) if cat.name_ru else None
        if cat_key_ru == category_key:
            return get_category_display_name(cat, lang_code)

        # Проверяем name_en
        cat_key_en = normalize_expense_category_key(cat.name_en) if cat.name_en else None
        if cat_key_en == category_key:
            return get_category_display_name(cat, lang_code)

        # Проверяем старое поле name (для обратной совместимости)
        cat_key_name = normalize_expense_category_key(cat.name) if cat.name else None
        if cat_key_name == category_key:
            return get_category_display_name(cat, lang_code)

    return None


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

    # Конвертируем числа словами в цифры (two -> 2, три -> 3)
    original_text = convert_words_to_numbers(original_text)

    # Убираем слова-маркеры операции (minus/минус/plus/плюс) ТОЛЬКО если после них идёт число
    # Примеры:
    # "Carat minus 2" -> "Carat 2" (удаляем, т.к. после "minus" идёт цифра)
    # "Apple minus two" -> "Apple two" -> "Apple 2" (удаляем, т.к. после "minus" идёт слово-число)
    # "Minus store" -> "Minus store" (НЕ удаляем, т.к. после "Minus" НЕТ числа)
    text_cleaned = original_text

    # Создаём паттерн из всех слов-чисел
    number_words_pattern = '|'.join(re.escape(word) for word in WORD_TO_NUMBER.keys())

    # Удаляем "minus/минус/plus/плюс" + пробелы, ТОЛЬКО если после них идёт цифра или слово-число
    operation_pattern = r'\b(minus|минус|plus|плюс)\s+(?=\d|(?:' + number_words_pattern + r')\b)'
    text_cleaned = re.sub(operation_pattern, '', text_cleaned, flags=re.IGNORECASE)
    text_cleaned = ' '.join(text_cleaned.split())  # Убираем двойные пробелы

    # Убираем знак "-" из начала если есть
    if text_cleaned.startswith('-'):
        text_cleaned = text_cleaned[1:].strip()

    # Сначала извлекаем дату, если она есть
    expense_date, text_without_date = extract_date_from_text(text_cleaned)
    date_removed = text_without_date != text_cleaned

    # Используем текст без даты для дальнейшего парсинга
    text_to_parse = text_without_date
    
    # Ищем сумму
    amount, text_without_amount = extract_amount_from_patterns(text_to_parse)

    if (not amount or amount <= 0) and date_removed:
        amount_with_date, text_without_amount_with_date = extract_amount_from_patterns(text_cleaned)
        if amount_with_date and amount_with_date > 0:
            amount = amount_with_date
            text_without_amount = text_without_amount_with_date
            text_to_parse = text_cleaned
            expense_date = None

    # Если не нашли сумму, возвращаем None
    # Пользователь должен указать сумму явно
    if not amount or amount <= 0:
        logger.debug(f"No amount found in text: {original_text}")
        return None

    # Определяем категорию по ключевым словам
    category = None
    max_score = 0
    # ВАЖНО: Для поиска ключевых слов используем текст БЕЗ суммы,
    # чтобы числа вроде "95" не совпадали с суммой "9500"
    text_for_keywords = (text_without_amount if text_without_amount else text_to_parse).lower()
    user_categories = []  # Инициализируем список категорий пользователя

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
            # Собираем все варианты названия категории (без эмодзи) для сравнения
            category_names_to_check = []

            # Основное название (очищенное от эмодзи)
            if user_cat.name:
                clean_name = strip_leading_emoji(user_cat.name).lower().strip()
                if clean_name:
                    category_names_to_check.append(clean_name)

            # Мультиязычные названия (name_ru, name_en) - также очищаем от эмодзи
            if hasattr(user_cat, 'name_ru') and user_cat.name_ru:
                clean_name_ru = strip_leading_emoji(user_cat.name_ru).lower().strip()
                if clean_name_ru and clean_name_ru not in category_names_to_check:
                    category_names_to_check.append(clean_name_ru)

            if hasattr(user_cat, 'name_en') and user_cat.name_en:
                clean_name_en = strip_leading_emoji(user_cat.name_en).lower().strip()
                if clean_name_en and clean_name_en not in category_names_to_check:
                    category_names_to_check.append(clean_name_en)

            # Проверяем прямое вхождение названия категории в текст (ЦЕЛЫМ СЛОВОМ)
            category_matched = False
            for cat_name in category_names_to_check:
                if keyword_matches_in_text(cat_name, text_for_keywords):
                    # Используем язык пользователя для отображения категории
                    lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                    category = get_category_display_name(user_cat, lang_code)
                    max_score = 100  # Максимальный приоритет для пользовательских категорий
                    category_matched = True
                    logger.info(f"Category matched by name: '{cat_name}' in text '{text_for_keywords}' → {category}")
                    break

            if category_matched:
                break

            # Проверяем ключевые слова пользовательской категории
            @sync_to_async
            def get_keywords():
                return list(user_cat.keywords.all())

            keywords = await get_keywords()
            for kw in keywords:
                # ИЗМЕНЕНО: Используем keyword_matches_in_text вместо `in` для точного совпадения целых слов
                # Используем text_for_keywords (текст без суммы) для поиска
                if keyword_matches_in_text(kw.keyword.lower(), text_for_keywords):
                    # Обновляем last_used и usage_count при использовании ключевого слова
                    @sync_to_async
                    def update_keyword_usage():
                        from django.utils import timezone
                        keyword = CategoryKeyword.objects.get(id=kw.id)
                        keyword.usage_count += 1
                        keyword.save(update_fields=['usage_count', 'last_used'])  # last_used обновится auto_now

                    await update_keyword_usage()

                    # Используем язык пользователя для отображения категории
                    lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                    category = get_category_display_name(user_cat, lang_code)
                    max_score = 100
                    break
            
            if category:
                break
    
    # Переменная для хранения category_key
    category_key = None

    # Если не нашли в пользовательских, ищем в стандартных
    if not category:
        # Определяем язык пользователя для отображения результата
        lang_code = profile.language_code if profile and hasattr(profile, 'language_code') else 'ru'

        # Используем новую систему с category_key (аналогично доходам)
        # Ищем по объединенным ключевым словам (русские + английские)
        # text_for_keywords уже содержит текст без суммы
        detected_key = detect_expense_category_key(text_for_keywords)
        if detected_key:
            category_key = detected_key

            # Если есть профиль - ищем категорию пользователя по ключу (используя уже загруженные данные)
            if profile and user_categories:
                category = find_user_category_by_key(user_categories, category_key, lang_code)
                if category:
                    logger.info(f"Found user category '{category}' by key '{category_key}'")
                else:
                    logger.info(f"User category not found for key '{category_key}', using default")

            # Fallback: если нет профиля или не нашли у пользователя - берем из definitions
            if not category:
                category = get_expense_category_display_for_key(category_key, lang_code)

    # Формируем описание (текст без суммы и без даты)
    description = text_without_amount if text_without_amount is not None else text_without_date

    # Убираем одиночный знак "-" из описания (может остаться после извлечения суммы)
    # Важно: удаляем только одиночный дефис с пробелами, не внутри слов (WiFi-роутер)
    if description:
        description = re.sub(r'\s+-\s+', ' ', description)  # " - " → " "
        description = re.sub(r'^\s*-\s*', '', description)  # "- " в начале → ""
        description = re.sub(r'\s*-\s*$', '', description)  # " -" в конце → ""
        description = description.strip()

    # Убираем лишние пробелы
    # Примечание: слова-маркеры операции (plus/minus/плюс/минус) уже удалены
    # на этапе предварительной обработки текста, если они стояли перед числом
    description = ' '.join(description.split())
    if description:
        description = re.sub(r'[.,:;!?]+$', '', description).strip()
    
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
        'category_key': category_key,  # Язык-независимый ключ категории
        'currency': currency,
        'confidence': 0.5 if category else 0.2,
        'expense_date': expense_date  # Добавляем дату, если она была указана
    }

    # Если текст содержит только число (без описания), пропускаем AI
    # и сразу назначаем "Прочие расходы"
    if not category and is_number_only(original_text):
        logger.info(f"Number-only expense detected: '{original_text}', skipping AI")
        # Назначаем "Прочие расходы" / "Other expenses"
        result['category_key'] = DEFAULT_EXPENSE_CATEGORY_KEY
        # Используем язык пользователя для отображения категории
        if profile and hasattr(profile, 'language_code'):
            lang_code = profile.language_code if profile.language_code in ('ru', 'en') else 'ru'
        else:
            lang_code = 'ru'
        result['category'] = get_expense_category_display_for_key(DEFAULT_EXPENSE_CATEGORY_KEY, lang_code)
        result['confidence'] = 0.5
        return result

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
                categories = ExpenseCategory.objects.filter(profile=profile)
                lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                return [get_category_display_name(cat, lang_code) for cat in categories]

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
                from bot.services.ai_selector import get_service, get_fallback_chain, AISelector
                
                # Получаем категории пользователя на нужном языке
                @sync_to_async
                def get_profile_categories():
                    categories = ExpenseCategory.objects.filter(profile=profile)
                    # Используем язык пользователя для отображения категорий
                    lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                    return [get_category_display_name(cat, lang_code) for cat in categories]

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
                    
                    # Готовим текст для AI: убираем пунктуацию
                    # Примечание: operation words (plus/minus/плюс/минус) уже удалены на этапе
                    # предварительной обработки, если они стояли перед числом
                    ai_text = text_without_date or original_text
                    if ai_text:
                        ai_text = ''.join(ch if ch.isalnum() or ch.isspace() else ' ' for ch in ai_text)
                        ai_text = ' '.join(ai_text.split())
                        if not ai_text:
                            ai_text = text_without_date or original_text

                    # Пробуем сначала основной AI сервис с таймаутом
                    try:
                        logger.info(f"Getting AI service for categorization...")
                        ai_service = get_service('categorization')
                        logger.info(f"AI service obtained: {type(ai_service).__name__}")
                        logger.info(f"Calling categorize_expense with timeout=10s...")
                        ai_result = await asyncio.wait_for(
                            ai_service.categorize_expense(
                                text=ai_text,  # Отправляем очищенный текст без даты
                                amount=amount,
                                currency=currency,
                                categories=user_categories,
                                user_context=user_context
                            ),
                            timeout=10.0  # 10 секунд общий таймаут для изолированного процесса
                        )
                        logger.info(f"AI categorization completed")
                    except asyncio.TimeoutError:
                        logger.warning(f"AI categorization timeout for '{original_text}'")
                        ai_result = None
                    except Exception as e:
                        logger.error(f"AI categorization error: {e}")
                        ai_result = None
                    
                    # Если основной провайдер не сработал, пробуем ОДИН fallback из .env
                    if not ai_result:
                        logger.warning(f"Primary AI failed, trying ONE fallback from .env")
                        fallback_chain = get_fallback_chain('categorization')

                        # ВАЖНО: Берем только ПЕРВЫЙ провайдер из цепочки (не перебираем все!)
                        if fallback_chain:
                            fallback_provider = fallback_chain[0]
                            try:
                                logger.info(f"Trying fallback to {fallback_provider}...")
                                fallback_service = AISelector(fallback_provider)
                                ai_result = await asyncio.wait_for(
                                    fallback_service.categorize_expense(
                                        text=ai_text,  # Отправляем очищенный текст без даты
                                        amount=amount,
                                        currency=currency,
                                        categories=user_categories,
                                        user_context=user_context
                                    ),
                                    timeout=5.0  # 5 секунд таймаут для fallback
                                )
                                if ai_result:
                                    logger.info(f"{fallback_provider} fallback successful")
                            except asyncio.TimeoutError:
                                logger.error(f"{fallback_provider} fallback timeout")
                            except Exception as e:
                                logger.error(f"{fallback_provider} fallback failed: {e}")
                    
                    if ai_result:
                        # Централизованная валидация категории (как у доходов)
                        from bot.services.expense_categorization import find_best_matching_expense_category

                        # AI вернул сырую категорию - нужно найти соответствие среди категорий пользователя
                        raw_category = ai_result.get('category', '')
                        matched_category = await find_best_matching_expense_category(
                            raw_category,
                            user_categories
                        )

                        # Обновляем только если нашли валидную категорию
                        if matched_category:
                            result['category'] = matched_category
                            # Определяем category_key для AI категории
                            result['category_key'] = normalize_expense_category_key(matched_category)
                            result['confidence'] = ai_result.get('confidence', result['confidence'])
                            result['ai_enhanced'] = True
                            result['ai_provider'] = ai_result.get('provider', 'unknown')
                        else:
                            logger.warning(f"AI suggested category '{raw_category}' but no match found in user categories")
                            # AI не смог подобрать категорию - оставляем result без изменений
                        
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
        # Определяем язык пользователя для дефолтной категории
        lang_code = profile.language_code if profile and hasattr(profile, 'language_code') else 'ru'
        result['category'] = get_expense_category_display_for_key(DEFAULT_EXPENSE_CATEGORY_KEY, lang_code)
        result['category_key'] = DEFAULT_EXPENSE_CATEGORY_KEY
        logger.info(f"Using default category '{result['category']}' for '{original_text}'")
    
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

    # Конвертируем числа словами в цифры (two -> 2, три -> 3)
    original_text = convert_words_to_numbers(original_text)

    # Убираем символ + в начале
    text_for_parsing = original_text
    if text_for_parsing.startswith('+'):
        text_for_parsing = text_for_parsing[1:].strip()

    # Убираем слова-маркеры операции (plus/плюс) ТОЛЬКО если после них идёт число
    # Примеры:
    # "Bonus plus 1000" -> "Bonus 1000" (удаляем, т.к. после "plus" идёт цифра)
    # "Plus membership" -> "Plus membership" (НЕ удаляем, т.к. после "Plus" НЕТ числа)

    # Создаём паттерн из всех слов-чисел (используем тот же словарь WORD_TO_NUMBER)
    number_words_pattern = '|'.join(re.escape(word) for word in WORD_TO_NUMBER.keys())

    # Удаляем "plus/плюс" + пробелы, ТОЛЬКО если после них идёт цифра или слово-число
    operation_pattern = r'\b(plus|плюс)\s+(?=\d|(?:' + number_words_pattern + r')\b)'
    text_for_parsing = re.sub(operation_pattern, '', text_for_parsing, flags=re.IGNORECASE)

    # Удаляем символ "+" перед числами (для поддержки "+10 тыс", "+5000" и т.д.)
    text_for_parsing = re.sub(r'\+\s*(\d)', r'\1', text_for_parsing)

    text_for_parsing = ' '.join(text_for_parsing.split())  # Убираем двойные пробелы
    
    # Сначала извлекаем дату, если она есть
    expense_date, text_without_date = extract_date_from_text(text_for_parsing)
    date_removed = text_without_date != text_for_parsing

    text_to_parse = text_without_date
    amount, text_without_amount = extract_amount_from_patterns(text_to_parse)

    if (not amount or amount <= 0) and date_removed:
        amount_with_date, text_without_amount_with_date = extract_amount_from_patterns(text_for_parsing)
        if amount_with_date and amount_with_date > 0:
            amount = amount_with_date
            text_without_amount = text_without_amount_with_date
            text_to_parse = text_for_parsing
            expense_date = None

    # ВАЖНО: Для поиска ключевых слов используем текст БЕЗ суммы,
    # чтобы числа вроде "95" не совпадали с суммой "9500"
    text_for_keywords = (text_without_amount if text_without_amount else text_to_parse).lower()

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
    ai_categorized = False
    ai_confidence = None

    # Определяем язык пользователя для отображения категорий
    lang_code = 'ru'
    if profile and hasattr(profile, 'language_code') and profile.language_code:
        candidate_lang = profile.language_code.lower()
        if candidate_lang in ('ru', 'en'):
            lang_code = candidate_lang

    # Пытаемся определить категорию по встроенным ключевым словам
    # text_for_keywords уже содержит текст без суммы
    detected_key = detect_income_category_key(text_for_keywords)
    if detected_key:
        category_key = detected_key
        category = get_income_category_display_for_key(category_key, lang_code)

    # Если текст содержит только число (без описания), пропускаем AI
    # и сразу назначаем "Прочие доходы"
    if not category and is_number_only(original_text):
        logger.info(f"Number-only income detected: '{original_text}', skipping AI")
        category_key = DEFAULT_INCOME_CATEGORY_KEY
        category = get_income_category_display_for_key(category_key, lang_code)

    # Если категорию не нашли, пытаемся определить через AI
    if not category and profile and use_ai:
        from bot.services.income_categorization import categorize_income

        # ВАЖНО: Передаём текст БЕЗ суммы для более точной категоризации
        text_for_ai = text_without_amount if text_without_amount else (text_without_date if text_without_date else original_text)
        ai_result = await categorize_income(text_for_ai, user_id, profile)

        if ai_result:
            ai_category_label = ai_result.get('category')
            ai_category_key = normalize_income_category_key(ai_category_label)
            if ai_category_key:
                category_key = ai_category_key
                category = get_income_category_display_for_key(ai_category_key, lang_code)
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

            for keyword_obj in keywords:
                # ИСПРАВЛЕНО: Используем keyword_matches_in_text для проверки целого слова
                # вместо простого `in` (защита от "95" в "9500")
                if keyword_matches_in_text(keyword_obj.keyword.lower(), text_for_keywords):
                    best_match = keyword_obj.category
                    break  # При строгой уникальности достаточно первого совпадения

            if best_match:
                category = get_category_display_name(best_match, lang_code)
                normalized_key = normalize_income_category_key(category)
                if normalized_key:
                    category_key = normalized_key
        except Exception as e:
            logger.warning(f"Error checking income keywords: {e}")

        if not category:
            @sync_to_async
            def get_income_category_names():
                categories = IncomeCategory.objects.filter(profile=profile)
                lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                return [get_category_display_name(cat, lang_code) for cat in categories]

            user_income_categories = await get_income_category_names()

            for user_cat in user_income_categories:
                # ИСПРАВЛЕНО: Используем keyword_matches_in_text для безопасного поиска
                # Старая логика `lowered in text_lower or any(word in lowered ...)` была опасна:
                # - "на" in "аренда недвижимости" = True (ложное срабатывание!)
                # - "с" in "фриланс" = True (ложное срабатывание!)
                cat_name_clean = strip_leading_emoji(user_cat).lower().strip()
                if cat_name_clean and keyword_matches_in_text(cat_name_clean, text_for_keywords):
                    category = user_cat
                    normalized_key = normalize_income_category_key(user_cat)
                    if normalized_key:
                        category_key = normalized_key
                        category = get_income_category_display_for_key(category_key, lang_code)
                    break

    # Финальные сопряжения
    if category and not category_key:
        normalized_key = normalize_income_category_key(category)
        if normalized_key:
            category_key = normalized_key
            category = get_income_category_display_for_key(category_key, lang_code)

    if not category:
        category_key = category_key or DEFAULT_INCOME_CATEGORY_KEY
        category = get_income_category_display_for_key(category_key, lang_code)

    # Формируем описание (используем текст без даты и без суммы)
    description = text_without_amount if text_without_amount else (text_without_date if text_without_date else get_text('income', lang_code))

    # Убираем знак "+" из описания
    if description:
        description = description.replace('+', '').strip()

    # Убираем лишние пробелы и капитализируем
    # Примечание: слова-маркеры операции (plus/плюс) уже удалены
    # на этапе предварительной обработки текста, если они стояли перед числом
    description = ' '.join(description.split())
    if description and len(description) > 0:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Если описание пустое или слишком короткое, используем категорию
    if not description or len(description) < 2:
        if category:
            # Убираем эмодзи из категории для описания
            description = re.sub(r'[^\w\s]', '', category).strip()
        else:
            description = get_text('income', lang_code)
    
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
