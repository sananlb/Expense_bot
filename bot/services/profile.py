"""
Service for managing user profiles
"""
from asgiref.sync import sync_to_async
from datetime import datetime
import logging

from expenses.models import Profile, UserSettings

logger = logging.getLogger(__name__)


@sync_to_async
def get_or_create_profile(telegram_id: int, **user_data) -> Profile:
    """
    Получить или создать профиль пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        **user_data: Дополнительные данные пользователя (language_code)
        
    Returns:
        Profile instance
    """
    try:
        # Определяем валюту по умолчанию на основе языка
        language_code = user_data.get('language_code', 'ru')[:2]
        default_currency = 'RUB' if language_code == 'ru' else 'USD'
        
        profile, created = Profile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'language_code': language_code,
                'timezone': 'Europe/Moscow',  # По умолчанию московское время
                'currency': default_currency,  # Валюта на основе языка
                'is_active': True,
            }
        )
        
        if created:
            # Создаем настройки пользователя
            UserSettings.objects.create(profile=profile)
            logger.info(f"Created new profile for user {telegram_id}")
                
        # Убеждаемся что настройки существуют
        if not hasattr(profile, 'settings'):
            UserSettings.objects.create(profile=profile)
            
        return profile
        
    except Exception as e:
        logger.error(f"Error creating/getting profile for user {telegram_id}: {e}")
        raise


@sync_to_async
def update_profile_activity(telegram_id: int) -> None:
    """
    Обновить время последней активности пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
    """
    try:
        Profile.objects.filter(telegram_id=telegram_id).update(
            last_activity=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error updating activity for user {telegram_id}: {e}")


@sync_to_async
def get_profile_settings(telegram_id: int) -> UserSettings:
    """
    Получить настройки пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        UserSettings instance
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        return profile.settings
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        raise
    except Exception as e:
        logger.error(f"Error getting settings for user {telegram_id}: {e}")
        raise