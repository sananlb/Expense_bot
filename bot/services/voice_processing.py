import os
import logging
import tempfile
import time
from typing import Optional, Dict, Any
import aiofiles
import aiohttp

from aiogram import types
from aiogram.types import File

logger = logging.getLogger(__name__)


class VoiceProcessor:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.yandex_api_key = os.getenv('YANDEX_API_KEY')
        self.yandex_folder_id = os.getenv('YANDEX_FOLDER_ID')
        self.yandex_oauth_token = os.getenv('YANDEX_OAUTH_TOKEN')
        self._yandex_iam_token = None
        self._yandex_iam_expires = None
        
    async def download_voice_file(self, bot, file_id: str) -> Optional[str]:
        """Download voice file from Telegram"""
        try:
            # Get file info
            file: File = await bot.get_file(file_id)
            file_path = file.file_path
            
            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"voice_{file_id}.ogg")
            
            # Download file
            await bot.download_file(file_path, temp_path)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error downloading voice file: {e}")
            return None
    
    async def transcribe_with_openai(self, audio_path: str) -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API"""
        if not self.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return None
            
        try:
            import openai
            openai.api_key = self.openai_api_key
            
            # Read audio file
            async with aiofiles.open(audio_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # Create form data
            url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            # Prepare multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', audio_data, 
                              filename='audio.ogg', 
                              content_type='audio/ogg')
            form_data.add_field('model', 'whisper-1')
            form_data.add_field('language', 'ru')  # Russian language
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=form_data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get('text', '')
                    else:
                        error_text = await resp.text()
                        logger.error(f"OpenAI API error: {resp.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"OpenAI transcription error: {e}")
            return None
    
    async def transcribe_with_google(self, audio_path: str) -> Optional[str]:
        """Fallback: Transcribe using Google Speech-to-Text"""
        if not self.google_api_key:
            logger.warning("Google API key not configured")
            return None
            
        try:
            # For Google Cloud Speech, we would need to:
            # 1. Convert OGG to WAV or FLAC
            # 2. Use google-cloud-speech library
            # This is a placeholder for now
            logger.info("Google Speech-to-Text integration not implemented yet")
            return None
            
        except Exception as e:
            logger.error(f"Google transcription error: {e}")
            return None
    
    async def get_yandex_iam_token(self) -> Optional[str]:
        """Get Yandex IAM token for API calls"""
        if not self.yandex_oauth_token:
            return None
            
        # Check if token is still valid
        if self._yandex_iam_token and self._yandex_iam_expires:
            import datetime
            if datetime.datetime.now() < self._yandex_iam_expires:
                return self._yandex_iam_token
        
        # Get new IAM token
        try:
            url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
            headers = {"Content-Type": "application/json"}
            data = {"yandexPassportOauthToken": self.yandex_oauth_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self._yandex_iam_token = result['iamToken']
                        # Token valid for 12 hours, refresh after 11 hours
                        import datetime
                        self._yandex_iam_expires = datetime.datetime.now() + datetime.timedelta(hours=11)
                        return self._yandex_iam_token
                    else:
                        logger.error(f"Failed to get Yandex IAM token: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting Yandex IAM token: {e}")
            return None
    
    async def transcribe_with_yandex(self, audio_path: str) -> Optional[str]:
        """Transcribe audio using Yandex SpeechKit"""
        if not self.yandex_folder_id:
            logger.warning("Yandex folder ID not configured")
            return None
            
        iam_token = await self.get_yandex_iam_token()
        if not iam_token:
            logger.warning("Failed to get Yandex IAM token")
            return None
        
        try:
            # Read audio file
            async with aiofiles.open(audio_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # Yandex SpeechKit API
            url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
            headers = {
                "Authorization": f"Bearer {iam_token}"
            }
            params = {
                "lang": "ru-RU",
                "folderId": self.yandex_folder_id,
                "format": "oggopus"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    params=params,
                    data=audio_data
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get('result', '')
                    else:
                        error_text = await resp.text()
                        logger.error(f"Yandex API error: {resp.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Yandex transcription error: {e}")
            return None
    
    async def process_voice_message(self, message: types.Message, bot, user_language: str = 'ru') -> Optional[str]:
        """Main method to process voice message"""
        if not message.voice:
            return None
            
        voice = message.voice
        file_id = voice.file_id
        duration = voice.duration
        
        # Check duration limit (max 60 seconds)
        if duration > 60:
            await message.answer("⚠️ Голосовое сообщение слишком длинное. Максимум 60 секунд.")
            return None
        
        # Show typing indicator
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Download voice file
        audio_path = await self.download_voice_file(bot, file_id)
        if not audio_path:
            return None
        
        try:
            text = None
            
            # For Russian language, try Yandex first
            if user_language == 'ru' and self.yandex_folder_id:
                text = await self.transcribe_with_yandex(audio_path)
            
            # Fallback to OpenAI
            if not text and self.openai_api_key:
                text = await self.transcribe_with_openai(audio_path)
            
            # Fallback to Google
            if not text and self.google_api_key:
                text = await self.transcribe_with_google(audio_path)
            
            return text
                
        finally:
            # Clean up temp file
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception as e:
                logger.error(f"Error removing temp file: {e}")
    
    async def cleanup_old_files(self):
        """Clean up old temporary voice files"""
        try:
            temp_dir = tempfile.gettempdir()
            for filename in os.listdir(temp_dir):
                if filename.startswith('voice_') and filename.endswith('.ogg'):
                    file_path = os.path.join(temp_dir, filename)
                    # Remove files older than 1 hour
                    if os.path.getmtime(file_path) < (time.time() - 3600):
                        os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")


# Singleton instance
voice_processor = VoiceProcessor()


async def process_voice_expense(message: types.Message, bot, user_language: str = 'ru') -> Optional[str]:
    """Helper function for easy integration - использует оптимизированную версию из voice_recognition.py"""
    from .voice_recognition import process_voice_for_expense
    return await process_voice_for_expense(message, bot, user_language)