"""
Mixin класс для централизованной ротации API ключей.
Устраняет дублирование кода между различными AI сервисами.
"""
import threading
import logging
from typing import Optional, List, ClassVar, Dict, Tuple
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


class KeyRotationMixin(ABC):
    """
    Mixin для round-robin ротации API ключей.
    Предоставляет thread-safe механизм переключения между ключами.
    """
    
    # Классовые переменные для отслеживания состояния ротации
    _key_index: ClassVar[int] = 0
    _key_lock: ClassVar[threading.Lock] = threading.Lock()
    # Отслеживание статуса ключей: {key_index: (is_working, last_error_time)}
    _key_status: ClassVar[Dict[int, Tuple[bool, Optional[datetime]]]] = {}
    
    @classmethod
    @abstractmethod
    def get_api_keys(cls) -> List[str]:
        """
        Возвращает список API ключей для ротации.
        Должен быть реализован в наследующем классе.
        
        Returns:
            List[str]: Список API ключей
        """
        pass
    
    @classmethod
    def get_next_key(cls) -> Optional[Tuple[str, int]]:
        """
        Thread-safe получение следующего ключа с round-robin ротацией.
        
        Returns:
            Optional[Tuple[str, int]]: Кортеж (API ключ, индекс ключа) или None если ключи отсутствуют
        """
        keys = cls.get_api_keys()
        if not keys:
            logger.warning(f"[{cls.__name__}] No API keys available for rotation")
            return None
        
        with cls._key_lock:
            attempts = 0
            max_attempts = len(keys)
            
            while attempts < max_attempts:
                current_index = cls._key_index
                cls._key_index = (cls._key_index + 1) % len(keys)
                
                # Проверяем статус ключа (если он был помечен как нерабочий)
                if current_index in cls._key_status:
                    is_working, last_error_time = cls._key_status[current_index]
                    if not is_working and last_error_time:
                        # Если ключ не работал, проверяем прошло ли 5 минут
                        if datetime.now() - last_error_time < timedelta(minutes=5):
                            logger.debug(f"[{cls.__name__}] Skipping key #{current_index + 1} (marked as failed)")
                            attempts += 1
                            continue
                        else:
                            # Прошло 5 минут, пробуем снова
                            logger.info(f"[{cls.__name__}] Retrying key #{current_index + 1} after cooldown")
                
                key = keys[current_index]
                logger.info(f"[{cls.__name__}] Using API key #{current_index + 1} of {len(keys)}")
                return key, current_index
                
            # Все ключи помечены как нерабочие
            logger.error(f"[{cls.__name__}] All {len(keys)} keys are marked as failed")
            # Возвращаем первый ключ как последнюю попытку
            return keys[0], 0
    
    @classmethod
    def mark_key_success(cls, key_index: int):
        """
        Отмечает ключ как рабочий.
        
        Args:
            key_index: Индекс ключа в списке
        """
        with cls._key_lock:
            cls._key_status[key_index] = (True, None)
            logger.debug(f"[{cls.__name__}] Key #{key_index + 1} marked as working")
    
    @classmethod
    def mark_key_failure(cls, key_index: int, error: Optional[Exception] = None):
        """
        Отмечает ключ как нерабочий.
        
        Args:
            key_index: Индекс ключа в списке
            error: Исключение, которое привело к ошибке
        """
        with cls._key_lock:
            cls._key_status[key_index] = (False, datetime.now())
            error_msg = str(error)[:100] if error else "Unknown error"
            logger.error(f"[{cls.__name__}] Key #{key_index + 1} marked as failed: {error_msg}")
    
    @classmethod
    def get_key_name(cls, key_index: int) -> str:
        """
        Возвращает человекочитаемое имя ключа для логирования.
        
        Args:
            key_index: Индекс ключа
            
        Returns:
            str: Название ключа (например, "GOOGLE_API_KEY_1")
        """
        return f"{cls.__name__.replace('KeyRotationMixin', '').upper()}_API_KEY_{key_index + 1}"
    
    @classmethod
    def reset_rotation(cls):
        """Сбрасывает индекс ротации и статусы ключей."""
        with cls._key_lock:
            cls._key_index = 0
            cls._key_status = {}
            logger.info(f"[{cls.__name__}] Key rotation index and status reset")


class GoogleKeyRotationMixin(KeyRotationMixin):
    """
    Специализированный mixin для ротации Google API ключей.
    Автоматически загружает ключи из настроек Django.
    """
    
    @classmethod
    def get_api_keys(cls) -> List[str]:
        """
        Возвращает список Google API ключей из настроек.
        
        Returns:
            List[str]: Список Google API ключей
        """
        if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
            return settings.GOOGLE_API_KEYS
        return []
    
    @classmethod
    def get_key_name(cls, key_index: int) -> str:
        """Возвращает имя Google API ключа."""
        return f"GOOGLE_API_KEY_{key_index + 1}"


class OpenAIKeyRotationMixin(KeyRotationMixin):
    """
    Специализированный mixin для ротации OpenAI API ключей.
    Автоматически загружает ключи из настроек Django.
    """
    
    @classmethod
    def get_api_keys(cls) -> List[str]:
        """
        Возвращает список OpenAI API ключей из настроек.
        
        Returns:
            List[str]: Список OpenAI API ключей
        """
        if hasattr(settings, 'OPENAI_API_KEYS') and settings.OPENAI_API_KEYS:
            return settings.OPENAI_API_KEYS
        # Fallback на единичный ключ если пул не настроен
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            return [settings.OPENAI_API_KEY]
        return []
    
    @classmethod
    def get_key_name(cls, key_index: int) -> str:
        """Возвращает имя OpenAI API ключа."""
        # Если используется единичный ключ
        if hasattr(settings, 'OPENAI_API_KEY') and not hasattr(settings, 'OPENAI_API_KEYS'):
            return "OPENAI_API_KEY"
        return f"OPENAI_API_KEY_{key_index + 1}"