"""
Сервис для работы с подписками
"""
from django.utils import timezone
from expenses.models import Profile, Subscription
from datetime import datetime, timedelta
from typing import Optional


async def check_subscription(telegram_id: int, include_trial: bool = True) -> bool:
    """Проверка наличия активной подписки у пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        include_trial: Учитывать ли пробный период как подписку
    """
    try:
        profile = await Profile.objects.aget(telegram_id=telegram_id)
        
        # Бета-тестеры имеют полный доступ без подписки
        if profile.is_beta_tester:
            return True
        
        # Проверяем наличие активной подписки
        if include_trial:
            # Учитываем любую активную подписку включая пробный период
            has_subscription = await profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).aexists()
        else:
            # Исключаем пробный период
            has_subscription = await profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).exclude(type='trial').aexists()
        
        return has_subscription
    except Profile.DoesNotExist:
        return False


async def is_trial_active(telegram_id: int) -> bool:
    """Проверка активного пробного периода"""
    try:
        profile = await Profile.objects.aget(telegram_id=telegram_id)
        
        # Проверяем наличие активного пробного периода
        has_trial = await profile.subscriptions.filter(
            is_active=True,
            type='trial',
            end_date__gt=timezone.now()
        ).aexists()
        
        return has_trial
    except Profile.DoesNotExist:
        return False


async def get_active_subscription(telegram_id: int) -> Optional[Subscription]:
    """Получить активную подписку пользователя"""
    try:
        profile = await Profile.objects.aget(telegram_id=telegram_id)
        
        # Получаем последнюю активную подписку
        subscription = await profile.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).order_by('-end_date').afirst()
        
        return subscription
    except Profile.DoesNotExist:
        return None


async def deactivate_expired_subscriptions():
    """Деактивация истекших подписок (для периодического запуска)"""
    expired_count = await Subscription.objects.filter(
        is_active=True,
        end_date__lte=timezone.now()
    ).aupdate(is_active=False)
    
    return expired_count


def subscription_required_message() -> str:
    """Сообщение о необходимости подписки"""
    return (
        "❌ <b>Требуется подписка</b>\n\n"
        "Для использования этой функции необходима активная подписка.\n\n"
        "Нажмите кнопку ниже, чтобы оформить подписку:"
    )


def get_subscription_button():
    """Кнопка для перехода к оформлению подписки"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⭐ Оформить подписку",
        callback_data="menu_subscription"
    )
    
    return builder.as_markup()


# Декоратор для проверки подписки (опционально)
def require_subscription(func):
    """Декоратор для проверки подписки перед выполнением функции"""
    async def wrapper(message_or_callback, *args, **kwargs):
        from aiogram import types
        
        # Получаем telegram_id в зависимости от типа объекта
        if isinstance(message_or_callback, types.Message):
            telegram_id = message_or_callback.from_user.id
        elif isinstance(message_or_callback, types.CallbackQuery):
            telegram_id = message_or_callback.from_user.id
        else:
            # Если не можем определить тип, выполняем функцию без проверки
            return await func(message_or_callback, *args, **kwargs)
        
        # Проверяем подписку
        has_subscription = await check_subscription(telegram_id)
        
        if not has_subscription:
            # Отправляем сообщение о необходимости подписки
            if isinstance(message_or_callback, types.Message):
                await message_or_callback.answer(
                    subscription_required_message(),
                    reply_markup=get_subscription_button(),
                    parse_mode="HTML"
                )
            elif isinstance(message_or_callback, types.CallbackQuery):
                await message_or_callback.message.edit_text(
                    subscription_required_message(),
                    reply_markup=get_subscription_button(),
                    parse_mode="HTML"
                )
                await message_or_callback.answer()
            
            return  # Не выполняем основную функцию
        
        # Если подписка есть, выполняем функцию
        return await func(message_or_callback, *args, **kwargs)
    
    return wrapper
