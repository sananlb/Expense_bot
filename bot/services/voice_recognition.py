"""
Сервис распознавания голоса с поддержкой Yandex Speech, Google Speech и OpenAI Whisper
"""
import logging
import tempfile
import os
import json
from typing import Optional
import speech_recognition as sr
from pydub import AudioSegment
import aiofiles
import asyncio
import aiohttp
from io import BytesIO

logger = logging.getLogger(__name__)


class YandexSpeechKit:
    """Интеграция с Yandex SpeechKit для русского языка"""
    
    RECOGNITION_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    
    @classmethod
    async def transcribe(cls, audio_bytes: bytes) -> Optional[str]:
        """Распознать речь через Yandex SpeechKit"""
        try:
            # Проверяем наличие необходимых настроек
            api_key = os.getenv('YANDEX_API_KEY')
            folder_id = os.getenv('YANDEX_FOLDER_ID')
            
            if not api_key or not folder_id:
                logger.warning("Yandex SpeechKit не настроен")
                return None
            
            # Заголовки запроса
            headers = {
                'Authorization': f'Api-Key {api_key}',
            }
            
            # Параметры запроса
            params = {
                'topic': os.getenv('YANDEX_SPEECH_TOPIC', 'general:rc'),
                'lang': 'ru-RU',
                'folderId': folder_id,
                'format': 'oggopus',  # Формат Telegram голосовых
            }
            
            # Отправляем запрос
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    cls.RECOGNITION_URL,
                    headers=headers,
                    params=params,
                    data=audio_bytes,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        text = result.get('result', '').strip()
                        
                        # Постобработка
                        if text:
                            text = cls._postprocess_russian(text)
                            logger.info(f"Yandex SpeechKit распознал: {text}")
                            return text
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка Yandex SpeechKit: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Ошибка при распознавании через Yandex: {e}")
            return None
    
    @staticmethod
    def _postprocess_russian(text: str) -> str:
        """Постобработка русского текста"""
        if not text:
            return text
            
        # Убираем лишние знаки препинания в конце
        text = text.rstrip('.,!?')
        
        # Исправления для русской речи о расходах
        corrections = {
            'рублей': 'руб',
            'рубля': 'руб',
            'рубль': 'руб',
            'тысяч': 'тыс',
            'тысячи': 'тыс',
            'тысяча': 'тыс',
            'миллион': 'млн',
            'миллионов': 'млн',
            
            # Для множественных расходов
            ' и ': ', ',  # заменяем "и" на запятую
            ' плюс ': ', ',
            ' еще ': ', ',
        }
        
        text_lower = text.lower()
        for wrong, correct in corrections.items():
            if wrong in text_lower:
                text = text.replace(wrong, correct)
                text = text.replace(wrong.capitalize(), correct.capitalize())
        
        return text


class OpenAIWhisper:
    """Интеграция с OpenAI Whisper для транскрипции"""
    
    @classmethod
    async def transcribe(cls, audio_bytes: bytes, lang: str = 'ru') -> Optional[str]:
        """Распознать речь через OpenAI Whisper"""
        try:
            import openai
            
            # Проверяем наличие API ключа
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OpenAI API ключ не настроен")
                return None
            
            # Настраиваем клиента
            client = openai.OpenAI(api_key=api_key)
            
            # Создаем временный файл для аудио
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_file_path = tmp_file.name
            
            try:
                # Открываем файл и отправляем на транскрипцию
                with open(tmp_file_path, 'rb') as audio_file:
                    transcript = await asyncio.to_thread(
                        client.audio.transcriptions.create,
                        model="whisper-1",
                        file=audio_file,
                        language=lang.split('-')[0] if lang else "ru"
                    )
                
                text = transcript.text
                if text:
                    logger.info(f"OpenAI Whisper распознал: {text}")
                    return text
                    
            finally:
                # Удаляем временный файл
                os.unlink(tmp_file_path)
                
        except Exception as e:
            logger.error(f"Ошибка при распознавании через OpenAI Whisper: {e}")
            return None


async def recognize_voice(message, bot, user_language: str = 'ru') -> Optional[str]:
    """
    Распознавание голосового сообщения с fallback цепочкой:
    Для русского: Yandex -> Google -> OpenAI Whisper
    Для английского: Google -> OpenAI Whisper -> Yandex
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
        
        # Определяем язык для распознавания
        if user_language == 'ru':
            lang = 'ru-RU'
            # Цепочка для русского: Yandex -> Google -> Whisper
            
            # 1. Пробуем Yandex SpeechKit (лучший для русского)
            text = await YandexSpeechKit.transcribe(audio_bytes)
            if text:
                return text
            logger.info("Yandex SpeechKit не смог распознать, пробуем Google")
            
            # 2. Пробуем Google Speech Recognition (бесплатный fallback)
            text = await recognize_with_google(audio_bytes, lang)
            if text:
                return text
            logger.info("Google Speech не смог распознать, пробуем OpenAI Whisper")
            
            # 3. Пробуем OpenAI Whisper (универсальный fallback)
            text = await OpenAIWhisper.transcribe(audio_bytes, lang)
            if text:
                return text
                
        else:
            # Для английского и других языков
            lang = 'en-US' if user_language == 'en' else f'{user_language}-{user_language.upper()}'
            # Оптимальная цепочка для английского: Google -> Whisper -> Yandex
            
            # 1. Пробуем Google Speech Recognition (лучший для английского)
            text = await recognize_with_google(audio_bytes, lang)
            if text:
                return text
            logger.info("Google Speech не смог распознать, пробуем OpenAI Whisper")
            
            # 2. Пробуем OpenAI Whisper
            text = await OpenAIWhisper.transcribe(audio_bytes, user_language)
            if text:
                return text
            logger.info("OpenAI Whisper не смог распознать, пробуем Yandex")
            
            # 3. Пробуем Yandex (может работать с английским)
            text = await YandexSpeechKit.transcribe(audio_bytes)
            if text:
                return text
        
        logger.warning("Ни один сервис не смог распознать речь")
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при распознавании голоса: {e}")
        return None


async def recognize_with_google(audio_bytes: bytes, lang: str) -> Optional[str]:
    """Распознавание через Google Speech Recognition"""
    try:
        # Создаем временные файлы
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_ogg:
            ogg_path = tmp_ogg.name
            tmp_ogg.write(audio_bytes)
        
        # Конвертируем в WAV для speech_recognition
        wav_path = ogg_path.replace('.ogg', '.wav')
        
        # Используем pydub для конвертации
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")
        
        # Распознаем речь
        recognizer = sr.Recognizer()
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        
        # Пробуем Google
        try:
            text = recognizer.recognize_google(audio_data, language=lang)
            logger.info(f"Google Speech Recognition распознал: {text}")
            return text
        except sr.UnknownValueError:
            logger.info("Google Speech Recognition не смог распознать речь")
            return None
        except sr.RequestError as e:
            logger.error(f"Ошибка Google Speech Recognition: {e}")
            return None
        
    except Exception as e:
        logger.error(f"Ошибка при распознавании через Google: {e}")
        return None
    finally:
        # Очищаем временные файлы
        try:
            if 'ogg_path' in locals():
                os.unlink(ogg_path)
            if 'wav_path' in locals():
                os.unlink(wav_path)
        except:
            pass


async def process_voice_for_expense(message, bot, user_language: str = 'ru') -> Optional[str]:
    """
    Обработка голосового сообщения для расхода
    """
    # Проверяем длительность
    if message.voice.duration > 60:
        if user_language == 'ru':
            await message.answer("⚠️ Голосовое сообщение слишком длинное. Максимум 60 секунд.")
        else:
            await message.answer("⚠️ Voice message is too long. Maximum 60 seconds.")
        return None
    
    # Распознаем с использованием оптимальной цепочки для языка
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