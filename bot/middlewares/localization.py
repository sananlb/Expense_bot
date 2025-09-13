"""
Localization middleware для многоязычности
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


class LocalizationMiddleware(BaseMiddleware):
    """Middleware для определения языка пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Определяем язык пользователя
        user = None
        telegram_id = None
        
        if isinstance(event, Message):
            user = event.from_user
            telegram_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            telegram_id = event.from_user.id
            
        if user and telegram_id:
            # Пытаемся получить язык из профиля пользователя в БД
            try:
                from expenses.models import Profile
                profile = await sync_to_async(Profile.objects.filter(telegram_id=telegram_id).first)()
                
                if profile and profile.language_code:
                    # Используем язык из профиля
                    lang_code = profile.language_code
                else:
                    # Если профиля нет или язык не установлен, берем из Telegram
                    lang_code = user.language_code or 'ru'
                    # Поддерживаем только ru и en
                    if lang_code not in ['ru', 'en']:
                        lang_code = 'ru'
                    lang_code = lang_code[:2]  # Берем только первые 2 символа
                    
                    # Если профиль существует, обновляем язык
                    if profile and profile.language_code != lang_code:
                        profile.language_code = lang_code
                        await sync_to_async(profile.save)()
                        
            except Exception as e:
                logger.error(f"Error getting language from profile: {e}")
                # В случае ошибки используем язык из Telegram
                lang_code = user.language_code or 'ru'
                if lang_code not in ['ru', 'en']:
                    lang_code = 'ru'
                lang_code = lang_code[:2]
                
            data['lang'] = lang_code
        else:
            data['lang'] = 'ru'
            
        return await handler(event, data)