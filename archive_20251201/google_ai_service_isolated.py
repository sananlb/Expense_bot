"""
Google AI Service с изолированным выполнением в отдельном процессе
Решает проблему конфликта event loop между aiogram и google.generativeai на Windows
"""
import logging
import json
import asyncio
import os
from typing import Dict, List, Optional, Any
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from functools import partial

logger = logging.getLogger(__name__)

# Функция для выполнения в отдельном процессе
def _process_categorization(api_key: str, text: str, amount: float, currency: str, categories: List[str]) -> Optional[Dict[str, Any]]:
    """Выполняется в отдельном процессе, изолированно от основного event loop"""
    try:
        # Импортируем google.generativeai ТОЛЬКО в отдельном процессе
        import google.generativeai as genai
        
        # Конфигурируем API
        genai.configure(api_key=api_key)
        
        # Создаем промпт
        prompt = f"""
        Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
        {', '.join(categories)}
        
        Return ONLY valid JSON:
        {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
        """
        
        # Создаем модель и генерируем ответ синхронно
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        if not response or not response.text:
            return None
            
        # Парсим ответ
        text_response = response.text.strip()
        if text_response.startswith('```'):
            text_response = text_response[text_response.find('\n')+1:text_response.rfind('```')]
        
        result = json.loads(text_response)
        
        if result.get('category') in categories:
            return {
                'category': result['category'],
                'confidence': result.get('confidence', 0.8),
                'reasoning': result.get('reasoning', ''),
                'provider': 'google'
            }
            
    except Exception as e:
        return {'error': str(e)}
    
    return None


class GoogleAIService:
    """Сервис Google AI с изолированным выполнением"""
    
    def __init__(self):
        """Инициализация сервиса"""
        logger.info("[GoogleAI-Isolated] Init started")
        
        # Получаем API ключ
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")
            
        logger.info(f"[GoogleAI-Isolated] API key loaded: {self.api_key[:10]}...")
        
        # Создаем процессный пул для изолированного выполнения
        # Используем spawn для Windows совместимости
        ctx = mp.get_context('spawn')
        self.executor = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
        
        logger.info("[GoogleAI-Isolated] Service initialized with process pool")
    
    async def categorize_expense(
        self, 
        text: str, 
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Категоризация расхода в отдельном процессе"""
        try:
            logger.info(f"[GoogleAI-Isolated] Starting categorization for: {text[:30]}")
            
            # Выполняем в отдельном процессе, изолированно от основного event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                _process_categorization,
                self.api_key,
                text,
                amount,
                currency,
                categories
            )
            
            if result and 'error' in result:
                logger.error(f"[GoogleAI-Isolated] Process error: {result['error']}")
                return None
            
            if result:
                # Избегаем проблем с Unicode в логах Windows
                category = result.get('category', '').encode('ascii', 'ignore').decode('ascii')
                logger.info(f"[GoogleAI-Isolated] Categorized successfully: {category or 'category with emoji'}")
            
            return result
                
        except Exception as e:
            logger.error(f"[GoogleAI-Isolated] Error: {e}")
            return None
    
    async def chat(self, message: str, context: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
        """Чат - пока не реализован"""
        return "AI чат временно недоступен"
    
    def get_expense_categorization_prompt(self, text, amount, currency, categories, user_context):
        """Заглушка для совместимости"""
        return f"Categorize expense: {text}"
    
    def get_chat_prompt(self, message, context, user_context):
        """Заглушка для совместимости"""
        return message
    
    def __del__(self):
        """Очистка ресурсов"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)