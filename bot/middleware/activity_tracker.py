"""
Middleware для отслеживания активности пользователей и отправки уведомлений админу
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from django.core.cache import cache
from django.conf import settings
import asyncio

from bot.utils.logging_safe import log_safe_id, sanitize_callback_action

logger = logging.getLogger(__name__)


class ActivityTrackerMiddleware(BaseMiddleware):
    """Middleware для отслеживания активности пользователей"""
    
    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'unique_users': set(),
            'commands': {},
            'errors': []
        }
        self.last_report_time = datetime.now()
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обработка события"""
        user = None
        command = None
        
        # Получаем пользователя и команду
        if isinstance(event, Message):
            user = event.from_user
            if event.text and event.text.startswith('/'):
                command = event.text.split()[0]
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            callback_action, _ = sanitize_callback_action(event.data)
            command = f"callback:{callback_action}"
            
        if user:
            # Обновляем статистику
            self.stats['total_requests'] += 1
            self.stats['unique_users'].add(user.id)
            
            if command:
                self.stats['commands'][command] = self.stats['commands'].get(command, 0) + 1
            
            # Отслеживаем активность пользователя
            await self._track_user_activity(user.id)
        
        try:
            # Вызываем основной обработчик
            return await handler(event, data)
        except Exception as e:
            # Логируем ошибку
            error_info = {
                'time': datetime.now().isoformat(),
                'user_ref': log_safe_id(user.id, 'user') if user else None,
                'error': str(e),
                'command': command
            }
            self.stats['errors'].append(error_info)
            
            # Отправляем уведомление админу о критической ошибке
            if len(self.stats['errors']) >= 5:
                await self._send_error_alert()
                
            raise
            
    async def _track_user_activity(self, user_id: int):
        """Отслеживание активности пользователя"""
        activity_key = f"user_activity:{user_id}"
        last_activity_key = f"user_last_activity:{user_id}"
        
        # Получаем текущую активность
        activity_count = cache.get(activity_key, 0)
        activity_count += 1
        
        # Сохраняем обновленную активность
        cache.set(activity_key, activity_count, 3600)  # Храним час
        cache.set(last_activity_key, datetime.now().isoformat(), 86400)  # Храним сутки
        
        # Проверяем подозрительную активность
        if activity_count > 100:  # Более 100 запросов в час
            await self._send_suspicious_activity_alert(user_id, activity_count)
            
                
    async def _send_suspicious_activity_alert(self, user_id: int, activity_count: int):
        """Отправка уведомления о подозрительной активности"""
        alert_key = f"suspicious_alert_sent:{user_id}"
        
        if not cache.get(alert_key):
            from bot.services.admin_notifier import send_admin_alert
            
            message = (
                f"⚠️ *\\[Coins\\] Подозрительная активность*\n\n"
                f"User ID: `{user_id}`\n"
                f"Количество запросов за час: {activity_count}\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Возможно, это спам или автоматизированные запросы"
            )
            
            try:
                await send_admin_alert(message)
                cache.set(alert_key, True, 1800)  # Не отправляем повторно 30 минут
            except Exception as e:
                logger.error(f"Ошибка отправки алерта о подозрительной активности: {e}")
                
    async def _send_error_alert(self):
        """Отправка уведомления о множественных ошибках"""
        alert_key = "multiple_errors_alert"
        
        if not cache.get(alert_key):
            from bot.services.admin_notifier import send_admin_alert
            
            recent_errors = self.stats['errors'][-5:]
            error_details = "\n".join([
                f"• {err['time']}: {err['command'] or 'unknown'} - {err['error'][:50]}"
                for err in recent_errors
            ])
            
            message = (
                f"🚨 *\\[Coins\\] Множественные ошибки в боте*\n\n"
                f"Количество ошибок: {len(self.stats['errors'])}\n"
                f"Последние ошибки:\n{error_details}\n\n"
                f"Требуется проверка логов\\!"
            )
            
            try:
                await send_admin_alert(message)
                cache.set(alert_key, True, 600)  # Не отправляем повторно 10 минут
                self.stats['errors'] = []  # Очищаем список ошибок
            except Exception as e:
                logger.error(f"Ошибка отправки алерта об ошибках: {e}")
                
    async def get_daily_stats(self) -> Dict:
        """Получение статистики за день"""
        return {
            'total_requests': self.stats['total_requests'],
            'unique_users': len(self.stats['unique_users']),
            'popular_commands': sorted(
                self.stats['commands'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10],
            'errors_count': len(self.stats['errors'])
        }
        
    def reset_stats(self):
        """Сброс статистики"""
        self.stats = {
            'total_requests': 0,
            'unique_users': set(),
            'commands': {},
            'errors': []
        }
        self.last_report_time = datetime.now()


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для ограничения частоты запросов"""

    def __init__(self, messages_per_minute: int = 120, messages_per_hour: int = 3000):
        self.messages_per_minute = messages_per_minute
        self.messages_per_hour = messages_per_hour
        
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка rate limit"""
        user = None
        
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
            
        if user:
            # Проверяем лимиты
            if not await self._check_rate_limit(user.id):
                # Отправляем предупреждение пользователю
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ Слишком много запросов. Пожалуйста, подождите немного.",
                        show_alert=False
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "⚠️ Слишком много запросов. Подождите немного.",
                        show_alert=True
                    )
                return None
                
        return await handler(event, data)
        
    async def _check_rate_limit(self, user_id: int) -> bool:
        """Проверка rate limit для пользователя"""
        # Ключи для минутного и часового лимитов
        minute_key = f"rate_limit:minute:{user_id}"
        hour_key = f"rate_limit:hour:{user_id}"
        
        # Получаем текущие счетчики
        minute_count = cache.get(minute_key, 0)
        hour_count = cache.get(hour_key, 0)
        
        # Проверяем лимиты
        if minute_count >= self.messages_per_minute:
            logger.warning("Rate limit превышен для %s (минутный)", log_safe_id(user_id, "user"))
            return False
            
        if hour_count >= self.messages_per_hour:
            logger.warning("Rate limit превышен для %s (часовой)", log_safe_id(user_id, "user"))
            
            # Отправляем уведомление админу о блокировке
            from bot.services.admin_notifier import send_admin_alert
            message = (
                f"🚫 *\\[Coins\\] Пользователь заблокирован rate limiter*\n\n"
                f"User: `{log_safe_id(user_id, 'user')}`\n"
                f"Превышен часовой лимит: {hour_count}/{self.messages_per_hour}\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            asyncio.create_task(send_admin_alert(message))
            return False
            
        # Увеличиваем счетчики
        cache.set(minute_key, minute_count + 1, 60)
        cache.set(hour_key, hour_count + 1, 3600)
        
        return True
