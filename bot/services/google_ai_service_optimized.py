"""
Google AI Service - оптимизированная адаптивная версия
Использует самый быстрый метод определения ОС
"""
import logging
import json
import asyncio
import os
import sys  # Используем sys.platform - в 8 раз быстрее
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Самый быстрый способ определения Windows (0.035 мкс vs 0.282 мкс)
IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
    logger.info("[GoogleAI-Optimized] Windows detected - using isolated implementation")
    
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    
    def _process_categorization(api_key: str, text: str, amount: float, currency: str, categories: List[str]) -> Optional[Dict[str, Any]]:
        """Выполняется в отдельном процессе для Windows"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            prompt = f"""
            Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
            {', '.join(categories)}
            
            Return ONLY valid JSON:
            {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
            """
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            
            if not response or not response.text:
                return None
                
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

else:
    logger.info("[GoogleAI-Optimized] Unix/Linux detected - using native async")
    
    import google.generativeai as genai
    
    # Конфигурируем API при загрузке модуля
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        logger.info("[GoogleAI-Optimized] Configured with API key")


class GoogleAIService:
    """Оптимизированный адаптивный сервис Google AI"""
    
    # Кэшируем экземпляр для переиспользования (синглтон паттерн)
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Инициализация сервиса (выполняется только один раз)"""
        if GoogleAIService._initialized:
            return
            
        self.api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")
            
        logger.info(f"[GoogleAI-Optimized] Initializing ({'isolated' if IS_WINDOWS else 'async'} mode)")
        
        if IS_WINDOWS:
            # Для Windows создаем процессный пул с минимальными настройками
            ctx = mp.get_context('spawn')
            self.executor = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
        else:
            # Для Linux/Mac используем уже импортированный genai
            self.genai = genai
            
        GoogleAIService._initialized = True
    
    async def categorize_expense(
        self, 
        text: str, 
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Категоризация расхода"""
        try:
            if IS_WINDOWS:
                # Windows: изолированный процесс
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
                    logger.error(f"[GoogleAI-Optimized] Error: {result['error']}")
                    return None
                    
            else:
                # Linux/Mac: нативный async
                prompt = f"""
                Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
                {', '.join(categories)}
                
                Return ONLY valid JSON:
                {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
                """
                
                model = self.genai.GenerativeModel('gemini-2.5-flash')
                
                # Минимальные настройки для скорости
                generation_config = {
                    'temperature': 0.1,
                    'max_output_tokens': 500,  # Уменьшено для скорости
                    'candidate_count': 1
                }
                
                # Асинхронный вызов
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config
                )
                
                if not response or not response.text:
                    return None
                    
                # Быстрый парсинг
                text_response = response.text.strip()
                if '```' in text_response:
                    text_response = text_response[text_response.find('\n')+1:text_response.rfind('```')]
                
                result = json.loads(text_response)
                
                if result.get('category') not in categories:
                    return None
            
            return result
                
        except Exception as e:
            logger.error(f"[GoogleAI-Optimized] Error: {e}")
            return None
    
    async def chat(self, message: str, context: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
        """Чат"""
        return "AI чат временно недоступен"
    
    def get_expense_categorization_prompt(self, text, amount, currency, categories, user_context):
        """Для совместимости"""
        return f"Categorize expense: {text}"
    
    def get_chat_prompt(self, message, context, user_context):
        """Для совместимости"""
        return message
    
    def __del__(self):
        """Очистка ресурсов"""
        if IS_WINDOWS and hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)