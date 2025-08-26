"""
Google AI Service - адаптивная версия
Использует асинхронную версию на Linux/Mac и изолированную на Windows
"""
import logging
import json
import asyncio
import os
import platform
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Определяем ОС
IS_WINDOWS = platform.system() == 'Windows'

def _process_chat_wrapper(api_key: str, message: str, context_str: str, user_info: str) -> str:
    """Функция для выполнения чата в отдельном процессе"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        prompt = f"""Ты - помощник по учету расходов. Отвечай на русском языке.
        
{user_info}
Контекст разговора:
{context_str}

Вопрос пользователя: {message}

Дай полезный и точный ответ на вопрос пользователя."""
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        return "Не удалось получить ответ от AI"
    except Exception as e:
        return f"Ошибка AI: {str(e)}"

if IS_WINDOWS:
    # На Windows используем изолированную версию
    logger.info("[GoogleAI-Adaptive] Windows detected - using isolated process implementation")
    
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    
    # Функция для выполнения в отдельном процессе (только для Windows)
    def _process_categorization(api_key: str, text: str, amount: float, currency: str, categories: List[str]) -> Optional[Dict[str, Any]]:
        """Выполняется в отдельном процессе, изолированно от основного event loop"""
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
    # На Linux/Mac используем нативную асинхронную версию
    logger.info("[GoogleAI-Adaptive] Linux/Mac detected - using native async implementation")
    
    import google.generativeai as genai
    
    # Конфигурируем API при загрузке модуля (для Linux/Mac)
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        logger.info("[GoogleAI-Adaptive] Configured with API key (async mode)")


class GoogleAIService:
    """Адаптивный сервис Google AI"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.api_key = os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")
            
        logger.info(f"[GoogleAI-Adaptive] Initializing ({'isolated' if IS_WINDOWS else 'async'} mode)")
        
        if IS_WINDOWS:
            # Для Windows создаем процессный пул
            ctx = mp.get_context('spawn')
            self.executor = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
            logger.info("[GoogleAI-Adaptive] Process pool created for Windows")
        else:
            # Для Linux/Mac используем глобальный genai или импортируем его
            try:
                # Пробуем использовать глобальный genai
                self.genai = genai
            except NameError:
                # Если не найден, импортируем
                import google.generativeai as genai_local
                genai_local.configure(api_key=self.api_key)
                self.genai = genai_local
            logger.info("[GoogleAI-Adaptive] Using native async for Linux/Mac")
    
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
            logger.info(f"[GoogleAI-Adaptive] Categorizing: {text[:30]} ({'isolated' if IS_WINDOWS else 'async'} mode)")
            
            if IS_WINDOWS:
                # Windows: используем изолированный процесс
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
                    logger.error(f"[GoogleAI-Adaptive] Process error: {result['error']}")
                    return None
                    
            else:
                # Linux/Mac: используем нативный async
                prompt = f"""
                Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
                {', '.join(categories)}
                
                Return ONLY valid JSON:
                {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
                """
                
                model = self.genai.GenerativeModel('gemini-2.5-flash')
                
                # Настройки генерации
                generation_config = self.genai.GenerationConfig(
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
                
                # Асинхронный вызов
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                if not response or not response.text:
                    return None
                    
                # Парсим ответ
                text_response = response.text.strip()
                if text_response.startswith('```'):
                    text_response = text_response[text_response.find('\n')+1:text_response.rfind('```')]
                
                result = json.loads(text_response)
                
                if result.get('category') not in categories:
                    logger.warning(f"[GoogleAI-Adaptive] Invalid category: {result.get('category')}")
                    return None
            
            if result:
                # Безопасное логирование для Windows
                category_log = result.get('category', '')
                if IS_WINDOWS:
                    category_log = ''.join(c for c in category_log if ord(c) < 128).strip() or 'category_with_emoji'
                logger.info(f"[GoogleAI-Adaptive] Success: {category_log}")
                
            return result
                
        except Exception as e:
            logger.error(f"[GoogleAI-Adaptive] Error: {type(e).__name__}: {str(e)[:200]}")
            return None
    
    async def chat(self, message: str, context: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
        """Чат с AI используя Google Gemini"""
        if IS_WINDOWS:
            # На Windows используем процессный пул
            try:
                from .ai_selector import get_provider_settings
                settings = get_provider_settings('google')
                api_key = settings['api_key']
                
                # Подготавливаем контекст для промпта
                context_str = ""
                if context:
                    for msg in context[-10:]:  # Последние 10 сообщений
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        context_str += f"{role}: {content}\n"
                
                # Информация о пользователе и его расходах
                user_info = ""
                if user_context:
                    if user_context.get('total_today'):
                        user_info += f"Пользователь потратил сегодня: {user_context['total_today']} ₽\n"
                    if user_context.get('expenses_data'):
                        user_info += f"Данные о расходах: {json.dumps(user_context['expenses_data'], ensure_ascii=False)}\n"
                
                # Запускаем в процессном пуле
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    _process_chat_wrapper,
                    api_key,
                    message,
                    context_str,
                    user_info
                )
                return result
                
            except Exception as e:
                logger.error(f"[GoogleAI-Adaptive] Chat error: {e}")
                raise
        else:
            # На Unix-системах 
            # Проверяем, если это запрос на показ трат, используем простой подход
            message_lower = message.lower()
            if any(phrase in message_lower for phrase in [
                'покажи все траты', 'показать все траты', 'все траты за', 
                'траты в августе', 'траты за август', 'список трат'
            ]):
                logger.info(f"[GoogleAI-Adaptive] Linux branch - detected expense listing request, using direct approach")
                
                # Используем прямой подход как на Windows
                context_str = ""
                if context:
                    for msg in context[-10:]:
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        context_str += f"{role}: {content}\n"
                
                user_info = ""
                if user_context:
                    if user_context.get('total_today'):
                        user_info += f"Пользователь потратил сегодня: {user_context['total_today']} ₽\n"
                    if user_context.get('expenses_data'):
                        user_info += f"Данные о расходах: {json.dumps(user_context['expenses_data'], ensure_ascii=False)}\n"
                
                prompt = f"""Ты - помощник по учету расходов. Отвечай на русском языке.
                
{user_info}
Контекст разговора:
{context_str}

Вопрос пользователя: {message}

Дай полезный и точный ответ на вопрос пользователя. Если спрашивают о тратах за конкретный месяц, покажи все траты из данных за этот месяц с датами и суммами."""
                
                model = self.genai.GenerativeModel('gemini-2.5-flash')
                generation_config = self.genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=7500,
                    top_p=0.95
                )
                
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config
                )
                
                if response and response.text:
                    return response.text.strip()
                else:
                    return "Не удалось получить ответ от AI"
            else:
                # Для остальных запросов используем function calling
                logger.info(f"[GoogleAI-Adaptive] Linux branch - redirecting to chat_with_functions")
                logger.info(f"[GoogleAI-Adaptive] user_context: {user_context}")
                
                try:
                    from .google_ai_service import GoogleAIService as FunctionService
                    logger.info("[GoogleAI-Adaptive] FunctionService imported successfully")
                    
                    func_service = FunctionService()
                    logger.info("[GoogleAI-Adaptive] FunctionService instance created")
                    
                    # Извлекаем user_id из user_context
                    user_id = user_context.get('user_id') if user_context else None
                    logger.info(f"[GoogleAI-Adaptive] Calling chat_with_functions with user_id={user_id}")
                    
                    result = await func_service.chat_with_functions(message, context, user_context, user_id)
                    logger.info(f"[GoogleAI-Adaptive] Got result: {result[:100] if result else 'None'}...")
                    
                    return result
                except Exception as e:
                    logger.error(f"[GoogleAI-Adaptive] Error in Linux branch: {e}", exc_info=True)
                    raise
    
    def get_expense_categorization_prompt(self, text, amount, currency, categories, user_context):
        """Для совместимости с AIBaseService"""
        return f"Categorize expense: {text}"
    
    def get_chat_prompt(self, message, context, user_context):
        """Для совместимости с AIBaseService"""
        return message
    
    def __del__(self):
        """Очистка ресурсов"""
        if IS_WINDOWS and hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)