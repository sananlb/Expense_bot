"""
Утилита для управления индикатором "печатает..." с задержкой
"""

import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.types import Message


class DelayedTypingAction:
    """Контекстный менеджер для отправки индикатора "печатает..." с задержкой"""
    
    def __init__(self, message: Message, delay: float = 2.0, repeat_interval: float = 4.0):
        """
        Инициализация
        
        Args:
            message: Сообщение от пользователя
            delay: Задержка перед первым показом индикатора (секунды)
            repeat_interval: Интервал повторения индикатора (секунды)
        """
        self.message = message
        self.delay = delay
        self.repeat_interval = repeat_interval
        self.task: Optional[asyncio.Task] = None
        self._cancelled = False
        
    async def _typing_loop(self):
        """Цикл отправки индикатора печатания"""
        try:
            # Ждем начальную задержку
            await asyncio.sleep(self.delay)
            
            # Если за это время ответ уже отправлен, не показываем индикатор
            if self._cancelled:
                return
                
            # Отправляем первый индикатор
            await self.message.bot.send_chat_action(
                chat_id=self.message.chat.id, 
                action="typing"
            )
            
            # Повторяем с интервалом
            while not self._cancelled:
                await asyncio.sleep(self.repeat_interval)
                if not self._cancelled:
                    await self.message.bot.send_chat_action(
                        chat_id=self.message.chat.id,
                        action="typing"
                    )
        except asyncio.CancelledError:
            pass
        except Exception:
            pass  # Игнорируем ошибки
            
    async def __aenter__(self):
        """Запуск задачи при входе в контекст"""
        self.task = asyncio.create_task(self._typing_loop())
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Отмена задачи при выходе из контекста"""
        self._cancelled = True
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


async def send_typing_action(message: Message, immediate: bool = False):
    """
    Отправить индикатор "печатает..." с опциональной задержкой
    
    Args:
        message: Сообщение от пользователя
        immediate: Если True, отправить сразу без задержки
    """
    if immediate:
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )
    else:
        # Используем задержку 2 секунды
        await asyncio.sleep(2)
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action="typing"
        )