"""
OpenAI Service для expense_bot
"""
import logging
import json
import asyncio
import threading
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
        # Если нет пула клиентов, создаем единичный клиент
        if not OPENAI_CLIENTS:
            settings = get_provider_settings('openai')
            api_key = settings['api_key']
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
            
            # Асинхронный вызов
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "Ты помощник для категоризации расходов. Отвечай только валидным JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=1000,  # Увеличиваем до 1000
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
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
            return None
    
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Чат с OpenAI
        """
        try:
            # Формируем сообщения для OpenAI
            messages = [
                {
                    "role": "system",
                    "content": """Ты - умный помощник в боте для учета личных расходов. 
Помогай пользователю с учетом трат, отвечай на вопросы о расходах и давай советы по управлению финансами.
Будь дружелюбным и полезным. Отвечай кратко и по существу.
Если пользователь хочет записать трату - скажи, что нужно просто отправить сообщение вида "Продукты 500".
НЕ используй форматирование Markdown, пиши простым текстом."""
                }
            ]
            
            # Добавляем контекст
            if context:
                for msg in context[-10:]:  # Берем последние 10 сообщений
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            # Добавляем текущее сообщение
            messages.append({
                "role": "user",
                "content": message
            })
            
            model_name = get_model('chat', 'openai')
            
            # Получаем клиент с ротацией ключей
            client = self._get_client()
            
            # Асинхронный вызов
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_name,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                top_p=0.9
            )
            
            result = response.choices[0].message.content.strip()
            
            # Отмечаем успех
            if self.use_rotation:
                api_key = client.api_key
                self.api_key_manager.report_success(api_key)
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            
            # Отчитываемся об ошибке
            if self.use_rotation and 'client' in locals():
                api_key = client.api_key
                self.api_key_manager.report_error(api_key, e)
            
            return "Извините, произошла ошибка при обработке вашего сообщения. Попробуйте еще раз."