"""
Сервис для работы с Google Gemini AI
"""
import os
import logging
import google.generativeai as genai
from typing import List, Dict, Optional, Any
import json
import asyncio
import threading
from functools import partial
from django.conf import settings

logger = logging.getLogger(__name__)

# Создаем пул ключей Google AI
GOOGLE_API_KEYS = []

# Инициализируем ключи из настроек
if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
    GOOGLE_API_KEYS = settings.GOOGLE_API_KEYS
    logger.info(f"Инициализировано {len(GOOGLE_API_KEYS)} Google AI ключей")
else:
    logger.info("Не найдены GOOGLE_API_KEYS в настройках")
    GOOGLE_API_KEYS = []


class GeminiAIService:
    """Сервис для работы с Google Gemini AI"""
    
    _key_index = 0  # Для round-robin распределения
    _key_lock = threading.Lock()  # Для thread-safe доступа
    
    def __init__(self):
        # Если нет пула ключей, используем единичный ключ
        if not GOOGLE_API_KEYS:
            self.api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')
            if not self.api_key:
                logger.warning("GOOGLE_API_KEY not found in environment variables")
                self.model_name = None
            else:
                self.model_name = 'gemini-2.5-flash'
        else:
            self.api_key = None
            self.model_name = 'gemini-2.5-flash'
    
    @classmethod
    def get_next_key(cls) -> Optional[str]:
        """Thread-safe получение следующего ключа с round-robin ротацией"""
        if not GOOGLE_API_KEYS:
            return None
        
        # Thread-safe round-robin распределение
        with cls._key_lock:
            current_index = cls._key_index
            cls._key_index = (cls._key_index + 1) % len(GOOGLE_API_KEYS)
            return GOOGLE_API_KEYS[current_index]
    
    def _configure_api(self) -> Optional[str]:
        """Настроить API с ротацией ключей"""
        # Получаем следующий ключ по round-robin
        api_key = self.get_next_key()
        
        # Если нет пула, используем единичный ключ
        if not api_key and hasattr(self, 'api_key') and self.api_key:
            api_key = self.api_key
        
        if api_key:
            genai.configure(api_key=api_key)
            return api_key
        return None
    
    async def optimize_category_keywords(
        self, 
        new_category: str, 
        all_categories: List[Dict[str, any]],
        language: str = 'ru'
    ) -> Dict[str, List[str]]:
        """
        Оптимизирует ключевые слова для новой категории
        и перераспределяет существующие ключевые слова
        
        Args:
            new_category: Название новой категории
            all_categories: Список всех категорий пользователя с их ключевыми словами
            language: Язык пользователя
            
        Returns:
            Словарь с оптимизированными ключевыми словами для каждой категории
        """
        # Настраиваем API
        api_key = self._configure_api()
        if not api_key or not self.model_name:
            logger.error("Gemini AI not configured")
            return {}
        
        # Создаем модель
        model = genai.GenerativeModel(self.model_name)
        
        # Формируем промпт
        categories_info = []
        for cat in all_categories:
            keywords = cat.get('keywords', [])
            categories_info.append(f"- {cat['name']}: {', '.join(keywords) if keywords else 'нет ключевых слов'}")
        
        prompt = f"""
Пользователь создал новую категорию расходов: "{new_category}"

Текущие категории и их ключевые слова:
{chr(10).join(categories_info)}

Задача:
1. Проанализируй новую категорию и предложи для неё релевантные ключевые слова (10-15 слов)
2. Проверь существующие ключевые слова других категорий и перенеси те, которые больше подходят к новой категории
3. Убедись, что ключевые слова не дублируются между категориями

Ответ верни ТОЛЬКО в формате JSON без дополнительного текста:
{{
    "category_name": {{
        "add": ["слово1", "слово2"],
        "remove": ["слово3", "слово4"]
    }}
}}

Где:
- add - слова, которые нужно добавить в категорию
- remove - слова, которые нужно удалить из категории
- Для новой категории будет только "add"
- Все слова должны быть в нижнем регистре

Язык ключевых слов: {language}
"""
        
        try:
            # Запускаем в отдельном потоке, чтобы не блокировать event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(model.generate_content, prompt)
            )
            
            # Извлекаем JSON из ответа
            response_text = response.text.strip()
            # Убираем markdown блоки кода, если есть
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            logger.info(f"Gemini AI keywords optimization result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in Gemini AI keywords optimization: {e}")
            
            # Возвращаем базовые ключевые слова для новой категории
            return {
                new_category: {
                    "add": self._get_basic_keywords(new_category),
                    "remove": []
                }
            }
    
    async def suggest_category_from_description(
        self,
        description: str,
        categories: List[str],
        recent_expenses: Optional[List[Dict]] = None,
        language: str = 'ru'
    ) -> Optional[str]:
        """
        Предлагает категорию на основе описания расхода
        
        Args:
            description: Описание расхода
            categories: Список доступных категорий
            recent_expenses: Недавние расходы пользователя для контекста
            language: Язык пользователя
            
        Returns:
            Название подходящей категории или None
        """
        # Настраиваем API
        api_key = self._configure_api()
        if not api_key or not self.model_name:
            return None
        
        # Создаем модель
        model = genai.GenerativeModel(self.model_name)
        
        # Формируем контекст из недавних расходов
        context = ""
        if recent_expenses:
            context = "\nНедавние расходы пользователя:\n"
            for exp in recent_expenses[:5]:
                context += f"- {exp.get('description', '')}: {exp.get('category', '')}\n"
        
        prompt = f"""
Определи категорию для расхода: "{description}"

Доступные категории:
{chr(10).join([f'- {cat}' for cat in categories])}
{context}

Ответь ТОЛЬКО названием категории из списка выше, которая лучше всего подходит.
Если ни одна категория не подходит точно, выбери наиболее близкую.
"""
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(model.generate_content, prompt)
            )
            
            suggested_category = response.text.strip()
            
            # Проверяем, что предложенная категория есть в списке
            result = None
            for cat in categories:
                if suggested_category.lower() in cat.lower() or cat.lower() in suggested_category.lower():
                    result = cat
                    break
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Gemini AI category suggestion: {e}")
            
            return None
    
    def _get_basic_keywords(self, category_name: str) -> List[str]:
        """Возвращает базовые ключевые слова для категории"""
        category_lower = category_name.lower()
        
        # Базовые ключевые слова на основе названия
        basic_keywords = []
        
        # Извлекаем слова из названия категории
        import re
        words = re.findall(r'\w+', category_lower)
        for word in words:
            if len(word) > 3:  # Только слова длиннее 3 символов
                basic_keywords.append(word)
        
        return basic_keywords


# Глобальный экземпляр сервиса
gemini_service = GeminiAIService()