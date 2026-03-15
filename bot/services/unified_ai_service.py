"""
Unified AI Service - универсальный сервис для OpenAI-совместимых API
Поддерживает DeepSeek, Qwen (DashScope), OpenRouter и другие модели.
"""
import logging
import json
import asyncio
import time
import re
import base64
import tempfile
import os
from typing import Dict, List, Optional, Any, Type, Callable, Awaitable

import httpx
from httpx_socks import AsyncProxyTransport
from openai import AsyncOpenAI
from django.conf import settings
from .ai_base_service import AIBaseService
from .ai_selector import get_model
from .key_rotation_mixin import KeyRotationMixin, DeepSeekKeyRotationMixin, QwenKeyRotationMixin, OpenRouterKeyRotationMixin
from bot.utils.logging_safe import log_safe_id, summarize_text

logger = logging.getLogger(__name__)

class UnifiedAIService(AIBaseService):
    """
    Универсальный сервис для работы с любым OpenAI-совместимым API.
    Заменяет собой специфичные реализации для каждого провайдера.
    """

    def __init__(self, provider_name: str):
        """
        Инициализация сервиса

        Args:
            provider_name: Имя провайдера ('deepseek', 'qwen', etc.)
        """
        super().__init__()
        self.provider_name = provider_name
        self.base_url = None
        self.api_key_mixin: Optional[Type[KeyRotationMixin]] = None
        self._http_client_with_proxy: Optional[httpx.AsyncClient] = None
        # Cache for AsyncOpenAI clients to prevent "Event loop is closed" errors
        # Key: (api_key, use_proxy) -> AsyncOpenAI client
        self._openai_clients: Dict[tuple, AsyncOpenAI] = {}

        # Настройка параметров провайдера
        if provider_name == 'deepseek':
            self.base_url = "https://api.deepseek.com/v1"
            self.api_key_mixin = DeepSeekKeyRotationMixin
        elif provider_name == 'qwen':
            self.base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
            self.api_key_mixin = QwenKeyRotationMixin
        elif provider_name == 'openrouter':
            self.base_url = "https://openrouter.ai/api/v1"
            self.api_key_mixin = OpenRouterKeyRotationMixin
            # Инициализируем прокси клиент для OpenRouter (только если режим proxy)
            self._initialize_proxy_client()
        else:
            raise ValueError(f"Unsupported provider for UnifiedAIService: {provider_name}")

    def _initialize_proxy_client(self):
        """Инициализация httpx клиента с SOCKS5 прокси (только для OpenRouter)"""
        connection_mode = os.getenv('OPENROUTER_CONNECTION_MODE', 'proxy').lower()

        # В режиме direct не инициализируем прокси вообще
        if connection_mode == 'direct':
            logger.info(f"[{self.provider_name}] 🌐 Режим подключения: direct (прокси отключен)")
            return

        proxy_url = os.getenv('AI_PROXY_URL')
        if not proxy_url:
            logger.info(f"[{self.provider_name}] AI_PROXY_URL не задан, работаем напрямую")
            return

        try:
            transport = AsyncProxyTransport.from_url(proxy_url)
            self._http_client_with_proxy = httpx.AsyncClient(
                transport=transport,
                timeout=15.0  # Единый timeout 15 секунд
            )
            proxy_display = proxy_url.split('@')[1] if '@' in proxy_url else proxy_url.replace('socks5://', '')

            logger.info(
                f"[{self.provider_name}] 🔒 SOCKS5 прокси инициализирован: {proxy_display} (timeout: 15s)"
            )
        except Exception as e:
            logger.warning(f"[{self.provider_name}] Не удалось инициализировать прокси ({e}), работаем напрямую")
            self._http_client_with_proxy = None

    async def aclose(self):
        """
        Закрываем все клиенты при завершении приложения.
        Включает httpx прокси-клиент и все кэшированные AsyncOpenAI клиенты.
        """
        # Close cached AsyncOpenAI clients
        for _, client in list(self._openai_clients.items()):
            try:
                close_method = getattr(client, 'close', None)
                if close_method:
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
            except Exception as e:
                logger.debug(f"[{self.provider_name}] Error closing OpenAI client: {e}")
        self._openai_clients.clear()

        # Close httpx proxy client
        if self._http_client_with_proxy:
            try:
                await self._http_client_with_proxy.aclose()
            except Exception:
                pass
            finally:
                # Do not keep reference to a closed proxy client.
                self._http_client_with_proxy = None

    def _get_client(self, use_proxy: bool = True) -> tuple[AsyncOpenAI, int]:
        """
        Получает или создаёт клиент OpenAI с актуальным ключом из ротации.
        Клиенты кэшируются для предотвращения утечек при закрытии event loop.

        Args:
            use_proxy: Использовать прокси (если доступен). False = прямое соединение.

        Returns:
            tuple: (клиент OpenAI, индекс ключа)
        """
        if not self.api_key_mixin:
            raise ValueError("API Key Mixin not configured")

        key_result = self.api_key_mixin.get_next_key()
        if not key_result:
            raise ValueError(f"No API keys available for {self.provider_name}")

        api_key, key_index = key_result

        # Используем прокси только для OpenRouter
        connection_mode = os.getenv('OPENROUTER_CONNECTION_MODE', 'proxy').lower()
        should_use_proxy = (
            use_proxy
            and self._http_client_with_proxy
            and connection_mode == 'proxy'
        )

        # Cache key: (api_key, should_use_proxy)
        cache_key = (api_key, should_use_proxy)

        # Return cached client if exists
        if cache_key in self._openai_clients:
            return self._openai_clients[cache_key], key_index

        # Create new client
        http_client = self._http_client_with_proxy if should_use_proxy else None

        # Для прокси-запросов: отключаем retry (мы сами делаем fallback)
        # и используем granular timeout (быстрый connect, дольше на read)
        if should_use_proxy:
            # Прокси: connect=5s (быстро понять что прокси недоступен), read=15s
            timeout = httpx.Timeout(15.0, connect=5.0)
            max_retries = 0  # Не retry - у нас свой fallback механизм
        else:
            # Прямое соединение: стандартный timeout, 1 retry
            timeout = 15.0
            max_retries = 1

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client
        )

        # Cache the client
        self._openai_clients[cache_key] = client

        return client, key_index

    def _is_proxy_error(self, error: Exception) -> bool:
        """Проверяет, является ли ошибка связанной с прокси"""
        error_str = str(error).lower()
        proxy_keywords = [
            'socks', 'proxy', 'connection refused', 'connection reset',
            'tunnel', 'handshake', 'connect timeout', 'proxyerror',
            'connection error'  # Generic connection errors when proxy is enabled
        ]
        return any(keyword in error_str for keyword in proxy_keywords)

    async def _notify_proxy_fallback(self, operation: str, error: Exception, proxy_time: float):
        """Уведомляет админа о fallback с прокси на прямое соединение"""
        try:
            from bot.services.admin_notifier import notify_critical_error
            await notify_critical_error(
                error_type="OpenRouter Proxy Fallback",
                details=f"Операция: {operation}, Ошибка: {str(error)[:150]}, Время прокси: {proxy_time:.2f}s"
            )
        except Exception as notify_error:
            logger.warning(f"[{self.provider_name}] Не удалось уведомить админа о fallback: {notify_error}")

    async def _make_api_call_with_proxy_fallback(
        self,
        create_call: Callable[[AsyncOpenAI], Awaitable[Any]],
        operation: str,
    ):
        """
        Выполняет API вызов с fallback на прямое соединение при ошибке прокси.

        Логика:
        1. Всегда сначала пробуем через прокси (если настроен)
        2. При ошибке прокси - fallback на прямое соединение
        3. Уведомляем админа о каждом fallback

        Args:
            create_call: Функция, принимающая client и возвращающая response
            operation: Название операции для логирования

        Returns:
            tuple: (response, response_time, key_index)
        """
        client, key_index = self._get_client(use_proxy=True)
        start_time = time.time()
        using_proxy = (
            self._http_client_with_proxy
            and os.getenv('OPENROUTER_CONNECTION_MODE', 'proxy').lower() == 'proxy'
        )

        try:
            response = await create_call(client)

            # Успех - помечаем ключ как рабочий
            if self.api_key_mixin:
                self.api_key_mixin.mark_key_success(key_index)

            elapsed = time.time() - start_time

            # Логируем режим подключения (только для прокси, чтобы не спамить)
            if using_proxy:
                logger.debug(
                    f"[{self.provider_name}] ✓ {operation} через SOCKS5 прокси: {elapsed:.2f}s"
                )

            return response, elapsed, key_index

        except Exception as api_error:
            # Проверяем ошибки прокси - делаем fallback
            if self._is_proxy_error(api_error) and self._http_client_with_proxy:
                proxy_elapsed = time.time() - start_time
                logger.warning(
                    f"[{self.provider_name}] ⚠️ Ошибка прокси после {proxy_elapsed:.2f}s ({api_error}), "
                    f"повторяю запрос напрямую"
                )

                # Уведомляем админа о fallback (async, не блокируем)
                asyncio.create_task(self._notify_proxy_fallback(operation, api_error, proxy_elapsed))

                # Повторяем запрос БЕЗ прокси
                try:
                    direct_start = time.time()
                    client_direct, key_index_direct = self._get_client(use_proxy=False)
                    response = await create_call(client_direct)

                    if self.api_key_mixin:
                        self.api_key_mixin.mark_key_success(key_index_direct)

                    direct_elapsed = time.time() - direct_start
                    total_elapsed = time.time() - start_time
                    logger.info(
                        f"[{self.provider_name}] ✓ {operation} через прямое соединение: {direct_elapsed:.2f}s "
                        f"(попытка прокси: {proxy_elapsed:.2f}s, всего: {total_elapsed:.2f}s)"
                    )
                    return response, total_elapsed, key_index_direct

                except Exception as direct_error:
                    # Если и прямое соединение не помогло - помечаем НОВЫЙ ключ как проблемный
                    if self.api_key_mixin:
                        self.api_key_mixin.mark_key_failure(key_index_direct, direct_error)
                    raise direct_error

            # Обычная ошибка API (не прокси)
            if self.api_key_mixin:
                self.api_key_mixin.mark_key_failure(key_index, api_error)
            raise api_error

    async def categorize_expense(
        self,
        text: str,
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Категоризация расхода
        """
        try:
            # Получаем промпт из базового класса
            prompt = self.get_expense_categorization_prompt(
                text, amount, currency, categories, user_context
            )

            model_name = get_model('categorization', self.provider_name)

            # Создаем функцию для API вызова
            async def create_call(client):
                return await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=1024
                )

            # Выполняем запрос с поддержкой прокси fallback
            response, response_time, key_index = await self._make_api_call_with_proxy_fallback(
                create_call, 'categorize_expense'
            )

            content = response.choices[0].message.content
            
            # Логируем метрики
            self._log_metrics(
                operation='categorize_expense',
                response_time=response_time,
                success=True,
                model=model_name,
                input_len=len(text),
                tokens=response.usage.total_tokens if hasattr(response, 'usage') else None,
                user_id=user_context.get('user_id') if user_context else None
            )
            
            # Парсим JSON
            try:
                result = json.loads(content)
                if 'category' in result:
                    return {
                        'category': result.get('category'),
                        'confidence': result.get('confidence', 0.8),
                        'reasoning': result.get('reasoning', ''),
                        'provider': self.provider_name
                    }
            except json.JSONDecodeError:
                logger.error("[%s] Failed to parse JSON: %s", self.provider_name, summarize_text(content))
                
            return None
            
        except Exception as e:
            logger.error("[%s] Categorization error: %s", self.provider_name, e)
            self._log_metrics(
                operation='categorize_expense',
                response_time=0,
                success=False,
                error=e,
                user_id=user_context.get('user_id') if user_context else None
            )
            return None

    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None,
        disable_functions: bool = False,
        timeout: Optional[float] = None
    ) -> str:
        """
        Чат с поддержкой вызова функций (через эмуляцию FUNCTION_CALL)

        Args:
            message: User message
            context: Conversation context
            user_context: User metadata (user_id, language)
            disable_functions: If True, skip function calling and use simple chat
            timeout: Custom timeout in seconds (overrides default 15s). Use for long tasks like insights.
        """
        user_id = user_context.get('user_id') if user_context else None
        user_language = user_context.get('language', 'ru') if user_context else 'ru'
        faq_context = user_context.get('faq_context') if user_context else None

        try:
            # Skip function calling if disabled
            if disable_functions:
                # Direct chat without function calling
                return await self._simple_chat(message, context, user_id, faq_context=faq_context, timeout=timeout)

            # 1. Попытка определить функцию (Intent Recognition)
            from bot.services.prompt_builder import build_function_call_prompt
            fc_prompt = build_function_call_prompt(message, context, user_language)

            model_name = get_model('chat', self.provider_name)

            start_time = time.time()

            # Первый запрос - определение интента
            # Используем более строгий промпт для DeepSeek/Qwen
            system_prompt = """Ты помощник бота ShowMeCoin. Если пользователь просит аналитику, верни ТОЛЬКО: FUNCTION_CALL: function_name(arg1=value).

СТРОГИЕ ПРАВИЛА:
1. НЕ говори "я могу" - объясняй КАК пользователю сделать что-то в боте
2. Трата: просто напиши "500 кофе" или "такси 300". Доход: "+50000 зарплата"
3. Меню бота (реальные кнопки): 💸Траты сегодня, 📁Категории, 💳Кешбэк, 🔄Ежемесячные, ⚙️Настройки, 🏠Семья
4. Команд "доход", "расход", "бюджет на месяц" НЕ СУЩЕСТВУЕТ!
5. На "как дела" - спроси чем помочь."""
            if faq_context:
                system_prompt += "\n\nFAQ (используй как источник фактов, не выдумывай функции вне списка):\n" + faq_context

            # Создаем функцию для первого API вызова (Intent Recognition)
            async def create_intent_call(client):
                return await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": fc_prompt}
                    ],
                    temperature=0.1,  # Минимальная температура для точности
                    max_tokens=200
                )

            # Выполняем запрос с поддержкой прокси fallback
            intent_response, intent_time, _ = await self._make_api_call_with_proxy_fallback(
                create_intent_call, 'chat_intent'
            )

            intent_text = intent_response.choices[0].message.content.strip()

            # Проверяем, вернула ли модель вызов функции
            if "FUNCTION_CALL:" in intent_text:
                # Извлекаем и выполняем функцию
                func_result = await self._execute_function_call(intent_text, message, user_id)

                self._log_metrics(
                    operation='chat_function',
                    response_time=time.time() - start_time,
                    success=True,
                    model=model_name,
                    input_len=len(message),
                    user_id=user_id
                )

                return func_result

            # 2. Если функции нет - обычный чат
            chat_system = """Ты - помощник бота ShowMeCoin для учета расходов и доходов.

СТРОГИЕ ПРАВИЛА:
1. НЕ говори "я могу" - объясняй КАК пользователю сделать что-то в боте
2. Трата: просто напиши "500 кофе" или "такси 300". Доход: "+50000 зарплата"
3. Меню бота (реальные кнопки): 💸Траты сегодня, 📁Категории, 💳Кешбэк, 🔄Ежемесячные, ⚙️Настройки, 🏠Семья
4. Команд "доход", "расход", "бюджет на месяц" НЕ СУЩЕСТВУЕТ!
5. НИКОГДА НЕ ВЫДУМЫВАЙ факты о боте! Если не знаешь точный ответ - скажи "Не знаю, уточните у поддержки" или направь на соответствующую команду (/subscription, /settings, /help)."""
            if faq_context:
                chat_system += "\n\nFAQ (единственный источник правды о боте):\n" + faq_context
            chat_messages = [
                {"role": "system", "content": chat_system}
            ]
            if context:
                for msg in context[-10:]:
                    chat_messages.append({"role": msg['role'], "content": msg['content']})
            chat_messages.append({"role": "user", "content": message})

            # Создаем функцию для второго API вызова (Chat)
            async def create_chat_call(client):
                return await client.chat.completions.create(
                    model=model_name,
                    messages=chat_messages,
                    temperature=0.7,
                    max_tokens=1000
                )

            # Выполняем запрос с поддержкой прокси fallback
            response, chat_time, _ = await self._make_api_call_with_proxy_fallback(
                create_chat_call, 'chat'
            )

            response_time = time.time() - start_time
            response_text = response.choices[0].message.content.strip()

            self._log_metrics(
                operation='chat',
                response_time=response_time,
                success=True,
                model=model_name,
                input_len=len(message),
                tokens=response.usage.total_tokens if hasattr(response, 'usage') else None,
                user_id=user_id
            )

            return response_text

        except Exception as e:
            logger.error(
                "[%s] Chat error for %s: %s",
                self.provider_name,
                log_safe_id(user_id, "user"),
                e,
            )
            self._log_metrics(
                operation='chat',
                response_time=0,
                success=False,
                error=e,
                user_id=user_id
            )
            return "Извините, сервис временно недоступен."

    async def _simple_chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_id: Optional[int] = None,
        faq_context: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> str:
        """
        Simple chat without function calling - just direct AI response

        Args:
            message: User message
            context: Conversation context
            user_id: Optional user ID for logging
            timeout: Custom timeout in seconds (overrides default)

        Returns:
            AI response text
        """
        model_name = get_model('chat', self.provider_name)

        start_time = time.time()

        # Build messages without Intent Recognition
        system_prompt = """Ты - помощник бота ShowMeCoin для учета расходов и доходов.

СТРОГИЕ ПРАВИЛА:
1. НЕ говори "я могу" - объясняй КАК пользователю сделать что-то в боте
2. Трата: просто напиши "500 кофе" или "такси 300". Доход: "+50000 зарплата"
3. Меню бота (реальные кнопки): 💸Траты сегодня, 📁Категории, 💳Кешбэк, 🔄Ежемесячные, ⚙️Настройки, 🏠Семья
4. Команд "доход", "расход", "бюджет на месяц" НЕ СУЩЕСТВУЕТ!
5. НИКОГДА НЕ ВЫДУМЫВАЙ факты о боте! Если не знаешь точный ответ - скажи "Не знаю, уточните у поддержки" или направь на соответствующую команду (/subscription, /settings, /help)."""
        if faq_context:
            system_prompt += "\n\nFAQ (единственный источник правды о боте):\n" + faq_context

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            for msg in context[-10:]:
                messages.append({"role": msg['role'], "content": msg['content']})
        messages.append({"role": "user", "content": message})

        # Создаем функцию для API вызова
        call_kwargs = dict(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        if timeout is not None:
            call_kwargs['timeout'] = timeout

        async def create_call(client):
            return await client.chat.completions.create(**call_kwargs)

        try:
            # Выполняем запрос с поддержкой прокси fallback
            response, response_time, _ = await self._make_api_call_with_proxy_fallback(
                create_call, 'simple_chat'
            )

            response_text = response.choices[0].message.content.strip()

            self._log_metrics(
                operation='simple_chat',
                response_time=response_time,
                success=True,
                model=model_name,
                input_len=len(message),
                tokens=response.usage.total_tokens if hasattr(response, 'usage') else None,
                user_id=user_id
            )

            return response_text

        except Exception as api_error:
            response_time = time.time() - start_time
            logger.error(
                "[%s] Simple chat error for %s: %s",
                self.provider_name,
                log_safe_id(user_id, "user"),
                api_error,
            )
            self._log_metrics(
                operation='simple_chat',
                response_time=response_time,
                success=False,
                model=model_name,
                input_len=len(message),
                error=api_error,
                user_id=user_id
            )
            raise api_error

    async def _execute_function_call(self, call_text: str, original_message: str, user_id: int) -> str:
        """Парсинг и выполнение функции из текстового ответа"""
        try:
            call_text = call_text.replace("FUNCTION_CALL:", "").strip()
            # Простой регекс для парсинга имени и аргументов
            m = re.match(r'(\w+)\((.*)\)', call_text, flags=re.DOTALL)
            if not m:
                return "Не удалось распознать команду."
                
            func_name = m.group(1)
            params_str = m.group(2)
            params = {}
            
            # Парсинг параметров (упрощенный)
            if params_str:
                # Пробуем извлечь spec_json (сложный случай)
                json_match = re.search(r"spec_json\s*=\s*['\"](.*)['\"]\s*\)?$", call_text, flags=re.DOTALL)
                if json_match:
                    params['spec_json'] = json_match.group(1)
                else:
                    # Обычный парсинг key=value
                    parts = params_str.split(',')
                    for part in parts:
                        if '=' in part:
                            k, v = part.split('=', 1)
                            k = k.strip()
                            v = v.strip().strip('"\'')
                            # Пытаемся привести типы
                            if v.isdigit():
                                v = int(v)
                            params[k] = v
            
            # Нормализация через утилиту
            from bot.services.function_call_utils import normalize_function_call
            func_name, params = normalize_function_call(original_message, func_name, params, user_id)
            
            # Импорт и вызов
            import django
            django.setup()
            from bot.services.expense_functions import ExpenseFunctions
            from bot.services.response_formatter import format_function_result
            
            funcs = ExpenseFunctions()
            if not hasattr(funcs, func_name):
                 return "Функция не найдена."
                 
            method = getattr(funcs, func_name)
            
            # Выполнение (асинхронно)
            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = await asyncio.to_thread(method, **params)
                
            # Форматирование результата
            if isinstance(result, dict) and user_id:
                result['user_id'] = user_id
                logger.info(
                    "[_execute_function_call] Added %s to result for function=%s",
                    log_safe_id(user_id, "user"),
                    func_name,
                )
            else:
                logger.warning(
                    "[_execute_function_call] Could NOT add user id. is_dict=%s user=%s",
                    isinstance(result, dict),
                    log_safe_id(user_id, "user"),
                )

            logger.info(
                "[_execute_function_call] Calling format_function_result with func_name=%s result_keys=%s",
                func_name,
                list(result.keys()) if isinstance(result, dict) else 'N/A',
            )
            formatted = format_function_result(func_name, result)
            logger.info(
                "[_execute_function_call] format_function_result returned: %s",
                summarize_text(formatted),
            )
            return formatted
            
        except Exception as e:
            logger.error("Function execution error: %s", e)
            return f"Ошибка при выполнении операции: {str(e)}"

    async def transcribe_voice(
        self,
        audio_bytes: bytes,
        model: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Транскрипция голосового сообщения через OpenRouter (Gemini multimodal).

        Args:
            audio_bytes: Аудио в формате OGG Opus (Telegram voice)
            model: Модель для транскрипции (по умолчанию из get_model('voice'))
            user_context: Контекст пользователя для метрик

        Returns:
            Распознанный текст или None при ошибке
        """
        if self.provider_name != 'openrouter':
            logger.error("[%s] transcribe_voice поддерживается только для OpenRouter", self.provider_name)
            return None

        user_id = user_context.get('user_id') if user_context else None
        start_time = time.time()

        try:
            # Конвертируем OGG в MP3 (Gemini лучше работает с MP3)
            mp3_bytes = await self._convert_ogg_to_mp3(audio_bytes)
            if not mp3_bytes:
                logger.error("[OpenRouter] Не удалось конвертировать OGG в MP3")
                return None

            # Кодируем в base64
            audio_base64 = base64.b64encode(mp3_bytes).decode('utf-8')

            # Получаем модель
            model_name = model or get_model('voice', self.provider_name)

            # Промпт для мультимодальной модели (как в nutrition_bot)
            system_prompt = (
                "You are a speech-to-text transcription system. "
                "Your ONLY task is to transcribe audio to text verbatim. "
                "NEVER explain, interpret, translate, or comment on the content. "
                "NEVER add any text that was not spoken in the audio. "
                "Output ONLY the exact words spoken, nothing more."
            )

            transcription_prompt = "Transcribe this audio. Output only the spoken words."

            # Формируем запрос с правильным форматом input_audio для OpenRouter
            messages: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": transcription_prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_base64,
                                "format": "mp3"
                            }
                        },
                    ],
                },
            ]

            # Создаем функцию для API вызова
            async def create_call(client):
                return await client.chat.completions.create(
                    model=model_name,
                    messages=messages,  # type: ignore
                    max_tokens=500,
                    temperature=0.0  # Минимальная температура для точной транскрипции
                )

            # Выполняем запрос с поддержкой прокси fallback
            response, response_time, _ = await self._make_api_call_with_proxy_fallback(
                create_call, 'transcribe_voice'
            )

            content = response.choices[0].message.content
            transcribed_text = content.strip() if content else ""

            # Проверяем, не является ли ответ отказом AI вместо транскрипции
            if transcribed_text:
                AI_REFUSAL_PATTERNS = [
                    "i'm sorry",
                    "i cannot",
                    "i'm unable",
                    "sorry, but",
                    "cannot transcribe",
                    "no audio",
                    "unable to process",
                    "unable to transcribe",
                    "no speech detected",
                    "could not transcribe",
                    "there is no audio",
                ]

                transcribed_lower = transcribed_text.lower()
                for pattern in AI_REFUSAL_PATTERNS:
                    if pattern in transcribed_lower:
                        logger.warning(
                            "[OpenRouter] AI returned refusal instead of transcription: %s",
                            summarize_text(transcribed_text),
                        )
                        # Логируем метрики для отказа AI (важно для мониторинга)
                        self._log_metrics(
                            operation='transcribe_voice',
                            response_time=response_time,
                            success=False,
                            model=model_name,
                            input_len=len(audio_bytes),
                            tokens=response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None,
                            user_id=user_id,
                            error=ValueError(f'AI refusal detected: {pattern}')
                        )
                        return None

            # Логируем метрики
            self._log_metrics(
                operation='transcribe_voice',
                response_time=response_time,
                success=True,
                model=model_name,
                input_len=len(audio_bytes),
                tokens=response.usage.total_tokens if hasattr(response, 'usage') and response.usage else None,
                user_id=user_id
            )

            logger.info(
                "[OpenRouter] Transcribed in %.2fs: %s",
                response_time,
                summarize_text(transcribed_text),
            )
            return transcribed_text if transcribed_text else None

        except Exception as e:
            response_time = time.time() - start_time
            logger.error("[OpenRouter] Ошибка транскрипции за %.2fs: %s", response_time, e)
            self._log_metrics(
                operation='transcribe_voice',
                response_time=response_time,
                success=False,
                error=e,
                user_id=user_id
            )
            return None

    async def _convert_ogg_to_mp3(self, ogg_bytes: bytes) -> Optional[bytes]:
        """
        Конвертирует OGG Opus в MP3 через pydub/ffmpeg.

        Args:
            ogg_bytes: Аудио в формате OGG Opus

        Returns:
            Аудио в формате MP3 или None при ошибке
        """
        try:
            from pydub import AudioSegment
            from io import BytesIO

            # Создаем временный файл для OGG (pydub требует файл для OGG)
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_ogg:
                tmp_ogg.write(ogg_bytes)
                tmp_ogg_path = tmp_ogg.name

            try:
                # Загружаем OGG и конвертируем в MP3
                audio = await asyncio.to_thread(
                    AudioSegment.from_ogg, tmp_ogg_path
                )

                # Экспортируем в MP3 в память
                mp3_buffer = BytesIO()
                await asyncio.to_thread(
                    audio.export, mp3_buffer, format='mp3', bitrate='64k'
                )
                mp3_buffer.seek(0)

                return mp3_buffer.read()

            finally:
                # Удаляем временный файл
                try:
                    os.unlink(tmp_ogg_path)
                except Exception:
                    pass

        except ImportError:
            logger.error("[OpenRouter] pydub не установлен для конвертации аудио")
            return None
        except Exception as e:
            logger.error("[OpenRouter] Ошибка конвертации OGG→MP3: %s", e)
            return None

    def _log_metrics(self, operation, response_time, success, model=None, input_len=0, tokens=None, error=None, user_id=None):
        """Запись метрик в БД (поддерживает и async, и sync контексты)"""
        try:
            from expenses.models import AIServiceMetrics
            
            error_type = type(error).__name__ if error else None
            error_msg = str(error)[:500] if error else None
            
            def _save_metrics():
                AIServiceMetrics.objects.create(
                    service=self.provider_name,
                    operation_type=operation,
                    response_time=response_time,
                    success=success,
                    model_used=model,
                    characters_processed=input_len,
                    tokens_used=tokens,
                    user_id=user_id,
                    error_type=error_type,
                    error_message=error_msg
                )

            # Проверяем наличие запущенного event loop
            try:
                loop = asyncio.get_running_loop()
                # Если мы в async контексте - используем create_task с to_thread
                loop.create_task(asyncio.to_thread(_save_metrics))
            except RuntimeError:
                # Если event loop нет (синхронный контекст, например Celery) - пишем синхронно
                # Можно также использовать run_in_executor если есть глобальный пул, но здесь проще так
                _save_metrics()
                
        except Exception as e:
            logger.warning("Failed to log metrics: %s", e)
