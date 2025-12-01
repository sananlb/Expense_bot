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
from .key_rotation_mixin import GoogleKeyRotationMixin
from django.conf import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Проверяем наличие ключей при инициализации
if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
    logger.info(f"[GoogleAI] Found {len(settings.GOOGLE_API_KEYS)} API keys for rotation")
else:
    logger.warning("[GoogleAI] No GOOGLE_API_KEYS found in settings")


def _get_error_message(error_key: str, user_context: Optional[Dict[str, Any]] = None) -> str:
    """Get error message in user's language"""
    user_lang = user_context.get('language', 'ru') if user_context else 'ru'

    ERROR_MESSAGES = {
        'service_unavailable': {
            'ru': 'Извините, сервис временно недоступен.',
            'en': 'Sorry, the service is temporarily unavailable.'
        },
        'no_response': {
            'ru': 'Извините, не удалось получить ответ от AI.',
            'en': 'Sorry, failed to get response from AI.'
        },
        'processing_error': {
            'ru': 'Извините, произошла ошибка при обработке вашего сообщения.',
            'en': 'Sorry, an error occurred while processing your message.'
        },
        'general_error': {
            'ru': 'Извините, произошла ошибка.',
            'en': 'Sorry, an error occurred.'
        },
        'timeout': {
            'ru': 'Извините, сервис временно недоступен. Попробуйте еще раз.',
            'en': 'Sorry, service temporarily unavailable. Please try again.'
        }
    }

    messages = ERROR_MESSAGES.get(error_key, ERROR_MESSAGES['general_error'])
    return messages.get(user_lang, messages['ru'])


class GoogleAIService(AIBaseService, GoogleKeyRotationMixin):
    """Сервис для работы с Google AI (Gemini) - упрощенная стабильная версия"""
    
    def __init__(self):
        """Инициализация сервиса"""
        api_keys = self.get_api_keys()
        if not api_keys:
            raise ValueError("GOOGLE_API_KEYS not found in settings")
        
        logger.info(f"[GoogleAI] Service initialized with {len(api_keys)} keys for rotation")
    
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
            
            model_name = get_model('categorization', 'google')
            
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return None
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for categorization")
            
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
            
            # Таймаут для ускорения категоризации: при превышении – fallback на OpenAI категоризацию
            import asyncio as _asyncio
            timeout_seconds = int(os.getenv('GOOGLE_CATEGORIZATION_TIMEOUT', os.getenv('GOOGLE_CHAT_TIMEOUT', '10')))
            try:
                response = await _asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    ),
                    timeout=timeout_seconds
                )
            except _asyncio.TimeoutError:
                logger.warning(f"[GoogleAI] categorize_expense timeout after {timeout_seconds}s, falling back to OpenAI categorization")
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    return await openai_service.categorize_expense(text, amount, currency, categories, user_context)
                except Exception as e:
                    logger.error(f"[GoogleAI] OpenAI categorization fallback failed after timeout: {e}")
                    return None
            
            if response and response.parts:
                text_response = response.text.strip()
                
                # Парсим ответ
                import json
                try:
                    # Пробуем распарсить как JSON
                    if text_response.startswith('{'):
                        result = json.loads(text_response)
                        # Помечаем ключ как рабочий после успешного ответа
                        self.mark_key_success(key_index)
                        return {
                            'category': result.get('category', categories[0] if categories else 'Прочие расходы'),
                            'confidence': float(result.get('confidence', 0.5))
                        }
                except:
                    pass
                
                # Если не JSON, ищем категорию в тексте
                text_lower = text_response.lower()
                for category in categories:
                    if category.lower() in text_lower:
                        # Помечаем ключ как рабочий после успешного ответа
                        self.mark_key_success(key_index)
                        return {
                            'category': category,
                            'confidence': 0.7
                        }
                
                # Если ничего не нашли, возвращаем первую категорию
                result = {
                    'category': categories[0] if categories else 'Прочие расходы',
                    'confidence': 0.3
                }
                # Помечаем ключ как рабочий
                self.mark_key_success(key_index)
                return result
            
            # Помечаем ключ как рабочий если дошли до сюда без исключений
            self.mark_key_success(key_index)
            return None
            
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
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
            # Добавляем контекст предыдущих сообщений для связанных вопросов
            enhanced_message = message
            if context and len(context) > 0:
                # Проверяем, является ли вопрос уточняющим
                clarifying_keywords = ['дата', 'когда', 'день', 'какой день', 'в какой', 'число']
                if any(keyword in message.lower() for keyword in clarifying_keywords):
                    # Добавляем контекст последних сообщений
                    recent_context = context[-2:] if len(context) >= 2 else context
                    context_str = ' '.join([f"{msg.get('role', '')}: {msg.get('content', '')}" for msg in recent_context])
                    enhanced_message = f"Контекст диалога: {context_str}\nТекущий вопрос: {message}"
            
            # Первый вызов AI для определения нужной функции
            response = await self._call_ai_with_functions(enhanced_message, context, user_context, user_id)
            
            logger.info(f"[GoogleAI] chat_with_functions - AI response type: {type(response)}, length: {len(response) if response else 0}")
            logger.info(f"[GoogleAI] chat_with_functions - AI response preview: {response[:200] if response else 'None'}")
            
            # Проверяем, нужно ли вызвать функцию
            if response and response.startswith("FUNCTION_CALL:"):
                # Извлекаем вызов функции
                function_call = response.replace("FUNCTION_CALL:", "").strip()
                logger.info(f"[GoogleAI] Function requested: {function_call}")
                
                # Выполняем функцию
                from .expense_functions import ExpenseFunctions
                functions = ExpenseFunctions()
                
                # Парсим вызов функции
                import re
                match = re.match(r'(\w+)\((.*)\)', function_call, flags=re.DOTALL)
                if match:
                    func_name = match.group(1)
                    params_str = match.group(2)
                    
                    # Парсим параметры
                    params = {'user_id': user_id}

                    # Сначала парсим обычные параметры для всех функций
                    if params_str and func_name != 'analytics_query':
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

                    # Специальная обработка analytics_query(spec_json=...)
                    if func_name == 'analytics_query':
                        spec = None
                        mjson = re.search(r"spec_json\s*=\s*'(.*)'\s*\)\s*$", function_call, flags=re.DOTALL)
                        if not mjson:
                            mjson = re.search(r' spec_json\s*=\s*"(.*)"\s*\)\s*$', function_call, flags=re.DOTALL)
                        if mjson:
                            spec = mjson.group(1)
                            params['spec_json'] = spec
                            from .function_call_utils import normalize_function_call
                            func_name, params = normalize_function_call(message, func_name, params, user_id)
                            # Вызываем функцию сразу
                            try:
                                logger.info(f"[GoogleAI] Calling function {func_name} with params: spec_json({len(spec)} chars)")
                                def run_sync_function():
                                    import django
                                    django.setup()
                                    from bot.services.expense_functions import ExpenseFunctions
                                    funcs = ExpenseFunctions()
                                    method = getattr(funcs, func_name)
                                    if hasattr(method, '__wrapped__'):
                                        method = method.__wrapped__
                                    return method(**params)
                                import asyncio as _a
                                result = await _a.to_thread(run_sync_function)
                            except Exception as e:
                                logger.error(f"[GoogleAI] Error calling function {func_name}: {e}", exc_info=True)
                                result = {'success': False, 'message': str(e)}
                            if result.get('success'):
                                try:
                                    from bot.services.response_formatter import format_function_result
                                    # Add user_id to result for language detection
                                    if user_context and 'user_id' in user_context:
                                        result['user_id'] = user_context['user_id']
                                    return format_function_result(func_name, result)
                                except Exception as _fmt_err:
                                    logger.error(f"[GoogleAI] Error formatting result for {func_name}: {_fmt_err}")
                                    import json as _json
                                    try:
                                        return _json.dumps(result, ensure_ascii=False)[:1000]
                                    except Exception:
                                        return str(result)[:1000]
                            else:
                                error_msg = result.get('message', 'Failed to get data' if user_context and user_context.get('language') == 'en' else 'Не удалось получить данные')
                                error_prefix = "Error:" if user_context and user_context.get('language') == 'en' else "Ошибка:"
                                return f"{error_prefix} {error_msg}"

                    from .function_call_utils import normalize_function_call
                    func_name, params = normalize_function_call(message, func_name, params, user_id)

                    # Вызываем функцию
                    if hasattr(functions, func_name):
                        try:
                            logger.info(f"[GoogleAI] Calling function {func_name} with params: {params}")
                            
                            import inspect
                            import asyncio
                            
                            async def call_function():
                                import django
                                django.setup()
                                from bot.services.expense_functions import ExpenseFunctions
                                funcs = ExpenseFunctions()
                                method = getattr(funcs, func_name)
                                if hasattr(method, '__wrapped__'):
                                    method = method.__wrapped__
                                if inspect.iscoroutinefunction(method):
                                    return await method(**params)
                                else:
                                    def run_sync():
                                        return method(**params)
                                    return await asyncio.to_thread(run_sync)
                            
                            result = await call_function()
                            
                            try:
                                import json as _json
                                _prev = _json.dumps(result, ensure_ascii=True)
                            except Exception:
                                _prev = str(result).encode('ascii','ignore').decode('ascii')
                            if len(_prev) > 300:
                                _prev = _prev[:300] + '...'
                            logger.info(f"[GoogleAI] Function {func_name} returned: {_prev}")

                        except Exception as e:
                            logger.error(f"[GoogleAI] Error calling function {func_name}: {e}", exc_info=True)
                            error_prefix = "Function execution error:" if user_context and user_context.get('language') == 'en' else "Ошибка при выполнении функции:"
                            result = {
                                'success': False,
                                'message': f'{error_prefix} {str(e)}'
                            }
                        
                        if result.get('success'):
                            # Используем универсальный форматтер
                            try:
                                from bot.services.response_formatter import format_function_result
                                # Add user_id to result for language detection
                                if user_context and 'user_id' in user_context:
                                    result['user_id'] = user_context['user_id']
                                return format_function_result(func_name, result)
                            except Exception as _fmt_err:
                                logger.error(f"[GoogleAI] Error formatting result for {func_name}: {_fmt_err}")
                                import json as _json
                                try:
                                    return _json.dumps(result, ensure_ascii=False)[:1000]
                                except Exception:
                                    return str(result)[:1000]

                    elif func_name == 'get_max_expense_day':
                        # Нормализация period/month/year -> period_days
                        import calendar as _cal
                        period_days = params.get('period_days')
                        if not period_days:
                            period = str(params.get('period', '')).lower()
                            month = params.get('month')
                            year = params.get('year')
                            try:
                                if period == 'week':
                                    period_days = 7
                                elif period == 'year':
                                    period_days = 365
                                elif period == 'month':
                                    if month and year:
                                        period_days = _cal.monthrange(int(year), int(month))[1]
                                    else:
                                        period_days = 31
                            except Exception:
                                period_days = None
                        new_params = {'user_id': user_id}
                        if period_days:
                            try:
                                new_params['period_days'] = int(period_days)
                            except Exception:
                                pass
                        params = new_params
                    elif func_name == 'get_daily_totals':
                        # Обработка get_daily_totals будет через универсальный форматтер
                        pass
                    elif func_name == 'get_category_total_by_dates':
                        # Обработка get_category_total_by_dates будет через универсальный форматтер
                        pass
                    elif func_name == 'analytics_query':
                        # Обработка analytics_query будет через универсальный форматтер
                        pass
                    else:
                        logger.error(f"Function {func_name} not found")
                        return f"Извините, не могу выполнить запрос. Функция {func_name} не найдена."
            
            # Если функция не нужна, возвращаем обычный ответ
            # Помечаем ключ как рабочий перед возвратом успешного результата
            if 'key_index' in locals():
                self.mark_key_success(key_index)
            return response
            
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI Chat] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI Chat] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
                logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return _get_error_message('processing_error', user_context)
    
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
            try:
                _msg_preview = (message or '')[:100]
                _msg_preview = _msg_preview.encode('ascii','ignore').decode('ascii')
            except Exception:
                _msg_preview = ''
            logger.info(f"[GoogleAI] _call_ai_with_functions started for message: {_msg_preview}")
            
            from datetime import datetime
            today = datetime.now()
            
            from bot.services.prompt_builder import build_function_call_prompt
            # Here we receive already-enhanced message; use the parameter
            # Extract user language from user_context if available
            user_language = user_context.get('language', 'ru') if user_context else 'ru'
            prompt = build_function_call_prompt(message, context, user_language)

            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return _get_error_message('service_unavailable', user_context)
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat with functions")
            
            model_name = get_model('chat', 'google')
            # Get user language for system instruction (только русский и английский)
            user_lang = user_context.get('language', 'ru') if user_context else 'ru'
            lang_names = {'ru': 'Russian', 'en': 'English'}
            lang_name = lang_names.get(user_lang, 'Russian')

            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=f"You are a finance tracking assistant for both expenses and income. Analyze the user's question and determine if a function call is needed. **IMPORTANT: You MUST respond in {lang_name} language.**"
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=5000,  # Увеличено для обработки больших списков трат
                top_p=0.9
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            logger.info(f"[GoogleAI] Calling generate_content_async with prompt length: {len(prompt)}")
            logger.info(f"[GoogleAI] Generation config: max_output_tokens={generation_config.max_output_tokens}")
            
            # Ограничиваем время форматирования, при таймауте пробуем OpenAI
            import asyncio as _asyncio
            timeout_seconds = int(os.getenv('GOOGLE_CHAT_FORMAT_TIMEOUT', os.getenv('GOOGLE_CHAT_TIMEOUT', '15')))
            try:
                response = await _asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    ),
                    timeout=timeout_seconds
                )
            except _asyncio.TimeoutError:
                logger.warning(f"[GoogleAI] _call_ai_simple timeout after {timeout_seconds}s, falling back to OpenAI formatter")
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    # Используем OpenAI как простой чат для форматирования текста промпта
                    return await openai_service.chat(prompt, [], None)
                except Exception as e:
                    logger.error(f"[GoogleAI] OpenAI formatter fallback failed after timeout: {e}")
                    return _get_error_message('timeout', user_context)
            
            logger.info(f"[GoogleAI] generate_content_async completed")
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                
                # Логируем текст ответа
                if hasattr(response, 'text'):
                    try:
                        response_text = response.text
                        logger.info(f"[GoogleAI] Response text length: {len(response_text) if response_text else 0}")
                        logger.info(f"[GoogleAI] Response text preview: {response_text[:500] if response_text else 'No text'}")
                        
                        # Проверяем наличие FUNCTION_CALL
                        if response_text and 'FUNCTION_CALL:' in response_text:
                            logger.info(f"[GoogleAI] FUNCTION_CALL detected in response")
                        elif response_text:
                            logger.warning(f"[GoogleAI] No FUNCTION_CALL found, AI returned plain text")
                    except Exception as e:
                        logger.error(f"[GoogleAI] Error accessing response text: {e}")
                
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                # Помечаем ключ как рабочий перед возвратом успешного результата
                self.mark_key_success(key_index)
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return _get_error_message('no_response', user_context)
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error in _call_ai_with_functions with {key_name}: {e}")
                else:
                    logger.error(f"[GoogleAI] Error in _call_ai_with_functions with key {key_index}: {e}")
            else:
                logger.error(f"[GoogleAI] Error in _call_ai_with_functions: {e}")
            return _get_error_message('general_error', user_context)
    
    async def _call_ai_simple(self, prompt: str, user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Простой вызов AI для форматирования ответа
        """
        try:
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return _get_error_message('service_unavailable', user_context)
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat with functions")
            
            model_name = get_model('chat', 'google')
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="Answer in Russian with complete information. Always include dates, amounts, descriptions when available. Be natural but informative."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=5000,  # Увеличено для полных ответов с большим количеством трат
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
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                
                # Попробуем извлечь данные из промпта для форматирования локально
                try:
                    if "Данные:" in prompt and "expenses" in prompt:
                        logger.info("[GoogleAI] Attempting local fallback formatting")
                        # Извлекаем JSON из промпта
                        json_start = prompt.find("Данные:") + len("Данные:")
                        json_end = prompt.find("\n\nВАЖНО:")
                        if json_end == -1:
                            json_end = len(prompt)
                        
                        json_str = prompt[json_start:json_end].strip()
                        data = json.loads(json_str)
                        
                        if 'expenses' in data:
                            expenses_data = data['expenses']
                            total = data.get('total', 0)
                            count = data.get('count', len(expenses_data))
                            
                            if expenses_data:
                                # Используем универсальный форматтер
                                from bot.utils.expense_formatter import format_expenses_from_dict_list
                                
                                result_text = format_expenses_from_dict_list(
                                    expenses_data,
                                    title="📋 Список трат",
                                    subtitle=f"Найдено: {count} трат на сумму {total:,.0f} ₽",
                                    max_expenses=100
                                )
                                
                                logger.info(f"[GoogleAI] Fallback formatting successful, returning {len(result_text)} chars")
                                return result_text
                            else:
                                return "Траты за указанный период не найдены."
                except Exception as fallback_error:
                    logger.error(f"[GoogleAI] Fallback formatting failed: {fallback_error}")
                # Попытаемся отдать форматирование OpenAI с учётом контекста пользователя
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    return await openai_service.chat(prompt, [], user_context)
                except Exception:
                    return _get_error_message('no_response', user_context)
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error in _call_ai_simple with {key_name}: {e}")
                else:
                    logger.error(f"[GoogleAI] Error in _call_ai_simple with key {key_index}: {e}")
            else:
                logger.error(f"[GoogleAI] Error in _call_ai_simple: {e}")
            # Попытаемся отдать форматирование OpenAI с учётом контекста пользователя
            try:
                from .openai_service import OpenAIService
                openai_service = OpenAIService()
                return await openai_service.chat(prompt, [], user_context)
            except Exception:
                return _get_error_message('general_error', user_context)
    
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
            
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return _get_error_message('service_unavailable', user_context)
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat")

            # Get user language for system instruction (только русский и английский)
            user_lang = user_context.get('language', 'ru') if user_context else 'ru'
            lang_names = {'ru': 'Russian', 'en': 'English'}
            lang_name = lang_names.get(user_lang, 'Russian')

            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=f"You are an expense tracking bot. Answer naturally and concisely. **IMPORTANT: You MUST respond in {lang_name} language.**"
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=5000,  # Увеличено для полных ответов с большим количеством трат
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
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                # Помечаем ключ как рабочий перед возвратом успешного результата
                self.mark_key_success(key_index)
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return _get_error_message('no_response', user_context)
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI Chat] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI Chat] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
                logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return _get_error_message('processing_error', user_context)
