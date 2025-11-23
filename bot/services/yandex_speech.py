"""
Yandex SpeechKit интеграция для распознавания речи.

Используется как primary провайдер для русского языка
и как fallback для других языков.
"""
import logging
import time
import aiohttp
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class YandexSpeechKit:
    """Интеграция с Yandex SpeechKit"""

    RECOGNITION_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"

    @classmethod
    async def transcribe_primary(cls, audio_bytes: bytes) -> Optional[str]:
        """
        Распознать речь через Yandex SpeechKit (без fallback).

        Fallback управляется в VoiceRecognitionService для симметричности.

        Args:
            audio_bytes: Аудио в формате OGG Opus (Telegram voice)

        Returns:
            Распознанный текст или None при ошибке
        """
        start_time = time.time()

        try:
            api_key = getattr(settings, 'YANDEX_API_KEY', None)
            folder_id = getattr(settings, 'YANDEX_FOLDER_ID', None)

            if not api_key or not folder_id:
                logger.warning("[YANDEX] API_KEY или FOLDER_ID не настроены")
                return None

            headers = {
                'Authorization': f'Api-Key {api_key}',
            }

            params = {
                'topic': getattr(settings, 'YANDEX_SPEECH_TOPIC', 'general:rc'),
                'folderId': folder_id,
                'format': 'oggopus',
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    cls.RECOGNITION_URL,
                    headers=headers,
                    params=params,
                    data=audio_bytes,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    elapsed = time.time() - start_time

                    if response.status == 200:
                        result = await response.json()
                        text = result.get('result', '').strip()

                        if text:
                            text = cls._postprocess_text(text)
                            logger.info(f"[YANDEX] Распознал за {elapsed:.2f}s: {text}")
                            return text
                        else:
                            logger.warning(f"[YANDEX] Пустой результат за {elapsed:.2f}s")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"[YANDEX] Ошибка {response.status} за {elapsed:.2f}s: {error_text}")
                        return None

        except aiohttp.ClientError as e:
            elapsed = time.time() - start_time
            logger.error(f"[YANDEX] Network error за {elapsed:.2f}s: {e}")
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[YANDEX] Exception за {elapsed:.2f}s: {e}")
            return None

    @staticmethod
    def _postprocess_text(text: str) -> str:
        """Постобработка текста для expense_bot"""
        if not text:
            return text

        # Убираем лишние знаки препинания в конце
        text = text.rstrip('.,!?')

        # Исправления для финансовых терминов (русский)
        corrections = {
            'рублей': 'руб',
            'рубля': 'руб',
            'рубль': 'руб',
            'долларов': '$',
            'доллара': '$',
            'доллар': '$',
            'евро': '€',
            # Разделители для множественных трат
            ' и ': ', ',
            ' плюс ': ', ',
            ' еще ': ', ',
            ' ещё ': ', ',
        }

        text_lower = text.lower()
        for wrong, correct in corrections.items():
            if wrong in text_lower:
                text = text.replace(wrong, correct)
                text = text.replace(wrong.capitalize(), correct.capitalize())

        return text
