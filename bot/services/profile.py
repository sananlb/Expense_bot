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
        **user_data: Дополнительные данные пользователя (username, first_name, last_name, language_code)
        
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
                'username': user_data.get('username', ''),
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
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
        else:
            # Обновляем данные пользователя если они изменились
            updated = False
            
            if user_data.get('username') and profile.username != user_data['username']:
                profile.username = user_data['username']
                updated = True
                
            if user_data.get('first_name') and profile.first_name != user_data['first_name']:
                profile.first_name = user_data['first_name']
                updated = True
                
            if user_data.get('last_name') and profile.last_name != user_data['last_name']:
                profile.last_name = user_data['last_name']
                updated = True
                
            if updated:
                profile.save()
                
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