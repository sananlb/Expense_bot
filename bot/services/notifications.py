import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from expenses.models import Profile, Expense, Budget
from ..services.expense import get_expenses_summary
from ..utils import format_amount, get_month_name

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def send_monthly_report(self, user_id: int, profile: Profile, year: int = None, month: int = None):
        """Send monthly expense report for specified year/month (defaults to current month)"""
        try:
            from ..services.pdf_report import PDFReportService
            from ..services.monthly_insights import MonthlyInsightsService
            from aiogram.types import BufferedInputFile

            today = date.today()

            # Если год/месяц не указаны - используем текущий месяц
            report_year = year if year is not None else today.year
            report_month = month if month is not None else today.month

            # Генерируем PDF отчет
            pdf_service = PDFReportService()
            pdf_bytes = await pdf_service.generate_monthly_report(
                user_id=user_id,
                year=report_year,
                month=report_month
            )

            month_name = get_month_name(report_month, 'ru')

            if pdf_bytes:
                # Генерируем AI инсайты для включения в caption
                caption = f"📊 Ежемесячный отчет за {month_name} {report_year}"

                try:
                    insights_service = MonthlyInsightsService()

                    # Проверяем существующий инсайт или генерируем новый
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
                        full_caption = f"{caption}\n\n{insight_text}"

                        # Telegram ограничивает caption до 1024 символов
                        if len(full_caption) <= 1024:
                            caption = full_caption
                        else:
                            # Если текст слишком длинный, обрезаем инсайт
                            max_insight_length = 1024 - len(caption) - 20  # -20 для "\n\n" и "..."
                            if max_insight_length > 100:
                                truncated_insight = insight_text[:max_insight_length] + "..."
                                caption = f"{caption}\n\n{truncated_insight}"
                            # Если даже обрезка не помогает, отправляем без инсайта

                        logger.info(f"Monthly insights generated for user {user_id} for {report_year}-{report_month:02d}")
                    else:
                        logger.info(f"No insights generated for user {user_id} for {report_year}-{report_month:02d} (not enough data)")

                except Exception as e:
                    logger.error(f"Error generating insights for user {user_id}: {e}")
                    # Продолжаем выполнение с базовым caption, даже если инсайты не удалось сгенерировать

                # Отправляем PDF файл с caption (включая инсайты если есть)
                pdf_file = BufferedInputFile(
                    pdf_bytes,
                    filename=f"monthly_report_{report_year}_{report_month:02d}.pdf"
                )

                await self.bot.send_document(
                    chat_id=user_id,
                    document=pdf_file,
                    caption=caption,
                    parse_mode='HTML'
                )

                logger.info(f"Monthly PDF report sent to user {user_id} for {report_year}-{report_month:02d}")

            # Если расходов не было - ничего не отправляем

        except Exception as e:
            logger.error(f"Error sending monthly report to user {user_id}: {e}")

    def _format_insight_text(self, insight, month: int, year: int) -> str:
        """Format insight for display in message"""
        # Месяцы на русском
        months_ru = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        period = f"{months_ru.get(month, month)} {year}"

        text = f"🤖 <b>AI анализ за {period}</b>\n\n"

        # Финансовая сводка (компактный формат)
        text += f"💰 Расходы: {float(insight.total_expenses):,.0f} ₽".replace(',', ' ')

        if insight.total_incomes > 0:
            balance = insight.balance
            balance_emoji = "📈" if balance >= 0 else "📉"
            balance_sign = "+" if balance >= 0 else ""
            text += f" | Баланс: {balance_emoji} {balance_sign}{float(balance):,.0f} ₽".replace(',', ' ')

        text += f"\n📊 Количество трат: {insight.expenses_count}\n\n"

        # Топ 3 категории (сокращено с 5)
        if insight.top_categories:
            text += f"🏆 <b>Топ категорий:</b>\n"
            for i, cat in enumerate(insight.top_categories[:3], 1):
                percentage = cat.get('percentage', 0)
                amount = cat.get('amount', 0)
                category_name = cat.get('category', 'Без категории')
                text += f"{i}. {category_name}: {amount:,.0f}₽ ({percentage:.0f}%)\n".replace(',', ' ')
            text += "\n"

        # AI резюме
        if insight.ai_summary:
            text += f"📝 {insight.ai_summary}\n\n"

        # AI анализ (только первые 3 пункта)
        if insight.ai_analysis:
            analysis_lines = insight.ai_analysis.split('\n')
            # Берем только первые 3 пункта
            key_points = [line for line in analysis_lines if line.strip().startswith('•')][:3]
            if key_points:
                text += f"📊 <b>Ключевые моменты:</b>\n"
                text += '\n'.join(key_points) + "\n"

        return text
    
    async def send_budget_warning(self, user_id: int, budget: Budget, spent: Decimal, percent: float):
        """Send budget warning notification"""
        try:
            period_text = {
                'daily': 'день',
                'weekly': 'неделю', 
                'monthly': 'месяц'
            }.get(budget.period, budget.period)
            
            # Получаем язык пользователя для правильного отображения
            from bot.utils.language import get_user_language
            user_lang = await get_user_language(user_id)
            
            if budget.category:
                category_display = budget.category.get_display_name(user_lang)
                cat_text = f" в категории {category_display}"
            else:
                cat_text = ""
            
            text = f"""⚠️ <b>Предупреждение о бюджете</b>
            
Вы потратили {percent:.0f}% от бюджета на {period_text}{cat_text}.

💰 Потрачено: {format_amount(spent, 'RUB', 'ru')}
📊 Лимит: {format_amount(budget.amount, 'RUB', 'ru')}
💵 Осталось: {format_amount(budget.amount - spent, 'RUB', 'ru')}"""
            
            if percent >= 100:
                text += "\n\n❗ <b>Бюджет превышен!</b>"
            elif percent >= 90:
                text += "\n\n⚠️ <b>Осталось менее 10% бюджета</b>"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Мои расходы", callback_data="expenses_today")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            logger.info(f"Budget warning sent to user {user_id} ({percent:.0f}%)")
            
        except Exception as e:
            logger.error(f"Error sending budget warning to user {user_id}: {e}")