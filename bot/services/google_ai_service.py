"""
Google AI Service - основной сервис для работы с Google Gemini
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from .ai_base_service import AIBaseService
from .ai_selector import get_model

# Настройка логирования
logger = logging.getLogger(__name__)

# Загружаем API ключ
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("[GoogleAI] API key configured")
else:
    logger.error("[GoogleAI] GOOGLE_API_KEY not found in environment")


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
        Категоризация расхода с помощью Google AI
        
        Args:
            text: Текст описания расхода
            amount: Сумма расхода
            currency: Валюта
            categories: Список доступных категорий
            user_context: Дополнительный контекст пользователя
            
        Returns:
            Словарь с категорией и уверенностью или None при ошибке
        """
        try:
            prompt = self.get_expense_categorization_prompt(text, amount, currency, categories, user_context)
            
            model_name = 'gemini-2.5-flash'  # Используем фиксированную модель
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="You are an expense categorization assistant. Always respond with a valid category name from the provided list."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=1500,
                top_p=0.8
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
                text_response = response.text.strip()
                
                # Парсим ответ
                import json
                try:
                    # Пробуем распарсить как JSON
                    if text_response.startswith('{'):
                        result = json.loads(text_response)
                        return {
                            'category': result.get('category', categories[0] if categories else 'Прочее'),
                            'confidence': float(result.get('confidence', 0.5))
                        }
                except:
                    pass
                
                # Если не JSON, ищем категорию в тексте
                text_lower = text_response.lower()
                for category in categories:
                    if category.lower() in text_lower:
                        return {
                            'category': category,
                            'confidence': 0.7
                        }
                
                # Если ничего не нашли, возвращаем первую категорию
                return {
                    'category': categories[0] if categories else 'Прочее',
                    'confidence': 0.3
                }
            
            return None
            
        except Exception as e:
            logger.error(f"[GoogleAI] Error: {type(e).__name__}: {str(e)[:200]}")
            return None
    
    async def chat_with_functions(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None,
        user_id: int = None
    ) -> str:
        """
        Чат с Google AI и поддержкой функций
        """
        try:
            # Первый вызов AI для определения нужной функции
            response = await self._call_ai_with_functions(message, context, user_context, user_id)
            
            # Проверяем, нужно ли вызвать функцию
            if response and response.startswith("FUNCTION_CALL:"):
                # Извлекаем вызов функции
                function_call = response.replace("FUNCTION_CALL:", "").strip()
                logger.info(f"AI requested function: {function_call}")
                
                # Выполняем функцию
                from .expense_functions import ExpenseFunctions
                functions = ExpenseFunctions()
                
                # Парсим вызов функции
                import re
                match = re.match(r'(\w+)\((.*)\)', function_call)
                if match:
                    func_name = match.group(1)
                    params_str = match.group(2)
                    
                    # Парсим параметры
                    params = {'user_id': user_id}
                    if params_str:
                        # Простой парсинг параметров
                        for param in params_str.split(','):
                            if '=' in param:
                                key, value = param.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                                # Преобразуем типы
                                if value.isdigit():
                                    value = int(value)
                                elif value.replace('.', '').isdigit():
                                    value = float(value)
                                params[key] = value
                    
                    # Вызываем функцию
                    if hasattr(functions, func_name):
                        try:
                            logger.info(f"[GoogleAI] Calling function {func_name} with params: {params}")
                            
                            # Создаем синхронную функцию для выполнения в потоке
                            def run_sync_function():
                                import django
                                django.setup()
                                
                                # Импортируем функции после setup
                                from bot.services.expense_functions import ExpenseFunctions
                                funcs = ExpenseFunctions()
                                
                                # Получаем метод без декоратора (прямой вызов)
                                method = getattr(funcs, func_name)
                                # Если метод обернут в sync_to_async, получаем оригинальную функцию
                                if hasattr(method, '__wrapped__'):
                                    method = method.__wrapped__
                                
                                # Вызываем синхронную версию
                                return method(**params)
                            
                            # Выполняем в потоке
                            import asyncio
                            result = await asyncio.to_thread(run_sync_function)
                            logger.info(f"[GoogleAI] Function {func_name} returned: {result}")
                        except Exception as e:
                            logger.error(f"[GoogleAI] Error calling function {func_name}: {e}", exc_info=True)
                            result = {
                                'success': False,
                                'message': f'Ошибка при выполнении функции: {str(e)}'
                            }
                        
                        # Формируем промпт с результатом функции
                        if result.get('success'):
                            result_prompt = f"""Пользователь спросил: {message}

Данные для ответа: {json.dumps(result, ensure_ascii=False, indent=2)}

Сформулируй краткий и понятный ответ на русском языке, используя эти данные.
НЕ показывай техническую информацию типа success, НЕ используй условные конструкции.
Просто дай прямой ответ на вопрос пользователя."""
                        else:
                            result_prompt = f"""Пользователь спросил: {message}

Произошла ошибка: {result.get('message', 'Неизвестная ошибка')}

Вежливо объясни пользователю, что произошла ошибка."""
                        
                        # Второй вызов AI для форматирования ответа
                        final_response = await self._call_ai_simple(result_prompt)
                        return final_response
                    else:
                        logger.error(f"Function {func_name} not found")
                        return f"Извините, не могу выполнить запрос. Функция {func_name} не найдена."
            
            # Если функция не нужна, возвращаем обычный ответ
            return response
            
        except Exception as e:
            logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."
    
    async def _call_ai_with_functions(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None,
        user_id: int = None
    ) -> str:
        """
        Вызов AI с инструкциями о функциях
        """
        try:
            prompt = f"""Ты - помощник по учету расходов. У тебя есть доступ к функциям для анализа трат.

ДОСТУПНЫЕ ФУНКЦИИ:
1. get_max_expense_day() - для вопросов "В какой день я больше всего потратил?"
2. get_period_total(period='today'|'yesterday'|'week'|'month'|'year') - для "Сколько я потратил сегодня/вчера/на этой неделе?"
3. get_max_single_expense() - для "Какая моя самая большая трата?"
4. get_category_statistics() - для "На что я трачу больше всего?"
5. get_average_expenses() - для "Сколько я трачу в среднем?"
6. get_recent_expenses(limit=10) - для "Покажи последние траты"
7. search_expenses(query='текст') - для "Когда я покупал..."
8. get_weekday_statistics() - для "В какие дни недели я трачу больше?"
9. predict_month_expense() - для "Сколько я потрачу в этом месяце?"
10. check_budget_status(budget_amount=50000) - для "Уложусь ли я в бюджет?"
11. compare_periods() - для "Я стал тратить больше или меньше?"
12. get_expense_trend() - для "Покажи динамику трат"
13. get_expenses_by_amount_range(min_amount=1000) - для "Покажи траты больше 1000"
14. get_category_total(category='продукты', period='month') - для "Сколько я трачу на продукты?"

ВАЖНО: Если вопрос требует анализа данных, ответь ТОЛЬКО в формате:
FUNCTION_CALL: имя_функции(параметр1=значение1, параметр2=значение2)

Если вопрос не требует анализа данных (приветствие, общий вопрос), отвечай обычным текстом.

Вопрос пользователя: {message}"""

            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="You are an expense tracking assistant. Analyze the user's question and determine if a function call is needed."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=200,
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
            logger.error(f"[GoogleAI] Error in _call_ai_with_functions: {e}")
            return "Извините, произошла ошибка."
    
    async def _call_ai_simple(self, prompt: str) -> str:
        """
        Простой вызов AI для форматирования ответа
        """
        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="You are a helpful assistant. Format the response nicely in Russian."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1500,
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
            logger.error(f"[GoogleAI] Error in _call_ai_simple: {e}")
            return "Извините, произошла ошибка."
    
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Обычный чат с Google AI (для обратной совместимости)
        """
        try:
            # Если есть user_context с user_id, используем функции
            if user_context and 'user_id' in user_context:
                return await self.chat_with_functions(
                    message=message,
                    context=context,
                    user_context=user_context,
                    user_id=user_context['user_id']
                )
            
            # Иначе обычный чат
            prompt = self.get_chat_prompt(message, context, user_context)
            
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="You are a helpful expense tracking assistant. Respond in the same language as the user's message."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1500,
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