"""
Сервис для отправки уведомлений администратору через отдельного Telegram бота
"""
import aiohttp
import logging
import asyncio
import html
from typing import Optional, Dict, List
from django.conf import settings
from datetime import datetime, timedelta
from django.core.cache import cache
import os
from bot.utils.language import get_text

logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    """Экранирование специальных символов для MarkdownV2"""
    if not text:
        return ""
    text = str(text)
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


class TelegramNotifier:
    """Класс для отправки уведомлений через Telegram API"""
    
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, token: str = None):
        self.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
        
    async def _make_request(self, method: str, data: Dict) -> Dict:
        """Выполнить запрос к Telegram API"""
        url = self.BASE_URL.format(token=self.token, method=method)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as response:
                    result = await response.json()
                    
                    if not result.get('ok'):
                        raise Exception(
                            f"Telegram API error: {result.get('description', 'Unknown error')}"
                        )
                        
                    return result.get('result', {})
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout при отправке в Telegram")
            raise Exception("Network timeout")
        except Exception as e:
            logger.error(f"Ошибка при отправке в Telegram: {e}")
            raise
    
    async def send_message(self,
                          chat_id: int,
                          text: str,
                          parse_mode: Optional[str] = None,
                          disable_notification: bool = False,
                          reply_markup: Optional[Dict] = None) -> Optional[int]:
        """
        Отправить текстовое сообщение
        
        Args:
            chat_id: ID чата/пользователя
            text: Текст сообщения
            parse_mode: Режим парсинга (Markdown, HTML)
            disable_notification: Отправить без звука
            reply_markup: Клавиатура (InlineKeyboard)
            
        Returns:
            message_id отправленного сообщения
        """
        data = {
            'chat_id': chat_id,
            'text': text,
            'disable_notification': disable_notification
        }

        if parse_mode is not None:
            data['parse_mode'] = parse_mode
        
        if reply_markup:
            data['reply_markup'] = reply_markup
            
        for attempt in range(3):
            try:
                result = await self._make_request('sendMessage', data)
                return result.get('message_id')
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(1 * (2 ** attempt))
        
        return None


# Создаем отдельный экземпляр для админских уведомлений
admin_notifier = TelegramNotifier(
    token=os.getenv('MONITORING_BOT_TOKEN', os.getenv('TELEGRAM_BOT_TOKEN'))
)


async def send_admin_alert(
    message: str,
    disable_notification: bool = False,
    parse_mode: Optional[str] = None,
    allow_html_tags: bool = False
) -> bool:
    """
    Отправить алерт администратору через отдельного бота.

    ВАЖНО: По умолчанию отправляет plain text (parse_mode=None) и экранирует
    HTML-символы, если явно выбран parse_mode='HTML' и allow_html_tags=False.

    Args:
        message: Текст сообщения
        disable_notification: Отправить без звука
        parse_mode: Режим парсинга ('HTML', 'MarkdownV2', или None)
        allow_html_tags: Если False, экранирует все HTML символы (безопасно для ненадежных данных)

    Returns:
        True если сообщение отправлено успешно

    Example:
        # С HTML тегами (явно)
        await send_admin_alert(
            "🔴 <b>Error</b>\n"
            "User: 123 - Status: failed"
            ,
            parse_mode='HTML',
            allow_html_tags=True
        )

        # Для ненадежных данных - экранировать все
        await send_admin_alert(
            user_input_data,
            parse_mode='HTML',
            allow_html_tags=False
        )
    """
    admin_id = os.getenv('ADMIN_TELEGRAM_ID')

    if not admin_id:
        logger.warning("ADMIN_TELEGRAM_ID не настроен")
        return False

    logger.info(f"Попытка отправки админского уведомления. ADMIN_TELEGRAM_ID: {admin_id}")
    logger.info(f"Используется токен бота: {'MONITORING_BOT_TOKEN' if os.getenv('MONITORING_BOT_TOKEN') else 'TELEGRAM_BOT_TOKEN'}")

    try:
        # Экранируем только если явно запрошено (для ненадежных данных)
        if parse_mode == 'HTML' and not allow_html_tags:
            # Полное экранирование для ненадежных данных
            escaped_message = html.escape(message)
        elif parse_mode == 'MarkdownV2':
            # Если кто-то передаст MarkdownV2, используем старую функцию
            escaped_message = escape_markdown_v2(message)
        else:
            # HTML с тегами или None - без экранирования
            escaped_message = message

        await admin_notifier.send_message(
            chat_id=int(admin_id),
            text=escaped_message,
            parse_mode=parse_mode,
            disable_notification=disable_notification
        )
        logger.info("Админское уведомление отправлено успешно")
        return True

    except Exception as e:
        logger.error(f"Ошибка отправки админского алерта: {e}")
        logger.error(f"Детали ошибки: chat_id={admin_id}, message_length={len(message)}, parse_mode={parse_mode}")

        # Fallback: пробуем отправить без форматирования
        if parse_mode is not None:
            try:
                logger.info("Пробую отправить без форматирования (fallback)...")
                await admin_notifier.send_message(
                    chat_id=int(admin_id),
                    text=message,  # Оригинальный текст без экранирования
                    parse_mode=None,
                    disable_notification=disable_notification
                )
                logger.info("Админское уведомление отправлено без форматирования (fallback)")
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback тоже упал: {fallback_error}")

        return False


async def send_daily_report():
    """Отправка ежедневного отчета администратору"""
    from expenses.models import Profile, Expense, ExpenseCategory
    from django.db.models import Sum, Count
    from django.utils import timezone
    from asgiref.sync import sync_to_async
    
    logger.info("Начинаем формирование ежедневного отчета администратору")
    
    yesterday = timezone.now().date() - timedelta(days=1)
    today = timezone.now().date()
    
    # Собираем статистику через sync_to_async для Django ORM
    total_users = await sync_to_async(Profile.objects.count)()
    active_users = await sync_to_async(
        lambda: Profile.objects.filter(
            expenses__created_at__date=yesterday
        ).distinct().count()
    )()
    
    expenses_stats = await sync_to_async(
        lambda: Expense.objects.filter(
            created_at__date=yesterday
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
    )()
    
    new_users = await sync_to_async(
        lambda: Profile.objects.filter(
            created_at__date=yesterday
        ).count()
    )()
    
    # Топ категорий
    top_categories = await sync_to_async(
        lambda: list(Expense.objects.filter(
            created_at__date=yesterday
        ).values('category__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:5])
    )()
    
    categories_text = "\n".join([
        f"  • {cat['category__name'] or get_text('no_category', 'ru')}: "
        f"{round(cat['total'], 2)} ({cat['count']} записей)"
        for cat in top_categories
    ])

    # Формируем отчет (HTML, без экранирования - будет автоматически)
    report = (
        f"📊 <b>[Coins] Ежедневный отчет за {yesterday.strftime('%d.%m.%Y')}</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"  • Всего: {total_users}\n"
        f"  • Активных вчера: {active_users}\n"
        f"  • Новых вчера: {new_users}\n\n"
        f"💰 <b>Расходы:</b>\n"
        f"  • Количество: {expenses_stats['count'] or 0}\n"
        f"  • Сумма: {round(expenses_stats['total'] or 0, 2)}\n\n"
    )

    if categories_text:
        report += f"📂 <b>Топ категорий:</b>\n{categories_text}\n\n"

    # Проверяем ошибки
    error_count = cache.get('daily_errors_count', 0)
    if error_count > 0:
        report += f"⚠️ <b>Ошибок за день:</b> {error_count}\n\n"

    report += f"🕐 Отчет сформирован: {datetime.now().strftime('%H:%M:%S')}"
    
    try:
        logger.info(f"Отправляем ежедневный отчет за {yesterday}")
        result = await send_admin_alert(report, disable_notification=True)
        if result:
            logger.info(f"Ежедневный отчет за {yesterday} отправлен администратору успешно")
            cache.delete('daily_errors_count')
        else:
            logger.error(f"Не удалось отправить ежедневный отчет за {yesterday}")
        return result
    except Exception as e:
        logger.error(f"Ошибка отправки ежедневного отчета: {e}", exc_info=True)
        return False


async def notify_critical_error(error_type: str, details: str, user_id: Optional[int] = None):
    """
    Отправка уведомления о критической ошибке

    Args:
        error_type: Тип ошибки
        details: Детали ошибки
        user_id: ID пользователя (если применимо)
    """
    # Используем cache для предотвращения спама
    alert_key = f"critical_error:{error_type}"

    if cache.get(alert_key):
        # Уже отправляли недавно
        return

    message = (
        f"🚨 <b>[Coins] КРИТИЧЕСКАЯ ОШИБКА</b>\n\n"
        f"Тип: {error_type}\n"
    )

    if user_id:
        message += f"Пользователь: {user_id}\n"

    message += (
        f"Детали: {details[:200]}\n"  # Ограничиваем длину
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Требуется немедленная проверка!"
    )

    try:
        await send_admin_alert(message)
        cache.set(alert_key, True, 1800)  # Не отправляем повторно 30 минут

        # Увеличиваем счетчик ошибок дня
        daily_errors = cache.get('daily_errors_count', 0)
        cache.set('daily_errors_count', daily_errors + 1, 86400)

    except Exception as e:
        logger.error(f"Не удалось отправить критическое уведомление: {e}")


async def notify_payment_received(user_id: int, amount: float, payment_type: str):
    """
    Уведомление о получении платежа

    Args:
        user_id: ID пользователя
        amount: Сумма платежа
        payment_type: Тип платежа
    """
    # Форматируем сумму без лишних нулей
    amount_str = f"{int(amount)}" if amount == int(amount) else f"{amount:.2f}"
    message = (
        f"💳 <b>Получен платеж!</b>\n\n"
        f"Пользователь: {user_id}\n"
        f"Сумма: {amount_str} руб.\n"
        f"Тип: {payment_type}\n"
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        await send_admin_alert(message)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о платеже: {e}")


async def notify_bot_started():
    """Уведомление о запуске бота"""
    message = (
        f"✅ <b>[Coins] Бот запущен</b>\n\n"
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Версия: 1.0.0\n"
        f"Окружение: {'Development' if settings.DEBUG else 'Production'}"
    )

    try:
        await send_admin_alert(message, disable_notification=True)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о запуске: {e}")


async def notify_bot_stopped():
    """Уведомление об остановке бота"""
    message = (
        f"🛑 <b>[Coins] Бот остановлен</b>\n\n"
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        await send_admin_alert(message, disable_notification=True)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об остановке: {e}")
