"""
Задача для отправки уведомлений об окончании подписки
"""
import asyncio
from datetime import timedelta
from django.utils import timezone
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from expenses.models import Subscription, Profile


async def check_expiring_subscriptions(bot: Bot):
    """Проверка подписок, истекающих через сутки"""
    # Находим подписки, которые истекают через 24 часа
    tomorrow = timezone.now() + timedelta(days=1)
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Находим подписки, истекающие завтра, по которым еще не отправлено уведомление
    expiring_subscriptions = await Subscription.objects.filter(
        is_active=True,
        end_date__gte=tomorrow_start,
        end_date__lte=tomorrow_end,
        notification_sent=False
    ).select_related('profile').aiterator()
    
    async for subscription in expiring_subscriptions:
        try:
            # Формируем сообщение
            if subscription.type == 'trial':
                message = (
                    "🎁 <b>Ваш пробный период заканчивается завтра!</b>\n\n"
                    "Не упустите возможность продолжить пользоваться всеми функциями:\n"
                    "• Голосовой ввод расходов\n"
                    "• Редактирование категорий\n"
                    "• Управление кешбэками\n"
                    "• Экспорт отчетов в PDF\n\n"
                    "Оформите подписку прямо сейчас со скидкой!"
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
            
            # Отмечаем, что уведомление отправлено
            subscription.notification_sent = True
            await subscription.asave(update_fields=['notification_sent'])
            
        except Exception as e:
            print(f"Ошибка при отправке уведомления пользователю {subscription.profile.telegram_id}: {e}")


async def run_notification_task(bot: Bot):
    """Запуск периодической проверки подписок"""
    while True:
        try:
            await check_expiring_subscriptions(bot)
        except Exception as e:
            print(f"Ошибка в задаче уведомлений: {e}")
        
        # Проверяем каждый час
        await asyncio.sleep(3600)