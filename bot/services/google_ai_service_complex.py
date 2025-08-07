"""
Google AI Service для expense_bot - исправленная версия
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
        logger.info("[GoogleAI] Service initialized")
        
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
            logger.info(f"[GoogleAI] Starting categorization for text: {text[:30]}")
            
            # Создаем промпт
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            
            # Логируем промпт для отладки (первые 500 символов)
            prompt_preview = prompt[:500].replace('\n', ' ')
            logger.info(f"[GoogleAI] Prompt preview: {prompt_preview}...")
            
            # Создаем модель каждый раз заново
            model_name = get_model('categorization', 'google')
            logger.info(f"[GoogleAI] Creating model: {model_name}")
            
            try:
                # Переконфигурируем API
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel(model_name)
            except Exception as e:
                logger.error(f"[GoogleAI] Failed to create model: {e}")
                return None
            
            # Настройки генерации
            generation_config = genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2000,  # Увеличиваем до 2000
                top_p=0.95,
                top_k=40
            )
            
            # Настройки безопасности - максимально разрешающие
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
            
            logger.info(f"[GoogleAI] Generation config: temp={generation_config.temperature}, max_tokens={generation_config.max_output_tokens}")
            
            # Пробуем простой синхронный вызов в executor
            logger.info(f"[GoogleAI] Calling API with prompt length: {len(prompt)} chars")
            
            try:
                # Используем run_in_executor для изоляции блокирующего вызова
                loop = asyncio.get_event_loop()
                
                # Функция для синхронного вызова
                def call_api():
                    try:
                        # Отключаем вывод ошибок в stderr
                        import sys
                        import io
                        old_stderr = sys.stderr
                        sys.stderr = io.StringIO()
                        
                        try:
                            logger.info(f"[GoogleAI-Thread] Calling generate_content with safety_settings...")
                            # Используем safety_settings из внешней области видимости
                            result = model.generate_content(
                                prompt, 
                                generation_config=generation_config,
                                safety_settings=safety_settings
                            )
                            logger.info(f"[GoogleAI-Thread] Got response object")
                            return result
                        finally:
                            sys.stderr = old_stderr
                    except Exception as e:
                        logger.error(f"[GoogleAI] API call error: {str(e)[:100]}")
                        return None
                
                # Вызываем с таймаутом
                try:
                    response = await asyncio.wait_for(
                        loop.run_in_executor(None, call_api),
                        timeout=8.0
                    )
                except asyncio.TimeoutError:
                    logger.error("[GoogleAI] API timeout after 8 seconds")
                    return None
                
                if not response:
                    logger.error("[GoogleAI] No response from API")
                    return None
                    
            except Exception as e:
                logger.error(f"[GoogleAI] Execution error: {str(e)[:100]}")
                return None
            
            # Обрабатываем ответ
            logger.info(f"[GoogleAI] Processing response...")
            
            # Детальное логирование ответа
            if hasattr(response, 'candidates') and response.candidates:
                logger.info(f"[GoogleAI] Found {len(response.candidates)} candidates")
                for i, candidate in enumerate(response.candidates):
                    logger.info(f"[GoogleAI] Candidate {i}:")
                    
                    # Логируем safety ratings
                    if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            if rating.probability.name != 'NEGLIGIBLE':
                                logger.warning(f"[GoogleAI] Safety: {rating.category.name} = {rating.probability.name}")
                    
                    # Логируем finish reason
                    if hasattr(candidate, 'finish_reason'):
                        logger.info(f"[GoogleAI] Finish reason: {candidate.finish_reason}")
                    
                    # Проверяем content
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts') and candidate.content.parts:
                            logger.info(f"[GoogleAI] Content has {len(candidate.content.parts)} parts")
                        else:
                            logger.warning(f"[GoogleAI] Content has no parts")
            else:
                logger.warning(f"[GoogleAI] No candidates in response")
            
            try:
                response_text = response.text
                logger.info(f"[GoogleAI] Got response text, length: {len(response_text)}")
            except Exception as e:
                logger.error(f"[GoogleAI] Cannot get response.text: {str(e)[:200]}")
                return None
            
            if not response_text:
                logger.warning("[GoogleAI] Empty response text")
                return None
            
            # Парсим JSON
            try:
                # Убираем markdown блоки если есть
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.startswith('```'):
                    response_text = response_text[3:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                result = json.loads(response_text)
                
                # Валидация
                if 'category' in result and result['category'] in categories:
                    logger.info(f"[GoogleAI] Successfully categorized as: {result['category'][:20]}")
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'google'
                    }
                else:
                    logger.warning(f"[GoogleAI] Invalid category in response")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"[GoogleAI] JSON parse error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"[GoogleAI] General error: {str(e)[:100]}")
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
                max_output_tokens=500,
                top_p=0.9
            )
            
            # Синхронный вызов через executor
            loop = asyncio.get_event_loop()
            
            def call_api():
                try:
                    import sys
                    import io
                    old_stderr = sys.stderr
                    sys.stderr = io.StringIO()
                    
                    try:
                        result = model.generate_content(prompt, generation_config=generation_config)
                        return result.text.strip() if result and result.text else None
                    finally:
                        sys.stderr = old_stderr
                except Exception as e:
                    logger.error(f"[GoogleAI Chat] Error: {str(e)[:100]}")
                    return None
            
            try:
                response_text = await asyncio.wait_for(
                    loop.run_in_executor(None, call_api),
                    timeout=8.0
                )
                return response_text or "Извините, произошла ошибка при обработке вашего сообщения."
            except asyncio.TimeoutError:
                logger.error("[GoogleAI Chat] Timeout")
                return "Извините, сервис временно недоступен. Попробуйте позже."
                
        except Exception as e:
            logger.error(f"[GoogleAI Chat] Error: {str(e)[:100]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."