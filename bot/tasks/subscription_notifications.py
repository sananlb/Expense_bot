"""
Задача для отправки уведомлений об окончании подписки
"""
import asyncio
from datetime import timedelta
from django.utils import timezone
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from expenses.models import Subscription, Profile, SubscriptionNotification

logger = logging.getLogger(__name__)


async def check_expiring_subscriptions(bot: Bot):
    """Проверка подписок и отправка уведомлений за 1 день до истечения"""
    now = timezone.now()
    
    # Проверяем подписки, истекающие завтра
    tomorrow = now + timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Находим подписки, истекающие завтра
    expiring_subscriptions = Subscription.objects.filter(
        is_active=True,
        end_date__gte=tomorrow_start,
        end_date__lte=tomorrow_end
    ).select_related('profile')
    
    async for subscription in expiring_subscriptions:
        try:
            # Проверяем, не было ли уже отправлено уведомление для этой подписки
            notification_exists = await SubscriptionNotification.objects.filter(
                subscription=subscription,
                notification_type='one_day'
            ).aexists()
            
            if notification_exists:
                logger.info(f"Уведомление для подписки {subscription.id} уже отправлено")
                continue
            
            # Формируем сообщение
            if subscription.type == 'trial':
                message = (
                    "🎁 <b>Ваш пробный период заканчивается завтра!</b>\n\n"
                    "Не упустите возможность продолжить пользоваться всеми функциями:\n"
                    "• Голосовой ввод расходов\n"
                    "• Редактирование категорий\n"
                    "• Управление кешбэками\n"
                    "• Экспорт отчетов в PDF\n\n"
                    "Оформите подписку прямо сейчас!"
                )
            else:
                message = (
                    f"⏰ <b>Ваша подписка заканчивается завтра!</b>\n\n"
                    f"Дата окончания: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"Продлите подписку сейчас, чтобы не потерять доступ к премиум функциям."
                )
            
            # Создаем клавиатуру
            builder = InlineKeyboardBuilder()
            builder.button(
                text="⭐ Продлить подписку",
                callback_data="menu_subscription"
            )
            
            # Отправляем уведомление
            await bot.send_message(
                chat_id=subscription.profile.telegram_id,
                text=message,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            
            # Сохраняем информацию об отправленном уведомлении
            await SubscriptionNotification.objects.acreate(
                subscription=subscription,
                notification_type='one_day',
                sent_at=now
            )
            
            logger.info(f"Отправлено уведомление пользователю {subscription.profile.telegram_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {subscription.profile.telegram_id}: {e}")


async def run_notification_task(bot: Bot):
    """Запуск периодической проверки подписок"""
    while True:
        try:
            await check_expiring_subscriptions(bot)
        except Exception as e:
            logger.error(f"Ошибка в задаче уведомлений: {e}")
        
        # Проверяем каждые 4 часа
        await asyncio.sleep(14400)