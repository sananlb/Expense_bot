"""
Улучшенный парсер для извлечения информации о расходах из текстовых сообщений
Поддерживает более сложные паттерны, AI-обработку и интеграцию с OpenAI API
"""
import re
import json
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

# Импортируем ротацию ключей
try:
    from bot.services.key_rotation_mixin import OpenAIKeyRotationMixin
except ImportError:
    OpenAIKeyRotationMixin = None

# Импортируем новый модуль категоризации
from .expense_categorizer import categorize_expense, correct_typos

# Расширенные паттерны для извлечения суммы
AMOUNT_PATTERNS = [
    # Прямые упоминания суммы с валютой
    r'(\d+(?:[.,]\d+)?)\s*(?:руб|рублей|рубл|р\.?|₽)',
    r'(\d+(?:[.,]\d+)?)\s*(?:долл|доллар|долларов|\$|usd)',
    r'(\d+(?:[.,]\d+)?)\s*(?:евро|€|eur)',
    
    # Числа в контексте трат
    r'(?:потратил|потрачено|купил|заплатил|стоил|цена|стоимость|за)\s+(?:на\s+)?.*?(\d+(?:[.,]\d+)?)',
    r'(\d+(?:[.,]\d+)?)\s*(?:за|на|стоит|стоило)',
    
    # Простые числа (с низким приоритетом)
    r'(\d+(?:[.,]\d+)?)\s*$',  # просто число в конце
    r'^(\d+(?:[.,]\d+)?)(?:\s|$)',  # число в начале
    r'(?<!\d)(\d+(?:[.,]\d+)?)(?!\d)',  # число посередине
]

# Расширенный словарь ключевых слов для категорий с весами
CATEGORY_KEYWORDS = {
    'продукты': {
        'high': ['продукты', 'еда', 'пища', 'покушать', 'голодный'],
        'medium': ['магазин', 'супермаркет', 'гипермаркет', 'овощи', 'фрукты', 'мясо', 'хлеб', 'молоко'],
        'brands': ['пятерочка', 'перекресток', 'дикси', 'магнит', 'лента', 'ашан', 'metro', 'spar', 'окей', 'глобус']
    },
    'транспорт': {
        'high': ['транспорт', 'поездка', 'доехать', 'добраться'],
        'medium': ['такси', 'метро', 'автобус', 'маршрутка', 'трамвай', 'троллейбус', 'электричка', 'поезд'],
        'brands': ['яндекс', 'uber', 'gett', 'ситимобил', 'везет'],
        'fuel': ['бензин', 'дизель', 'газ', 'азс', 'заправка', 'топливо']
    },
    'кафе': {
        'high': ['кафе', 'ресторан', 'обед', 'завтрак', 'ужин', 'перекус', 'поесть'],
        'medium': ['кофе', 'чай', 'пицца', 'бургер', 'сендвич', 'суши', 'роллы'],
        'brands': ['макдональдс', 'kfc', 'бургер кинг', 'subway', 'starbucks', 'costa']
    },
    'развлечения': {
        'high': ['развлечения', 'отдых', 'досуг'],
        'medium': ['кино', 'театр', 'концерт', 'клуб', 'бар', 'игры', 'боулинг', 'караоке', 'парк'],
        'brands': ['кинотеатр', 'мультиплекс', 'синема парк']
    },
    'здоровье': {
        'high': ['здоровье', 'лечение', 'болезнь', 'больной'],
        'medium': ['аптека', 'лекарства', 'врач', 'клиника', 'больница', 'анализы', 'медицина', 'таблетки'],
        'brands': ['36.6', 'ригла', 'столичка']
    },
    'одежда': {
        'high': ['одежда', 'обувь', 'гардероб'],
        'medium': ['джинсы', 'футболка', 'куртка', 'платье', 'рубашка', 'кроссовки', 'ботинки'],
        'brands': ['zara', 'hm', 'uniqlo', 'reserved', 'bershka', 'pull&bear']
    },
    'связь': {
        'high': ['связь', 'интернет', 'телефон'],
        'medium': ['мобильный', 'тариф', 'пополнение'],
        'brands': ['мтс', 'билайн', 'мегафон', 'теле2', 'yota']
    },
    'дом': {
        'high': ['дом', 'квартира', 'жилье'],
        'medium': ['коммуналка', 'свет', 'вода', 'газ', 'квартплата', 'жкх', 'электричество'],
        'brands': ['мосэнерго', 'мосгаз']
    },
    'подарки': {
        'high': ['подарок', 'подарки', 'сюрприз'],
        'medium': ['день рождения', 'праздник', 'новый год', '8 марта', '23 февраля'],
        'brands': []
    },
    'другое': {
        'high': ['другое', 'прочее', 'разное'],
        'medium': [],
        'brands': []
    }
}

# Веса для разных типов совпадений
CATEGORY_WEIGHTS = {
    'high': 3,
    'medium': 2,
    'brands': 2,
    'fuel': 2
}


@dataclass
class ParsedExpense:
    """Результат парсинга расхода"""
    amount: float
    description: str
    category: str
    confidence: float = 0.0
    currency: str = 'RUB'
    ai_processed: bool = False
    raw_text: str = ''


def normalize_text(text: str) -> str:
    """Нормализация текста для лучшего парсинга"""
    if not text:
        return ''
    
    # Базовая нормализация
    text = text.strip().lower()
    
    # Замены для лучшего распознавания
    replacements = {
        'кафешка': 'кафе',
        'маршка': 'маршрутка',
        'пятёрочка': 'пятерочка',
        'магаз': 'магазин',
        'рест': 'ресторан',
        'врачу': 'врач',
        'лекарство': 'лекарства',
        'такса': 'такси',
        'электричка': 'электричка поезд'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


def extract_amount_advanced(text: str) -> Tuple[Optional[Decimal], str]:
    """Продвинутое извлечение суммы с учетом контекста"""
    normalized_text = normalize_text(text)
    best_amount = None
    best_pattern = ''
    best_priority = -1
    
    for i, pattern in enumerate(AMOUNT_PATTERNS):
        matches = list(re.finditer(pattern, normalized_text, re.IGNORECASE))
        
        for match in matches:
            try:
                amount_str = match.group(1).replace(',', '.')
                amount = Decimal(amount_str)
                
                if amount <= 0 or amount > 1000000:  # Разумные ограничения
                    continue
                
                # Приоритет паттернов (чем меньше индекс, тем выше приоритет)
                current_priority = len(AMOUNT_PATTERNS) - i
                
                if current_priority > best_priority:
                    best_amount = amount
                    best_pattern = match.group(0)
                    best_priority = current_priority
            except (ValueError, IndexError):
                continue
    
    # Удаляем найденную сумму из текста
    text_without_amount = normalized_text
    if best_pattern:
        text_without_amount = normalized_text.replace(best_pattern, ' ').strip()
        text_without_amount = ' '.join(text_without_amount.split())
    
    return best_amount, text_without_amount


def categorize_advanced(text: str) -> Tuple[str, float]:
    """Продвинутая категоризация с использованием улучшенного модуля"""
    # Используем новую функцию категоризации
    category, confidence, corrected_text = categorize_expense(text)
    
    # Возвращаем категорию и уверенность
    return category, confidence


async def _enhance_with_ai(parsed_expense: ParsedExpense) -> Optional[ParsedExpense]:
    """Улучшение парсинга с помощью AI"""
    if not openai:
        return None
    
    try:
        # Формируем промпт для OpenAI
        prompt = f"""
Проанализируй текст о расходе и определи категорию и описание.

Текст: "{parsed_expense.raw_text}"
Найденная сумма: {parsed_expense.amount}

Доступные категории:
- продукты (еда, магазины, супермаркеты)
- транспорт (такси, метро, бензин, автобус)
- кафе (рестораны, кофе, обеды)
- развлечения (кино, театр, бары, игры)
- здоровье (аптека, врачи, лекарства)
- одежда (одежда, обувь)
- связь (интернет, телефон, мобильная связь)
- дом (коммунальные услуги, квартплата)
- подарки (подарки, праздники)
- другое (все остальное)

Верни JSON с полями:
- category: название категории
- description: краткое описание расхода (1-3 слова)
- confidence: уверенность от 0 до 1
"""
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник для категоризации расходов. Отвечай только валидным JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.1
        )
        
        ai_response = response.choices[0].message.content.strip()
        ai_data = json.loads(ai_response)
        
        # Валидируем ответ AI
        if (
            'category' in ai_data and 
            'description' in ai_data and 
            ai_data['category'] in CATEGORY_KEYWORDS and
            ai_data.get('confidence', 0) > parsed_expense.confidence
        ):
            return ParsedExpense(
                amount=parsed_expense.amount,
                description=ai_data['description'],
                category=ai_data['category'],
                confidence=ai_data.get('confidence', 0.8),
                currency=parsed_expense.currency,
                ai_processed=True,
                raw_text=parsed_expense.raw_text
            )
    
    except Exception as e:
        print(f"AI processing error: {e}")
    
    return None


def parse_expense_message(text: str, use_ai: bool = False) -> Optional[ParsedExpense]:
    """
    Продвинутый парсер текстовых сообщений с поддержкой AI
    
    Примеры:
    - "Кофе 200" -> ParsedExpense(amount=200, description='Кофе', category='кафе')
    - "Потратил на бензин 4095" -> ParsedExpense(amount=4095, description='бензин', category='транспорт')
    - "Купил в пятерочке продукты за 1500" -> ParsedExpense(amount=1500, description='продукты в пятерочке', category='продукты')
    """
    if not text or not text.strip():
        return None
    
    original_text = text.strip()
    
    # Исправляем опечатки
    corrected_text = correct_typos(original_text)
    
    # Извлекаем сумму
    amount, text_without_amount = extract_amount_advanced(corrected_text)
    
    if not amount or amount <= 0:
        return None
    
    # Определяем категорию (используя исправленный текст)
    category, confidence = categorize_advanced(corrected_text.lower())
    
    # Формируем описание из исправленного текста
    description = text_without_amount.strip()
    if not description:
        description = 'Расход'
    
    # Капитализация только первой буквы, не меняя регистр остальных
    if description and len(description) > 0:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Создаем результат
    result = ParsedExpense(
        amount=float(amount),
        description=description,
        category=category,
        confidence=confidence,
        raw_text=original_text
    )
    
    # Если AI доступен и уверенность низкая, пытаемся улучшить с помощью AI
    if use_ai and confidence < 0.7 and openai:
        try:
            ai_result = asyncio.run(_enhance_with_ai(result))
            if ai_result:
                return ai_result
        except Exception:
            pass  # Fallback to rule-based result
    
    return result


def extract_amount_from_text(text: str) -> Optional[float]:
    """
    Извлекает только сумму из текста
    """
    parsed = parse_expense_message(text)
    return parsed.amount if parsed else None


def suggest_category(description: str) -> Tuple[str, float]:
    """
    Предлагает категорию на основе описания с оценкой уверенности
    """
    category, confidence = categorize_advanced(description.lower())
    return category, confidence


def parse_multiple_expenses(text: str) -> List[ParsedExpense]:
    """
    Парсинг нескольких расходов из одного сообщения
    
    Примеры:
    - "Кофе 200, такси 300" -> [ParsedExpense(...), ParsedExpense(...)]
    - "Обед 500 р, кино 400" -> [ParsedExpense(...), ParsedExpense(...)]
    """
    if not text:
        return []
    
    # Разделители для нескольких расходов
    separators = [',', ';', '\n', ' и ', ' + ']
    
    # Пытаемся разделить текст
    parts = [text.strip()]
    for separator in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(p.strip() for p in part.split(separator) if p.strip())
        parts = new_parts
    
    results = []
    for part in parts:
        if len(part) > 3:  # Минимальная длина для разумного текста
            parsed = parse_expense_message(part)
            if parsed:
                results.append(parsed)
    
    return results


def validate_expense_data(parsed: ParsedExpense) -> List[str]:
    """
    Валидация данных о расходе
    
    Возвращает список ошибок валидации
    """
    errors = []
    
    if parsed.amount <= 0:
        errors.append("Сумма должна быть положительной")
    
    if parsed.amount > 1000000:
        errors.append("Сумма слишком большая")
    
    if not parsed.description or len(parsed.description.strip()) < 1:
        errors.append("Описание не может быть пустым")
    
    if len(parsed.description) > 255:
        errors.append("Описание слишком длинное")
    
    if parsed.category not in CATEGORY_KEYWORDS:
        errors.append(f"Неизвестная категория: {parsed.category}")
    
    return errors


# Функции для интеграции с OpenAI API
class ExpenseParserAI:
    """Класс для AI-обработки расходов с использованием OpenAI"""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = api_key
        
        # Если ключ не передан, пытаемся получить из ротации
        if not api_key and OpenAIKeyRotationMixin:
            if OpenAIKeyRotationMixin.get_api_keys():
                self.api_key = OpenAIKeyRotationMixin.get_next_key()
        
        self.available = bool(OpenAI and self.api_key)
    
    async def parse_expense_with_ai(self, text: str, user_context: Optional[Dict] = None) -> Optional[ParsedExpense]:
        """
        Парсинг расхода с использованием AI и контекста пользователя
        
        user_context может содержать:
        - recent_categories: список недавно использованных категорий
        - preferred_places: предпочитаемые места
        - spending_patterns: паттерны трат пользователя
        """
        if not self.available:
            return parse_expense_message(text)
        
        try:
            # Формируем контекстуальный промпт
            context_info = ""
            if user_context:
                if user_context.get('recent_categories'):
                    context_info += f"Недавние категории пользователя: {', '.join(user_context['recent_categories'])}\n"
                if user_context.get('preferred_places'):
                    context_info += f"Предпочитаемые места: {', '.join(user_context['preferred_places'])}\n"
            
            prompt = f"""
Проанализируй текст о расходе и извлеки сумму, категорию и описание.

{context_info}

Текст: "{text}"

Доступные категории: продукты, транспорт, кафе, развлечения, здоровье, одежда, связь, дом, подарки, другое

Верни JSON:
{{
    "amount": число (сумма расхода),
    "description": "краткое описание",
    "category": "категория",
    "confidence": число от 0 до 1,
    "currency": "RUB/USD/EUR/ARS/COP/PEN/CLP/MXN/BRL"
}}
"""
            
            # Используем новый API OpenAI с клиентом
            client = OpenAI(api_key=self.api_key)
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу финансовых трат. Отвечай только валидным JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            ai_data = json.loads(ai_response)
            
            # Валидация и создание результата
            if all(key in ai_data for key in ['amount', 'description', 'category']):
                return ParsedExpense(
                    amount=float(ai_data['amount']),
                    description=ai_data['description'],
                    category=ai_data['category'],
                    confidence=ai_data.get('confidence', 0.9),
                    currency=ai_data.get('currency', 'RUB'),
                    ai_processed=True,
                    raw_text=text
                )
        
        except Exception as e:
            print(f"AI parsing error: {e}")
        
        # Fallback to rule-based parsing
        return parse_expense_message(text)
    
    async def suggest_expense_improvements(self, parsed: ParsedExpense) -> Dict[str, Any]:
        """
        Предложения по улучшению данных о расходе
        """
        if not self.available:
            return {}
        
        try:
            prompt = f"""
Проанализируй расход и предложи улучшения:

Сумма: {parsed.amount} {parsed.currency}
Описание: {parsed.description}
Категория: {parsed.category}
Уверенность: {parsed.confidence}

Предложи:
1. Более точное описание (если возможно)
2. Альтернативные категории (если уверенность низкая)
3. Теги для лучшей классификации
4. Потенциальные проблемы

Верни JSON с полями: improved_description, alternative_categories, suggested_tags, potential_issues
"""
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content.strip())
        
        except Exception as e:
            print(f"AI improvement error: {e}")
            return {}