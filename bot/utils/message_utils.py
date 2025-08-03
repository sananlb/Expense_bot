"""
Утилиты для работы с сообщениями
"""
from typing import Optional, Dict, Any, TYPE_CHECKING
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, ReplyKeyboardMarkup, CallbackQuery
import asyncio
import logging

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def delete_message_with_effect(bot: Bot, chat_id: int, message_id: int, delay: float = 0.3) -> bool:
    """
    Удалить сообщение с эффектом плавного исчезновения
    
    Args:
        bot: Объект бота
        chat_id: ID чата
        message_id: ID сообщения для удаления
        delay: Задержка перед удалением для визуального эффекта
    """
    # Ждем, чтобы пользователь увидел анимацию
    await asyncio.sleep(delay)
    
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:
        # Игнорируем ошибки удаления - это нормально для уже удаленных сообщений
        logger.debug(f"Не удалось удалить сообщение {message_id}: {e}")
        return False


async def delete_last_menu(state: 'FSMContext', bot: Bot, chat_id: int) -> None:
    """
    Удалить последнее отправленное меню с inline-кнопками
    
    Args:
        state: FSM контекст
        bot: Объект бота
        chat_id: ID чата
    """
    try:
        data = await state.get_data()
        last_menu_id = data.get('last_menu_message_id')
        if last_menu_id:
            await bot.delete_message(chat_id=chat_id, message_id=last_menu_id)
            # Очищаем ID после успешного удаления
            await state.update_data(last_menu_message_id=None)
    except Exception as e:
        # Логируем только на уровне debug, так как это нормальная ситуация
        logger.debug(f"Не удалось удалить меню: {e}")
        # Очищаем ID в любом случае
        await state.update_data(last_menu_message_id=None)


async def send_message_with_cleanup(
    message: Message | CallbackQuery,
    state: 'FSMContext',
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup] = None,
    **kwargs
) -> Message:
    """
    Отправить сообщение и удалить предыдущее меню
    
    Args:
        message: Объект сообщения или CallbackQuery
        state: FSM контекст  
        text: Текст для отправки
        reply_markup: Клавиатура
        **kwargs: Дополнительные параметры для send_message
    
    Returns:
        Отправленное сообщение
    """
    # Получаем chat_id и bot
    if isinstance(message, CallbackQuery):
        chat_id = message.message.chat.id
        bot = message.bot
    else:
        chat_id = message.chat.id
        bot = message.bot
    
    # Удаляем старое меню если есть
    data = await state.get_data()
    old_menu_id = data.get('last_menu_message_id')
    
    # Если это callback query, отвечаем на него
    if isinstance(message, CallbackQuery):
        await message.answer()
        # Если старое меню совпадает с текущим сообщением callback, редактируем его
        if old_menu_id == message.message.message_id:
            try:
                edited_msg = await message.message.edit_text(
                    text=text,
                    reply_markup=reply_markup,
                    **kwargs
                )
                # Важно: обновляем ID сообщения в состоянии даже при редактировании
                await state.update_data(last_menu_message_id=edited_msg.message_id)
                return edited_msg
            except Exception:
                # Если не удалось отредактировать, отправляем новое
                pass
    
    # Отправляем новое сообщение
    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        **kwargs
    )
    
    # Удаляем старое меню после успешной отправки нового
    if old_menu_id and old_menu_id != sent_message.message_id:
        asyncio.create_task(delete_message_with_effect(bot, chat_id, old_menu_id))
    
    # Сохраняем ID нового сообщения, если есть клавиатура
    if reply_markup is not None:
        await state.update_data(last_menu_message_id=sent_message.message_id)
    
    return sent_message


