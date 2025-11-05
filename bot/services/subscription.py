"""
Сервис для работы с подписками
"""
from django.utils import timezone
from expenses.models import Profile, Subscription, UserSettings
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
    """
    Деактивация истекших подписок (для периодического запуска)

    При окончании подписки автоматически отключает:
    - Семейный режим (view_scope → 'personal')
    - Кешбек трекинг (cashback_enabled → False)
    - Обновляет команды бота для скрытия /cashback
    """
    now = timezone.now()

    # Получаем истекшие подписки (без await - queryset не awaitable!)
    expired_subscriptions = Subscription.objects.filter(
        is_active=True,
        end_date__lte=now
    ).select_related('profile')

    expired_count = 0
    user_ids_to_update: set[int] = set()

    async for subscription in expired_subscriptions:
        # Деактивируем подписку
        subscription.is_active = False
        await subscription.asave()
        expired_count += 1

        # Проверяем есть ли у пользователя другие активные подписки
        profile = subscription.profile
        has_other_active = await Subscription.objects.filter(
            profile=profile,
            is_active=True,
            end_date__gt=now
        ).aexists()

        # Если нет других активных подписок, отключаем премиум функции
        if not has_other_active:
            # Получаем или создаем настройки пользователя
            settings, _ = await UserSettings.objects.aget_or_create(profile=profile)
            changed_fields = []

            # Отключаем семейный режим (переводим в личный)
            if settings.view_scope == 'household':
                settings.view_scope = 'personal'
                changed_fields.append('view_scope')

            # Отключаем кешбек
            if settings.cashback_enabled:
                settings.cashback_enabled = False
                changed_fields.append('cashback_enabled')

            # Сохраняем изменения в настройках
            if changed_fields:
                await settings.asave(update_fields=changed_fields)
                user_ids_to_update.add(profile.telegram_id)

    # Обновляем команды бота для пользователей (скрываем /cashback)
    if user_ids_to_update:
        await _update_commands_for_users(list(user_ids_to_update))

    return expired_count


async def _update_commands_for_users(user_ids: list):
    """
    Обновить команды бота для списка пользователей

    Args:
        user_ids: Список telegram_id пользователей
    """
    from bot.utils.commands import update_user_commands
    from aiogram import Bot
    import os

    try:
        # Получаем инстанс бота
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            return

        bot = Bot(token=bot_token)

        # Обновляем команды для каждого пользователя
        for user_id in user_ids:
            try:
                await update_user_commands(bot, user_id)
            except Exception as e:
                # Логируем ошибку, но продолжаем обновлять других пользователей
                pass

        # Закрываем сессию бота
        await bot.session.close()

    except Exception as e:
        # Если не удалось обновить команды, не критично - обновятся при следующем взаимодействии
        pass


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
