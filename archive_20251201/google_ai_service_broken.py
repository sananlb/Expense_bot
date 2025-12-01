"""
Google AI Service для expense_bot - асинхронная версия на основе nutrition_bot
"""
import logging
logger = logging.getLogger(__name__)
logger.info("[GoogleAI Module] Starting imports...")

import json
import asyncio
import os
from typing import Dict, List, Optional, Any

logger.info("[GoogleAI Module] Importing google.generativeai...")
import google.generativeai as genai
logger.info("[GoogleAI Module] google.generativeai imported")

logger.info("[GoogleAI Module] Importing AIBaseService...")
from .ai_base_service import AIBaseService
logger.info("[GoogleAI Module] AIBaseService imported")


class GoogleAIService(AIBaseService):
    """Сервис для работы с Google AI (Gemini) - стабильная асинхронная версия"""
    
    def __init__(self):
        """Инициализация сервиса"""
        logger.info("[GoogleAI] Starting __init__...")
        
        # Импортируем здесь, чтобы избежать циклического импорта
        logger.info("[GoogleAI] Importing get_provider_settings...")
        from .ai_selector import get_provider_settings
        
        logger.info("[GoogleAI] Getting provider settings...")
        settings = get_provider_settings('google')
        self.api_key = settings['api_key']
        
        logger.info(f"[GoogleAI] API key obtained: {self.api_key[:10]}...")
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        logger.info("[GoogleAI] Configuring genai...")
        genai.configure(api_key=self.api_key)
        logger.info("[GoogleAI] Service initialized (async version)")
        logger.info(f"[GoogleAI] Using generate_content_async method")
        
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
        max_attempts = 2
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"[GoogleAI-Async] Categorization attempt {attempt + 1}/{max_attempts} for: {text[:30]}")
                
                # Создаем промпт
                prompt = self.get_expense_categorization_prompt(
                    text, amount, currency, categories, user_context
                )
                
                # Создаем модель с системной инструкцией
                from .ai_selector import get_model
                model_name = get_model('categorization', 'google')
                logger.info(f"[GoogleAI-Async] Using model: {model_name}")
                
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction="You are an expense categorization assistant. Return ONLY valid JSON without any additional text or markdown formatting."
                )
                
                # Настройки генерации
                generation_config = genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=1000,
                    candidate_count=1,
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
                
                logger.info(f"[GoogleAI-Async] Calling async API...")
                logger.info(f"[GoogleAI-Async] Model type: {type(model)}")
                logger.info(f"[GoogleAI-Async] Has async method: {hasattr(model, 'generate_content_async')}")
                
                # Асинхронный вызов с таймаутом
                try:
                    logger.info(f"[GoogleAI-Async] Starting async call with timeout=10s...")
                    response = await asyncio.wait_for(
                        model.generate_content_async(
                            prompt,
                            generation_config=generation_config,
                            safety_settings=safety_settings
                        ),
                        timeout=10.0
                    )
                    logger.info(f"[GoogleAI-Async] Response received")
                except asyncio.TimeoutError:
                    logger.error(f"[GoogleAI-Async] Request timeout on attempt {attempt + 1}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)
                        continue
                    else:
                        return None
                
                logger.info(f"[GoogleAI-Async] Got response")
                
                # Проверяем блокировку контента
                if not response.parts:
                    if response.candidates:
                        for i, candidate in enumerate(response.candidates):
                            logger.warning(f"Candidate {i}: finish_reason={getattr(candidate, 'finish_reason', 'UNKNOWN')}")
                            if hasattr(candidate, 'safety_ratings'):
                                for rating in candidate.safety_ratings:
                                    logger.warning(f"Safety: {rating.category} = {rating.probability}")
                    
                    logger.error(f"[GoogleAI-Async] Content blocked by safety filters")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)
                        continue
                    else:
                        return None
                
                # Обрабатываем ответ
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
                        logger.info(f"[GoogleAI-Async] Categorized successfully: {result['category']}")
                        return {
                            'category': result['category'],
                            'confidence': result.get('confidence', 0.8),
                            'reasoning': result.get('reasoning', ''),
                            'provider': 'google'
                        }
                    else:
                        logger.warning(f"[GoogleAI-Async] Invalid category in response: {result.get('category')}")
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(1)
                            continue
                        else:
                            return None
                        
                except json.JSONDecodeError as e:
                    logger.error(f"[GoogleAI-Async] JSON parse error: {e}, response: {response_text[:200]}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)
                        continue
                    else:
                        return None
                    
            except Exception as e:
                logger.error(f"[GoogleAI-Async] Error on attempt {attempt + 1}: {type(e).__name__}: {str(e)[:200]}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    return None
        
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
            
            from .ai_selector import get_model
            model_name = get_model('chat', 'google')
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="You are a helpful expense tracking assistant. Respond in the same language as the user's message."
            )
            
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
            
            logger.info(f"[GoogleAI-Async Chat] Calling API...")
            
            try:
                response = await asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    ),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.error("[GoogleAI-Async Chat] Request timeout")
                return "Извините, сервис временно недоступен. Попробуйте позже."
            
            if response and response.parts:
                return response.text.strip()
            else:
                logger.warning("[GoogleAI-Async Chat] Empty response or content blocked")
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            logger.error(f"[GoogleAI-Async Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."