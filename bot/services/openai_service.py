"""
OpenAI Service для expense_bot
"""
import logging
import os
import json
import asyncio
import threading
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
import openai
from openai import OpenAI
from django.conf import settings
from .ai_base_service import AIBaseService
from .ai_selector import get_provider_settings, get_model

logger = logging.getLogger(__name__)

# Создаем пул клиентов OpenAI
OPENAI_CLIENTS = []

# Проверяем наличие OPENAI_API_KEYS в settings
if hasattr(settings, 'OPENAI_API_KEYS') and settings.OPENAI_API_KEYS:
    for api_key in settings.OPENAI_API_KEYS:
        OPENAI_CLIENTS.append(OpenAI(api_key=api_key))
    logger.info(f"Инициализировано {len(OPENAI_CLIENTS)} OpenAI клиентов")
else:
    logger.info("Не найдены OPENAI_API_KEYS в настройках, используем единичный ключ")
    OPENAI_CLIENTS = []


class OpenAIService(AIBaseService):
    """Сервис для работы с OpenAI"""
    
    _client_index = 0  # Для round-robin распределения
    _client_lock = threading.Lock()  # Для thread-safe доступа
    
    def __init__(self):
        """Инициализация сервиса"""
        super().__init__()
        self.use_rotation = False  # Добавляем атрибут
        # Если нет пула клиентов, создаем единичный клиент из Django settings/ENV
        if not OPENAI_CLIENTS:
            try:
                # Берем ключ из Django settings или переменных окружения
                api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')
            except Exception:
                api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.fallback_client = OpenAI(api_key=api_key)
            else:
                self.fallback_client = None
        else:
            self.fallback_client = None
    
    @classmethod
    def get_client(cls):
        """Thread-safe получение клиента OpenAI с round-robin ротацией"""
        if not OPENAI_CLIENTS:
            return None
        
        # Thread-safe round-robin распределение
        with cls._client_lock:
            current_index = cls._client_index
            cls._client_index = (cls._client_index + 1) % len(OPENAI_CLIENTS)
            return OPENAI_CLIENTS[current_index]
    
    def _get_client(self) -> OpenAI:
        """Получить клиент для текущего запроса"""
        client = self.get_client()
        if client:
            return client
        elif self.fallback_client:
            return self.fallback_client
        else:
            raise ValueError("No OpenAI API keys available")
        
    async def categorize_expense(
        self, 
        text: str, 
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Категоризация расхода через OpenAI
        """
        try:
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )
            
            model_name = get_model('categorization', 'openai')
            
            # Получаем клиент с ротацией ключей
            client = self._get_client()
            
            # Засекаем время перед вызовом API
            start_time = time.time()
            
            # Асинхронный вызов
            # Для новых моделей используем специальные параметры
            completion_params = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты помощник для категоризации расходов. Отвечай только валидным JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "response_format": {"type": "json_object"}
            }

            # Настройки для разных типов моделей
            is_reasoning_model = 'o1' in model_name or 'o3' in model_name
            is_gpt5 = 'gpt-5' in model_name

            if is_reasoning_model or is_gpt5:
                # Новые модели используют max_completion_tokens
                completion_params["max_completion_tokens"] = 1000

                # Только gpt-5 не поддерживает кастомный temperature
                if not is_gpt5:
                    completion_params["temperature"] = 0.1
            else:
                # Старые модели (gpt-4, gpt-3.5)
                completion_params["max_tokens"] = 1000
                completion_params["temperature"] = 0.1

            response = await asyncio.to_thread(
                client.chat.completions.create,
                **completion_params
            )
            
            # Вычисляем время ответа
            response_time = time.time() - start_time
            
            # Логируем метрики в БД
            try:
                from expenses.models import AIServiceMetrics
                await asyncio.to_thread(
                    AIServiceMetrics.objects.create,
                    service='openai',
                    operation_type='categorize_expense',
                    response_time=response_time,
                    success=True,
                    model_used=model_name,
                    characters_processed=len(text),
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else None,
                    user_id=user_context.get('user_id') if user_context else None
                )
            except Exception as e:
                logger.warning(f"Failed to log AI metrics: {e}")
            
            logger.info(f"OpenAI categorization took {response_time:.2f}s for text length {len(text)}")
            
            content = response.choices[0].message.content
            
            # Парсим ответ
            try:
                result = json.loads(content)
                
                # Валидация результата
                if 'category' in result and result['category'] in categories:
                    logger.info(f"OpenAI categorized '{text}' as '{result['category']}' with confidence {result.get('confidence', 0)}")
                    return {
                        'category': result['category'],
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': 'openai'
                    }
                else:
                    logger.warning(f"OpenAI returned invalid category: {result.get('category')}")
                    return None
                    
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI response: {content}")
                return None
                
        except Exception as e:
            logger.error(f"OpenAI categorization error: {e}")
            
            # Логируем неудачную попытку в метрики
            try:
                from expenses.models import AIServiceMetrics
                await asyncio.to_thread(
                    AIServiceMetrics.objects.create,
                    service='openai',
                    operation_type='categorize_expense',
                    response_time=0,
                    success=False,
                    error_type=type(e).__name__[:100],
                    error_message=str(e)[:500],
                    user_id=user_context.get('user_id') if user_context else None
                )
            except Exception as log_error:
                logger.warning(f"Failed to log AI error metrics: {log_error}")
            
            return None
    
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Чат с OpenAI с поддержкой FUNCTION_CALL: ..., как у Gemini.
        Сначала просим модель выбрать функцию, при отсутствии FUNCTION_CALL — обычный чат.
        """
        try:
            # Попытка: выбор функции
            try:
                today = datetime.now()
                from bot.services.prompt_builder import build_function_call_prompt
                fc_prompt = build_function_call_prompt(message, context)

                model_name_fc = get_model('chat', 'openai')
                client_fc = self._get_client()
                sel_t0 = time.time()
                logger.info(f"[OpenAI] START function selection at {datetime.now().isoformat()}")
                sel_resp = await asyncio.to_thread(
                    client_fc.chat.completions.create,
                    model=model_name_fc,
                    messages=[
                        {"role": "system", "content": "Ты помощник бота учета финансов. При анализе данных отвечай только в виде FUNCTION_CALL: ..."},
                        {"role": "user", "content": fc_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.3,
                )
                sel_elapsed = time.time() - sel_t0
                logger.info(f"[OpenAI] END function selection took {sel_elapsed:.2f}s")
                sel_text = sel_resp.choices[0].message.content.strip() if sel_resp and sel_resp.choices else ""

                if sel_text.startswith("FUNCTION_CALL:"):
                    call_text = sel_text.replace("FUNCTION_CALL:", "").strip()
                    m = re.match(r'(\w+)\((.*)\)', call_text, flags=re.DOTALL)
                    if m:
                        func_name = m.group(1)
                        params_str = m.group(2)
                        # Special robust handling for analytics_query(spec_json=...)
                        if func_name == 'analytics_query':
                            spec = None
                            # Try single-quoted first
                            mjson = re.search(r"spec_json\s*=\s*'(.*)'\s*\)\s*$", call_text, flags=re.DOTALL)
                            if not mjson:
                                # Try double-quoted
                                mjson = re.search(r' spec_json\s*=\s*"(.*)"\s*\)\s*$', call_text, flags=re.DOTALL)
                            if mjson:
                                spec = mjson.group(1)
                                params = {"spec_json": spec}
                                from bot.services.function_call_utils import normalize_function_call
                                func_name, params = normalize_function_call(message, func_name, params, user_context.get('user_id') if user_context else None)
                                # Execute immediately
                                try:
                                    def run_sync_function():
                                        import django
                                        django.setup()
                                        from bot.services.expense_functions import ExpenseFunctions
                                        funcs = ExpenseFunctions()
                                        method = getattr(funcs, func_name)
                                        if hasattr(method, '__wrapped__'):
                                            method = method.__wrapped__
                                        return method(**params)
                                    result = await asyncio.to_thread(run_sync_function)
                                except Exception as e:
                                    logger.error(f"[OpenAI] Function {func_name} error: {e}")
                                    result = {'success': False, 'message': str(e)}

                                if result.get('success'):
                                    try:
                                        from bot.services.response_formatter import format_function_result
                                        return format_function_result(func_name, result)
                                    except Exception:
                                        import json as _json
                                        try:
                                            return _json.dumps(result, ensure_ascii=False)[:1000]
                                        except Exception:
                                            return str(result)[:1000]
                                else:
                                    return f"Ошибка: {result.get('message','Не удалось получить данные')}"
                            # If no spec_json matched, fall back to generic parsing below
                        # Санитация: если имя функции не ASCII (модель вернула русское имя), маппим по эвристике
                        if any(ord(ch) > 127 for ch in (func_name or '')):
                            low = message.lower()
                            if ('день' in low or 'дата' in low) and ('больше' in low or 'максим' in low) and ('потрат' in low or 'траты' in low):
                                func_name = 'get_max_expense_day'
                        params: Dict[str, Any] = {"user_id": user_context.get('user_id') if user_context else None}
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

                        from bot.services.function_call_utils import normalize_function_call
                        func_name, params = normalize_function_call(message, func_name, params, user_context.get('user_id') if user_context else None)

                        # Исполнение функции
                        try:
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
                            result = await call_function()
                        except Exception as e:
                            logger.error(f"[OpenAI] Function {func_name} error: {e}")
                            result = {'success': False, 'message': str(e)}

                        if result.get('success'):
                            try:
                                from bot.services.response_formatter import format_function_result
                                return format_function_result(func_name, result)
                            except Exception:
                                import json as _json
                                try:
                                    return _json.dumps(result, ensure_ascii=False)[:1000]
                                except Exception:
                                    return str(result)[:1000]
                        else:
                            return f"Ошибка: {result.get('message','Не удалось получить данные')}"
            except Exception:
                pass

            # Обычный чат если функция не выбрана
            messages = [
                {
                    "role": "system",
                    "content": """Ты - умный помощник в боте для учета личных расходов и доходов. 
Помогай пользователю с учетом финансов, отвечай на вопросы и давай советы."""
                }
            ]
            if context:
                for msg in context[-10:]:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            messages.append({"role": "user", "content": message})

            model_name = get_model('chat', 'openai')
            client = self._get_client()
            start_time = time.time()
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_name,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                top_p=0.9
            )
            response_time = time.time() - start_time
            try:
                from expenses.models import AIServiceMetrics
                await asyncio.to_thread(
                    AIServiceMetrics.objects.create,
                    service='openai',
                    operation_type='chat',
                    response_time=response_time,
                    success=True,
                    model_used=model_name,
                    characters_processed=len(message),
                    tokens_used=response.usage.total_tokens if hasattr(response, 'usage') else None,
                    user_id=user_context.get('user_id') if user_context else None
                )
            except Exception as e:
                logger.warning(f"Failed to log AI metrics: {e}")
            logger.info(f"OpenAI chat took {response_time:.2f}s for message length {len(message)}")
            result = response.choices[0].message.content.strip()
            if self.use_rotation:
                api_key = client.api_key
                self.api_key_manager.report_success(api_key)
            return result
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            try:
                from expenses.models import AIServiceMetrics
                await asyncio.to_thread(
                    AIServiceMetrics.objects.create,
                    service='openai',
                    operation_type='chat',
                    response_time=0,
                    success=False,
                    error_type=type(e).__name__[:100],
                    error_message=str(e)[:500],
                    user_id=user_context.get('user_id') if user_context else None
                )
            except Exception as log_error:
                logger.warning(f"Failed to log AI error metrics: {log_error}")
            if self.use_rotation and 'client' in locals():
                api_key = client.api_key
                self.api_key_manager.report_error(api_key, e)
            return "Извините, произошла ошибка при обработке вашего сообщения. Попробуйте еще раз."
