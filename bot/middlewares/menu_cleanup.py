"""
Middleware для автоматического закрытия старых меню при новых сообщениях
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from ..utils.message_utils import delete_message_with_effect
import asyncio
import logging

logger = logging.getLogger(__name__)


class MenuCleanupMiddleware(BaseMiddleware):
    """Middleware для закрытия старых меню при любом новом сообщении от пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем callback queries
        if isinstance(event, CallbackQuery):
            return await handler(event, data)
            
        # Получаем состояние из контекста
        state: FSMContext = data.get('state')
        
        if state and isinstance(event, Message):
            # Получаем ID последнего меню
            state_data = await state.get_data()
            old_menu_id = state_data.get('last_menu_message_id')
            
            # Если есть старое меню, удаляем его
            if old_menu_id:
                try:
                    # Асинхронно удаляем старое меню
                    asyncio.create_task(
                        delete_message_with_effect(
                            event.bot, 
                            event.chat.id, 
                            old_menu_id,
                            delay=0.1  # Быстрое удаление
                        )
                    )
                    # Очищаем ID из состояния
                    await state.update_data(last_menu_message_id=None)
                    logger.debug(f"Deleted old menu {old_menu_id} for user {event.from_user.id}")
                except Exception as e:
                    logger.debug(f"Failed to delete old menu: {e}")
        
        # Вызываем обработчик
        return await handler(event, data)