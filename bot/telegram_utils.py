import os
import asyncio
from aiogram import Bot
import logging

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id, text, parse_mode='Markdown'):
    """
    Синхронная функция для отправки сообщения через Telegram Bot API
    """
    try:
        # Получаем токен бота
        bot_token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ValueError("Bot token not found in environment variables")
        
        # Создаем бота
        bot = Bot(token=bot_token)
        
        # Создаем event loop если его нет
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Отправляем сообщение
        result = loop.run_until_complete(
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode
            )
        )
        
        # Закрываем сессию бота
        loop.run_until_complete(bot.session.close())
        
        logger.info(f"Message sent to {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")
        raise