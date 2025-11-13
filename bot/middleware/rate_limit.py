"""
Rate limiting middleware для защиты от спама
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""

    def __init__(self, rate_limit: int = 120, time_window: int = 60):
        """
        Args:
            rate_limit: Максимальное количество запросов
            time_window: Временное окно в секундах
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.user_requests = {}  # {user_id: [timestamp1, timestamp2, ...]}
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка rate limit перед обработкой"""
        user_id = event.from_user.id
        current_time = datetime.now()
        
        # Очищаем старые записи
        if user_id in self.user_requests:
            # Оставляем только записи в пределах временного окна
            cutoff_time = current_time - timedelta(seconds=self.time_window)
            self.user_requests[user_id] = [
                timestamp for timestamp in self.user_requests[user_id]
                if timestamp > cutoff_time
            ]
        else:
            self.user_requests[user_id] = []
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            # Превышен лимит
            logger.warning(f"Rate limit exceeded for user {user_id}")
            
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Слишком много запросов. Подождите немного и попробуйте снова."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком много запросов. Подождите немного.",
                    show_alert=True
                )
            return  # Не вызываем handler
        
        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)
        
        # Вызываем handler
        return await handler(event, data)


class CommandRateLimitMiddleware(BaseMiddleware):
    """Специальный rate limit для команд"""
    
    def __init__(self):
        """Настройки лимитов для разных команд"""
        self.command_limits = {
            '/start': {'limit': 10, 'window': 60},  # Увеличено с 3 до 10
            '/help': {'limit': 15, 'window': 60},  # Увеличено с 5 до 15
            '/add': {'limit': 200, 'window': 86400},  # Увеличено с 100 до 200 в день
            '/categories': {'limit': 30, 'window': 60},  # Увеличено с 10 до 30
            '/recurring': {'limit': 30, 'window': 60},  # Увеличено с 10 до 30
            '/settings': {'limit': 30, 'window': 60},  # Увеличено с 10 до 30
            '/today': {'limit': 50, 'window': 60},  # Увеличено с 20 до 50
            '/month': {'limit': 50, 'window': 60},  # Увеличено с 20 до 50
            '/chat': {'limit': 60, 'window': 60},  # Увеличено с 30 до 60 для AI чата
        }
        self.default_limit = {'limit': 40, 'window': 60}  # Увеличено с 15 до 40
        self.user_commands = {}  # {user_id: {command: [timestamps]}}
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка rate limit для команд"""
        # Проверяем только сообщения с командами
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)
        
        # Извлекаем команду
        text = event.text.strip()
        if not text.startswith('/'):
            return await handler(event, data)
        
        command = text.split()[0].split('@')[0].lower()
        user_id = event.from_user.id
        current_time = datetime.now()
        
        # Получаем лимиты для команды
        limits = self.command_limits.get(command, self.default_limit)
        rate_limit = limits['limit']
        time_window = limits['window']
        
        # Инициализируем структуру для пользователя
        if user_id not in self.user_commands:
            self.user_commands[user_id] = {}
        if command not in self.user_commands[user_id]:
            self.user_commands[user_id][command] = []
        
        # Очищаем старые записи
        cutoff_time = current_time - timedelta(seconds=time_window)
        self.user_commands[user_id][command] = [
            timestamp for timestamp in self.user_commands[user_id][command]
            if timestamp > cutoff_time
        ]
        
        # Проверяем лимит
        if len(self.user_commands[user_id][command]) >= rate_limit:
            logger.warning(f"Command rate limit exceeded for user {user_id}, command {command}")
            
            if command == '/add':
                await event.answer(
                    "⚠️ Достигнут дневной лимит добавления расходов (100 записей).\n"
                    "Попробуйте завтра."
                )
            elif command == '/chat':
                await event.answer(
                    "⚠️ AI чат временно недоступен из-за превышения лимита запросов.\n"
                    "Попробуйте через минуту."
                )
            else:
                await event.answer(
                    f"⚠️ Слишком много запросов команды {command}.\n"
                    f"Подождите немного и попробуйте снова."
                )
            return  # Не вызываем handler
        
        # Добавляем текущий запрос
        self.user_commands[user_id][command].append(current_time)
        
        # Вызываем handler
        return await handler(event, data)