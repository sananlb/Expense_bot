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


async def delete_subscription_messages(state: 'FSMContext', bot: Bot, chat_id: int) -> None:
    """
    Удалить сообщения связанные с подпиской (инвойс и кнопку назад)
    
    Args:
        state: FSM контекст
        bot: Объект бота
        chat_id: ID чата
    """
    try:
        data = await state.get_data()
        
        # Удаляем инвойс
        invoice_msg_id = data.get('invoice_msg_id')
        if invoice_msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=invoice_msg_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить инвойс: {e}")
        
        # Удаляем сообщение с кнопкой "Назад"
        back_msg_id = data.get('subscription_back_msg_id')
        if back_msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=back_msg_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить кнопку назад: {e}")
        
        # Очищаем ID из состояния
        await state.update_data(invoice_msg_id=None, subscription_back_msg_id=None)
    except Exception as e:
        logger.debug(f"Ошибка при удалении сообщений подписки: {e}")


async def send_message_with_cleanup(
    message: Message | CallbackQuery,
    state: 'FSMContext',
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup] = None,
    keep_message: bool = False,
    **kwargs
) -> Message:
    """
    Отправить сообщение и удалить предыдущее меню
    
    Args:
        message: Объект сообщения или CallbackQuery
        state: FSM контекст  
        text: Текст для отправки
        reply_markup: Клавиатура
        keep_message: Если True, сообщение не будет удалено при следующем вызове
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
    persistent_cashback = data.get('persistent_cashback_menu', False)
    
    # Если меню кешбека постоянное, не удаляем его
    if persistent_cashback and old_menu_id:
        # Просто отправляем новое сообщение без удаления старого
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
        # Не обновляем last_menu_message_id чтобы сохранить ссылку на меню кешбека
        return sent_message
    
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
                if not keep_message:
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
    
    # Удаляем старое меню после успешной отправки нового (только если это не сообщение о трате)
    if old_menu_id and old_menu_id != sent_message.message_id and not keep_message:
        asyncio.create_task(delete_message_with_effect(bot, chat_id, old_menu_id))
    
    # Сохраняем ID нового сообщения, если есть клавиатура и не надо сохранять сообщение
    if reply_markup is not None and not keep_message:
        await state.update_data(last_menu_message_id=sent_message.message_id)
    
    return sent_message


