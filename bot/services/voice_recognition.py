"""
Сервис распознавания голоса с симметричным fallback:
- RU: Yandex SpeechKit → OpenRouter (Gemini)
- EN: OpenRouter (Gemini) → Yandex SpeechKit

Централизованное управление моделями через ai_selector.
"""
import logging
import time
from typing import Optional
from io import BytesIO

from .yandex_speech import YandexSpeechKit
from .ai_selector import get_service, get_model

logger = logging.getLogger(__name__)


class VoiceRecognitionService:
    """
    Централизованный сервис распознавания голоса с симметричным fallback.

    Архитектура:
    - RU: Yandex (primary) → OpenRouter/Gemini (fallback)
    - EN/другие: OpenRouter/Gemini (primary) → Yandex (fallback)
    """

    @classmethod
    async def transcribe(
        cls,
        audio_bytes: bytes,
        user_language: str = 'ru',
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Распознать голосовое сообщение с симметричным fallback.

        Args:
            audio_bytes: Аудио в формате OGG Opus (Telegram voice)
            user_language: Язык пользователя ('ru', 'en', etc.)
            user_id: ID пользователя для логирования

        Returns:
            Распознанный текст или None
        """
        start_time = time.time()

        # Минимальный размер аудио для распознавания
        # Нормальное аудио: 5000-8500 байт/сек, пустое/тишина: ~1000 байт/сек
        MIN_AUDIO_BYTES = 3000

        # Проверяем что аудио не "пустое" (случайное нажатие кнопки записи)
        if len(audio_bytes) < MIN_AUDIO_BYTES:
            logger.warning(f"[VoiceRecognition] User {user_id} | Audio too small: {len(audio_bytes)} bytes, skipping recognition")
            return None

        if user_language == 'ru':
            # RU: Yandex → OpenRouter
            text = await cls._transcribe_with_fallback(
                audio_bytes,
                primary='yandex',
                fallback='openrouter',
                user_id=user_id
            )
        else:
            # EN/другие: OpenRouter → Yandex
            text = await cls._transcribe_with_fallback(
                audio_bytes,
                primary='openrouter',
                fallback='yandex',
                user_id=user_id
            )

        elapsed = time.time() - start_time
        if text:
            logger.info(f"[VoiceRecognition] User {user_id} | Lang: {user_language} | Time: {elapsed:.2f}s | Text: {text[:50]}...")
        else:
            logger.warning(f"[VoiceRecognition] User {user_id} | Lang: {user_language} | Time: {elapsed:.2f}s | FAILED")

        return text

    @classmethod
    async def _transcribe_with_fallback(
        cls,
        audio_bytes: bytes,
        primary: str,
        fallback: str,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Распознавание с fallback.

        Args:
            audio_bytes: Аудио данные
            primary: Основной провайдер ('yandex' или 'openrouter')
            fallback: Резервный провайдер
            user_id: ID пользователя

        Returns:
            Распознанный текст или None
        """
        # 1. Пробуем primary
        text = await cls._transcribe_single(audio_bytes, primary, user_id)
        if text:
            return text

        logger.info(f"[VoiceRecognition] Primary ({primary}) failed, trying fallback ({fallback})")

        # 2. Пробуем fallback
        text = await cls._transcribe_single(audio_bytes, fallback, user_id)
        if text:
            return text

        return None

    @classmethod
    async def _transcribe_single(
        cls,
        audio_bytes: bytes,
        provider: str,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Распознавание через конкретный провайдер.

        Args:
            audio_bytes: Аудио данные
            provider: 'yandex' или 'openrouter'
            user_id: ID пользователя

        Returns:
            Распознанный текст или None
        """
        try:
            if provider == 'yandex':
                return await YandexSpeechKit.transcribe_primary(audio_bytes)

            elif provider == 'openrouter':
                # Получаем сервис через ai_selector
                service = get_service('voice')
                model = get_model('voice', 'openrouter')

                user_context = {'user_id': user_id} if user_id else None
                return await service.transcribe_voice(
                    audio_bytes,
                    model=model,
                    user_context=user_context
                )

            else:
                logger.error(f"[VoiceRecognition] Unknown provider: {provider}")
                return None

        except Exception as e:
            logger.error(f"[VoiceRecognition] Error with {provider}: {e}")
            return None


async def recognize_voice(message, bot, user_language: str = 'ru') -> Optional[str]:
    """
    Распознавание голосового сообщения.
    Legacy API для совместимости с существующим кодом.

    Args:
        message: Telegram message object
        bot: Telegram bot instance
        user_language: Язык пользователя

    Returns:
        Распознанный текст или None
    """
    try:
        # Показываем индикатор "печатает..."
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

        # Получаем файл
        file_info = await bot.get_file(message.voice.file_id)
        file_path = file_info.file_path

        # Скачиваем файл в память
        file_bytes = BytesIO()
        await bot.download_file(file_path, file_bytes)
        file_bytes.seek(0)
        audio_bytes = file_bytes.read()

        # Получаем user_id для логирования
        user_id = message.from_user.id
        duration = message.voice.duration

        logger.info(f"[VOICE_INPUT] User {user_id} | Duration: {duration}s | Lang: {user_language}")

        # Используем новый централизованный сервис
        text = await VoiceRecognitionService.transcribe(
            audio_bytes,
            user_language=user_language,
            user_id=user_id
        )

        return text

    except Exception as e:
        logger.error(f"Ошибка при распознавании голоса: {e}")
        return None


async def process_voice_for_expense(message, bot, user_language: str = 'ru') -> Optional[str]:
    """
    Обработка голосового сообщения для расхода.
    Legacy API для совместимости.

    Args:
        message: Telegram message object
        bot: Telegram bot instance
        user_language: Язык пользователя

    Returns:
        Распознанный текст или None
    """
    # Проверяем длительность
    try:
        from django.conf import settings
        max_seconds = getattr(settings, 'MAX_VOICE_DURATION_SECONDS', 60)
    except Exception:
        max_seconds = 60

    if message.voice.duration > max_seconds:
        if user_language == 'ru':
            await message.answer(f"⚠️ Голосовое сообщение слишком длинное. Максимум {max_seconds} секунд.")
        else:
            await message.answer(f"⚠️ Voice message is too long. Maximum {max_seconds} seconds.")
        return None

    # Распознаем через централизованный сервис
    text = await recognize_voice(message, bot, user_language)

    if not text:
        if user_language == 'ru':
            await message.answer(
                "❌ Не удалось распознать речь.\n\n"
                "Попробуйте:\n"
                "• Говорить четче\n"
                "• Уменьшить фоновый шум\n"
                "• Отправить текстовое сообщение"
            )
        else:
            await message.answer(
                "❌ Failed to recognize speech.\n\n"
                "Try to:\n"
                "• Speak more clearly\n"
                "• Reduce background noise\n"
                "• Send a text message"
            )
        return None

    return text
