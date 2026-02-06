"""
Logging middleware для Expense Bot
"""
import time
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery, InlineQuery

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Advanced logging middleware с структурированным логированием"""
    
    def __init__(self):
        super().__init__()
        self.request_count = 0
        self.start_time = time.time()

        # Статистика по типам сообщений
        self.message_types = defaultdict(int)

        # Логгер для аудита
        self.audit_logger = logging.getLogger('audit')

        # Логгер для отслеживания callback (отдельный файл)
        self.callback_logger = logging.getLogger('callback_tracking')
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Structured logging of all requests для aiogram 3.x"""
        self.request_count += 1
        request_start = time.time()
        
        # Получаем информацию о пользователе и чате
        user = None
        chat = None
        
        if isinstance(event, Message):
            user = event.from_user
            chat = event.chat
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            if event.message:
                chat = event.message.chat
        elif isinstance(event, InlineQuery):
            user = event.from_user
        
        # Базовая информация
        log_data = {
            'request_id': self.request_count,
            'timestamp': datetime.now().isoformat(),
            'user_id': user.id if user else None,
            # 'username': УДАЛЕНО для privacy (GDPR compliance)
            'chat_id': chat.id if chat else None,
            'chat_type': chat.type if chat else None,
        }
        
        # Определяем тип сообщения
        message_type = self._get_message_type(event)
        log_data['message_type'] = message_type
        self.message_types[message_type] += 1
        
        # Дополнительная информация в зависимости от типа
        if isinstance(event, Message):
            log_data['message_id'] = event.message_id
            if event.text:
                log_data['text_length'] = len(event.text)
                # Логируем команды
                if event.text.startswith('/'):
                    log_data['command'] = event.text.split()[0]
            elif event.photo:
                log_data['photo_count'] = len(event.photo)
                log_data['photo_size'] = event.photo[-1].file_size
            elif event.voice:
                log_data['voice_duration'] = event.voice.duration
                log_data['voice_size'] = event.voice.file_size
        elif isinstance(event, CallbackQuery):
            # Полный callback_data без обрезания
            callback_data = event.data or ""
            log_data['callback_data'] = callback_data

            # Умный парсинг: отделяем числовые параметры с конца
            # edit_expense_456 -> action: edit_expense, params: 456
            # set_category_15_42 -> action: set_category, params: 15_42
            # expenses_today -> action: expenses_today, params: ""
            parts = callback_data.split('_')

            # Найти индекс первого числового параметра с конца
            param_start_idx = len(parts)
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].isdigit():
                    param_start_idx = i
                else:
                    break

            if param_start_idx < len(parts):
                log_data['callback_action'] = '_'.join(parts[:param_start_idx])
                log_data['callback_params'] = '_'.join(parts[param_start_idx:])
            else:
                log_data['callback_action'] = callback_data
                log_data['callback_params'] = ""

            # Дополнительные поля для отладки
            log_data['callback_id'] = event.id
            if event.message:
                log_data['message_id'] = event.message.message_id

            # Логируем в отдельный файл для callback
            self.callback_logger.info(json.dumps(log_data, ensure_ascii=False))
        
        # Логируем
        logger.info(f"Request: {json.dumps(log_data, ensure_ascii=False)}")
        
        # Аудит лог для важных действий
        if message_type in ['photo', 'voice', 'callback_query', 'command']:
            # Для callback используем callback_action для более детального логирования
            action_detail = log_data.get('callback_action', message_type)
            self.audit_logger.info(
                f"AUDIT: user={user.id if user else 'unknown'} "
                f"action={action_detail} "
                f"details={log_data}"
            )
        
        # Сохраняем время начала обработки
        data['request_start'] = request_start
        
        try:
            # Выполняем обработчик
            result = await handler(event, data)
            
            # Измеряем время обработки
            duration = time.time() - request_start
            
            # Логируем медленные запросы
            if duration > 6.0:  # Более 6 секунд
                logger.warning(
                    f"Slow request detected: "
                    f"type={message_type}, "
                    f"duration={duration:.2f}s, "
                    f"user={user.id if user else 'unknown'}"
                )
            
            # Периодическая статистика
            if self.request_count % 1000 == 0:
                self._log_statistics()
            
            return result
            
        except Exception as e:
            # Логируем ошибки
            duration = time.time() - request_start
            logger.error(
                f"Request error: "
                f"type={message_type}, "
                f"duration={duration:.2f}s, "
                f"user={user.id if user else 'unknown'}, "
                f"error={str(e)}"
            )
            raise
    
    def _get_message_type(self, event: Any) -> str:
        """Определение типа сообщения"""
        if isinstance(event, Message):
            if event.text:
                if event.text.startswith('/'):
                    return 'command'
                return 'text'
            elif event.photo:
                return 'photo'
            elif event.voice:
                return 'voice'
            elif event.document:
                return 'document'
            elif event.location:
                return 'location'
            else:
                return 'other_message'
        elif isinstance(event, CallbackQuery):
            return 'callback_query'
        elif isinstance(event, InlineQuery):
            return 'inline_query'
        else:
            return 'unknown'
    
    def _log_statistics(self):
        """Логирование статистики"""
        uptime = time.time() - self.start_time
        rps = self.request_count / uptime if uptime > 0 else 0
        
        stats = {
            'total_requests': self.request_count,
            'uptime_seconds': int(uptime),
            'requests_per_second': round(rps, 2),
            'message_types': dict(self.message_types),
        }
        
        logger.info(f"Statistics: {json.dumps(stats)}")