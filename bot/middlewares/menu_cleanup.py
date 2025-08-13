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
        
        # Сохраняем информацию о старом меню для удаления после обработки
        old_menu_id = None
        if state and isinstance(event, Message):
            state_data = await state.get_data()
            old_menu_id = state_data.get('last_menu_message_id')
        
        # Сначала вызываем обработчик (он отправит новое меню)
        result = await handler(event, data)
        
        # Теперь удаляем старое меню ПОСЛЕ того, как обработчик завершился
        if old_menu_id and state:
            try:
                # Проверяем, что меню еще не было удалено обработчиком
                state_data = await state.get_data()
                current_menu_id = state_data.get('last_menu_message_id')
                cashback_menu_ids = state_data.get('cashback_menu_ids', [])
                
                # ВАЖНОЕ ЛОГИРОВАНИЕ для отладки
                logger.debug(f"MenuCleanup CHECK: old_menu={old_menu_id}, current_menu={current_menu_id}, cashback_ids={cashback_menu_ids}")
                
                # НЕ удаляем ТОЛЬКО если это меню кешбека из списка
                if old_menu_id in cashback_menu_ids:
                    logger.info(f"SKIPPING deletion - this is a cashback menu! old_menu={old_menu_id}")
                    return result
                
                # Удаляем только если ID изменился (значит было отправлено новое меню)
                if current_menu_id != old_menu_id:
                    asyncio.create_task(
                        delete_message_with_effect(
                            event.bot, 
                            event.chat.id, 
                            old_menu_id,
                            delay=0.3  # Стандартная задержка для плавного перехода
                        )
                    )
                    logger.debug(f"Scheduled deletion of old menu {old_menu_id} for user {event.from_user.id}")
            except Exception as e:
                logger.debug(f"Failed to delete old menu: {e}")
        
        return result