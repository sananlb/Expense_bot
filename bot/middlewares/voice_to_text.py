"""
Middleware для автоматической транскрибации голосовых сообщений в текст.

Этот middleware перехватывает голосовые сообщения и преобразует их в текст,
добавляя результат в message.text, чтобы все последующие обработчики
могли работать с голосовыми сообщениями как с текстовыми.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class VoiceToTextMiddleware(BaseMiddleware):
    """
    Middleware для автоматического преобразования голосовых сообщений в текст.

    Работает следующим образом:
    1. Проверяет, является ли сообщение голосовым
    2. Проверяет подписку пользователя (голосовой ввод - премиум функция)
    3. Распознаёт голосовое сообщение
    4. Сохраняет распознанный текст в data['voice_text'] для использования в обработчиках
    """

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Обрабатываем только голосовые сообщения
        if not event.voice:
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        # Проверяем подписку
        from bot.services.subscription import check_subscription
        has_subscription = await check_subscription(user_id)

        if not has_subscription:
            # Без подписки голосовой ввод недоступен - пропускаем дальше,
            # обработчик сам покажет сообщение о подписке
            data['voice_text'] = None
            data['voice_no_subscription'] = True
            return await handler(event, data)

        # Получаем язык пользователя
        lang = data.get('lang', 'ru')
        if not lang:
            from bot.services.user_settings import get_user_language
            try:
                lang = await get_user_language(user_id) or 'ru'
            except Exception:
                lang = 'ru'

        # Распознаём голосовое сообщение
        try:
            from bot.services.voice_recognition import process_voice_for_expense
            text = await process_voice_for_expense(event, event.bot, lang)

            if text:
                text = text.strip()
                logger.info(f"[VoiceToText] User {user_id}: voice transcribed to '{text[:50]}...'")
                data['voice_text'] = text
            else:
                logger.warning(f"[VoiceToText] User {user_id}: failed to transcribe voice")
                data['voice_text'] = None
                data['voice_transcribe_failed'] = True

        except Exception as e:
            logger.error(f"[VoiceToText] User {user_id}: error transcribing voice: {e}")
            data['voice_text'] = None
            data['voice_transcribe_failed'] = True

        return await handler(event, data)
