"""
Утилиты для работы с базой данных
"""
import logging
from typing import Optional
from asgiref.sync import sync_to_async
from expenses.models import Profile, ExpenseCategory

logger = logging.getLogger(__name__)


def get_or_create_user_profile_sync(telegram_id: int, **defaults) -> Profile:
    """
    Синхронная версия получения или создания профиля пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        **defaults: Дополнительные параметры для создания профиля
        
    Returns:
        Profile: Профиль пользователя
    """
    profile, created = Profile.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'language_code': 'ru',
            **defaults
        }
    )
    if created:
        logger.info(f"Created new profile for user {telegram_id}")
    return profile


@sync_to_async
def get_or_create_user_profile(telegram_id: int, **defaults) -> Profile:
    """
    Получить или создать профиль пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        **defaults: Дополнительные параметры для создания профиля
        
    Returns:
        Profile: Профиль пользователя
    """
    profile, created = Profile.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'language_code': 'ru',
            **defaults
        }
    )
    if created:
        logger.info(f"Created new profile for user {telegram_id}")
    return profile


@sync_to_async
def get_user_profile(telegram_id: int) -> Optional[Profile]:
    """
    Получить профиль пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        
    Returns:
        Profile или None если не найден
    """
    try:
        return Profile.objects.get(telegram_id=telegram_id)
    except Profile.DoesNotExist:
        return None


@sync_to_async  
def update_user_profile(telegram_id: int, **kwargs) -> Optional[Profile]:
    """
    Обновить профиль пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        **kwargs: Поля для обновления
        
    Returns:
        Profile или None если не найден
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        for key, value in kwargs.items():
            setattr(profile, key, value)
        profile.save()
        return profile
    except Profile.DoesNotExist:
        logger.warning(f"Profile not found for user {telegram_id}")
        return None


@sync_to_async
def get_user_categories(telegram_id: int, include_system: bool = True) -> list[ExpenseCategory]:
    """
    Получить категории пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        include_system: Включать ли системные категории
        
    Returns:
        Список категорий
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        categories = ExpenseCategory.objects.filter(
            profile=profile,
            is_active=True
        )
        
        if include_system:
            system_categories = ExpenseCategory.objects.filter(
                profile=None,
                is_system=True,
                is_active=True
            )
            # Объединяем и сортируем
            all_categories = list(categories) + list(system_categories)
            return sorted(all_categories, key=lambda x: x.order)
        
        return list(categories.order_by('order'))
        
    except Profile.DoesNotExist:
        if include_system:
            return list(ExpenseCategory.objects.filter(
                profile=None,
                is_system=True,
                is_active=True
            ).order_by('order'))
        return []