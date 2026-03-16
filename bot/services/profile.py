"""
Service for managing user profiles
"""
from asgiref.sync import sync_to_async
from datetime import datetime
from typing import Tuple
import logging

from expenses.models import Profile, UserSettings, Household
from bot.constants import (
    DEFAULT_CURRENCY_CODE,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_TIMEZONE,
    get_default_currency_for_language,
)
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


@sync_to_async
def get_user_settings(telegram_id: int) -> UserSettings:
    """
    Получить настройки пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        UserSettings instance
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        if not hasattr(profile, 'settings'):
            settings = UserSettings.objects.create(profile=profile)
        else:
            settings = profile.settings
        return settings
    except Profile.DoesNotExist:
        # Создаем профиль если не существует
        profile = Profile.objects.create(
            telegram_id=telegram_id,
            language_code=DEFAULT_LANGUAGE_CODE,
            timezone=DEFAULT_TIMEZONE,
            currency=DEFAULT_CURRENCY_CODE,
            is_active=True
        )
        settings = UserSettings.objects.create(profile=profile)
        return settings


@sync_to_async
def toggle_cashback(telegram_id: int) -> bool:
    """
    Переключить состояние кешбэка
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Новое состояние кешбэка (True - включен, False - выключен)
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        if not hasattr(profile, 'settings'):
            settings = UserSettings.objects.create(profile=profile)
        else:
            settings = profile.settings
        
        settings.cashback_enabled = not settings.cashback_enabled
        settings.save()
        return settings.cashback_enabled
    except Profile.DoesNotExist:
        # Создаем профиль если не существует
        profile = Profile.objects.create(
            telegram_id=telegram_id,
            language_code=DEFAULT_LANGUAGE_CODE,
            timezone=DEFAULT_TIMEZONE,
            currency=DEFAULT_CURRENCY_CODE,
            is_active=True
        )
        settings = UserSettings.objects.create(profile=profile)
        settings.cashback_enabled = False
        settings.save()
        return settings.cashback_enabled


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
        language_code = user_data.get('language_code', DEFAULT_LANGUAGE_CODE)[:2]
        default_currency = get_default_currency_for_language(language_code)
        
        profile, created = Profile.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'language_code': language_code,
                'timezone': DEFAULT_TIMEZONE,
                'currency': default_currency,  # Валюта на основе языка
                'is_active': True,
            }
        )
        
        if created:
            # Создаем настройки пользователя
            UserSettings.objects.create(profile=profile)
            logger.info("Created new profile for %s", log_safe_id(telegram_id, "user"))
                
        # Убеждаемся что настройки существуют
        if not hasattr(profile, 'settings'):
            UserSettings.objects.create(profile=profile)
            
        return profile
        
    except Exception as e:
        logger.error("Error creating/getting profile for %s: %s", log_safe_id(telegram_id, "user"), e)
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
        logger.error("Error updating activity for %s: %s", log_safe_id(telegram_id, "user"), e)


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
        logger.error("Profile not found for %s", log_safe_id(telegram_id, "user"))
        raise
    except Exception as e:
        logger.error("Error getting settings for %s: %s", log_safe_id(telegram_id, "user"), e)
        raise


@sync_to_async
def delete_user_profile(telegram_id: int) -> Tuple[bool, str]:
    """
    Полное удаление профиля пользователя и всех связанных данных.

    Returns:
        Tuple[bool, str]: (success, error_code)
        - (True, "") — успешно удалено
        - (False, "NOT_FOUND") — профиль не найден
        - (False, "ERROR") — ошибка удаления

    Удаляются:
    - Все данные через Django CASCADE (23 модели)
    - AIServiceMetrics (хранит telegram_id как BigIntegerField, не FK)
    - Household целиком, если пользователь был создателем
    """
    from django.db import transaction
    from expenses.models import AIServiceMetrics, UserSettings

    try:
        with transaction.atomic():
            profile = Profile.objects.filter(telegram_id=telegram_id).first()

            if not profile:
                logger.warning("Profile not found for %s", log_safe_id(telegram_id, "user"))
                return (False, "NOT_FOUND")

            profile_id = profile.id
            household_id = profile.household_id

            # 1. Удаляем AI метрики (user_id - BigIntegerField, не FK)
            metrics_deleted = AIServiceMetrics.objects.filter(user_id=telegram_id).delete()[0]
            if metrics_deleted > 0:
                logger.info("Deleted %s AIServiceMetrics for %s", metrics_deleted, log_safe_id(telegram_id, "user"))

            # 2. Если пользователь - создатель household, удаляем household целиком
            created_households = Household.objects.filter(creator_id=profile_id)
            for household in created_households:
                # Сбрасываем view_scope в 'personal' для всех участников
                # (чтобы они не остались в невалидном состоянии с view_scope='household' без household)
                settings_reset = UserSettings.objects.filter(
                    profile__household=household
                ).update(view_scope='personal')
                if settings_reset > 0:
                    logger.info(
                        "Reset view_scope to 'personal' for %s members of household %s",
                        settings_reset,
                        household.id,
                    )

                # Открепляем всех участников от household
                members_count = Profile.objects.filter(household=household).update(household=None)
                logger.info(
                    "Removed %s members from household %s before deletion (creator: %s)",
                    members_count,
                    household.id,
                    log_safe_id(telegram_id, "user"),
                )
                # Удаляем household
                household.delete()
                logger.info("Deleted household %s (creator was %s)", household.id, log_safe_id(telegram_id, "user"))

            # 3. Удаляем профиль — CASCADE удалит все остальное
            profile.delete()

            logger.info(
                "Profile deleted for %s: profile_id=%s, was_in_household=%s",
                log_safe_id(telegram_id, "user"),
                profile_id,
                household_id,
            )
            return (True, "")

    except Exception as e:
        logger.error("Failed to delete profile for %s: %s", log_safe_id(telegram_id, "user"), e)
        return (False, "ERROR")
