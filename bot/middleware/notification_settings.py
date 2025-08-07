"""
Middleware для обработки состояний настроек уведомлений
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.routers.settings import NotificationStates
import logging

logger = logging.getLogger(__name__)


class NotificationSettingsMiddleware(BaseMiddleware):
    """
    Middleware для автоматической очистки состояний настроек уведомлений
    при вводе команд или других действиях
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обработка входящих событий"""
        
        # Получаем FSM контекст если он есть
        state: FSMContext = data.get('state')
        if not state:
            return await handler(event, data)
            
        # Получаем текущее состояние
        current_state = await state.get_state()
        
        # Проверяем, находимся ли мы в процессе настройки уведомлений
        if current_state and current_state.startswith('NotificationStates:'):
            # Проверяем тип события
            if isinstance(event, Message):
                # Если это команда - очищаем состояние
                if event.text and event.text.startswith('/'):
                    await state.clear()
                    logger.info(f"Cleared notification settings state due to command: {event.text}")
                    
            elif isinstance(event, CallbackQuery):
                # Проверяем callback_data
                if event.data and not any(prefix in event.data for prefix in [
                    'notif_', 'weekday_', 'time_', 'back_to_notifications', 
                    'toggle_weekly', 'toggle_monthly', 'save_notif_time'
                ]):
                    # Если это не связано с настройками уведомлений - очищаем состояние
                    await state.clear()
                    logger.info(f"Cleared notification settings state due to unrelated callback: {event.data}")
        
        # Продолжаем обработку
        return await handler(event, data)