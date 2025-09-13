"""
Database middleware для подключения Django ORM
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import django
from django.db import connections
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)


def close_connections():
    """Синхронная функция для закрытия соединений"""
    for conn in connections.all():
        conn.close()


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для работы с Django ORM в async контексте"""
    
    def __init__(self):
        django.setup()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            # Обрабатываем запрос
            result = await handler(event, data)
        finally:
            # Закрываем все соединения для текущего потока
            await sync_to_async(close_connections, thread_sensitive=True)()
        
        return result