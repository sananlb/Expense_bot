"""
Middleware для сброса флага bot_blocked при активности пользователя.

Когда пользователь блокирует бота, мы ставим bot_blocked=True.
Когда он возвращается (любой message/callback), сбрасываем флаг.

Используется debounce через Redis чтобы не бомбить БД на каждом апдейте.
"""
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from django.core.cache import cache
from django.utils import timezone
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)

# Debounce: не проверять чаще чем раз в N секунд на пользователя
DEBOUNCE_SECONDS = 300  # 5 минут


class BotUnblockMiddleware(BaseMiddleware):
    """
    Сбрасывает bot_blocked=False при любой активности пользователя.

    Должен быть зарегистрирован на самом раннем уровне (до других middleware),
    чтобы обработать все входящие апдейты.
    """

    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None

        if user_id:
            # Debounce: проверяем не чаще чем раз в DEBOUNCE_SECONDS
            cache_key = f"bot_unblock_check:{user_id}"

            if not cache.get(cache_key):
                # Ставим флаг в кеш сразу, чтобы параллельные запросы не дублировали
                cache.set(cache_key, True, DEBOUNCE_SECONDS)

                # Асинхронно проверяем и сбрасываем bot_blocked
                try:
                    await self._reset_bot_blocked(user_id)
                except Exception as e:
                    # Не блокируем обработку из-за ошибки БД
                    logger.error(f"Error resetting bot_blocked for user {user_id}: {e}")

        return await handler(event, data)

    @sync_to_async
    def _reset_bot_blocked(self, user_id: int) -> None:
        """Сбрасывает bot_blocked если был установлен"""
        from expenses.models import Profile

        try:
            profile = Profile.objects.get(telegram_id=user_id)

            if profile.bot_blocked:
                # Логируем для статистики
                blocked_duration = None
                if profile.bot_blocked_at:
                    blocked_duration = timezone.now() - profile.bot_blocked_at
                    logger.info(
                        f"User {user_id} returned after blocking bot. "
                        f"Was blocked since: {profile.bot_blocked_at}, "
                        f"duration: {blocked_duration}"
                    )
                else:
                    logger.info(f"User {user_id} returned after blocking bot (no timestamp)")

                # Сбрасываем флаг
                profile.bot_blocked = False
                profile.bot_blocked_at = None
                profile.save(update_fields=['bot_blocked', 'bot_blocked_at'])

        except Profile.DoesNotExist:
            # Профиль ещё не создан - это нормально для новых пользователей
            pass
