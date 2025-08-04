"""
AI Selector - выбор и управление AI провайдерами
Аналог из nutrition_bot для expense_bot
"""
import os
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Конфигурация AI провайдеров
AI_PROVIDERS = {
    'categorization': {
        'provider': os.getenv('AI_PROVIDER_CATEGORIZATION', 'google'),  # google или openai
        'model': {
            'google': os.getenv('GOOGLE_MODEL_CATEGORIZATION', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_CATEGORIZATION', 'gpt-4o-mini')
        }
    },
    'chat': {
        'provider': os.getenv('AI_PROVIDER_CHAT', 'google'),
        'model': {
            'google': os.getenv('GOOGLE_MODEL_CHAT', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_CHAT', 'gpt-4o-mini')
        }
    },
    'default': {
        'provider': os.getenv('AI_PROVIDER_DEFAULT', 'google'),
        'model': {
            'google': os.getenv('GOOGLE_MODEL_DEFAULT', 'gemini-2.5-flash'),
            'openai': os.getenv('OPENAI_MODEL_DEFAULT', 'gpt-4o-mini')
        }
    }
}


class AISelector:
    """Селектор AI сервисов"""
    _instances = {}

    def __new__(cls, provider_type: str):
        if provider_type not in cls._instances:
            if provider_type == 'openai':
                from .openai_service import OpenAIService
                cls._instances[provider_type] = OpenAIService()
            elif provider_type == 'google':
                from .google_ai_service import GoogleAIService
                cls._instances[provider_type] = GoogleAIService()
            else:
                raise ValueError(f"Unsupported AI provider: {provider_type}")
        return cls._instances[provider_type]


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
        return models.get(provider, 'gemini-2.5-flash')
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
    if provider == 'google':
        return {
            'api_key': os.getenv('GOOGLE_API_KEY'),
            'default_model': 'gemini-2.5-flash',
            'max_tokens': 150,
            'temperature': 0.1
        }
    elif provider == 'openai':
        return {
            'api_key': os.getenv('OPENAI_API_KEY'),
            'default_model': 'gpt-4o-mini',
            'max_tokens': 150,
            'temperature': 0.1
        }
    else:
        raise ValueError(f"Unknown provider: {provider}")