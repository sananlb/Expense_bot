"""
Утилиты для работы с сообщениями
"""
from typing import Optional, Dict, Any, TYPE_CHECKING
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, ReplyKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramNotFound
import asyncio
import logging

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


async def safe_delete_message(
    message: Message | None = None,
    bot: Bot | None = None,
    chat_id: int | None = None,
    message_id: int | None = None
) -> bool:
    """
    Безопасное удаление сообщения с обработкой типовых ошибок.

    Usage:
        await safe_delete_message(message=message)
        await safe_delete_message(bot=bot, chat_id=123, message_id=456)
    """
    try:
        if message is not None:
            await message.delete()
            return True
        if bot and chat_id and message_id:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        logger.warning("safe_delete_message called without message or bot/chat_id/message_id")
        return False
    except (TelegramBadRequest, TelegramNotFound) as exc:
        if "message to delete not found" in str(exc).lower() or "message can't be deleted" in str(exc).lower():
            logger.debug(f"Message already deleted or not found: {exc}")
        else:
            logger.warning(f"Error deleting message: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error deleting message: {exc}")
        return False


async def safe_edit_message(
    message: Message,
    text: str,
    **kwargs
) -> Optional[Message]:
    """
    Безопасное редактирование сообщения с обработкой 'not modified'.

    Обрабатывает типичные ошибки:
    - "message is not modified" - возвращает оригинальное сообщение
    - "message to edit not found" - возвращает None
    - Другие ошибки - пробрасываются

    Args:
        message: Сообщение для редактирования
        text: Новый текст
        **kwargs: Дополнительные параметры (parse_mode, reply_markup, etc.)

    Returns:
        Отредактированное сообщение или оригинальное если не изменилось, None если не найдено

    Example:
        # Вместо message.edit_text():
        await safe_edit_message(message, "New text", parse_mode="HTML")

        # С клавиатурой:
        await safe_edit_message(
            message,
            "Updated",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    """
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        error_text = str(e).lower()
        if "message is not modified" in error_text:
            # Текст уже такой же - не ошибка, просто не нужно обновлять
            logger.debug(f"Message not modified (ignored): {text[:50]}...")
            return message  # Возвращаем оригинальное сообщение
        elif "message to edit not found" in error_text:
            # Сообщение уже удалено
            logger.warning(f"Message to edit not found: {message.message_id}")
            return None
        else:
            # Другие ошибки пробрасываем
            raise
    except Exception as e:
        logger.error(f"Unexpected error editing message: {e}")
        raise


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

        # Очищаем ID из состояния
        await state.update_data(invoice_msg_id=None)
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
    top5_menu_ids = data.get('top5_menu_ids', [])
    
    # ЛОГИРОВАНИЕ для отладки
    logger.debug(f"send_message_with_cleanup: old_menu={old_menu_id}, cashback_ids={cashback_menu_ids}, top5_ids={top5_menu_ids}, update_cashback={update_cashback_menu}")

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

    # Если старое меню - это меню ТОП 5 из списка, не удаляем его
    if old_menu_id in top5_menu_ids:
        # Просто отправляем новое сообщение без удаления меню ТОП 5
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
        # Обновляем last_menu_message_id на новое меню (НЕ ТОП 5)
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

    # Небольшая задержка чтобы пользователь увидел новое сообщение ДО удаления старого
    await asyncio.sleep(0.05)

    # Удаляем старое меню ПОСЛЕ успешной отправки нового
    if old_menu_id and old_menu_id != sent_message.message_id and not keep_message:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_menu_id)
        except Exception as e:
            logger.debug(f"Не удалось удалить старое меню {old_menu_id}: {e}")
    
    # Сохраняем ID нового сообщения, если есть клавиатура и не надо сохранять сообщение
    if reply_markup is not None and not keep_message:
        await state.update_data(last_menu_message_id=sent_message.message_id)
    
    return sent_message


