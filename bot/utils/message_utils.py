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
        cashback_menu_ids = data.get('cashback_menu_ids', [])
        
        # НЕ удаляем меню если это меню кешбека из списка
        if last_menu_id in cashback_menu_ids:
            logger.debug(f"Skipping deletion of cashback menu {last_menu_id}")
            return
            
        if last_menu_id:
            await bot.delete_message(chat_id=chat_id, message_id=last_menu_id)
            # Очищаем ID после успешного удаления
            await state.update_data(last_menu_message_id=None)
    except Exception as e:
        # Логируем только на уровне debug, так как это нормальная ситуация
        logger.debug(f"Не удалось удалить меню: {e}")
        # Очищаем ID в любом случае, но только если это НЕ меню кешбека
        data = await state.get_data()
        cashback_menu_ids = data.get('cashback_menu_ids', [])
        if last_menu_id not in cashback_menu_ids:
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
    update_cashback_menu: bool = False,
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
        update_cashback_menu: Если True, это обновление меню кешбека - нужно обновить ID
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
    cashback_menu_ids = data.get('cashback_menu_ids', [])
    
    # ЛОГИРОВАНИЕ для отладки
    logger.debug(f"send_message_with_cleanup: old_menu={old_menu_id}, cashback_ids={cashback_menu_ids}, update_cashback={update_cashback_menu}")
    
    # Если старое меню - это меню кешбека из списка, не удаляем его
    if old_menu_id in cashback_menu_ids and not update_cashback_menu:
        # Просто отправляем новое сообщение без удаления меню кешбека
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
        # Обновляем last_menu_message_id на новое меню (НЕ кешбек)
        if reply_markup is not None and not keep_message:
            await state.update_data(last_menu_message_id=sent_message.message_id)
        return sent_message
    
    # Если это callback query, отвечаем на него
    if isinstance(message, CallbackQuery):
        await message.answer()
        # НЕ редактируем старое сообщение - всегда создаем новое и удаляем старое
        # Это обеспечивает правильный порядок: новое появляется, потом старое исчезает
    
    # Отправляем новое сообщение СНАЧАЛА
    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        **kwargs
    )

    # Удаляем старое меню ПОСЛЕ успешной отправки нового (без задержки)
    if old_menu_id and old_menu_id != sent_message.message_id and not keep_message:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_menu_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить старое меню {old_menu_id}: {e}")
    
    # Сохраняем ID нового сообщения, если есть клавиатура и не надо сохранять сообщение
    if reply_markup is not None and not keep_message:
        await state.update_data(last_menu_message_id=sent_message.message_id)
    
    return sent_message


