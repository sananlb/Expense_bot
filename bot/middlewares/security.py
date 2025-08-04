"""
Модуль безопасности для Expense Bot
"""
import re
import html
import hashlib
import secrets
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Валидатор безопасности для пользовательского ввода"""
    
    # Паттерны потенциально опасного контента
    DANGEROUS_PATTERNS = [
        # SQL инъекции
        r"(union|select|insert|update|delete|drop|create|alter|exec|execute)\s+",
        # XSS попытки
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        # Path traversal
        r"\.\./",
        r"\.\.\\",
        # Command injection
        r"[;&|]\s*(ls|cat|rm|wget|curl|nc|bash|sh|cmd|powershell)",
        # LDAP injection
        r"[)(]*\*",
    ]
    
    # Максимальные размеры
    MAX_TEXT_LENGTH = 4096
    MAX_EXPENSE_DESCRIPTION_LENGTH = 255
    MAX_CATEGORY_NAME_LENGTH = 100
    
    @classmethod
    def validate_text_input(cls, text: str, field_name: str = "text") -> str:
        """
        Валидация текстового ввода
        
        Args:
            text: Входной текст
            field_name: Название поля для ошибок
            
        Returns:
            Очищенный текст
            
        Raises:
            ValidationError: Если текст содержит опасный контент
        """
        if not text:
            return ""
        
        # Проверка длины
        if len(text) > cls.MAX_TEXT_LENGTH:
            raise ValidationError(
                f"{field_name} слишком длинный. Максимум {cls.MAX_TEXT_LENGTH} символов."
            )
        
        # Проверка на опасные паттерны
        text_lower = text.lower()
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"Обнаружен опасный паттерн в {field_name}: {pattern}")
                raise ValidationError(
                    "Текст содержит недопустимые символы или команды."
                )
        
        # HTML escape для безопасности
        return html.escape(text.strip())
    
    @classmethod
    def validate_expense_description(cls, description: str) -> str:
        """Валидация описания расхода"""
        if not description:
            return ""
        
        if len(description) > cls.MAX_EXPENSE_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Описание расхода слишком длинное. Максимум {cls.MAX_EXPENSE_DESCRIPTION_LENGTH} символов."
            )
        
        # Разрешаем только буквы, цифры, пробелы, валюты и базовую пунктуацию
        allowed_pattern = r"^[а-яА-ЯёЁa-zA-Z0-9\s\-\.,!?()$€₽¥£₴₸]+$"
        if not re.match(allowed_pattern, description):
            raise ValidationError(
                "Описание расхода содержит недопустимые символы."
            )
        
        return description.strip()
    
    @classmethod
    def validate_category_name(cls, category_name: str) -> str:
        """Валидация названия категории"""
        if not category_name:
            raise ValidationError("Название категории не может быть пустым")
        
        if len(category_name) > cls.MAX_CATEGORY_NAME_LENGTH:
            raise ValidationError(
                f"Название категории слишком длинное. Максимум {cls.MAX_CATEGORY_NAME_LENGTH} символов."
            )
        
        # Разрешаем только буквы, цифры, пробелы и базовую пунктуацию
        allowed_pattern = r"^[а-яА-ЯёЁa-zA-Z0-9\s\-\.,!?()]+$"
        if not re.match(allowed_pattern, category_name):
            raise ValidationError(
                "Название категории содержит недопустимые символы."
            )
        
        return category_name.strip()
    
    @classmethod
    def validate_amount(cls, amount: Any) -> float:
        """Валидация суммы расхода"""
        try:
            amount_float = float(amount)
            if amount_float <= 0 or amount_float > 1000000:
                raise ValidationError(
                    "Сумма должна быть от 0.01 до 1,000,000"
                )
            return amount_float
        except (ValueError, TypeError):
            raise ValidationError("Некорректная сумма")
    
    @classmethod
    def sanitize_ai_prompt(cls, user_input: str) -> str:
        """
        Очистка пользовательского ввода для AI промптов
        Предотвращает prompt injection
        """
        # Удаляем потенциальные команды для AI
        dangerous_ai_patterns = [
            r"ignore.*previous.*instructions",
            r"forget.*everything",
            r"system.*prompt",
            r"you.*are.*now",
            r"act.*as",
            r"pretend.*to.*be",
            r"new.*instructions",
            r"</system>",
            r"<system>",
        ]
        
        cleaned = user_input
        for pattern in dangerous_ai_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Ограничиваем длину
        if len(cleaned) > 1000:
            cleaned = cleaned[:1000] + "..."
        
        return cleaned.strip()


class RateLimiter:
    """Rate limiter с Redis backend"""
    
    @classmethod
    def get_key(cls, user_id: int, action: str) -> str:
        """Генерация ключа для rate limiting"""
        return f"rate_limit:{action}:{user_id}"
    
    @classmethod
    def check_rate_limit(cls, user_id: int, action: str, max_requests: int, window_seconds: int) -> bool:
        """
        Проверка rate limit
        
        Returns:
            True если лимит не превышен, False если превышен
        """
        key = cls.get_key(user_id, action)
        
        try:
            # Для django-redis используем нативные методы Redis
            from django_redis import get_redis_connection
            conn = get_redis_connection("default")
            
            # Используем pipeline для атомарности
            pipe = conn.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            result = pipe.execute()
            
            current_count = result[0]
            
            if current_count > max_requests:
                # Превышен лимит
                return False
            
            return True
            
        except ImportError:
            # Fallback на обычный cache API
            current_count = cache.get(key, 0)
            
            if current_count >= max_requests:
                return False
            
            # Увеличиваем счетчик
            cache.set(key, current_count + 1, window_seconds)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке rate limit: {e}")
            # В случае ошибки разрешаем запрос
            return True
    
    @classmethod
    def get_remaining_time(cls, user_id: int, action: str) -> int:
        """Получить оставшееся время блокировки в секундах"""
        key = cls.get_key(user_id, action)
        try:
            # django-redis поддерживает ttl
            from django_redis import get_redis_connection
            conn = get_redis_connection("default")
            ttl = conn.ttl(key)
            return max(0, ttl) if ttl is not None else 0
        except Exception as e:
            logger.debug(f"Не удалось получить TTL: {e}")
            # Fallback - если ключ существует, возвращаем примерное время
            if cache.get(key) is not None:
                return 60
            return 0


class FileValidator:
    """Валидатор для загружаемых файлов"""
    
    # Разрешенные MIME types для фото
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/webp',
    ]
    
    # Максимальные размеры в байтах
    MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_VOICE_SIZE = 5 * 1024 * 1024   # 5 MB
    
    @classmethod
    def validate_photo(cls, file_size: int, mime_type: Optional[str] = None) -> None:
        """Валидация загружаемого фото"""
        if file_size > cls.MAX_PHOTO_SIZE:
            raise ValidationError(
                f"Фото слишком большое. Максимальный размер: {cls.MAX_PHOTO_SIZE // 1024 // 1024} МБ"
            )
        
        if mime_type and mime_type not in cls.ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                f"Неподдерживаемый тип файла. Разрешены: {', '.join(cls.ALLOWED_IMAGE_TYPES)}"
            )
    
    @classmethod
    def validate_voice(cls, file_size: int, duration: Optional[int] = None) -> None:
        """Валидация голосового сообщения"""
        if file_size > cls.MAX_VOICE_SIZE:
            raise ValidationError(
                f"Голосовое сообщение слишком большое. Максимальный размер: {cls.MAX_VOICE_SIZE // 1024 // 1024} МБ"
            )
        
        if duration and duration > 60:
            raise ValidationError(
                "Голосовое сообщение слишком длинное. Максимум: 60 секунд"
            )


def log_security_event(event_type: str, user_id: Optional[int], details: Dict[str, Any]):
    """Логирование событий безопасности"""
    logger.warning(
        f"SECURITY_EVENT: {event_type}",
        extra={
            'user_id': user_id,
            'event_type': event_type,
            'details': details,
            'timestamp': timezone.now().isoformat(),
        }
    )