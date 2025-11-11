"""
Middleware для очистки PII из старых FSM states
Удаляет username, first_name, last_name из pending_profile_data
"""
from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram.fsm.context import FSMContext
from typing import Callable, Dict, Any, Awaitable
import logging

logger = logging.getLogger(__name__)


class FSMCleanupMiddleware(BaseMiddleware):
    """Удаляет PII из FSM state если они там есть (старые states)"""

    def __init__(self):
        self.cleaned_users = set()  # Кеш очищенных пользователей

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        state: FSMContext = data.get('state')

        if state:
            user_id = None
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

            # Очищаем только один раз на пользователя
            if user_id and user_id not in self.cleaned_users:
                await self._cleanup_pii(state, user_id)
                self.cleaned_users.add(user_id)

        return await handler(event, data)

    async def _cleanup_pii(self, state: FSMContext, user_id: int):
        """Удалить PII из state если они есть"""
        try:
            data = await state.get_data()

            if 'pending_profile_data' in data:
                pending = data['pending_profile_data']

                # Проверить наличие PII
                has_pii = any(key in pending for key in ['username', 'first_name', 'last_name'])

                if has_pii:
                    logger.warning(f"Found PII in FSM state for user {user_id}, cleaning...")

                    # Удалить PII
                    pending.pop('username', None)
                    pending.pop('first_name', None)
                    pending.pop('last_name', None)

                    # Обновить state
                    await state.update_data(pending_profile_data=pending)

                    logger.info(f"PII cleaned from FSM state for user {user_id}")

        except Exception as e:
            logger.error(f"Error cleaning FSM state for user {user_id}: {e}")
