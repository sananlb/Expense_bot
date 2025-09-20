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
            logger.info(f"MenuCleanup: Found old_menu_id={old_menu_id} for user {event.from_user.id}")
        
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
                logger.info(f"MenuCleanup AFTER handler: old_menu={old_menu_id}, current_menu={current_menu_id}, cashback_ids={cashback_menu_ids}, text={event.text[:20] if event.text else None}")
                
                # НЕ удаляем ТОЛЬКО если это меню кешбека из списка
                if old_menu_id in cashback_menu_ids:
                    logger.info(f"SKIPPING deletion - this is a cashback menu! old_menu={old_menu_id}")
                    return result

                # Проверяем, является ли сообщение потенциальной тратой
                is_potential_expense = False
                if event.text:
                    text = event.text.strip()
                    # Проверяем, похоже ли на трату/доход:
                    # 1. Начинается с цифры или знака +/-
                    # 2. ИЛИ содержит цифры в любом месте (для формата "описание сумма")
                    if text:
                        has_digits = any(char.isdigit() for char in text)
                        starts_with_number = text[0].isdigit() or text[0] in '+-'
                        # Проверяем что это не просто команда
                        is_not_command = not text.startswith('/')

                        if has_digits and is_not_command:
                            is_potential_expense = True
                            logger.info(f"Detected potential expense: '{text[:30]}...' (has_digits={has_digits})")

                # Удаляем старое меню если:
                # 1. ID изменился (было отправлено новое меню)
                # 2. ИЛИ это потенциальная трата (тогда удаляем любое старое меню)
                should_delete = False
                if current_menu_id != old_menu_id:
                    # Меню изменилось - удаляем старое
                    should_delete = True
                    logger.info(f"Menu changed: old={old_menu_id}, new={current_menu_id}")
                elif is_potential_expense and old_menu_id:
                    # Это трата и есть старое меню - удаляем его
                    should_delete = True
                    logger.info(f"Expense detected with old menu: {old_menu_id}")
                    # Очищаем ID из состояния, так как меню будет удалено
                    await state.update_data(last_menu_message_id=None)

                if should_delete:
                    asyncio.create_task(
                        delete_message_with_effect(
                            event.bot,
                            event.chat.id,
                            old_menu_id,
                            delay=0.1  # Уменьшаем задержку для более быстрого удаления
                        )
                    )
                    logger.info(f"Scheduled deletion of old menu {old_menu_id} for user {event.from_user.id}")
            except Exception as e:
                logger.debug(f"Failed to delete old menu: {e}")
        
        return result