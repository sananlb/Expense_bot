"""
Google AI Service для expense_bot
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
        self.models = {}  # Кэш моделей для разных типов
        
    def _get_model(self, service_type: str = 'categorization'):
        """Получает или создает модель"""
        # Временно отключаем кэширование для отладки
        model_name = get_model(service_type, 'google')
        logger.info(f"[GoogleAI] Creating new model: {model_name} for {service_type}")
        try:
            # Переконфигурируем API на каждый вызов
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(model_name)
            logger.info(f"[GoogleAI] Model created successfully: {model_name}")
            return model
        except Exception as e:
            logger.error(f"[GoogleAI] Failed to create model: {type(e).__name__}: {str(e)}")
            raise
    
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
            logger.info(f"[GoogleAI] Starting categorization for '{text}'")
            logger.info(f"[GoogleAI] Categories count: {len(categories)}")
            
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            logger.info(f"[GoogleAI] Prompt generated, length: {len(prompt)}")
            
            logger.info(f"[GoogleAI] Getting model for categorization")
            model = self._get_model('categorization')
            logger.info(f"[GoogleAI] Model retrieved successfully")
            
            # Генерация с настройками для JSON
            generation_config = genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=1000  # Увеличиваем лимит токенов до 1000
                # Убираем response_mime_type, так как может вызывать проблемы
            )
            logger.info(f"[GoogleAI] Generation config created")
            
            # Безопасное логирование без Unicode символов для Windows
            try:
                text_clean = ''.join(c for c in text[:30] if ord(c) < 128).strip()
                logger.info(f"[GoogleAI] Calling API for '{text_clean}...' with timeout=10s")
                logger.info(f"[GoogleAI] Model type: {type(model)}")
                logger.info(f"[GoogleAI] Prompt preview: {prompt[:100]}...")
            except Exception as log_err:
                logger.warning(f"[GoogleAI] Logging error: {log_err}")
                pass
            
            # Используем более простой подход через ThreadPoolExecutor
            try:
                logger.info(f"[GoogleAI] Starting API call with timeout=10s")
                
                # Используем ThreadPoolExecutor для выполнения синхронного кода
                import concurrent.futures
                import threading
                
                response = None
                exception = None
                
                def sync_generate():
                    nonlocal response, exception
                    try:
                        # Отключаем stderr временно для предотвращения ошибок в Windows
                        import sys
                        old_stderr = sys.stderr
                        sys.stderr = open(os.devnull, 'w')
                        
                        try:
                            response = model.generate_content(prompt, generation_config=generation_config)
                        finally:
                            # Восстанавливаем stderr
                            sys.stderr.close()
                            sys.stderr = old_stderr
                            
                    except Exception as e:
                        exception = e
                
                # Запускаем в отдельном потоке с таймаутом
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(sync_generate)
                    try:
                        future.result(timeout=10.0)  # 10 секунд таймаут
                    except concurrent.futures.TimeoutError:
                        logger.error(f"[GoogleAI] API call timeout after 10 seconds")
                        return None
                
                if exception:
                    raise exception
                    
                if not response:
                    logger.error(f"[GoogleAI] No response received")
                    return None
                    
                logger.info(f"[GoogleAI] Response received from API")
                
                # Проверяем, что ответ содержит текст
                try:
                    response_text = response.text
                except Exception as e:
                    # response.text может вызвать ошибку если ответ был заблокирован
                    logger.warning(f"Google AI response error: {str(e)[:100]}")
                    if hasattr(response, 'candidates') and response.candidates:
                        for candidate in response.candidates:
                            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                                for rating in candidate.safety_ratings:
                                    if rating.probability.name != 'NEGLIGIBLE':
                                        logger.warning(f"Safety filter triggered: {rating.category.name} = {rating.probability.name}")
                    return None
                
                if not response_text:
                    logger.warning(f"Google AI returned empty response")
                    return None
                    
                logger.info(f"Google AI responded successfully")
            except asyncio.TimeoutError:
                logger.error(f"Google AI timeout after 10 seconds")
                return None
            except Exception as e:
                error_msg = str(e) if str(e) else type(e).__name__
                # Очищаем от Unicode для Windows
                error_msg_clean = ''.join(c for c in error_msg[:200] if ord(c) < 128).strip()
                logger.error(f"Google AI error: {error_msg_clean}")
                return None
            
            # Парсим ответ
            try:
                # response_text уже получен выше
                # Убираем markdown блоки кода если они есть
                if response_text.startswith('```json'):
                    response_text = response_text[7:]  # Убираем ```json
                if response_text.startswith('```'):
                    response_text = response_text[3:]  # Убираем ```
                if response_text.endswith('```'):
                    response_text = response_text[:-3]  # Убираем ``` в конце
                response_text = response_text.strip()
                
                result = json.loads(response_text)
                
                # Валидация результата
                if 'category' in result and result['category'] in categories:
                    # Безопасное логирование без Unicode для Windows
                    try:
                        text_clean = ''.join(c for c in text[:20] if ord(c) < 128).strip()
                        cat_clean = ''.join(c for c in result['category'] if ord(c) < 128).strip()
                        logger.info(f"Google AI categorized '{text_clean}' as '{cat_clean}' with confidence {result.get('confidence', 0)}")
                    except:
                        pass  # Игнорируем ошибки логирования
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'google'
                    }
                else:
                    # Безопасное логирование
                    try:
                        cat_name = result.get('category', 'None')
                        cat_clean = ''.join(c for c in str(cat_name) if ord(c) < 128).strip()
                        logger.warning(f"Google AI returned invalid category: {cat_clean}")
                    except:
                        logger.warning(f"Google AI returned invalid category")
                    return None
                    
            except json.JSONDecodeError as e:
                # Безопасное логирование без Unicode
                try:
                    response_clean = ''.join(c for c in response_text[:200] if ord(c) < 128).strip()
                    logger.error(f"Failed to parse Google AI JSON: {e}. Response start: {response_clean}...")
                except:
                    logger.error(f"Failed to parse Google AI JSON: {e}")
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