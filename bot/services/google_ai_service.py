"""
Google AI Service для expense_bot - упрощенная рабочая версия на основе nutrition_bot
"""
import logging
import json
import asyncio
import os
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from .ai_base_service import AIBaseService
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Глобальная инициализация клиента при загрузке модуля
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("[GoogleAI] Module configured with API key")


class GoogleAIService(AIBaseService):
    """Сервис для работы с Google AI (Gemini) - упрощенная стабильная версия"""
    
    def __init__(self):
        """Инициализация сервиса"""
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        self.api_key = GOOGLE_API_KEY
        logger.info("[GoogleAI] Service initialized (fixed version)")
        
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
            logger.info(f"[GoogleAI] Starting categorization for: {text[:30]}")
            
            # Создаем промпт
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            
            # Создаем модель
            model_name = 'gemini-2.5-flash'  # Используем фиксированную модель
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
            
            # Safety settings
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            # Простой асинхронный вызов без лишних оберток
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info(f"[GoogleAI] Got response")
            
            # Проверяем блокировку контента
            if not response.parts:
                logger.warning(f"[GoogleAI] Empty response or content blocked")
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
                    logger.info(f"[GoogleAI] Categorized successfully: {result['category']}")
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'google'
                    }
                else:
                    logger.warning(f"[GoogleAI] Invalid category in response: {result.get('category')}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"[GoogleAI] JSON parse error: {e}, response: {response_text[:200]}")
                return None
                    
        except Exception as e:
            logger.error(f"[GoogleAI] Error: {type(e).__name__}: {str(e)[:200]}")
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
            
            model_name = 'gemini-2.5-flash'
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
            
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            if response and response.parts:
                return response.text.strip()
            else:
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."