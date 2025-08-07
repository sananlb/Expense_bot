"""
Google AI Service для expense_bot - упрощенная версия
"""
import logging
import json
import asyncio
import os
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
        logger.info("[GoogleAI] Service initialized (simple version)")
        
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
            logger.info(f"[GoogleAI-Simple] Starting categorization for: {text[:30]}")
            
            # Создаем промпт
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            
            # Создаем модель
            model_name = get_model('categorization', 'google')
            logger.info(f"[GoogleAI-Simple] Using model: {model_name}")
            
            # Переконфигурируем API на каждый вызов
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(model_name)
            
            # Настройки генерации
            generation_config = genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2000,
                top_p=0.95,
                top_k=40
            )
            
            # Safety settings - максимально разрешающие
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            logger.info(f"[GoogleAI-Simple] Calling API...")
            
            # Простой синхронный вызов в отдельном потоке через asyncio
            # БЕЗ сложной обработки stderr и прочего
            def sync_call():
                return model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
            
            # Используем asyncio.to_thread для Python 3.9+
            # или run_in_executor для более старых версий
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(sync_call),
                    timeout=10.0
                )
            except AttributeError:
                # Fallback для Python < 3.9
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, sync_call),
                    timeout=10.0
                )
            
            logger.info(f"[GoogleAI-Simple] Got response")
            
            # Обрабатываем ответ
            if not response or not response.text:
                logger.warning(f"[GoogleAI-Simple] Empty response")
                return None
            
            response_text = response.text.strip()
            
            # Убираем markdown блоки если есть
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Парсим JSON
            try:
                result = json.loads(response_text)
                
                if 'category' in result and result['category'] in categories:
                    logger.info(f"[GoogleAI-Simple] Categorized successfully")
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'google'
                    }
                else:
                    logger.warning(f"[GoogleAI-Simple] Invalid category in response")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"[GoogleAI-Simple] JSON parse error: {e}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"[GoogleAI-Simple] Timeout after 10 seconds")
            return None
        except Exception as e:
            logger.error(f"[GoogleAI-Simple] Error: {type(e).__name__}: {str(e)[:100]}")
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
            
            model_name = get_model('chat', 'google')
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(model_name)
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
                top_p=0.9
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            def sync_call():
                return model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
            
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(sync_call),
                    timeout=10.0
                )
            except AttributeError:
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, sync_call),
                    timeout=10.0
                )
            
            if response and response.text:
                return response.text.strip()
            else:
                return "Извините, не удалось получить ответ от AI."
                
        except asyncio.TimeoutError:
            logger.error("[GoogleAI-Simple Chat] Timeout")
            return "Извините, сервис временно недоступен. Попробуйте позже."
        except Exception as e:
            logger.error(f"[GoogleAI-Simple Chat] Error: {str(e)[:100]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."