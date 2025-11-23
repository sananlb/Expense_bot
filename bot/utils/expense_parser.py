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

logger = logging.getLogger(__name__)

# Словарь для конвертации чисел словами в цифры
WORD_TO_NUMBER = {
    # Английский
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
    # Русский
    'ноль': 0, 'один': 1, 'одна': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10,
    'одиннадцать': 11, 'двенадцать': 12, 'тринадцать': 13, 'четырнадцать': 14, 'пятнадцать': 15,
    'шестнадцать': 16, 'семнадцать': 17, 'восемнадцать': 18, 'девятнадцать': 19, 'двадцать': 20,
    'тридцать': 30, 'сорок': 40, 'пятьдесят': 50, 'шестьдесят': 60, 'семьдесят': 70,
    'восемьдесят': 80, 'девяносто': 90, 'сто': 100, 'тысяча': 1000,
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

def keyword_matches_in_text(keyword: str, text: str) -> bool:
    """
    Проверяет есть ли ключевое слово в тексте как ЦЕЛОЕ СЛОВО с учетом склонений.

    Алгоритм:
    1. Разбивает текст на отдельные слова
    2. Проверяет что ключевое слово является НАЧАЛОМ слова (стем)
    3. Разрешает окончания до 3 символов (склонения: магнит → магните, магнита)
    4. НЕ разрешает если после ключевого слова больше 3 символов (магнит ≠ магнитрон)

    Примеры:
    - keyword_matches_in_text("магнит", "купил в магните") -> True ✅ (склонение +2 символа)
    - keyword_matches_in_text("магнит", "магнитрон") -> False ✅ (рон = +3 символа, лимит)
    - keyword_matches_in_text("магнит", "супер-магнит") -> True ✅ (точное совпадение части)
    - keyword_matches_in_text("кофе", "кофейня") -> False ✅ (йня = +3 символа, лимит)
    - keyword_matches_in_text("кофе", "кофе") -> True ✅ (точное совпадение)

    Args:
        keyword: Ключевое слово для поиска (одно слово)
        text: Текст для поиска

    Returns:
        True если keyword найдено как целое слово (с учетом склонений) в text
    """
    if not keyword or not text:
        return False

    # Нормализуем для поиска
    keyword_lower = keyword.lower().strip()
    text_lower = text.lower()

    # Разбиваем текст на слова (по пробелам, запятым, точкам и т.д.)
    # Оставляем дефисы внутри слов (супер-магнит)
    import re
    text_words = re.findall(r'[\wа-яёА-ЯЁ\-]+', text_lower)

    # Проверяем каждое слово в тексте
    for word in text_words:
        # Точное совпадение - всегда ОК
        if word == keyword_lower:
            return True

        # Проверяем что слово начинается с ключевого слова (стем)
        if word.startswith(keyword_lower):
            # Вычисляем разницу в длине (окончание)
            ending_length = len(word) - len(keyword_lower)

            # Разрешаем окончания до 2 символов (склонения)
            # магнит (6) → магните (8) = +2 ✅
            # магнит (6) → магнитрон (9) = +3 ❌
            if ending_length <= 2:
                return True

    return False


def convert_words_to_numbers(text: str) -> str:
    """
    Конвертирует числа словами в цифры
    Примеры:
    - "Apple minus two" -> "Apple minus 2"
    - "кофе три" -> "кофе 3"
    - "twenty five" -> "25"
    - "двадцать пять" -> "25"
    """
    if not text:
        return text

    text_lower = text.lower()
    words = text_lower.split()
    result_words = []
    i = 0

    while i < len(words):
        word = words[i].strip('.,!?;:')

        # Проверяем, является ли слово числом
        if word in WORD_TO_NUMBER:
            number = WORD_TO_NUMBER[word]

            # Проверяем следующее слово для составных чисел (twenty one -> 21)
            if i + 1 < len(words):
                next_word = words[i + 1].strip('.,!?;:')
                if next_word in WORD_TO_NUMBER:
                    next_number = WORD_TO_NUMBER[next_word]
                    # Если следующее число меньше 10 и текущее кратно 10
                    if next_number < 10 and number >= 10 and number < 100:
                        number += next_number
                        i += 1  # Пропускаем следующее слово

            result_words.append(str(number))
        else:
            result_words.append(words[i])

        i += 1

    return ' '.join(result_words)

# Вспомогательная функция для безопасного использования sync_to_async с Django ORM
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
    # Числа с пробелами-разделителями тысяч (ПРИОРИТЕТ!)
    # Примеры: "10 000", "1 000 000", "10 000.50"
    # ВАЖНО: Длинные варианты валют ПЕРВЫМИ (рублей перед руб, доллар перед долл, dollars перед usd)
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:рублей|rub+les?|руб|₽|р)\b',  # 10 000 руб, rubles, rubbles
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:доллар(?:ов)?|dollars?|долл|usd|\$)\b',  # 10 000 USD
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:euros?|евро|eur|€)\b',  # 10 000 EUR
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:pounds?|фунт(?:ов)?|gbp|£)\b',  # 10 000 GBP
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:юаней|yuan|юан|cny|¥)\b',  # 10 000 CNY
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:аргентинских?|pesos?|песо|ars)\b',  # 10 000 ARS
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:колумбийских?|cop)\b',  # 10 000 COP
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:перуанских?|soles?|солей?|pen)\b',  # 10 000 PEN
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:чилийских?|clp)\b',  # 10 000 CLP
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:мексиканских?|mxn)\b',  # 10 000 MXN
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:бразильских?|reais?|реалов?|brl)\b',  # 10 000 BRL
    # CIS currencies (числа с пробелами) - русские и английские названия
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лари|lari|gel|georgian\s+lari)\b',  # 10 000 GEL
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:тенге|теньге|тнг|kzt|tenge|kazakh\S*\s+tenge)\b',  # 10 000 KZT
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:гривен|гривн[а-я]*|грн|uah|hryvnia|hryvnya|ukrainian\s+hryvnia)\b',  # 10 000 UAH
    r"(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сум(?:ов)?|so['\']m|uzs|uzbek\S*\s+so['\']m)\b",  # 10 000 UZS (апостроф обязателен)
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:драм(?:ов)?|dram|amd|armenian\s+dram)\b',  # 10 000 AMD
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:манат(?:ов)?|manat|azn|azerbaijani\s+manat)\b',  # 10 000 AZN
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сом(?:ов)?|kgs|kyrgyz\S*\s+som)\b',  # 10 000 KGS
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:сомони|somoni|tjs|tajik\S*\s+somoni)\b',  # 10 000 TJS
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лей|леев|лея|mdl|lei|moldovan\s+lei?)\b',  # 10 000 MDL
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:бел[ао]рус\S*\s+руб\S*|byn|byr|belarusian\s+ruble?)\b',  # 10 000 BYN
    # Other world currencies (числа с пробелами)
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:франк(?:ов|а)?|francs?|chf|swiss\s+francs?)\b',  # 10 000 CHF
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:рупи[йяею]|rupees?|inr|indian\s+rupees?)\b',  # 10 000 INR
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*(?:лир[аы]?|liras?|try|turkish\s+liras?)\b',  # 10 000 TRY
    r'(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s*$',  # 10 000 в конце
    r'^(\d{1,3}(?:[\s,]\d{3})+(?:[.,]\d+)?)\s',  # 10 000 в начале
    # Паттерн для числа с разделителями в середине УДАЛЕН - используется fallback
    # Обычные числа БЕЗ пробелов (fallback)
    # ВАЖНО: Длинные варианты валют ПЕРВЫМИ (английские полные формы включены)
    r'(\d+(?:[.,]\d+)?)\s*(?:рублей|rub+les?|руб|₽|р)\b',  # 100 руб, 100.50 р, 100 rubles/rubbles
    r'(\d+(?:[.,]\d+)?)\s*(?:доллар(?:ов)?|dollars?|долл|usd|\$)\b',  # 100 USD, $100, 100 dollars
    r'(\d+(?:[.,]\d+)?)\s*(?:euros?|евро|eur|€)\b',  # 100 EUR, €100, 100 euros
    r'(\d+(?:[.,]\d+)?)\s*(?:pounds?|фунт(?:ов)?|gbp|£)\b',  # 100 GBP, £100, 100 pounds
    r'(\d+(?:[.,]\d+)?)\s*(?:юаней|yuan|юан|cny|¥)\b',  # 100 CNY, 100 yuan
    # Latin American currencies
    r'(\d+(?:[.,]\d+)?)\s*(?:аргентинских?|pesos?|песо|ars)\b',  # 100 ARS, 100 pesos
    r'(\d+(?:[.,]\d+)?)\s*(?:колумбийских?|cop)\b',  # 100 COP
    r'(\d+(?:[.,]\d+)?)\s*(?:перуанских?|soles?|солей?|pen)\b',  # 100 PEN, 100 soles
    r'(\d+(?:[.,]\d+)?)\s*(?:чилийских?|clp)\b',  # 100 CLP
    r'(\d+(?:[.,]\d+)?)\s*(?:мексиканских?|mxn)\b',  # 100 MXN
    r'(\d+(?:[.,]\d+)?)\s*(?:бразильских?|reais?|реалов?|brl)\b',  # 100 BRL, 100 reais
    # CIS currencies (обычные числа) - русские и английские названия с сокращениями
    r'(\d+(?:[.,]\d+)?)\s*(?:лари|lari|gel)\b',  # 100 GEL, 100 лари
    r'(\d+(?:[.,]\d+)?)\s*(?:тенге|теньге|тнг|kzt|tenge)\b',  # 100 KZT, 100 тенге, 100 tenge
    r'(\d+(?:[.,]\d+)?)\s*(?:гривен|гривн[а-я]*|грн|uah|hryvnia|hryvnya|uah)\b',  # 100 UAH, 100 hryvnia
    r"(\d+(?:[.,]\d+)?)\s*(?:сум(?:ов)?|so['\']m|uzs)\b",  # 100 UZS, 100 сум, 100 so'm (апостроф обязателен)
    r'(\d+(?:[.,]\d+)?)\s*(?:драм(?:ов)?|dram|amd)\b',  # 100 AMD, 100 драм, 100 dram
    r'(\d+(?:[.,]\d+)?)\s*(?:манат(?:ов)?|manat|azn)\b',  # 100 AZN, 100 манат, 100 manat
    r'(\d+(?:[.,]\d+)?)\s*(?:сом(?:ов)?|som|kgs)\b',  # 100 KGS, 100 сом, 100 som (киргизский)
    r'(\d+(?:[.,]\d+)?)\s*(?:сомони|somoni|tjs)\b',  # 100 TJS, 100 сомони, 100 somoni
    r'(\d+(?:[.,]\d+)?)\s*(?:лей|леев|лея|mdl|lei)\b',  # 100 MDL, 100 лей, 100 lei
    r'(\d+(?:[.,]\d+)?)\s*(?:бел[ао]рус\S*\s+руб\S*|byn|byr|belarusian\s+ruble?)\b',  # 100 BYN
    # Other world currencies (обычные числа)
    r'(\d+(?:[.,]\d+)?)\s*(?:франк(?:ов|а)?|francs?|chf)\b',  # 100 CHF, 100 франков, 100 francs
    r'(\d+(?:[.,]\d+)?)\s*(?:рупи[йяею]|rupees?|inr)\b',  # 100 INR, 100 рупий, 100 rupees
    r'(\d+(?:[.,]\d+)?)\s*(?:лир[аы]?|liras?|try)\b',  # 100 TRY, 100 лир, 100 liras
    r'(\d+(?:[.,]\d+)?)\s*$',  # просто число в конце
    r'^(\d+(?:[.,]\d+)?)\s',  # число в начале
    # Паттерн для числа в середине с пробелами (для поддержки множителей)
    # Примеры: "долг 5 тыс рублей", "купил 10 тысяч продуктов"
    r'\s(\d+(?:[.,]\d+)?)\s',  # число в середине (окружено пробелами)
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
    get_income_type,
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

        # Удаляем пробелы и заменяем запятые на точки
        amount_str = match.group(1).replace(' ', '').replace(',', '.')
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
        'carrot', 'carrots', 'vegetable', 'vegetables',
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
    text_lower = text_to_parse.lower()  # Создаем text_lower для поиска категорий
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
            user_cat_lower = user_cat.name.lower()

            # Проверяем прямое вхождение названия категории в текст (ЦЕЛЫМ СЛОВОМ)
            if keyword_matches_in_text(user_cat_lower, text_lower):
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
                # ИЗМЕНЕНО: Используем keyword_matches_in_text вместо `in` для точного совпадения целых слов
                if keyword_matches_in_text(kw.keyword.lower(), text_lower):
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
        detected_key = detect_expense_category_key(text_lower)
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

    text_lower = text_to_parse.lower()

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

            for keyword_obj in keywords:
                if keyword_obj.keyword.lower() in text_lower:
                    best_match = keyword_obj.category
                    break  # При строгой уникальности достаточно первого совпадения

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
                categories = IncomeCategory.objects.filter(profile=profile)
                lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
                return [get_category_display_name(cat, lang_code) for cat in categories]

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
                    'other': get_text('income', 'ru'),
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
    Использует словарь по умолчанию (русские категории)
    """
    description_lower = description.lower()

    # Используем словарь по умолчанию для обратной совместимости
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in description_lower:
                return category

    return 'Прочие расходы'
