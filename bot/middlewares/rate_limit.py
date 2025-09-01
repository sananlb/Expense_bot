"""
Rate limiting middleware для Expense Bot
"""
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from django.conf import settings
import asyncio

from .security import RateLimiter, log_security_event

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Advanced rate limiting middleware с поддержкой aiogram 3.x"""
    
    def __init__(self, 
                 requests_per_minute: int = None,
                 requests_per_hour: int = None,
                 burst_size: int = 10,
                 use_redis: bool = True):
        super().__init__()
        
        # Используем настройки из settings.py или переданные параметры
        self.requests_per_minute = requests_per_minute or getattr(
            settings, 'BOT_RATE_LIMIT_MESSAGES_PER_MINUTE', 100
        )
        self.requests_per_hour = requests_per_hour or getattr(
            settings, 'BOT_RATE_LIMIT_MESSAGES_PER_HOUR', 2000
        )
        self.burst_size = burst_size
        self.use_redis = use_redis
        
        # Локальное хранилище (резервное)
        self.user_requests: Dict[int, list] = defaultdict(list)
        self.user_warnings: Dict[int, int] = defaultdict(int)
        self.blocked_users: Dict[int, datetime] = {}
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'unique_users': set(),
        }
        
        # Запускаем периодическую очистку
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._stats_reporter())
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Обработчик middleware для aiogram 3.x"""
        # Получаем пользователя из события
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        elif hasattr(event, 'from_user'):
            user = event.from_user
        
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        now = datetime.now()
        
        # Обновляем статистику
        self.stats['total_requests'] += 1
        self.stats['unique_users'].add(user_id)
        
        # Проверяем Redis rate limiter если доступен
        if self.use_redis:
            try:
                # Проверяем минутный лимит
                if not RateLimiter.check_rate_limit(
                    user_id, 'messages_minute', 
                    self.requests_per_minute, 60
                ):
                    await self._handle_rate_limit_exceeded(
                        event, user_id, 'minute', 
                        RateLimiter.get_remaining_time(user_id, 'messages_minute')
                    )
                    return
                
                # Проверяем часовой лимит
                if not RateLimiter.check_rate_limit(
                    user_id, 'messages_hour',
                    self.requests_per_hour, 3600
                ):
                    await self._handle_rate_limit_exceeded(
                        event, user_id, 'hour',
                        RateLimiter.get_remaining_time(user_id, 'messages_hour')
                    )
                    return
                    
            except Exception as e:
                logger.error(f"Redis rate limiter error: {e}")
                # Fallback на локальный rate limiter
        
        # Локальная проверка (резервная или основная)
        if not self.use_redis or True:  # Всегда проверяем burst
            # Проверяем блокировку
            if user_id in self.blocked_users:
                if now < self.blocked_users[user_id]:
                    remaining = (self.blocked_users[user_id] - now).seconds
                    await self._handle_blocked_user(event, user_id, remaining)
                    return
                else:
                    del self.blocked_users[user_id]
                    self.user_warnings[user_id] = 0
            
            # Очищаем старые запросы
            self._cleanup_user_requests(user_id, now)
            
            # Проверяем burst
            if self._check_burst(user_id):
                self.blocked_users[user_id] = now + timedelta(minutes=5)
                await self._handle_burst_detected(event, user_id)
                return
            
            # Добавляем текущий запрос
            self.user_requests[user_id].append(now)
        
        # Передаем управление следующему обработчику
        return await handler(event, data)
    
    def _cleanup_user_requests(self, user_id: int, now: datetime):
        """Очистка старых запросов пользователя"""
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > hour_ago
        ]
    
    def _check_burst(self, user_id: int) -> bool:
        """Проверка на burst активность"""
        if len(self.user_requests[user_id]) < self.burst_size:
            return False
        
        recent_requests = self.user_requests[user_id][-self.burst_size:]
        time_diff = (recent_requests[-1] - recent_requests[0]).total_seconds()
        
        return time_diff < 2  # burst_size запросов за 2 секунды
    
    async def _handle_rate_limit_exceeded(self, event: Any, user_id: int, 
                                         limit_type: str, remaining_seconds: int):
        """Обработка превышения rate limit"""
        self.stats['blocked_requests'] += 1
        
        log_security_event(
            'rate_limit_exceeded',
            user_id,
            {'type': limit_type, 'remaining_seconds': remaining_seconds}
        )
        
        if limit_type == 'minute':
            message = f"⚠️ Превышен лимит сообщений в минуту ({self.requests_per_minute}).\n"
        else:
            message = f"⚠️ Превышен часовой лимит сообщений ({self.requests_per_hour}).\n"
        
        message += f"Попробуйте через {remaining_seconds} секунд."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
    
    async def _handle_burst_detected(self, event: Any, user_id: int):
        """Обработка обнаружения burst"""
        log_security_event(
            'burst_activity_detected',
            user_id,
            {'burst_size': self.burst_size}
        )
        
        message = "⛔ Обнаружена подозрительная активность.\nВы временно заблокированы на 5 минут."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
    
    async def _handle_blocked_user(self, event: Any, user_id: int, 
                                  remaining_seconds: int):
        """Обработка заблокированного пользователя"""
        self.user_warnings[user_id] += 1
        
        # Показываем сообщение только каждое 10-е обращение
        if self.user_warnings[user_id] % 10 == 0:
            message = f"🚫 Вы временно заблокированы.\nОсталось: {remaining_seconds} секунд."
            
            if isinstance(event, Message):
                await event.answer(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
    
    async def _cleanup_loop(self):
        """Периодическая очистка данных"""
        while True:
            await asyncio.sleep(300)  # Каждые 5 минут
            try:
                now = datetime.now()
                hour_ago = now - timedelta(hours=1)
                
                # Очищаем старые запросы
                for user_id in list(self.user_requests.keys()):
                    self.user_requests[user_id] = [
                        req_time for req_time in self.user_requests[user_id]
                        if req_time > hour_ago
                    ]
                    if not self.user_requests[user_id]:
                        del self.user_requests[user_id]
                
                # Очищаем истекшие блокировки
                for user_id in list(self.blocked_users.keys()):
                    if self.blocked_users[user_id] < now:
                        del self.blocked_users[user_id]
                        if user_id in self.user_warnings:
                            del self.user_warnings[user_id]
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _stats_reporter(self):
        """Периодический отчет статистики"""
        while True:
            await asyncio.sleep(3600)  # Каждый час
            try:
                logger.info(
                    f"Rate limiter stats: "
                    f"requests={self.stats['total_requests']}, "
                    f"blocked={self.stats['blocked_requests']}, "
                    f"unique_users={len(self.stats['unique_users'])}"
                )
                # Сброс статистики
                self.stats['blocked_requests'] = 0
                self.stats['unique_users'].clear()
            except Exception as e:
                logger.error(f"Error in stats reporter: {e}")