"""
Google AI Service - адаптивная версия
Использует асинхронную версию на Linux/Mac и изолированную на Windows
"""
import logging
import json
import asyncio
import os
import platform
import threading
import time
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from django.conf import settings
from .key_rotation_mixin import GoogleKeyRotationMixin
from .ai_base_service import AIBaseService

load_dotenv()

logger = logging.getLogger(__name__)

# Создаем пул ключей Google AI из настроек
GOOGLE_API_KEYS = []
if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
    GOOGLE_API_KEYS = settings.GOOGLE_API_KEYS
    logger.info(f"[GoogleAI-Adaptive] Initialized {len(GOOGLE_API_KEYS)} API keys for rotation")
else:
    logger.warning("[GoogleAI-Adaptive] No GOOGLE_API_KEYS found in settings for rotation")

# Определяем ОС
IS_WINDOWS = platform.system() == 'Windows'

def _process_chat_wrapper(api_key: str, message: str, context_str: str, user_info: str) -> str:
    """Функция для выполнения чата в отдельном процессе"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Проверяем, это вопрос о доходах или расходах
        income_keywords = ['доход', 'заработ', 'получ', 'зарплат', 'прибыл']
        expense_keywords = ['трат', 'потрат', 'расход', 'купил', 'покуп']
        
        is_income_query = any(keyword in message.lower() for keyword in income_keywords)
        is_expense_query = any(keyword in message.lower() for keyword in expense_keywords)
        
        # Специальные слова для аналитических запросов
        analysis_keywords = ['самый большой', 'максимальн', 'больше всего', 'меньше всего', 
                           'средн', 'динамик', 'тренд', 'статистик', 'сколько']
        is_analysis_query = any(keyword in message.lower() for keyword in analysis_keywords)
        
        if is_analysis_query and (is_income_query or is_expense_query):
            # Это аналитический запрос - объясняем как получить данные
            prompt = f"""Ты - помощник по учету расходов и доходов. Отвечай на русском языке.

Пользователь задает аналитический вопрос о {'доходах' if is_income_query else 'расходах'}.

Для получения такой аналитики используй специальные команды:

{'ДЛЯ АНАЛИЗА ДОХОДОВ:' if is_income_query else 'ДЛЯ АНАЛИЗА РАСХОДОВ:'}
{'''- "покажи доходы" - показать последние доходы
- "доходы за месяц" - доходы за текущий месяц  
- "доходы за неделю" - доходы за последнюю неделю
- "финансовая сводка" - полная сводка доходов и расходов''' if is_income_query else 
'''- "покажи траты" - показать последние траты
- "траты за месяц" - траты за текущий месяц
- "траты за неделю" - траты за последнюю неделю  
- "финансовая сводка" - полная сводка доходов и расходов'''}

К сожалению, я не могу напрямую выполнить аналитические запросы типа "самый большой доход" или "максимальная трата".
Но ты можешь использовать команды выше, чтобы посмотреть свои операции и найти нужную информацию.

Вопрос пользователя: {message}

Дай дружелюбный ответ, объяснив какую команду использовать."""
        else:
            # Обычный запрос
            prompt = f"""Ты - помощник по учету расходов и доходов. Отвечай на русском языке.

ВАЖНО: НИКОГДА не говори "у меня есть только данные о расходах" - это НЕПРАВДА! 
Ты работаешь с ДОХОДАМИ и РАСХОДАМИ.

Если пользователь спрашивает аналитику (самый большой, максимальный, средний и т.д.), 
объясни что нужно использовать специальные команды:
- Для доходов: "покажи доходы", "доходы за месяц"
- Для расходов: "покажи траты", "траты за месяц"
- Для полной сводки: "финансовая сводка"
        
{user_info}
Контекст разговора:
{context_str}

Вопрос пользователя: {message}

Дай полезный и точный ответ на вопрос пользователя."""
        
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Safety settings
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        response = model.generate_content(prompt, safety_settings=safety_settings)

        # Безопасная проверка response.text
        try:
            if response and response.parts and response.text:
                return response.text.strip()
        except ValueError as e:
            if "valid Part" in str(e):
                return "Извините, не могу обработать этот запрос."
            raise

        return "Не удалось получить ответ от AI"
    except Exception as e:
        return f"Ошибка AI: {str(e)}"

if IS_WINDOWS:
    # На Windows используем изолированную версию
    logger.info("[GoogleAI-Adaptive] Windows detected - using isolated process implementation")
    
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing as mp
    
    # Функция для выполнения в отдельном процессе (только для Windows)
    def _process_categorization(api_key: str, text: str, amount: float, currency: str, categories: List[str], prompt: str = None) -> Optional[Dict[str, Any]]:
        """Выполняется в отдельном процессе, изолированно от основного event loop"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            # Используем переданный промпт или fallback к простому
            if not prompt:
                prompt = f"""
                Categorize the expense "{text}" (amount: {amount} {currency}) into one of these categories:
                {', '.join(categories)}

                Return ONLY valid JSON:
                {{"category": "selected_category", "confidence": 0.8, "reasoning": "brief explanation"}}
                """

            model = genai.GenerativeModel('gemini-2.5-flash')

            # Safety settings
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]

            response = model.generate_content(prompt, safety_settings=safety_settings)

            # Безопасная проверка response.text с детальной обработкой safety блокировки
            try:
                if not response or not response.parts:
                    # Собираем информацию о блокировке
                    blocked_info = {'safety_blocked': True, 'blocked_categories': []}

                    if hasattr(response, 'candidates') and response.candidates:
                        for candidate in response.candidates:
                            if hasattr(candidate, 'finish_reason'):
                                blocked_info['finish_reason'] = str(candidate.finish_reason)

                            if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                                for rating in candidate.safety_ratings:
                                    if rating.probability.name != 'NEGLIGIBLE':
                                        blocked_info['blocked_categories'].append(
                                            f"{rating.category.name}={rating.probability.name}"
                                        )

                    return blocked_info

                text_response = response.text.strip()
            except ValueError as e:
                if "valid Part" in str(e):
                    return {
                        'safety_blocked': True,
                        'error': str(e),
                        'blocked_categories': []
                    }
                raise

            if text_response.startswith('```'):
                text_response = text_response[text_response.find('\n')+1:text_response.rfind('```')]

            result = json.loads(text_response)

            # Возвращаем сырой результат - валидация категории будет в parser
            # (централизованный подход как у доходов через find_best_matching_expense_category)
            if result and 'category' in result:
                return {
                    'category': result.get('category'),  # Сырая категория от AI
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


class GoogleAIService(AIBaseService, GoogleKeyRotationMixin):
    """Адаптивный сервис Google AI с единым промптом из AIBaseService"""
    
    def __init__(self):
        """Инициализация сервиса"""
        super().__init__()  # Инициализируем AIBaseService
        api_keys = self.get_api_keys()
        if not api_keys:
            raise ValueError("GOOGLE_API_KEYS not found in settings")
        logger.info(f"[GoogleAI-Adaptive] Initializing ({'isolated' if IS_WINDOWS else 'async'} mode) with {len(api_keys)} keys")
        
        if IS_WINDOWS:
            # Для Windows создаем процессный пул
            ctx = mp.get_context('spawn')
            self.executor = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
            logger.info("[GoogleAI-Adaptive] Process pool created for Windows")
        else:
            # Для Linux/Mac используем глобальный genai
            self.genai = genai
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
            logger.info(f"[GoogleAI-Adaptive] Categorizing: {text[:100]} ({'isolated' if IS_WINDOWS else 'async'} mode)")
            
            if IS_WINDOWS:
                # Windows: используем изолированный процесс
                key_result = self.get_next_key()
                if not key_result:
                    logger.error("[GoogleAI-Adaptive] No API keys available")
                    return None
                api_key, key_index = key_result
                key_name = self.get_key_name(key_index)

                # Формируем промпт из базового класса (единый для всех AI)
                prompt = self.get_expense_categorization_prompt(
                    text=text,
                    amount=amount,
                    currency=currency,
                    categories=categories,
                    user_context=user_context
                )

                loop = asyncio.get_event_loop()

                # Засекаем время перед вызовом
                start_time = time.time()

                result = await loop.run_in_executor(
                    self.executor,
                    _process_categorization,
                    api_key,
                    text,
                    amount,
                    currency,
                    categories,
                    prompt  # Передаем готовый промпт
                )
                
                # Вычисляем время ответа
                response_time = time.time() - start_time

                # Проверяем на safety блокировку
                safety_blocked = result and result.get('safety_blocked', False)

                if safety_blocked:
                    logger.warning(f"[GoogleAI-Adaptive] Content '{text[:30]}' blocked by safety filters on Windows")
                    if result.get('blocked_categories'):
                        logger.warning(f"[GoogleAI-Adaptive] Blocked by: {', '.join(result['blocked_categories'])}")
                    if result.get('finish_reason'):
                        logger.warning(f"[GoogleAI-Adaptive] Finish reason: {result['finish_reason']}")

                # Определяем тип ошибки и успешность
                error_type = None
                error_message = None
                success = result is not None and 'error' not in result and not safety_blocked

                if safety_blocked:
                    error_type = 'safety_blocked'
                    error_message = 'Content blocked by safety filters'
                    if result.get('blocked_categories'):
                        error_message += f": {', '.join(result['blocked_categories'])}"
                elif result and 'error' in result:
                    error_type = 'process_error'
                    error_message = result.get('error')

                # Логируем метрики в БД
                try:
                    from expenses.models import AIServiceMetrics
                    await asyncio.to_thread(
                        AIServiceMetrics.objects.create,
                        service='google',
                        operation_type='categorize_expense',
                        response_time=response_time,
                        success=success,
                        model_used='gemini-2.5-flash',
                        characters_processed=len(text),
                        user_id=user_context.get('user_id') if user_context else None,
                        error_type=error_type[:100] if error_type else None,
                        error_message=error_message[:500] if error_message else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to log AI metrics: {e}")

                logger.info(f"Google AI (Windows) categorization took {response_time:.2f}s")

                # Обрабатываем различные типы ошибок
                if safety_blocked:
                    logger.warning(f"[GoogleAI-Adaptive] Safety block detected, will fallback to OpenAI")
                    return None

                if result and 'error' in result:
                    logger.error(f"[GoogleAI-Adaptive] Process error: {result['error']}")
                    # Помечаем ключ как failed только при реальных ошибках, не при safety блокировке
                    self.mark_key_failure(key_index, Exception(result['error']))
                    return None
                    
            else:
                # Linux/Mac: используем нативный async
                # Формируем промпт из базового класса (единый для всех AI)
                prompt = self.get_expense_categorization_prompt(
                    text=text,
                    amount=amount,
                    currency=currency,
                    categories=categories,
                    user_context=user_context
                )
                
                # Получаем следующий ключ для ротации
                key_result = self.get_next_key()
                if not key_result:
                    logger.error("[GoogleAI-Adaptive] No API keys available")
                    return None
                api_key, key_index = key_result
                key_name = self.get_key_name(key_index)
                
                # Конфигурируем с новым ключом
                self.genai.configure(api_key=api_key)
                
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
                
                # Засекаем время перед вызовом API
                start_time = time.time()
                
                # Асинхронный вызов
                response = await model.generate_content_async(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                # Вычисляем время ответа
                response_time = time.time() - start_time

                # Проверяем блокировку по safety_ratings
                response_text = None
                safety_blocked = False

                try:
                    # Проверяем наличие parts перед обращением к response.text
                    if not response or not response.parts:
                        safety_blocked = True
                        logger.warning("[GoogleAI-Adaptive] Response has no parts - likely blocked by safety filters")

                        # Логируем детали блокировки
                        if hasattr(response, 'candidates') and response.candidates:
                            for i, candidate in enumerate(response.candidates):
                                if hasattr(candidate, 'finish_reason'):
                                    logger.warning(f"[GoogleAI-Adaptive] Candidate {i} finish_reason: {candidate.finish_reason}")

                                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                                    blocked_categories = []
                                    for rating in candidate.safety_ratings:
                                        if rating.probability.name != 'NEGLIGIBLE':
                                            blocked_categories.append(f"{rating.category.name}={rating.probability.name}")

                                    if blocked_categories:
                                        logger.warning(f"[GoogleAI-Adaptive] Blocked by: {', '.join(blocked_categories)}")
                    else:
                        response_text = response.text.strip()

                except ValueError as e:
                    if "valid Part" in str(e):
                        safety_blocked = True
                        logger.warning(f"[GoogleAI-Adaptive] Response blocked by safety filters: {e}")
                    else:
                        logger.error(f"[GoogleAI-Adaptive] ValueError getting response text: {e}")
                except Exception as e:
                    logger.error(f"[GoogleAI-Adaptive] Unexpected error getting response text: {e}")

                # Логируем метрики в БД
                try:
                    from expenses.models import AIServiceMetrics
                    await asyncio.to_thread(
                        AIServiceMetrics.objects.create,
                        service='google',
                        operation_type='categorize_expense',
                        response_time=response_time,
                        success=response_text is not None,
                        model_used='gemini-2.5-flash',
                        characters_processed=len(text),
                        user_id=user_context.get('user_id') if user_context else None,
                        error_type='safety_blocked' if safety_blocked else None,
                        error_message='Content blocked by safety filters' if safety_blocked else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to log AI metrics: {e}")

                logger.info(f"Google AI (async) categorization took {response_time:.2f}s")

                if not response_text:
                    # Помечаем ключ как требующий fallback при safety блокировке
                    if safety_blocked:
                        logger.warning(f"[GoogleAI-Adaptive] Content '{text[:30]}' blocked by safety filters, will fallback to OpenAI")
                    return None

                # Парсим ответ
                text_response = response_text
                if text_response.startswith('```'):
                    text_response = text_response[text_response.find('\n')+1:text_response.rfind('```')]
                
                result = json.loads(text_response)

                # Возвращаем сырой результат - валидация категории будет в parser
                # (централизованный подход как у доходов через find_best_matching_expense_category)
                # Помечаем ключ как успешный
                self.mark_key_success(key_index)
            
            if result:
                # Безопасное логирование для Windows
                category_log = result.get('category', '')
                if IS_WINDOWS:
                    category_log = ''.join(c for c in category_log if ord(c) < 128).strip() or 'category_with_emoji'
                logger.info(f"[GoogleAI-Adaptive] Success: {category_log}")
                # Помечаем ключ как рабочий
                self.mark_key_success(key_index)
                
            return result
                
        except Exception as e:
            # Логируем неудачную попытку в метрики
            try:
                from expenses.models import AIServiceMetrics
                await asyncio.to_thread(
                    AIServiceMetrics.objects.create,
                    service='google',
                    operation_type='categorize_expense',
                    response_time=0,
                    success=False,
                    error_type=type(e).__name__[:100],
                    error_message=str(e)[:500],
                    user_id=user_context.get('user_id') if user_context else None
                )
            except Exception as log_error:
                logger.warning(f"Failed to log AI error metrics: {log_error}")
            
            # Помечаем ключ как нерабочий если он был получен
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                logger.error(f"[GoogleAI-Adaptive] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
            else:
                logger.error(f"[GoogleAI-Adaptive] Error: {type(e).__name__}: {str(e)[:200]}")
            return None
    
    async def chat(self, message: str, context: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
        """Чат с AI используя Google Gemini"""
        # ВСЕГДА используем основной сервис с функциями если есть user_id
        if user_context and 'user_id' in user_context:
            try:
                from .google_ai_service import GoogleAIService as FunctionService
                func_service = FunctionService()
                user_id = user_context.get('user_id')
                
                # Используем chat который сам определит нужны ли функции
                result = await func_service.chat(message, context, user_context)
                return result
            except Exception as e:
                logger.error(f"[GoogleAI-Adaptive] Error using function service: {e}")
                # Fallback на простой чат
                
        if IS_WINDOWS:
            # На Windows используем процессный пул
            try:
                # Получаем следующий ключ для ротации
                key_result = self.get_next_key()
                if not key_result:
                    logger.error("[GoogleAI-Adaptive] No API keys available")
                    return "Извините, сервис временно недоступен."
                api_key, key_index = key_result
                key_name = self.get_key_name(key_index)
                
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
                
                # Засекаем время перед вызовом
                start_time = time.time()
                
                result = await loop.run_in_executor(
                    self.executor,
                    _process_chat_wrapper,
                    api_key,
                    message,
                    context_str,
                    user_info
                )
                # Если модель вернула FUNCTION_CALL: ... как текст — выполним его здесь
                if isinstance(result, str) and result.strip().startswith('FUNCTION_CALL:'):
                    try:
                        call = result.replace('FUNCTION_CALL:', '').strip()
                        import re
                        m = re.match(r'(\w+)\((.*)\)', call, flags=re.DOTALL)
                        if m:
                            func_name = m.group(1)
                            params: Dict[str, Any] = {}
                            if func_name == 'analytics_query':
                                # Robust spec_json extraction (handles commas inside JSON)
                                mjson = re.search(r"spec_json\s*=\s*'(.*)'\s*\)\s*$", call, flags=re.DOTALL)
                                if not mjson:
                                    mjson = re.search(r' spec_json\s*=\s*"(.*)"\s*\)\s*$', call, flags=re.DOTALL)
                                if mjson:
                                    params['spec_json'] = mjson.group(1)
                            else:
                                params_str = m.group(2)
                                if params_str:
                                    for p in params_str.split(','):
                                        if '=' in p:
                                            k, v = p.split('=', 1)
                                            k = k.strip()
                                            v = v.strip().strip('\"\'')
                                            if v.isdigit():
                                                v = int(v)
                                            elif v.replace('.', '').isdigit():
                                                v = float(v)
                                            params[k] = v
                            # Нормализация и исполнение
                            from .function_call_utils import normalize_function_call
                            func_name, params = normalize_function_call(message, func_name, params, user_context.get('user_id') if user_context else None)
                            import inspect
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
                                    return await asyncio.to_thread(lambda: method(**params))
                            fn_result = await call_function()
                            from bot.services.response_formatter import format_function_result
                            # Add user_id to result for language detection
                            if user_context and 'user_id' in user_context:
                                fn_result['user_id'] = user_context['user_id']
                            result = format_function_result(func_name, fn_result)
                    except Exception as _e:
                        logger.error(f"[GoogleAI-Adaptive] Failed to execute FUNCTION_CALL in Windows path: {_e}")
                
                # Вычисляем время ответа
                response_time = time.time() - start_time
                
                # Логируем метрики в БД
                try:
                    from expenses.models import AIServiceMetrics
                    await asyncio.to_thread(
                        AIServiceMetrics.objects.create,
                        service='google',
                        operation_type='chat',
                        response_time=response_time,
                        success=True,
                        model_used='gemini-2.5-flash',
                        characters_processed=len(message),
                        user_id=user_context.get('user_id') if user_context else None
                    )
                except Exception as e:
                    logger.warning(f"Failed to log AI metrics: {e}")
                
                logger.info(f"Google AI (Windows) chat took {response_time:.2f}s")
                
                return result
                
            except Exception as e:
                logger.error(f"[GoogleAI-Adaptive] Chat error: {e}")
                raise
        else:
            # На Unix-системах используем версию с function calling
            logger.info(f"[GoogleAI-Adaptive] Linux branch - redirecting to chat_with_functions")
            logger.info(f"[GoogleAI-Adaptive] user_context: {user_context}")
            
            try:
                from .google_ai_service import GoogleAIService as FunctionService
                logger.info("[GoogleAI-Adaptive] FunctionService imported successfully")
                
                # Перед созданием сервиса конфигурируем API с текущим ключом
                key_result = self.get_next_key()
                if not key_result:
                    logger.error("[GoogleAI-Adaptive] No API keys available")
                    return "Извините, сервис временно недоступен."
                api_key, key_index = key_result
                key_name = self.get_key_name(key_index)
                
                self.genai.configure(api_key=api_key)
                
                func_service = FunctionService()
                logger.info("[GoogleAI-Adaptive] FunctionService instance created")
                
                # Извлекаем user_id из user_context
                user_id = user_context.get('user_id') if user_context else None
                logger.info(f"[GoogleAI-Adaptive] Calling chat_with_functions with user_id={user_id}")
                
                # Засекаем время перед вызовом
                start_time = time.time()
                
                result = await func_service.chat_with_functions(message, context, user_context, user_id)
                
                # Вычисляем время ответа
                response_time = time.time() - start_time
                
                # Логируем метрики в БД
                try:
                    from expenses.models import AIServiceMetrics
                    await asyncio.to_thread(
                        AIServiceMetrics.objects.create,
                        service='google',
                        operation_type='chat_with_functions',
                        response_time=response_time,
                        success=True,
                        model_used='gemini-2.5-flash',
                        characters_processed=len(message),
                        user_id=user_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to log AI metrics: {e}")
                
                logger.info(f"Google AI (Linux) chat_with_functions took {response_time:.2f}s")
                logger.info(f"[GoogleAI-Adaptive] Got result: {result[:100] if result else 'None'}...")
                
                return result
            except Exception as e:
                logger.error(f"[GoogleAI-Adaptive] Error in Linux branch: {e}", exc_info=True)
                raise
    
    # get_expense_categorization_prompt теперь наследуется из AIBaseService

    def get_chat_prompt(self, message, context, user_context):
        """Для совместимости с AIBaseService"""
        return message
    
    def __del__(self):
        """Очистка ресурсов"""
        if IS_WINDOWS and hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
