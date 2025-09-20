"""
Middleware для защиты от спама и массовых регистраций ботов
"""
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message
import asyncio

logger = logging.getLogger(__name__)


class AntiSpamMiddleware(BaseMiddleware):
    """
    Middleware для защиты от массовых регистраций и спама
    """

    def __init__(self):
        super().__init__()
        # Хранилище временных меток команд /start для каждого пользователя
        self.start_timestamps = defaultdict(list)
        # Хранилище для подсчета регистраций в единицу времени
        self.registration_window = defaultdict(int)
        self.window_reset_time = datetime.now()

        # Настройки защиты
        self.MAX_STARTS_PER_HOUR = 3  # Максимум 3 команды /start в час от одного пользователя
        self.MAX_REGISTRATIONS_PER_MINUTE = 5  # Максимум 5 новых регистраций в минуту глобально
        self.BAN_DURATION = timedelta(hours=1)  # Длительность временного бана
        self.banned_users = {}  # Словарь забаненных пользователей

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка входящих сообщений
        """
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        now = datetime.now()

        # Проверяем, не забанен ли пользователь
        if user_id in self.banned_users:
            ban_until = self.banned_users[user_id]
            if now < ban_until:
                remaining = (ban_until - now).seconds // 60
                await event.answer(
                    f"⚠️ Вы временно заблокированы из-за подозрительной активности.\n"
                    f"Попробуйте через {remaining} минут."
                )
                logger.warning(f"Blocked spam attempt from user {user_id}")
                return
            else:
                # Снимаем бан
                del self.banned_users[user_id]

        # Проверка команды /start
        if event.text and event.text.startswith('/start'):
            # Сбрасываем счетчик регистраций каждую минуту
            if now - self.window_reset_time > timedelta(minutes=1):
                self.registration_window.clear()
                self.window_reset_time = now

            # Проверяем глобальный лимит регистраций
            total_registrations = sum(self.registration_window.values())
            if total_registrations >= self.MAX_REGISTRATIONS_PER_MINUTE:
                logger.warning(f"Global registration limit reached: {total_registrations} registrations/minute")
                await event.answer(
                    "⚠️ Сервис временно перегружен. Попробуйте через несколько минут."
                )
                return

            # Очищаем старые записи для пользователя
            self.start_timestamps[user_id] = [
                ts for ts in self.start_timestamps[user_id]
                if now - ts < timedelta(hours=1)
            ]

            # Проверяем персональный лимит
            if len(self.start_timestamps[user_id]) >= self.MAX_STARTS_PER_HOUR:
                # Баним пользователя
                self.banned_users[user_id] = now + self.BAN_DURATION
                logger.warning(f"User {user_id} banned for spam: {len(self.start_timestamps[user_id])} /start commands")
                await event.answer(
                    "⚠️ Обнаружена подозрительная активность.\n"
                    "Доступ временно ограничен."
                )
                return

            # Добавляем временную метку
            self.start_timestamps[user_id].append(now)
            self.registration_window[user_id] += 1

            # Добавляем небольшую задержку для новых пользователей (против ботов)
            if len(self.start_timestamps[user_id]) == 1:
                await asyncio.sleep(0.5)  # 500ms задержка для первой регистрации

        # Пропускаем дальше
        return await handler(event, data)