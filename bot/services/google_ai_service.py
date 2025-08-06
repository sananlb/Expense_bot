"""
Google AI Service для expense_bot
"""
import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from .ai_base_service import AIBaseService
from .ai_selector import get_provider_settings, get_model

logger = logging.getLogger(__name__)


class GoogleAIService(AIBaseService):
    """Сервис для работы с Google AI (Gemini)"""
    
    def __init__(self):
        """Инициализация сервиса"""
        settings = get_provider_settings('google')
        self.api_key = settings['api_key']
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        genai.configure(api_key=self.api_key)
        self.models = {}  # Кэш моделей для разных типов
        
    def _get_model(self, service_type: str = 'categorization'):
        """Получает или создает модель"""
        if service_type not in self.models:
            model_name = get_model(service_type, 'google')
            logger.info(f"Creating Google AI model: {model_name} for {service_type}")
            self.models[service_type] = genai.GenerativeModel(model_name)
        return self.models[service_type]
    
    async def categorize_expense(
        self, 
        text: str, 
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Категоризация расхода через Google AI
        """
        try:
            logger.info(f"Starting Google AI categorization for '{text}'")
            
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            
            logger.info(f"Getting model for categorization")
            model = self._get_model('categorization')
            logger.info(f"Model retrieved: {model}")
            
            # Генерация с настройками для JSON
            generation_config = genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=1000  # Увеличиваем лимит токенов до 1000
                # Убираем response_mime_type, так как может вызывать проблемы
            )
            logger.info(f"Generation config created")
            
            logger.info(f"Calling Google AI API with timeout=5s...")
            # Асинхронный вызов с таймаутом
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        model.generate_content,
                        prompt,
                        generation_config=generation_config
                    ),
                    timeout=5.0  # 5 секунд таймаут
                )
                logger.info(f"Google AI responded successfully")
            except asyncio.TimeoutError:
                logger.error(f"Google AI timeout after 5 seconds for '{text}'")
                return None
            except Exception as e:
                logger.error(f"Google AI error: {e}")
                return None
            
            # Парсим ответ
            try:
                result = json.loads(response.text)
                
                # Валидация результата
                if 'category' in result and result['category'] in categories:
                    # Убираем эмоджи для логирования в Windows
                    cat_clean = ''.join(c for c in result['category'] if ord(c) < 128).strip()
                    logger.info(f"Google AI categorized '{text[:20]}' as '{cat_clean}' with confidence {result.get('confidence', 0)}")
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'google'
                    }
                else:
                    cat_name = result.get('category', 'None')
                    cat_clean = ''.join(c for c in str(cat_name) if ord(c) < 128).strip()
                    logger.warning(f"Google AI returned invalid category: {cat_clean}")
                    return None
                    
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Google AI response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Google AI categorization error: {e}")
            return None
    
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Чат с Google AI
        """
        try:
            prompt = self.get_chat_prompt(message, context, user_context)
            
            model = self._get_model('chat')
            
            # Генерация с настройками для чата
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,  # Увеличиваем до 1000
                top_p=0.9
            )
            
            # Асинхронный вызов
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=generation_config
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Google AI chat error: {e}")
            return "Извините, произошла ошибка при обработке вашего сообщения. Попробуйте еще раз."