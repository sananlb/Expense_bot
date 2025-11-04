import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from expenses.models import Profile, Expense
from ..services.expense import get_expenses_summary
from ..utils import format_amount, get_month_name

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def send_monthly_report_notification(self, user_id: int, profile: Profile, year: int = None, month: int = None):
        """Send monthly report notification with format selection buttons"""
        try:
            from ..services.monthly_insights import MonthlyInsightsService

            today = date.today()

            # Если год/месяц не указаны - используем предыдущий месяц
            if year is None or month is None:
                if today.month == 1:
                    report_month = 12
                    report_year = today.year - 1
                else:
                    report_month = today.month - 1
                    report_year = today.year
            else:
                report_year = year
                report_month = month

            month_name = get_month_name(report_month, 'ru')

            # Генерируем AI инсайты
            caption = f"📊 Ваш отчет за {month_name} {report_year} готов!"

            try:
                insights_service = MonthlyInsightsService()
                insight = await insights_service.get_insight(profile, report_year, report_month)

                if not insight:
                    # Генерируем новый инсайт
                    insight = await insights_service.generate_insight(
                        profile=profile,
                        year=report_year,
                        month=report_month,
                        provider='google',
                        force_regenerate=False
                    )

                if insight:
                    # Формируем текст инсайта и добавляем к caption
                    insight_text = self._format_insight_text(insight, report_month, report_year)
                    full_caption = f"{caption}\n\n{insight_text}\n\n💡 <i>Выберите формат отчета для скачивания:</i>"

                    # Telegram ограничивает текстовые сообщения до 4096 символов
                    if len(full_caption) <= 4000:
                        caption = full_caption
                    else:
                        # Если текст слишком длинный, обрезаем инсайт
                        max_insight_length = 4000 - len(caption) - 50
                        if max_insight_length > 100:
                            truncated_insight = insight_text[:max_insight_length] + "..."
                            caption = f"{caption}\n\n{truncated_insight}\n\n💡 <i>Выберите формат отчета для скачивания:</i>"
                        else:
                            caption += "\n\n💡 <i>Выберите формат отчета для скачивания:</i>"

                    logger.info(f"Monthly insights generated for user {user_id} for {report_year}-{report_month:02d}")
                else:
                    caption += "\n\n💡 <i>Выберите формат отчета для скачивания:</i>"
                    logger.info(f"No insights generated for user {user_id} for {report_year}-{report_month:02d} (not enough data)")

            except Exception as e:
                logger.error(f"Error generating insights for user {user_id}: {e}")
                caption += "\n\n💡 <i>Выберите формат отчета для скачивания:</i>"

            # Создаем клавиатуру с кнопками форматов (в один ряд)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 CSV", callback_data=f"monthly_report_csv_{report_year}_{report_month}"),
                    InlineKeyboardButton(text="📊 Excel", callback_data=f"monthly_report_xlsx_{report_year}_{report_month}"),
                    InlineKeyboardButton(text="📄 PDF", callback_data=f"monthly_report_pdf_{report_year}_{report_month}")
                ]
            ])

            # Отправляем сообщение с кнопками
            await self.bot.send_message(
                chat_id=user_id,
                text=caption,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

            logger.info(f"Monthly report notification sent to user {user_id} for {report_year}-{report_month:02d}")

        except Exception as e:
            logger.error(f"Error sending monthly report notification to user {user_id}: {e}")

    def _format_insight_text(self, insight, month: int, year: int) -> str:
        """Format insight for display in message"""
        text = ""

        # Финансовая сводка (каждый показатель с новой строки)
        text += f"💸 Расходы: {float(insight.total_expenses):,.0f} ₽\n".replace(',', ' ')
        text += f"💵 Доходы: {float(insight.total_incomes):,.0f} ₽\n".replace(',', ' ')

        # Баланс показываем всегда
        balance = insight.balance
        balance_emoji = "📈" if balance >= 0 else "📉"
        balance_sign = "+" if balance >= 0 else ""
        text += f"⚖️ Баланс: {balance_emoji} {balance_sign}{float(balance):,.0f} ₽\n".replace(',', ' ')

        text += f"🧮 Количество трат: {insight.expenses_count}\n\n"

        # Топ 5 категорий (только с ненулевыми расходами)
        if insight.top_categories:
            text += f"🏆 <b>Топ категорий:</b>\n"
            displayed_count = 0
            for cat in insight.top_categories:
                percentage = cat.get('percentage', 0)
                amount = cat.get('amount', 0)
                category_name = cat.get('category', 'Без категории')

                # Показываем только категории с ненулевыми расходами
                if amount > 0:
                    displayed_count += 1
                    text += f"{displayed_count}. {category_name}: {amount:,.0f}₽ ({percentage:.0f}%)\n".replace(',', ' ')

                    # Ограничиваем вывод 5 категориями
                    if displayed_count >= 5:
                        break
            text += "\n"

        # AI резюме
        if insight.ai_summary:
            text += f"📝 {insight.ai_summary}\n\n"

        # AI анализ (исключаем первый пункт о топ категории, берем 2-4 пункты)
        if insight.ai_analysis:
            analysis_lines = insight.ai_analysis.split('\n')
            # Берем только пункты со значком •
            all_points = [line for line in analysis_lines if line.strip().startswith('•')]
            # Пропускаем первый пункт (обычно дублирует топ категорию), берем следующие 3
            key_points = all_points[1:4] if len(all_points) > 1 else []
            if key_points:
                text += f"📊 <b>Ключевые моменты:</b>\n"
                text += '\n'.join(key_points) + "\n"

        return text