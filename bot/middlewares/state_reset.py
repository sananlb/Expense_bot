"""
Middleware для сброса состояния FSM при выполнении команд или неподходящем вводе
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from ..routers.cashback import CashbackForm
import logging

logger = logging.getLogger(__name__)


class StateResetMiddleware(BaseMiddleware):
    """Middleware для сброса состояния при выполнении команд или неподходящем вводе"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем состояние из контекста
        state: FSMContext = data.get('state')
        
        if state and hasattr(event, 'text') and event.text:
            current_state = await state.get_state()
            
            # Проверяем, является ли сообщение командой
            if event.text.startswith('/'):
                # Сбрасываем состояние при любой команде
                await state.clear()
                logger.info(f"State cleared for user {event.from_user.id} on command {event.text}")
            
            # Проверяем состояние ожидания процента кешбэка
            elif current_state == CashbackForm.waiting_for_percent.state:
                # Проверяем, является ли текст числом (с возможной точкой или запятой и знаком %)
                text = event.text.strip().replace('%', '').replace(',', '.')
                try:
                    float(text)
                    # Это число, продолжаем обработку
                except ValueError:
                    # Это не число, сбрасываем состояние
                    await state.clear()
                    logger.info(f"State cleared for user {event.from_user.id} on invalid percent input: {event.text}")
                    await event.answer("❌ Действие отменено. Используйте команды для навигации.")
                    return None
            
            # Аналогично для других состояний с числовым вводом
            elif current_state and "waiting_for_limit" in current_state:
                text = event.text.strip().replace(' ', '').replace(',', '.')
                try:
                    float(text)
                except ValueError:
                    await state.clear()
                    logger.info(f"State cleared for user {event.from_user.id} on invalid limit input: {event.text}")
                    await event.answer("❌ Действие отменено. Используйте команды для навигации.")
                    return None
        
        # Вызываем обработчик
        return await handler(event, data)