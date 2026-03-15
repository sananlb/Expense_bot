"""
Роутер для команды /blogger_stats - просмотр статистики для блогеров
"""
from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
import logging
from typing import Optional

from bot.services.utm_tracking import get_blogger_stats_by_name
from bot.services.profile import get_or_create_profile
from bot.utils.message_utils import send_message_with_cleanup
from bot.utils.logging_safe import summarize_text

logger = logging.getLogger(__name__)

router = Router(name="blogger_stats")


def format_blogger_stats(stats: dict, lang: str = 'ru') -> str:
    """
    Форматирование статистики блогера в красивый отчет

    Args:
        stats: Словарь со статистикой
        lang: Язык отчета

    Returns:
        Отформатированная строка с отчетом
    """
    if not stats.get('found'):
        if lang == 'en':
            return (
                "📊 <b>Blogger Statistics</b>\n\n"
                f"❌ No data found for blogger <b>{stats.get('blogger_name', 'unknown')}</b>\n\n"
                "Please check:\n"
                "• The blogger name is correct\n"
                "• Users have registered through your link\n"
                "• Format: /blogger_stats NAME (without b_ prefix)"
            )
        else:
            return (
                "📊 <b>Статистика блогера</b>\n\n"
                f"❌ Нет данных по блогеру <b>{stats.get('blogger_name', 'неизвестно')}</b>\n\n"
                "Проверьте:\n"
                "• Правильность имени блогера\n"
                "• Были ли регистрации по вашей ссылке\n"
                "• Формат: /blogger_stats ИМЯ (без префикса b_)"
            )

    # Подготовка данных
    name = stats['blogger_name']
    total = stats['total_users']
    active = stats['active_users']
    paying = stats['paying_users']
    trial = stats['trial_users']
    conv_active = stats['conversion_to_active']
    conv_paying = stats['conversion_to_paying']
    campaigns = stats.get('campaigns', [])

    # Определяем эмодзи для эффективности
    if conv_paying >= 15:
        efficiency_emoji = "🔥"
        efficiency_text = "Отлично!" if lang == 'ru' else "Excellent!"
    elif conv_paying >= 10:
        efficiency_emoji = "✅"
        efficiency_text = "Хорошо" if lang == 'ru' else "Good"
    elif conv_paying >= 5:
        efficiency_emoji = "📈"
        efficiency_text = "Нормально" if lang == 'ru' else "Normal"
    else:
        efficiency_emoji = "📊"
        efficiency_text = "Нужно улучшать" if lang == 'ru' else "Needs improvement"

    if lang == 'en':
        text = (
            f"📊 <b>Blogger Statistics: {name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👥 <b>Users</b>\n"
            f"├ Total registered: <b>{total}</b>\n"
            f"├ Active (7 days): <b>{active}</b>\n"
            f"├ Trial subscription: <b>{trial}</b>\n"
            f"└ Paid subscription: <b>{paying}</b>\n\n"

            f"📈 <b>Conversions</b>\n"
            f"├ To active: <b>{conv_active:.1f}%</b>\n"
            f"└ To paying: <b>{conv_paying:.1f}%</b>\n\n"

            f"{efficiency_emoji} <b>Efficiency: {efficiency_text}</b>\n"
        )

        # Добавляем ссылки-примеры
        if campaigns:
            text += "\n🔗 <b>Your links:</b>\n"
            for camp in campaigns[:3]:  # Показываем максимум 3
                text += f"• t.me/showmecoinbot?start=b_{camp}\n"
        else:
            text += f"\n🔗 <b>Your link:</b>\n"
            text += f"t.me/showmecoinbot?start=b_{name}\n"

        text += (
            "\n💡 <b>Tips:</b>\n"
            "• Use different links for different content\n"
            "• Track which format works better\n"
            "• Example: b_yourname_stories, b_yourname_reels"
        )

    else:  # Russian
        text = (
            f"📊 <b>Статистика блогера: {name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👥 <b>Пользователи</b>\n"
            f"├ Всего зарегистрировано: <b>{total}</b>\n"
            f"├ Активных (7 дней): <b>{active}</b>\n"
            f"├ С пробной подпиской: <b>{trial}</b>\n"
            f"└ С платной подпиской: <b>{paying}</b>\n\n"

            f"📈 <b>Конверсии</b>\n"
            f"├ В активных: <b>{conv_active:.1f}%</b>\n"
            f"└ В платящих: <b>{conv_paying:.1f}%</b>\n\n"

            f"{efficiency_emoji} <b>Эффективность: {efficiency_text}</b>\n"
        )

        # Добавляем ссылки-примеры
        if campaigns:
            text += "\n🔗 <b>Ваши ссылки:</b>\n"
            for camp in campaigns[:3]:  # Показываем максимум 3
                text += f"• t.me/showmecoinbot?start=b_{camp}\n"
        else:
            text += f"\n🔗 <b>Ваша ссылка:</b>\n"
            text += f"t.me/showmecoinbot?start=b_{name}\n"

        text += (
            "\n💡 <b>Советы:</b>\n"
            "• Используйте разные ссылки для разного контента\n"
            "• Отслеживайте, какой формат работает лучше\n"
            "• Пример: b_вашеимя_stories, b_вашеимя_reels"
        )

    return text


@router.message(Command("blogger_stats"))
async def cmd_blogger_stats(
    message: types.Message,
    state: FSMContext,
    command: Optional[CommandObject] = None,
    lang: str = 'ru'
):
    """Команда /blogger_stats - показать статистику для блогера"""

    user_id = message.from_user.id

    # Получаем аргументы команды
    blogger_name = None
    if command and command.args:
        blogger_name = command.args.strip()
        # Удаляем префикс b_ если пользователь его ввел (регистронезависимо)
        if blogger_name.lower().startswith('b_'):
            blogger_name = blogger_name[2:]

    if not blogger_name:
        # Показываем инструкцию
        if lang == 'en':
            text = (
                "📊 <b>Blogger Statistics</b>\n\n"
                "To view your statistics, use:\n"
                "<code>/blogger_stats YOUR_NAME</code>\n\n"
                "Example:\n"
                "• <code>/blogger_stats ivan</code>\n"
                "• <code>/blogger_stats maria</code>\n\n"
                "Use the same name as in your link:\n"
                "If your link is <code>b_ivan</code>, use <code>ivan</code>"
            )
        else:
            text = (
                "📊 <b>Статистика блогера</b>\n\n"
                "Для просмотра вашей статистики используйте:\n"
                "<code>/blogger_stats ВАШЕ_ИМЯ</code>\n\n"
                "Пример:\n"
                "• <code>/blogger_stats ivan</code>\n"
                "• <code>/blogger_stats maria</code>\n\n"
                "Используйте то же имя, что и в вашей ссылке:\n"
                "Если ваша ссылка <code>b_ivan</code>, используйте <code>ivan</code>"
            )
        await send_message_with_cleanup(message, state, text, parse_mode="HTML")
        return

    # Отправляем сообщение о загрузке
    loading_text = "⏳ Загружаю статистику..." if lang == 'ru' else "⏳ Loading statistics..."
    loading_msg = await message.answer(loading_text)

    try:
        # Получаем статистику
        stats = await get_blogger_stats_by_name(blogger_name)

        # Форматируем отчет
        report_text = format_blogger_stats(stats, lang)

        # Удаляем сообщение о загрузке
        try:
            await loading_msg.delete()
        except Exception as delete_error:
            logger.debug("Failed to delete blogger stats loading message: %s", delete_error)

        # Отправляем отчет
        await send_message_with_cleanup(message, state, report_text, parse_mode="HTML")

        # Логируем запрос
        if stats.get('found'):
            logger.info(
                "Blogger stats requested blogger=%s users=%s paying=%s",
                summarize_text(blogger_name),
                stats['total_users'],
                stats['paying_users'],
            )
        else:
            logger.info(
                "Blogger stats requested but no data found blogger=%s",
                summarize_text(blogger_name),
            )

    except Exception as e:
        logger.error(
            "Error getting blogger stats blogger=%s",
            summarize_text(blogger_name),
            exc_info=True,
        )

        # Удаляем сообщение о загрузке
        try:
            await loading_msg.delete()
        except Exception as delete_error:
            logger.debug("Failed to delete blogger stats loading message after error: %s", delete_error)

        error_text = (
            "❌ Произошла ошибка при получении статистики. Попробуйте позже."
            if lang == 'ru' else
            "❌ Error getting statistics. Please try again later."
        )
        await send_message_with_cleanup(message, state, error_text)
