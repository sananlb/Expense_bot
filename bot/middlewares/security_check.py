"""
Security middleware для проверки контента в Expense Bot
"""
import hashlib
import logging
from collections import defaultdict
from typing import Dict, Any, Callable, Awaitable, Set
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from django.conf import settings

from .security import SecurityValidator, FileValidator, log_security_event

logger = logging.getLogger(__name__)


class SecurityCheckMiddleware(BaseMiddleware):
    """Enhanced security middleware для проверки контента"""
    
    def __init__(self):
        super().__init__()
        
        # Расширенный список опасных паттернов
        self.suspicious_patterns = [
            # Code injection
            'script', 'eval', 'exec', '__import__', 'compile',
            'subprocess', 'os.system', 'open(', 'file(',
            
            # SQL injection
            'DROP TABLE', 'DELETE FROM', 'INSERT INTO', 'UPDATE SET',
            'UNION SELECT', 'OR 1=1', 'AND 1=1',
            
            # Path traversal
            '../', '..\\', '%2e%2e', '..%2F', '..%5C',
            '/etc/passwd', 'C:\\Windows',
            
            # XSS attempts
            '<script', 'javascript:', 'onerror=', 'onclick=',
            ' onload=', 'onmouseover=', '<iframe', '<embed',
            
            # Command injection
            '; ls', '| cat', '&& rm', '|| wget',
            '`', '$('
        ]
        
        # Honeypot токены для обнаружения сканеров
        self.honeypot_tokens = [
            'root', 'password123',
            'secret_key', 'api_token'
        ]
        
        # Статистика безопасности
        self.security_stats = defaultdict(int)
        
        # Кеш для проверенных сообщений
        self.checked_messages: Set[str] = set()
        
        # Максимальная длина сообщения
        self.max_message_length = getattr(settings, 'BOT_MAX_MESSAGE_LENGTH', 4096)
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Comprehensive security check для aiogram 3.x"""
        # Получаем сообщение и пользователя
        message = None
        user = None
        text = None
        
        if isinstance(event, Message):
            message = event
            user = event.from_user
            text = event.text or event.caption
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            # Callback queries обычно безопасны, но проверим data
            text = event.data
            
            # Пропускаем проверку для системных callback
            if text and any(text.startswith(prefix) for prefix in [
                'subscription_', 'sub_', 'menu_', 'expenses_', 'close',
                'pdf_', 'cashback_', 'referral_', 'settings_', 'category_'
            ]):
                return await handler(event, data)
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # Если нет текста и это не медиа-сообщение, пропускаем
        if not text and not (message and (message.photo or message.voice or message.document)):
            return await handler(event, data)
        
        # Проверяем текст если есть
        if text:
            # Пропускаем проверку для команд
            if isinstance(event, Message) and event.text and event.text.startswith('/'):
                # Это команда, пропускаем проверку паттернов
                return await handler(event, data)
            
            # Пропускаем проверку при редактировании трат и добавлении новых трат
            state = data.get('state')
            if state:
                current_state = await state.get_state()
                if current_state and ('EditExpenseForm' in str(current_state) or 'ExpenseForm' in str(current_state)):
                    return await handler(event, data)
            
            # Создаем хеш сообщения для кеша
            message_hash = hashlib.md5(text.encode()).hexdigest()
            if message_hash in self.checked_messages:
                return await handler(event, data)  # Уже проверено
            
            # Проверка на подозрительные паттерны
            detected_patterns = self._check_patterns(text)
            if detected_patterns:
                await self._handle_suspicious_content(
                    event, user_id, 'patterns', detected_patterns
                )
                return
            
            # Проверка на honeypot токены
            if self._check_honeypot(text):
                await self._handle_suspicious_content(
                    event, user_id, 'honeypot', ['honeypot_triggered']
                )
                return
            
            # Проверка длины сообщения
            if len(text) > self.max_message_length:
                await self._handle_oversized_content(event, len(text))
                return
            
            # Проверка на спам (повторяющиеся символы)
            if self._check_spam_patterns(text):
                await self._handle_suspicious_content(
                    event, user_id, 'spam', ['spam_pattern']
                )
                return
            
            # Добавляем в кеш проверенных
            self.checked_messages.add(message_hash)
            
            # Очищаем кеш если слишком большой
            if len(self.checked_messages) > 10000:
                self.checked_messages.clear()
        
        # Проверка файлов (только для сообщений)
        if message:
            if message.photo:
                if not await self._check_photo(message, user_id):
                    return
            elif message.voice:
                if not await self._check_voice(message, user_id):
                    return
            elif message.document:
                await self._handle_document(message, user_id)
                return
        
        # Передаем управление следующему обработчику
        return await handler(event, data)
    
    def _check_patterns(self, text: str) -> list:
        """Проверка на опасные паттерны"""
        text_lower = text.lower()
        detected = []
        
        for pattern in self.suspicious_patterns:
            pattern_lower = pattern.lower()
            # Для HTML/JS паттернов проверяем точное вхождение
            if pattern_lower.startswith('<') or '=' in pattern_lower or pattern_lower.startswith('javascript'):
                if pattern_lower in text_lower:
                    detected.append(pattern)
                    self.security_stats[f'pattern_{pattern}'] += 1
            # Для SQL команд проверяем с пробелами
            elif pattern_lower.startswith('drop') or pattern_lower.startswith('delete') or pattern_lower.startswith('insert') or pattern_lower.startswith('update'):
                if f' {pattern_lower} ' in f' {text_lower} ':
                    detected.append(pattern)
                    self.security_stats[f'pattern_{pattern}'] += 1
            # Для остальных - обычная проверка
            elif pattern_lower in text_lower:
                detected.append(pattern)
                self.security_stats[f'pattern_{pattern}'] += 1
        
        return detected
    
    def _check_honeypot(self, text: str) -> bool:
        """Проверка honeypot токенов"""
        text_lower = text.lower()
        for token in self.honeypot_tokens:
            if token in text_lower:
                self.security_stats['honeypot_triggered'] += 1
                return True
        return False
    
    def _check_spam_patterns(self, text: str) -> bool:
        """Проверка на спам паттерны"""
        # Проверка на повторяющиеся символы
        for i in range(len(text) - 2):
            if text[i] == text[i+1] == text[i+2]:
                # 3+ одинаковых символа подряд
                char_count = 3
                for j in range(i+3, len(text)):
                    if text[j] == text[i]:
                        char_count += 1
                    else:
                        break
                if char_count > 10:  # Более 10 одинаковых символов
                    return True
        
        # Проверка на CAPS LOCK спам
        upper_count = sum(1 for c in text if c.isupper())
        if len(text) > 10 and upper_count / len(text) > 0.7:
            return True
        
        return False
    
    async def _check_photo(self, message: Message, user_id: int) -> bool:
        """Проверка загружаемого фото"""
        photo = message.photo[-1]  # Берем самое большое фото
        
        try:
            FileValidator.validate_photo(
                photo.file_size,
                getattr(photo, 'mime_type', None)
            )
            return True
        except Exception as e:
            await message.answer(str(e))
            log_security_event(
                'invalid_photo_upload',
                user_id,
                {'size': photo.file_size, 'error': str(e)}
            )
            return False
    
    async def _check_voice(self, message: Message, user_id: int) -> bool:
        """Проверка голосового сообщения"""
        voice = message.voice
        
        try:
            FileValidator.validate_voice(
                voice.file_size,
                voice.duration
            )
            return True
        except Exception as e:
            await message.answer(str(e))
            log_security_event(
                'invalid_voice_upload',
                user_id,
                {'size': voice.file_size, 'duration': voice.duration, 'error': str(e)}
            )
            return False
    
    async def _handle_document(self, message: Message, user_id: int):
        """Обработка документов (не поддерживается)"""
        await message.answer(
            "📄 Загрузка документов не поддерживается.\n"
            "Пожалуйста, отправьте текстовое сообщение с описанием расхода."
        )
        
        log_security_event(
            'document_upload_attempt',
            user_id,
            {'filename': message.document.file_name}
        )
    
    async def _handle_suspicious_content(self, event: Any, user_id: int,
                                       threat_type: str, patterns: list):
        """Обработка подозрительного контента"""
        log_security_event(
            f'suspicious_content_{threat_type}',
            user_id,
            {
                'patterns': patterns,
                'text_sample': None  # Не логируем текст для безопасности
            }
        )
        
        message = "⚠️ Обнаружен недопустимый контент. Запрос отклонен."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
    
    async def _handle_oversized_content(self, event: Any, size: int):
        """Обработка слишком большого контента"""
        message = f"❌ Сообщение слишком длинное ({size} символов).\nМаксимум: {self.max_message_length} символов."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)