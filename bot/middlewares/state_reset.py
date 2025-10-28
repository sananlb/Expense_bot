"""
Middleware для сброса состояния FSM при выполнении команд или неподходящем вводе
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from ..routers.cashback import CashbackForm
from ..utils.message_utils import send_message_with_cleanup, delete_subscription_messages
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
            
            # Всегда удаляем сообщения подписки при любом новом сообщении от пользователя
            await delete_subscription_messages(state, event.bot, event.chat.id)
            
            # Проверяем, является ли сообщение командой
            if event.text.startswith('/'):
                # Сохраняем данные о персистентном меню кешбека и clarification message перед очисткой
                state_data = await state.get_data()
                persistent_cashback = state_data.get('persistent_cashback_menu', False)
                cashback_menu_ids = state_data.get('cashback_menu_ids', [])
                cashback_menu_month = state_data.get('cashback_menu_month')
                clarification_message_id = state_data.get('clarification_message_id')

                # Сбрасываем состояние при любой команде
                await state.clear()
                logger.info(f"State cleared for user {event.from_user.id} on command {event.text}")

                # Восстанавливаем флаг персистентного меню кешбека и список ID
                if persistent_cashback and cashback_menu_ids:
                    # Используем последний ID из списка для совместимости
                    last_id = cashback_menu_ids[-1] if cashback_menu_ids else None
                    await state.update_data(
                        persistent_cashback_menu=True,
                        cashback_menu_ids=cashback_menu_ids,  # Сохраняем весь список
                        cashback_menu_message_id=last_id,  # Для совместимости
                        cashback_menu_month=cashback_menu_month,
                        last_menu_message_id=last_id  # ВАЖНО: сохраняем ID как last_menu для защиты от удаления
                    )
                    logger.info(f"Restored persistent cashback menus ({len(cashback_menu_ids)} menus) for user {event.from_user.id}")

                # Восстанавливаем clarification_message_id чтобы menu_cleanup мог его удалить
                if clarification_message_id:
                    await state.update_data(clarification_message_id=clarification_message_id)
                    logger.info(f"Restored clarification_message_id={clarification_message_id} for cleanup")
            
            # Проверяем состояние ожидания процента кешбэка (при добавлении или редактировании)
            elif current_state in [CashbackForm.waiting_for_percent.state, CashbackForm.editing_percent.state]:
                # Теперь мы принимаем описание и процент, поэтому проверяем, есть ли число в конце
                import re
                text = event.text.strip()
                
                # Проверяем паттерны: только число ИЛИ текст + число в конце
                only_number = re.match(r'^(\d+(?:[.,]\d+)?)\s*%?$', text)
                text_and_number = re.match(r'^.*\s+(\d+(?:[.,]\d+)?)\s*%?$', text)
                
                if not only_number and not text_and_number:
                    # Нет числа ни в начале, ни в конце - это ошибка
                    await state.clear()
                    logger.info(f"State cleared for user {event.from_user.id} on invalid percent input: {event.text}")
                    await send_message_with_cleanup(event, state, "❌ Не найден процент. Введите процент или описание и процент.")
                    return None
                # Если паттерн совпал, продолжаем обработку
            
            # Аналогично для других состояний с числовым вводом
            elif current_state and "waiting_for_limit" in current_state:
                text = event.text.strip().replace(' ', '').replace(',', '.')
                try:
                    float(text)
                except ValueError:
                    await state.clear()
                    logger.info(f"State cleared for user {event.from_user.id} on invalid limit input: {event.text}")
                    await send_message_with_cleanup(event, state, "❌ Действие отменено. Используйте команды для навигации.")
                    return None
        
        # Вызываем обработчик
        return await handler(event, data)