"""
AI Selector - выбор и управление AI провайдерами
Аналог из nutrition_bot для expense_bot
"""
import os
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Конфигурация AI провайдеров
AI_PROVIDERS = {
    'categorization': {
        'provider': os.getenv('AI_PROVIDER_CATEGORIZATION', 'google'),  # Google по умолчанию
        'model': {
            'google': os.getenv('GOOGLE_MODEL_CATEGORIZATION', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_CATEGORIZATION', 'gpt-4o-mini'),
            'deepseek': os.getenv('DEEPSEEK_MODEL_CATEGORIZATION', 'deepseek-chat'),
            'qwen': os.getenv('QWEN_MODEL_CATEGORIZATION', 'qwen-plus')
        }
    },
    'chat': {
        'provider': os.getenv('AI_PROVIDER_CHAT', 'google'),  # Google по умолчанию
        'model': {
            'google': os.getenv('GOOGLE_MODEL_CHAT', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_CHAT', 'gpt-4o-mini'),
            'deepseek': os.getenv('DEEPSEEK_MODEL_CHAT', 'deepseek-chat'),
            'qwen': os.getenv('QWEN_MODEL_CHAT', 'qwen-plus')
        }
    },
    'insights': {
        'provider': os.getenv('AI_PROVIDER_INSIGHTS', 'google'),  # Google по умолчанию
        'model': {
            'google': os.getenv('GOOGLE_MODEL_INSIGHTS', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_INSIGHTS', 'gpt-4o-mini'),
            'deepseek': os.getenv('DEEPSEEK_MODEL_INSIGHTS', 'deepseek-chat'),
            'qwen': os.getenv('QWEN_MODEL_INSIGHTS', 'qwen-plus')
        }
    },
    'default': {
        'provider': os.getenv('AI_PROVIDER_DEFAULT', 'google'),  # Google по умолчанию
        'model': {
            'google': os.getenv('GOOGLE_MODEL_DEFAULT', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_DEFAULT', 'gpt-4o-mini'),
            'deepseek': os.getenv('DEEPSEEK_MODEL_DEFAULT', 'deepseek-chat'),
            'qwen': os.getenv('QWEN_MODEL_DEFAULT', 'qwen-plus')
        }
    }
}


class AISelector:
    """Селектор AI сервисов"""
    _instances = {}

    def __new__(cls, provider_type: str):
        # Используем кэширование для оптимизации
        if provider_type not in cls._instances:
            if provider_type == 'openai':
                logger.info(f"Creating new OpenAIService instance...")
                from .openai_service import OpenAIService
                cls._instances[provider_type] = OpenAIService()
                logger.info(f"OpenAIService instance created")
            elif provider_type == 'google':
                logger.info(f"[AISelector] Using adaptive GoogleAIService...")
                from .google_ai_service_adaptive import GoogleAIService
                logger.info(f"[AISelector] Creating GoogleAIService instance...")
                cls._instances[provider_type] = GoogleAIService()
                logger.info(f"[AISelector] GoogleAIService created successfully")
            elif provider_type in ('deepseek', 'qwen'):
                logger.info(f"[AISelector] Creating UnifiedAIService for {provider_type}...")
                from .unified_ai_service import UnifiedAIService
                cls._instances[provider_type] = UnifiedAIService(provider_name=provider_type)
                logger.info(f"[AISelector] UnifiedAIService ({provider_type}) created successfully")
            else:
                raise ValueError(f"Unsupported AI provider: {provider_type}")
        else:
            logger.info(f"Returning cached {provider_type} service instance")
        return cls._instances[provider_type]
    
    @classmethod
    def clear_cache(cls):
        """Очищает кэш экземпляров сервисов"""
        cls._instances.clear()
        logger.info("AI service cache cleared")


def get_service(service_type: str = 'default'):
    """
    Получает AI сервис на основе настроек
    
    Args:
        service_type: Тип сервиса ('categorization', 'chat', 'default')
        
    Returns:
        Экземпляр AI сервиса
    """
    config = AI_PROVIDERS.get(service_type, AI_PROVIDERS['default'])
    provider = config.get('provider', 'google')
    
    logger.info(f"Using {provider} for {service_type}")
    return AISelector(provider)


def get_model(service_type: str = 'default', provider: Optional[str] = None) -> str:
    """
    Получает имя модели для указанного типа сервиса
    
    Args:
        service_type: Тип сервиса
        provider: Провайдер (если не указан, берется из конфига)
        
    Returns:
        Имя модели
    """
    config = AI_PROVIDERS.get(service_type, AI_PROVIDERS['default'])
    
    if not provider:
        provider = config.get('provider', 'google')
    
    models = config.get('model', {})
    if isinstance(models, dict):
        # Возвращаем дефолтную модель в зависимости от провайдера, если не найдена в конфиге
        if provider == 'google':
            return models.get(provider, 'gemini-2.5-flash')
        elif provider == 'openai':
            return models.get(provider, 'gpt-4o-mini')
        elif provider == 'deepseek':
            return models.get(provider, 'deepseek-chat')
        elif provider == 'qwen':
            return models.get(provider, 'qwen-plus')
        return models.get(provider, 'gpt-4o-mini')
    else:
        return models


def get_provider_settings(provider: str) -> Dict[str, Any]:
    """
    Получает настройки для провайдера
    
    Args:
        provider: Имя провайдера
        
    Returns:
        Словарь с настройками
    """
    logger.info(f"get_provider_settings called for: {provider}")
    if provider == 'google':
        # Импортируем настройки чтобы получить ключи
        logger.info("Importing Django settings...")
        from expense_bot import settings
        logger.info("Django settings imported")
        
        # ВАЖНО: НЕ используем конкретный ключ - сервисы сами управляют ротацией
        api_keys_available = False
        if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
            api_keys_available = True
        elif hasattr(settings, 'GOOGLE_API_KEY') or os.getenv('GOOGLE_API_KEY'):
            api_keys_available = True
            
        return {
            'api_keys_available': api_keys_available,
            'default_model': 'gemini-2.5-flash',
            'max_tokens': 1500,
            'temperature': 0.1
        }
    elif provider == 'openai':
        # Импортируем настройки чтобы получить ключи
        from expense_bot import settings
        
        # ВАЖНО: НЕ используем конкретный ключ - сервисы сами управляют ротацией
        api_keys_available = False
        if hasattr(settings, 'OPENAI_API_KEYS') and settings.OPENAI_API_KEYS:
            api_keys_available = True
        elif hasattr(settings, 'OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY'):
            api_keys_available = True
            
        return {
            'api_keys_available': api_keys_available,
            'default_model': 'gpt-4o-mini',
            'max_tokens': 1500,
            'temperature': 0.1
        }
    elif provider == 'deepseek':
        from expense_bot import settings
        api_keys_available = False
        if hasattr(settings, 'DEEPSEEK_API_KEYS') and settings.DEEPSEEK_API_KEYS:
            api_keys_available = True
        elif hasattr(settings, 'DEEPSEEK_API_KEY') or os.getenv('DEEPSEEK_API_KEY'):
            api_keys_available = True
            
        return {
            'api_keys_available': api_keys_available,
            'default_model': 'deepseek-chat',
            'max_tokens': 4096,
            'temperature': 0.0
        }
    elif provider == 'qwen':
        from expense_bot import settings
        api_keys_available = False
        if hasattr(settings, 'DASHSCOPE_API_KEYS') and settings.DASHSCOPE_API_KEYS:
            api_keys_available = True
        elif hasattr(settings, 'DASHSCOPE_API_KEY') or os.getenv('DASHSCOPE_API_KEY'):
            api_keys_available = True
            
        return {
            'api_keys_available': api_keys_available,
            'default_model': 'qwen-plus',
            'max_tokens': 1500,
            'temperature': 0.1
        }
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_fallback_chain(service_type: str = 'default', primary_provider: Optional[str] = None) -> List[str]:
    """
    Получает цепочку fallback провайдеров из настроек .env

    Args:
        service_type: Тип сервиса ('categorization', 'chat', 'insights', 'default')
        primary_provider: Основной провайдер (если None, берется из AI_PROVIDERS)

    Returns:
        Список провайдеров для fallback (без основного провайдера)

    Example:
        >>> get_fallback_chain('categorization', 'google')
        ['deepseek', 'qwen', 'openai']  # Из AI_FALLBACK_CATEGORIZATION, исключая 'google'
    """
    from expense_bot import settings

    # Получаем основного провайдера если не указан
    if not primary_provider:
        config = AI_PROVIDERS.get(service_type, AI_PROVIDERS['default'])
        primary_provider = config.get('provider', 'google')

    # Получаем список fallback провайдеров из настроек
    fallback_attr_name = f'AI_FALLBACK_{service_type.upper()}'
    if not hasattr(settings, fallback_attr_name):
        # Fallback на дефолтный список если не настроен конкретный тип
        fallback_attr_name = 'AI_FALLBACK_DEFAULT'

    fallback_list = getattr(settings, fallback_attr_name, ['deepseek', 'qwen', 'openai'])

    # Исключаем основного провайдера и проверяем доступность ключей
    result = []
    for provider in fallback_list:
        if provider == primary_provider:
            continue

        # Проверяем что у провайдера есть ключи
        try:
            provider_settings = get_provider_settings(provider)
            if provider_settings.get('api_keys_available', False):
                result.append(provider)
        except Exception as e:
            logger.warning(f"Provider {provider} not available for fallback: {e}")
            continue

    logger.info(f"[AI Fallback] Service: {service_type}, Primary: {primary_provider}, Chain: {result}")
    return result