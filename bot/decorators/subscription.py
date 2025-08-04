"""
Декораторы для проверки подписки
"""
from functools import wraps
from typing import Union
from aiogram import types
from aiogram.fsm.context import FSMContext
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
import logging

logger = logging.getLogger(__name__)


def require_subscription(feature: str = None):
    """
    Декоратор для проверки подписки пользователя
    
    Args:
        feature: Название функции, требующей подписку
        
    Usage:
        @require_subscription()
        async def handler(message: types.Message):
            ...
            
        @require_subscription(feature="advanced_reports")
        async def handler(message: types.Message):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(message: Union[types.Message, types.CallbackQuery], *args, **kwargs):
            # Получаем user_id
            user_id = message.from_user.id
            
            # Проверяем подписку
            has_subscription = await check_subscription(user_id)
            
            if not has_subscription:
                # Определяем тип сообщения для правильного ответа
                if isinstance(message, types.CallbackQuery):
                    await message.answer("⚠️ Требуется подписка")
                    msg_to_send = message.message
                else:
                    msg_to_send = message
                
                # Отправляем сообщение о необходимости подписки
                feature_text = f" для функции '{feature}'" if feature else ""
                text = subscription_required_message() + feature_text
                
                await msg_to_send.answer(
                    text,
                    reply_markup=get_subscription_button(),
                    parse_mode="HTML"
                )
                
                logger.info(f"User {user_id} tried to access {func.__name__} without subscription")
                return
            
            # Если подписка есть, выполняем функцию
            return await func(message, *args, **kwargs)
            
        return wrapper
    return decorator


def require_premium(func):
    """
    Упрощенный декоратор для функций, требующих премиум подписку
    
    Usage:
        @require_premium
        async def handler(message: types.Message):
            ...
    """
    return require_subscription(feature="премиум")(func)


def check_beta_access(func):
    """
    Декоратор для проверки бета-доступа
    
    Usage:
        @check_beta_access
        async def handler(message: types.Message):
            ...
    """
    @wraps(func)
    async def wrapper(message: Union[types.Message, types.CallbackQuery], *args, **kwargs):
        from bot.utils.db_utils import get_user_profile
        
        user_id = message.from_user.id
        profile = await get_user_profile(user_id)
        
        if not profile or not profile.is_beta_tester:
            if isinstance(message, types.CallbackQuery):
                await message.answer("⚠️ Эта функция доступна только бета-тестерам")
            else:
                await message.answer(
                    "⚠️ Эта функция находится в бета-тестировании и пока недоступна.\n"
                    "Следите за обновлениями в нашем канале!"
                )
            return
        
        return await func(message, *args, **kwargs)
        
    return wrapper


def rate_limit(max_calls: int = 10, period: int = 60):
    """
    Декоратор для ограничения частоты вызовов
    
    Args:
        max_calls: Максимальное количество вызовов
        period: Период в секундах
        
    Usage:
        @rate_limit(max_calls=5, period=60)
        async def handler(message: types.Message):
            ...
    """
    def decorator(func):
        # Словарь для хранения истории вызовов
        call_history = {}
        
        @wraps(func)
        async def wrapper(message: Union[types.Message, types.CallbackQuery], *args, **kwargs):
            import time
            
            user_id = message.from_user.id
            current_time = time.time()
            
            # Инициализируем историю для пользователя
            if user_id not in call_history:
                call_history[user_id] = []
            
            # Удаляем старые вызовы
            call_history[user_id] = [
                call_time for call_time in call_history[user_id]
                if current_time - call_time < period
            ]
            
            # Проверяем лимит
            if len(call_history[user_id]) >= max_calls:
                if isinstance(message, types.CallbackQuery):
                    await message.answer("⚠️ Слишком много запросов. Попробуйте позже.")
                else:
                    await message.answer("⚠️ Слишком много запросов. Попробуйте через минуту.")
                return
            
            # Добавляем текущий вызов
            call_history[user_id].append(current_time)
            
            # Выполняем функцию
            return await func(message, *args, **kwargs)
            
        return wrapper
    return decorator