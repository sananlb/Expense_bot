"""
Конфигурация для AI-интеграции парсера расходов
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from bot.services.key_rotation_mixin import OpenAIKeyRotationMixin, GoogleKeyRotationMixin


@dataclass
class AIConfig:
    """Конфигурация AI сервисов"""
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 200
    openai_temperature: float = 0.1
    
    # Google AI (альтернатива)
    google_api_key: Optional[str] = None
    google_model: str = "gemini-2.5-flash"
    
    # Настройки обработки
    enable_ai_parsing: bool = True
    ai_confidence_threshold: float = 0.7
    fallback_to_rules: bool = True
    cache_ai_responses: bool = True
    cache_ttl_hours: int = 24
    
    # Ограничения использования
    max_ai_requests_per_user_per_day: int = 100
    max_ai_requests_per_hour: int = 20
    
    @classmethod
    def from_env(cls) -> 'AIConfig':
        """Создание конфигурации с ротацией ключей"""
        # Получаем ключи через ротацию если доступны
        openai_key = None
        if OpenAIKeyRotationMixin.get_api_keys():
            openai_key = OpenAIKeyRotationMixin.get_next_key()
        
        google_key = None
        if GoogleKeyRotationMixin.get_api_keys():
            google_key = GoogleKeyRotationMixin.get_next_key()
        
        return cls(
            openai_api_key=openai_key,
            openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            openai_max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', '200')),
            openai_temperature=float(os.getenv('OPENAI_TEMPERATURE', '0.1')),
            
            google_api_key=google_key,
            google_model=os.getenv('GOOGLE_AI_MODEL', 'gemini-2.5-flash'),
            
            enable_ai_parsing=os.getenv('ENABLE_AI_PARSING', 'true').lower() == 'true',
            ai_confidence_threshold=float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7')),
            fallback_to_rules=os.getenv('FALLBACK_TO_RULES', 'true').lower() == 'true',
            cache_ai_responses=os.getenv('CACHE_AI_RESPONSES', 'true').lower() == 'true',
            cache_ttl_hours=int(os.getenv('CACHE_TTL_HOURS', '24')),
            
            max_ai_requests_per_user_per_day=int(os.getenv('MAX_AI_REQUESTS_PER_USER_PER_DAY', '100')),
            max_ai_requests_per_hour=int(os.getenv('MAX_AI_REQUESTS_PER_HOUR', '20')),
        )


# Промпты для разных задач
AI_PROMPTS = {
    'expense_parsing': """
Проанализируй текст о расходе и извлеки информацию.

Текст: "{text}"
{context}

Доступные категории:
- продукты: еда, супермаркеты, магазины продуктов
- транспорт: такси, метро, автобус, бензин, парковка
- кафе: рестораны, кофе, обеды, доставка еды
- развлечения: кино, театр, бары, игры, концерты
- здоровье: аптека, врачи, лекарства, медицина
- одежда: одежда, обувь, аксессуары
- связь: интернет, мобильная связь, телефон
- дом: коммуналка, аренда, мебель, ремонт
- подарки: подарки, цветы, праздники
- другое: все остальное

Верни JSON:
{{
    "amount": число,
    "description": "краткое описание (1-4 слова)",
    "category": "категория из списка",
    "confidence": число от 0 до 1,
    "currency": "RUB/USD/EUR/ARS/COP/PEN/CLP/MXN/BRL"
}}
""",
    
    'category_suggestion': """
Определи наиболее подходящую категорию для описания расхода.

Описание: "{description}"
{context}

Доступные категории: продукты, транспорт, кафе, развлечения, здоровье, одежда, связь, дом, подарки, другое

Верни JSON: {{"category": "название", "confidence": число от 0 до 1, "reasoning": "краткое объяснение"}}
""",
    
    'expense_improvement': """
Проанализируй расход и предложи улучшения.

Сумма: {amount} {currency}
Описание: {description}
Категория: {category}
Уверенность: {confidence}

Предложи улучшения в JSON:
{{
    "improved_description": "более точное описание или null",
    "alternative_categories": ["список альтернативных категорий"],
    "suggested_tags": ["теги для классификации"],
    "potential_issues": ["возможные проблемы"],
    "confidence_score": число от 0 до 1
}}
""",
    
    'receipt_ocr': """
Извлеки информацию о покупках из текста чека.

Текст чека: "{receipt_text}"

Найди и верни JSON:
{{
    "total_amount": число,
    "items": [
        {{"name": "название", "amount": число, "category": "предполагаемая категория"}}
    ],
    "merchant": "название магазина или null",
    "date": "дата в формате YYYY-MM-DD или null",
    "confidence": число от 0 до 1
}}
"""
}


class AIUsageLimiter:
    """Ограничитель использования AI API"""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._usage_cache = {}  # В реальной системе нужно использовать Redis
    
    def can_make_request(self, user_id: int) -> bool:
        """Проверка возможности сделать AI запрос"""
        if not self.config.enable_ai_parsing:
            return False
        
        # Проверяем дневной лимит
        daily_key = f"daily:{user_id}"
        daily_count = self._usage_cache.get(daily_key, 0)
        
        if daily_count >= self.config.max_ai_requests_per_user_per_day:
            return False
        
        # Проверяем часовой лимит
        hourly_key = f"hourly:{user_id}"
        hourly_count = self._usage_cache.get(hourly_key, 0)
        
        if hourly_count >= self.config.max_ai_requests_per_hour:
            return False
        
        return True
    
    def record_usage(self, user_id: int):
        """Записать использование AI"""
        daily_key = f"daily:{user_id}"
        hourly_key = f"hourly:{user_id}"
        
        self._usage_cache[daily_key] = self._usage_cache.get(daily_key, 0) + 1
        self._usage_cache[hourly_key] = self._usage_cache.get(hourly_key, 0) + 1
    
    def get_usage_stats(self, user_id: int) -> Dict[str, int]:
        """Получить статистику использования"""
        return {
            'daily_used': self._usage_cache.get(f"daily:{user_id}", 0),
            'daily_limit': self.config.max_ai_requests_per_user_per_day,
            'hourly_used': self._usage_cache.get(f"hourly:{user_id}", 0),
            'hourly_limit': self.config.max_ai_requests_per_hour
        }


class AIResponseCache:
    """Кэш для AI ответов"""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._cache = {}  # В реальной системе нужно использовать Redis
    
    def get_cached_response(self, text: str, prompt_type: str) -> Optional[Dict[str, Any]]:
        """Получить кэшированный ответ"""
        if not self.config.cache_ai_responses:
            return None
        
        cache_key = f"{prompt_type}:{hash(text)}"
        return self._cache.get(cache_key)
    
    def cache_response(self, text: str, prompt_type: str, response: Dict[str, Any]):
        """Кэшировать ответ"""
        if not self.config.cache_ai_responses:
            return
        
        cache_key = f"{prompt_type}:{hash(text)}"
        self._cache[cache_key] = response


# Фабрики для создания AI компонентов
def create_ai_config() -> AIConfig:
    """Создание конфигурации AI из переменных окружения"""
    return AIConfig.from_env()


def create_usage_limiter(config: Optional[AIConfig] = None) -> AIUsageLimiter:
    """Создание ограничителя использования"""
    if config is None:
        config = create_ai_config()
    return AIUsageLimiter(config)


def create_response_cache(config: Optional[AIConfig] = None) -> AIResponseCache:
    """Создание кэша ответов"""
    if config is None:
        config = create_ai_config()
    return AIResponseCache(config)


# Утилиты для работы с промптами
def format_prompt(prompt_type: str, **kwargs) -> str:
    """Форматирование промпта с параметрами"""
    if prompt_type not in AI_PROMPTS:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    
    template = AI_PROMPTS[prompt_type]
    return template.format(**kwargs)


def add_context_to_prompt(base_prompt: str, user_context: Optional[Dict[str, Any]]) -> str:
    """Добавление пользовательского контекста к промпту"""
    if not user_context:
        return base_prompt.replace('{context}', '')
    
    context_parts = []
    
    if user_context.get('recent_categories'):
        context_parts.append(f"Недавние категории: {', '.join(user_context['recent_categories'])}")
    
    if user_context.get('preferred_places'):
        context_parts.append(f"Частые места: {', '.join(user_context['preferred_places'])}")
    
    if user_context.get('currency'):
        context_parts.append(f"Валюта пользователя: {user_context['currency']}")
    
    context_str = '\n'.join(context_parts) if context_parts else ''
    return base_prompt.replace('{context}', context_str)


# Валидаторы AI ответов
def validate_expense_parsing_response(response: Dict[str, Any]) -> bool:
    """Валидация ответа AI для парсинга расходов"""
    required_fields = ['amount', 'description', 'category', 'confidence']
    
    if not all(field in response for field in required_fields):
        return False
    
    # Проверяем типы данных
    try:
        amount = float(response['amount'])
        confidence = float(response['confidence'])
        
        if amount <= 0 or confidence < 0 or confidence > 1:
            return False
        
        if not isinstance(response['description'], str) or len(response['description']) < 1:
            return False
        
        if not isinstance(response['category'], str):
            return False
        
        return True
    
    except (ValueError, TypeError):
        return False


def validate_category_suggestion_response(response: Dict[str, Any]) -> bool:
    """Валидация ответа AI для предложения категории"""
    required_fields = ['category', 'confidence']
    
    if not all(field in response for field in required_fields):
        return False
    
    try:
        confidence = float(response['confidence'])
        if confidence < 0 or confidence > 1:
            return False
        
        if not isinstance(response['category'], str):
            return False
        
        return True
    
    except (ValueError, TypeError):
        return False