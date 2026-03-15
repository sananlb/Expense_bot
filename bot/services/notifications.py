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
from bot.utils.language import get_text
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def send_monthly_report_notification(
        self,
        user_id: int,
        profile: Profile,
        year: int = None,
        month: int = None,
        attempt: int = 1,
    ) -> bool:
        """Send monthly report notification with format selection buttons."""
        from ..services.monthly_insights import MonthlyInsightsService
        from django.core.cache import cache

        today = date.today()

        # Get user language first
        user_lang = profile.language_code or 'ru'

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

        month_name = get_month_name(report_month, user_lang)

        # Генерируем AI инсайты
        caption = f"📊 {get_text('monthly_report_ready', user_lang, month=month_name, year=report_year)}"

        try:
            insights_service = MonthlyInsightsService()
            insight = await insights_service.get_insight(profile, report_year, report_month)

            if not insight:
                # Генерируем новый инсайт
                insight = await insights_service.generate_insight(
                    profile=profile,
                    year=report_year,
                    month=report_month,
                    provider='deepseek',  # Use DeepSeek instead of Google
                    force_regenerate=False
                )

            # Check if insight is valid and doesn't contain error messages
            error_phrases = ['извините', 'временно недоступен', 'service unavailable', 'error', 'failed', 'test summary']
            has_error = insight and insight.ai_summary and any(
                phrase in insight.ai_summary.lower() for phrase in error_phrases
            )

            # Check minimum summary length (real AI summaries are at least 50 characters)
            is_too_short = insight and insight.ai_summary and len(insight.ai_summary.strip()) < 50

            if not insight or not insight.ai_summary or has_error or is_too_short:
                # Инсайт не сгенерирован или содержит ошибку - НЕ отправляем уведомление вообще
                if has_error:
                    logger.warning(
                        "Insight contains error message for %s period=%s-%02d. Notification not sent.",
                        log_safe_id(user_id, "user"),
                        report_year,
                        report_month,
                    )
                elif is_too_short:
                    logger.warning(
                        "Insight summary too short (%s chars) for %s period=%s-%02d. Notification not sent.",
                        len(insight.ai_summary.strip()),
                        log_safe_id(user_id, "user"),
                        report_year,
                        report_month,
                    )
                elif insight:
                    logger.warning(
                        "Insight exists but ai_summary is empty for %s period=%s-%02d. Notification not sent.",
                        log_safe_id(user_id, "user"),
                        report_year,
                        report_month,
                    )
                else:
                    logger.info(
                        "No insights generated for %s period=%s-%02d (not enough data). Notification not sent.",
                        log_safe_id(user_id, "user"),
                        report_year,
                        report_month,
                    )
                return False

            # Формируем текст инсайта и добавляем к caption
            # ВАЖНО: показываем инсайт только если он успешно сгенерирован (не содержит сообщений об ошибках)
            insight_text = await self._format_insight_text(insight, report_month, report_year, user_lang)
            choose_format_text = get_text('monthly_report_choose_format', user_lang)
            full_caption = f"{caption}\n\n{insight_text}\n\n💡 <i>{choose_format_text}</i>"

            # Telegram ограничивает текстовые сообщения до 4096 символов
            if len(full_caption) <= 4000:
                caption = full_caption
            else:
                # Если текст слишком длинный, обрезаем инсайт
                max_insight_length = 4000 - len(caption) - 50
                if max_insight_length > 100:
                    truncated_insight = insight_text[:max_insight_length] + "..."
                    caption = f"{caption}\n\n{truncated_insight}\n\n💡 <i>{choose_format_text}</i>"
                else:
                    caption += f"\n\n💡 <i>{choose_format_text}</i>"

            logger.info(
                "Monthly insights generated for %s period=%s-%02d",
                log_safe_id(user_id, "user"),
                report_year,
                report_month,
            )

        except Exception as e:
            # Ошибка при генерации инсайтов - НЕ отправляем уведомление вообще
            logger.error(
                "Error generating insights for %s: %s. Notification not sent.",
                log_safe_id(user_id, "user"),
                e,
            )
            return False

        # Создаем клавиатуру с кнопками форматов (в один ряд)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 CSV", callback_data=f"monthly_report_csv_{report_year}_{report_month}"),
                InlineKeyboardButton(text="📈 XLSX", callback_data=f"monthly_report_xlsx_{report_year}_{report_month}"),
                InlineKeyboardButton(text="📊 PDF", callback_data=f"monthly_report_pdf_{report_year}_{report_month}")
            ]
        ])

        # Idempotency check - don't send duplicates
        sent_key = f"monthly_report_sent:{user_id}:{report_year}:{report_month}"
        if cache.get(sent_key):
            logger.info(
                "[MONTHLY_REPORT] user=%s status=already_sent period=%s-%02d",
                log_safe_id(user_id, "user"),
                report_year,
                report_month,
            )
            return False

        # Prevent concurrent sends from parallel workers for the same user/period.
        inflight_key = f"monthly_report_sending:{user_id}:{report_year}:{report_month}"
        if not cache.add(inflight_key, True, timeout=600):
            logger.info(
                "[MONTHLY_REPORT] user=%s status=in_progress period=%s-%02d",
                log_safe_id(user_id, "user"),
                report_year,
                report_month,
            )
            return False

        try:
            # Let Telegram exceptions bubble up so Celery can decide retry strategy.
            await self.bot.send_message(
                chat_id=user_id,
                text=caption,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

            # Mark as sent for idempotency (keep for 7 days)
            cache.set(sent_key, True, timeout=86400 * 7)

            logger.info(
                "[MONTHLY_REPORT] user=%s status=sent attempt=%s period=%s-%02d",
                log_safe_id(user_id, "user"),
                attempt,
                report_year,
                report_month,
            )
            return True
        finally:
            cache.delete(inflight_key)

    async def _calculate_category_changes(self, insight, month: int, year: int):
        """
        Calculate category changes compared to previous month
        Called ONCE per user per month when sending notification

        Data is fetched directly from DB (Expense table) for reliability,
        not from cached MonthlyInsight which may have outdated format.

        Args:
            insight: Current month MonthlyInsight instance
            month: Current month (1-12)
            year: Current year

        Returns:
            List of category changes sorted by absolute change (biggest first)
        """
        import asyncio
        from calendar import monthrange
        from django.db.models import Sum
        from expenses.models import Expense

        # Get previous month dates
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        _, last_day = monthrange(prev_year, prev_month)
        prev_start = datetime(prev_year, prev_month, 1).date()
        prev_end = datetime(prev_year, prev_month, last_day).date()

        # Get previous month expenses grouped by category directly from DB
        currency = insight.profile.currency or 'RUB'
        prev_expenses = await asyncio.to_thread(
            lambda: list(
                Expense.objects.filter(
                    profile=insight.profile,
                    expense_date__gte=prev_start,
                    expense_date__lte=prev_end,
                    category__isnull=False,
                    currency=currency
                ).values(
                    'category_id',
                    'category__name',
                    'category__name_ru',
                    'category__name_en',
                    'category__icon'
                ).annotate(
                    total=Sum('amount')
                )
            )
        )

        if not prev_expenses:
            return []  # No previous data to compare

        # Build dicts for fast lookup by category_id and category name (legacy insights)
        prev_cats = {}
        prev_cats_by_name = {}
        for exp in prev_expenses:
            cat_id = exp['category_id']
            prev_cats[cat_id] = float(exp['total'] or 0)
            icon = (exp.get('category__icon') or '').strip()
            name_variants = [
                exp.get('category__name'),
                exp.get('category__name_ru'),
                exp.get('category__name_en'),
            ]
            for name in name_variants:
                if not name:
                    continue
                normalized = str(name).strip()
                if normalized:
                    prev_cats_by_name[normalized] = prev_cats[cat_id]
                    if icon and not normalized.startswith(icon):
                        prev_cats_by_name[f"{icon} {normalized}"] = prev_cats[cat_id]

        changes = []
        for cat in insight.top_categories:
            cat_id = cat.get('category_id')
            cat_name = cat.get('category')
            current_amount = cat.get('amount', 0)

            # Look up previous amount by category_id; fallback to name for legacy insights
            if cat_id:
                prev_amount = prev_cats.get(cat_id, 0)
            else:
                prev_amount = prev_cats_by_name.get(str(cat_name).strip(), 0) if cat_name else 0

            # Calculate change (new categories have prev_amount = 0)
            change = current_amount - prev_amount

            # Only show categories with meaningful change (>= 100 RUB to avoid noise)
            if abs(change) < 100:
                continue

            # Calculate percentage change
            if prev_amount > 0:
                # Existing category: calculate normal percentage
                change_pct = (change / prev_amount * 100)
            else:
                # New category: show as +100% (появилась впервые)
                change_pct = 100.0

            changes.append({
                'category': cat_name,
                'change': change,
                'change_percent': round(change_pct, 1),
                'trend': '📈' if change > 0 else '📉' if change < 0 else '➡️'
            })

        # Sort by absolute change (biggest changes first)
        changes.sort(key=lambda x: abs(x['change']), reverse=True)
        return changes

    async def _format_insight_text(self, insight, month: int, year: int, lang: str = 'ru') -> str:
        """Format insight for display in message"""
        from bot.utils.language import format_amount

        text = ""

        # Get user currency
        currency = insight.profile.currency or 'RUB'

        # Финансовая сводка (каждый показатель с новой строки)
        expenses_label = get_text('monthly_report_expenses', lang)
        text += f"💸 {expenses_label}: {format_amount(float(insight.total_expenses), currency, lang)}\n"

        # NEW: Если нет доходов - явно об этом сказать
        if insight.total_incomes > 0:
            incomes_label = get_text('monthly_report_incomes', lang)
            text += f"💵 {incomes_label}: {format_amount(float(insight.total_incomes), currency, lang)}\n"
        else:
            no_incomes_text = get_text('monthly_report_no_incomes', lang)
            text += f"ℹ️ <i>{no_incomes_text}</i>\n"

        # Баланс показываем всегда
        balance = insight.balance
        balance_emoji = "📈" if balance >= 0 else "📉"
        balance_sign = "+" if balance >= 0 else "-"
        balance_label = get_text('monthly_report_balance', lang)
        text += f"⚖️ {balance_label}: {balance_emoji} {balance_sign}{format_amount(abs(float(balance)), currency, lang)}\n"

        expenses_count_label = get_text('monthly_report_expenses_count', lang)
        text += f"🧮 {expenses_count_label}: {insight.expenses_count}\n\n"

        # Топ 5 категорий (только с ненулевыми расходами)
        if insight.top_categories:
            top_categories_label = get_text('monthly_report_top_categories', lang)
            text += f"🏆 <b>{top_categories_label}</b>\n"
            displayed_count = 0
            for cat in insight.top_categories:
                percentage = cat.get('percentage', 0)
                amount = cat.get('amount', 0)
                category_name = cat.get('category', get_text('no_category', lang))

                # Показываем только категории с ненулевыми расходами
                if amount > 0:
                    displayed_count += 1
                    text += f"{displayed_count}. {category_name}: {format_amount(amount, currency, lang)} ({percentage:.0f}%)\n"

                    # Ограничиваем вывод 5 категориями
                    if displayed_count >= 5:
                        break
            text += "\n"

        # NEW: Топ-5 изменений с прошлого месяца
        category_changes = await self._calculate_category_changes(insight, month, year)
        if category_changes:
            category_changes_label = get_text('monthly_report_category_changes', lang)
            text += f"📈 <b>{category_changes_label}</b>\n"
            for i, change in enumerate(category_changes[:5], 1):
                cat_name = change['category']
                change_pct = change['change_percent']
                change_amount = change['change']
                trend = change['trend']

                sign = '+' if change_amount > 0 else '-' if change_amount < 0 else ''
                text += f"{i}. {cat_name}: {sign}{format_amount(abs(change_amount), currency, lang)} ({sign}{abs(change_pct):.0f}% {trend})\n"
            text += "\n"

        # AI резюме
        if insight.ai_summary:
            text += f"📝 {insight.ai_summary}\n\n"

        # AI анализ
        if insight.ai_analysis:
            analysis_lines = insight.ai_analysis.split('\n')

            # Check format: Russian format uses "•" bullets, English format uses "**Title:**"
            has_bullets = any(line.strip().startswith('•') for line in analysis_lines)

            if has_bullets:
                # Russian format: берем только пункты со значком •
                all_points = [line for line in analysis_lines if line.strip().startswith('•')]
                # Берем все 3 пункта (крупные траты, регулярные расходы, совет)
                key_points = all_points[:3]

                if key_points:
                    key_points_label = get_text('monthly_report_key_points', lang) if lang == 'en' else 'Ключевые моменты:'
                    text += f"🔍 <b>{key_points_label}</b>\n"
                    # Remove bullets and add blank lines between points
                    formatted_points = []
                    import re
                    for point in key_points:
                        # Remove bullet marker and strip whitespace
                        clean_point = point.strip().lstrip('•').strip()
                        # Convert markdown **bold** to HTML <b>bold</b>
                        clean_point = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', clean_point)
                        # Remove "Персональный совет:" prefix if present
                        clean_point = re.sub(r'^Персональный совет:\s*', '', clean_point, flags=re.IGNORECASE)
                        clean_point = re.sub(r'^Personal advice:\s*', '', clean_point, flags=re.IGNORECASE)
                        formatted_points.append(clean_point)
                    text += '\n\n'.join(formatted_points) + "\n"
            else:
                # English format: split by double newlines to get individual points
                points = [p.strip() for p in insight.ai_analysis.split('\n\n') if p.strip()]

                # Take all 3 points (large expenses, regular expenses, advice)
                key_points = points[:3]

                if key_points:
                    key_points_label = get_text('monthly_report_key_points', lang) if lang == 'en' else 'Ключевые моменты:'
                    text += f"🔍 <b>{key_points_label}</b>\n"
                    # Convert markdown bold to HTML and add blank lines between points
                    formatted_points = []
                    for p in key_points:
                        # Convert markdown **bold** to HTML <b>bold</b>
                        import re
                        p_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', p)
                        formatted_points.append(p_html)
                    text += '\n\n'.join(formatted_points) + "\n"

        return text
