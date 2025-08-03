import os
import json
import logging
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from decimal import Decimal

import openai
import google.generativeai as genai
from aiogram.types import User

from expenses.models import ExpenseCategory, Expense
from profiles.models import Profile

logger = logging.getLogger(__name__)


class AIConfig:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    GOOGLE_MODEL = os.getenv('GOOGLE_MODEL', 'gemini-2.5-flash')
    
    USE_OPENAI = bool(OPENAI_API_KEY)
    USE_GOOGLE = bool(GOOGLE_API_KEY)
    
    AI_CONFIDENCE_THRESHOLD = float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7'))
    MAX_AI_REQUESTS_PER_DAY = int(os.getenv('MAX_AI_REQUESTS_PER_DAY', '100'))
    MAX_AI_REQUESTS_PER_HOUR = int(os.getenv('MAX_AI_REQUESTS_PER_HOUR', '20'))
    
    CACHE_TTL_HOURS = int(os.getenv('AI_CACHE_TTL_HOURS', '24'))


class AIUsageLimiter:
    def __init__(self):
        self._usage = {}  # {user_id: [(timestamp, provider), ...]}
    
    def can_use(self, user_id: int) -> bool:
        now = datetime.now()
        if user_id not in self._usage:
            self._usage[user_id] = []
        
        # Clean old entries
        self._usage[user_id] = [
            (ts, prov) for ts, prov in self._usage[user_id]
            if now - ts < timedelta(days=1)
        ]
        
        # Check daily limit
        daily_count = len(self._usage[user_id])
        if daily_count >= AIConfig.MAX_AI_REQUESTS_PER_DAY:
            return False
        
        # Check hourly limit
        hour_ago = now - timedelta(hours=1)
        hourly_count = sum(1 for ts, _ in self._usage[user_id] if ts > hour_ago)
        if hourly_count >= AIConfig.MAX_AI_REQUESTS_PER_HOUR:
            return False
        
        return True
    
    def record_usage(self, user_id: int, provider: str):
        if user_id not in self._usage:
            self._usage[user_id] = []
        self._usage[user_id].append((datetime.now(), provider))


class AIResponseCache:
    def __init__(self):
        self._cache = {}  # {hash: (response, timestamp)}
    
    def _get_key(self, text: str, user_id: int) -> str:
        content = f"{text}:{user_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, text: str, user_id: int) -> Optional[Dict[str, Any]]:
        key = self._get_key(text, user_id)
        if key in self._cache:
            response, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(hours=AIConfig.CACHE_TTL_HOURS):
                return response
            else:
                del self._cache[key]
        return None
    
    def set(self, text: str, user_id: int, response: Dict[str, Any]):
        key = self._get_key(text, user_id)
        self._cache[key] = (response, datetime.now())


class ExpenseCategorizer:
    def __init__(self):
        self.usage_limiter = AIUsageLimiter()
        self.cache = AIResponseCache()
        
        # Initialize AI clients
        if AIConfig.USE_OPENAI:
            openai.api_key = AIConfig.OPENAI_API_KEY
        
        if AIConfig.USE_GOOGLE:
            genai.configure(api_key=AIConfig.GOOGLE_API_KEY)
            self.google_model = genai.GenerativeModel(AIConfig.GOOGLE_MODEL)
    
    def get_system_prompt(self) -> str:
        return """Ты помощник для категоризации расходов. 
Твоя задача - анализировать текст и определять категорию расхода, сумму и описание.
Отвечай только валидным JSON без дополнительного текста."""
    
    def get_categorization_prompt(self, text: str, categories: List[str], 
                                  user_context: Optional[Dict[str, Any]] = None) -> str:
        context_info = ""
        if user_context:
            if 'recent_categories' in user_context:
                context_info += f"\nНедавние категории пользователя: {', '.join(user_context['recent_categories'])}"
            if 'preferred_currency' in user_context:
                context_info += f"\nПредпочитаемая валюта: {user_context['preferred_currency']}"
        
        categories_list = '\n'.join([f"- {cat}" for cat in categories])
        
        return f"""Проанализируй текст о расходе и извлеки информацию.

Текст: "{text}"
{context_info}

Доступные категории:
{categories_list}

Верни JSON в формате:
{{
    "amount": число (обязательно),
    "description": "краткое описание на русском (1-4 слова)",
    "category": "категория из списка выше",
    "confidence": число от 0 до 1,
    "currency": "RUB" (или USD/EUR/ARS/COP/PEN/CLP/MXN/BRL если явно указано)
}}

Примеры:
- "Кофе 300" -> {{"amount": 300, "description": "Кофе", "category": "Кафе и рестораны", "confidence": 0.9, "currency": "RUB"}}
- "Такси домой 450р" -> {{"amount": 450, "description": "Такси домой", "category": "Транспорт", "confidence": 0.95, "currency": "RUB"}}"""
    
    async def categorize_with_openai(self, text: str, categories: List[str],
                                    user_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            prompt = self.get_categorization_prompt(text, categories, user_context)
            
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model=AIConfig.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"OpenAI categorization error: {e}")
            return None
    
    async def categorize_with_google(self, text: str, categories: List[str],
                                   user_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            prompt = self.get_categorization_prompt(text, categories, user_context)
            full_prompt = f"{self.get_system_prompt()}\n\n{prompt}"
            
            response = await asyncio.to_thread(
                self.google_model.generate_content,
                full_prompt
            )
            
            content = response.text.strip()
            # Remove markdown code blocks if present
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            return json.loads(content.strip())
            
        except Exception as e:
            logger.error(f"Google AI categorization error: {e}")
            return None
    
    def validate_result(self, result: Dict[str, Any], categories: List[str]) -> bool:
        """Validate AI response"""
        required_fields = ['amount', 'description', 'category', 'confidence']
        
        # Check required fields
        if not all(field in result for field in required_fields):
            return False
        
        # Validate amount
        try:
            amount = float(result['amount'])
            if amount <= 0 or amount > 10_000_000:
                return False
        except (ValueError, TypeError):
            return False
        
        # Validate category
        if result['category'] not in categories:
            return False
        
        # Validate confidence
        try:
            confidence = float(result['confidence'])
            if not 0 <= confidence <= 1:
                return False
        except (ValueError, TypeError):
            return False
        
        # Validate description
        if not isinstance(result['description'], str) or len(result['description']) > 100:
            return False
        
        return True
    
    async def categorize(self, text: str, user_id: int, 
                        profile: Optional[Profile] = None) -> Optional[Dict[str, Any]]:
        """Main categorization method"""
        
        # Check cache
        cached = self.cache.get(text, user_id)
        if cached:
            logger.info(f"Using cached result for user {user_id}")
            return cached
        
        # Check usage limits
        if not self.usage_limiter.can_use(user_id):
            logger.warning(f"AI usage limit exceeded for user {user_id}")
            return None
        
        # Get categories for user
        if profile:
            categories = list(ExpenseCategory.objects.filter(
                profile=profile
            ).values_list('name', flat=True))
        else:
            categories = [
                "Продукты", "Транспорт", "Кафе и рестораны", 
                "Развлечения", "Здоровье", "Одежда и обувь",
                "Связь и интернет", "Дом и ЖКХ", "Подарки", "Прочие расходы"
            ]
        
        # Get user context
        user_context = {}
        if profile:
            # Get recent categories
            recent_expenses = Expense.objects.filter(
                profile=profile
            ).order_by('-created_at')[:10]
            
            recent_categories = list(set([
                exp.category.name for exp in recent_expenses 
                if exp.category
            ]))[:5]
            
            if recent_categories:
                user_context['recent_categories'] = recent_categories
            
            # Get preferred currency
            currencies = recent_expenses.values_list('currency', flat=True)
            if currencies:
                from collections import Counter
                currency_counts = Counter(currencies)
                user_context['preferred_currency'] = currency_counts.most_common(1)[0][0]
        
        result = None
        
        # Try Google AI first (Gemini 2.0 Flash)
        if AIConfig.USE_GOOGLE:
            result = await self.categorize_with_google(text, categories, user_context)
            if result and self.validate_result(result, categories):
                self.usage_limiter.record_usage(user_id, 'google')
                self.cache.set(text, user_id, result)
                return result
        
        # Fallback to OpenAI (GPT-4o-mini)
        if AIConfig.USE_OPENAI:
            result = await self.categorize_with_openai(text, categories, user_context)
            if result and self.validate_result(result, categories):
                self.usage_limiter.record_usage(user_id, 'openai')
                self.cache.set(text, user_id, result)
                return result
        
        logger.warning(f"All AI providers failed for user {user_id}")
        return None


# Singleton instance
categorizer = ExpenseCategorizer()


async def categorize_expense(text: str, user: User, profile: Optional[Profile] = None) -> Optional[Dict[str, Any]]:
    """Helper function for easy integration"""
    return await categorizer.categorize(text, user.id, profile)