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
            
            # НОВАЯ ПРОВЕРКА: Если у пользователя есть другие активные подписки, не отправляем уведомление
            # Проверяем наличие других активных подписок, которые будут действовать после истечения текущей
            other_active_subscriptions = await Subscription.objects.filter(
                profile=subscription.profile,
                is_active=True,
                end_date__gt=subscription.end_date  # Подписки, которые заканчиваются позже текущей
            ).aexists()
            
            if other_active_subscriptions:
                logger.info(
                    f"Пользователь {subscription.profile.telegram_id} имеет другие активные подписки. "
                    f"Не отправляем уведомление об истечении подписки {subscription.id}"
                )
                continue
            
            # Формируем сообщение
            if subscription.type == 'trial':
                message = (
                    "🎁 <b>Ваш пробный период заканчивается завтра!</b>\n\n"
                    "Не упустите возможность продолжить пользоваться всеми премиум функциями:\n"
                    "• 🎯 Естественные вопросы к статистике\n"
                    "• 🎤 Голосовой ввод трат\n"
                    "• 💵 Учёт доходов\n"
                    "• 🏷️ Редактирование категорий\n"
                    "• 💳 Отслеживание кэшбэка\n"
                    "• 🏠 Семейный доступ\n\n"
                    "Оформите подписку прямо сейчас!"
                )
            else:
                message = (
                    f"⏰ <b>Ваша подписка заканчивается завтра!</b>\n\n"
                    f"Дата окончания: {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"Не упустите возможность продолжить пользоваться всеми премиум функциями:\n"
                    f"• 🎯 Естественные вопросы к статистике\n"
                    f"• 🎤 Голосовой ввод трат\n"
                    f"• 💵 Учёт доходов\n"
                    f"• 🏷️ Редактирование категорий\n"
                    f"• 💳 Отслеживание кэшбэка\n"
                    f"• 🏠 Семейный доступ\n\n"
                    f"Продлите подписку прямо сейчас!"
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
            # Проверяем, заблокировал ли пользователь бота
            error_message = str(e)
            if "bot was blocked by the user" in error_message.lower() or "forbidden" in error_message.lower():
                # Отмечаем что пользователь заблокировал бота
                subscription.profile.bot_blocked = True
                subscription.profile.bot_blocked_at = timezone.now()
                await subscription.profile.asave(update_fields=['bot_blocked', 'bot_blocked_at'])
                logger.warning(f"Пользователь {subscription.profile.telegram_id} заблокировал бота. Профиль помечен.")
            else:
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