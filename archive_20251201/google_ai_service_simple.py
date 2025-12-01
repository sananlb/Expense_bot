"""
Google AI Service - максимально упрощенная версия без зависимостей
"""
import logging
import json
import asyncio
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class GoogleAIService:
    """Простейший сервис для работы с Google AI"""
    
    def __init__(self):
        """Инициализация сервиса"""
        logger.info("[GoogleAI-Simple] Starting init...")
        
        # Получаем API ключ
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")
            
        logger.info(f"[GoogleAI-Simple] API key loaded: {self.api_key[:10]}...")
        
        # Конфигурируем genai
        try:
            logger.info("[GoogleAI-Simple] Importing genai...")
            import google.generativeai as genai
            logger.info("[GoogleAI-Simple] Configuring genai...")
            genai.configure(api_key=self.api_key)
            self.genai = genai
            logger.info("[GoogleAI-Simple] Service initialized")
        except Exception as e:
            logger.error(f"[GoogleAI-Simple] Init error: {e}")
            raise
    
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
            logger.info(f"[GoogleAI-Simple] Categorizing: {text[:30]}")
            
            # Создаем промпт
            prompt = f"""
            Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
            {', '.join(categories)}
            
            Return ONLY valid JSON:
            {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
            """
            
            # Создаем модель
            model = self.genai.GenerativeModel('gemini-2.5-flash')
            
            # Генерируем ответ
            logger.info("[GoogleAI-Simple] Calling API...")
            response = await model.generate_content_async(prompt)
            logger.info("[GoogleAI-Simple] Got response")
            
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
            logger.error(f"[GoogleAI-Simple] Error: {e}")
            
        return None
    
    async def chat(self, message: str, context: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
        """Чат"""
        return "AI чат временно недоступен"
    
    def get_expense_categorization_prompt(self, text, amount, currency, categories, user_context):
        """Заглушка для совместимости"""
        return f"Categorize expense: {text}"
    
    def get_chat_prompt(self, message, context, user_context):
        """Заглушка для совместимости"""
        return message