"""
Service for generating AI-powered monthly insights about user's expenses
"""
import logging
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from expenses.models import (
    Profile, Expense, Income, MonthlyInsight,
    ExpenseCategory, IncomeCategory
)
from .ai_selector import get_service, get_model

logger = logging.getLogger(__name__)

# Throttling for admin notifications (avoid spam)
_last_fallback_notification = {}
_last_failure_notification = {}
NOTIFICATION_THROTTLE_HOURS = 1  # Only notify once per hour


class MonthlyInsightsService:
    """Service for generating monthly financial insights using AI"""

    def __init__(self):
        """Initialize the service"""
        self.ai_service = None
        self.ai_provider = None
        self.ai_model = None

    def _initialize_ai(self, provider: str = 'google'):
        """Initialize AI service based on provider"""
        if not self.ai_service or self.ai_provider != provider:
            # Use provider-specific service instead of always 'default'
            self.ai_service = get_service(provider)
            self.ai_provider = provider
            self.ai_model = get_model(provider, provider)
            logger.info(f"Initialized AI service: {provider} with model {self.ai_model}")

    async def _collect_month_data(
        self,
        profile: Profile,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Collect all financial data for the specified month

        Args:
            profile: User profile
            year: Year
            month: Month (1-12)

        Returns:
            Dictionary with financial data
        """
        # Calculate date range
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()

        # Collect expenses
        expenses = await asyncio.to_thread(
            lambda: list(Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('-expense_date'))
        )

        # Collect incomes
        incomes = await asyncio.to_thread(
            lambda: list(Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            ).select_related('category').order_by('-income_date'))
        )

        # Calculate totals
        total_expenses = sum(e.amount for e in expenses)
        total_incomes = sum(i.amount for i in incomes)

        # Group by categories
        expenses_by_category = {}
        for expense in expenses:
            if expense.category:
                cat_name = expense.category.get_display_name('ru')
                if cat_name not in expenses_by_category:
                    expenses_by_category[cat_name] = {
                        'amount': Decimal('0'),
                        'count': 0,
                        'items': []
                    }
                expenses_by_category[cat_name]['amount'] += expense.amount
                expenses_by_category[cat_name]['count'] += 1
                expenses_by_category[cat_name]['items'].append({
                    'date': expense.expense_date.strftime('%d.%m'),
                    'amount': float(expense.amount),
                    'description': expense.description[:50]
                })

        # Sort categories by amount
        sorted_categories = sorted(
            expenses_by_category.items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        )

        # Prepare top categories for storage
        top_categories = []
        for cat_name, cat_data in sorted_categories[:10]:
            percentage = (cat_data['amount'] / total_expenses * 100) if total_expenses > 0 else 0
            top_categories.append({
                'category': cat_name,
                'amount': float(cat_data['amount']),
                'percentage': round(float(percentage), 2),
                'count': cat_data['count']
            })

        return {
            'start_date': start_date,
            'end_date': end_date,
            'expenses': expenses,
            'incomes': incomes,
            'total_expenses': total_expenses,
            'total_incomes': total_incomes,
            'expenses_by_category': dict(sorted_categories),
            'top_categories': top_categories,
            'balance': total_incomes - total_expenses
        }

    def _build_analysis_prompt(
        self,
        profile: Profile,
        month_data: Dict[str, Any],
        prev_month_data: Optional[Dict[str, Any]],
        year: int,
        month: int
    ) -> str:
        """
        Build prompt for AI analysis

        Args:
            profile: User profile
            month_data: Collected month data
            prev_month_data: Previous month data for comparison (optional)
            year: Year
            month: Month

        Returns:
            Prompt string
        """
        months_ru = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }

        month_name = months_ru.get(month, str(month))

        # Prepare category details
        category_details = []
        for cat_name, cat_data in list(month_data['expenses_by_category'].items())[:10]:
            percentage = (cat_data['amount'] / month_data['total_expenses'] * 100) if month_data['total_expenses'] > 0 else 0
            category_details.append(
                f"- {cat_name}: {float(cat_data['amount']):.2f} ₽ ({percentage:.1f}%, {cat_data['count']} трат)"
            )

        # Build comparison section if previous month data exists
        comparison_section = ""
        if prev_month_data:
            # Calculate previous month
            prev_month = month - 1 if month > 1 else 12
            prev_month_name = months_ru.get(prev_month, str(prev_month))

            # Calculate changes
            expense_change = month_data['total_expenses'] - prev_month_data['total_expenses']
            expense_change_pct = (expense_change / prev_month_data['total_expenses'] * 100) if prev_month_data['total_expenses'] > 0 else 0

            comparison_section = f"""
СРАВНЕНИЕ С ПРЕДЫДУЩИМ МЕСЯЦЕМ ({prev_month_name}):
- Расходы в прошлом месяце: {float(prev_month_data['total_expenses']):.2f} ₽
- Изменение расходов: {float(expense_change):+.2f} ₽ ({expense_change_pct:+.1f}%)
- Доходы в прошлом месяце: {float(prev_month_data['total_incomes']):.2f} ₽
- Количество трат в прошлом месяце: {len(prev_month_data['expenses'])}
"""

        prompt = f"""Ты финансовый аналитик. Проанализируй траты пользователя за {month_name} {year} года.

ДАННЫЕ ЗА ТЕКУЩИЙ МЕСЯЦ:
- Всего потрачено: {float(month_data['total_expenses']):.2f} ₽
- Всего доходов: {float(month_data['total_incomes']):.2f} ₽
- Баланс: {float(month_data['balance']):.2f} ₽
- Количество трат: {len(month_data['expenses'])}

РАСХОДЫ ПО КАТЕГОРИЯМ:
{chr(10).join(category_details)}
{comparison_section}
ЗАДАНИЕ:
Создай два раздела анализа в формате JSON:

1. "summary" - краткое резюме месяца (1-2 предложения). Основные цифры{"и сравнение с прошлым месяцем" if prev_month_data else ""}.

2. "analysis" - ключевые моменты (максимум 3 пункта):
   - Самая большая категория расходов{"и её изменение" if prev_month_data else ""}
   - {"Динамика по сравнению с прошлым месяцем" if prev_month_data else "Необычные траты"}
   - {"Общий тренд (рост/снижение расходов)" if prev_month_data else "Финансовое поведение"}

ВАЖНО:
- Пиши на русском языке, кратко и по делу
- Используй конкретные цифры из данных
- {"ОБЯЗАТЕЛЬНО указывай сравнение с предыдущим месяцем" if prev_month_data else ""}
- Тон дружелюбный и мотивирующий
- Формат ответа: JSON с полями "summary", "analysis"
- В поле "analysis" используй массив из 3 коротких строк

Пример формата ответа:
{{
  "summary": "За {month_name} вы потратили X рублей, что на Y% {"меньше/больше чем в прошлом месяце" if prev_month_data else "при Z тратах"}.",
  "analysis": [
    "Основная категория: название (X₽, Y%)",
    "{"Расходы снизились/выросли на X%" if prev_month_data else "Заметная трата: описание"}",
    "{"Количество трат: X (было Y)" if prev_month_data else "Общее финансовое поведение"}"
  ]
}}"""

        return prompt

    async def _generate_ai_insights(
        self,
        profile: Profile,
        month_data: Dict[str, Any],
        prev_month_data: Optional[Dict[str, Any]],
        year: int,
        month: int,
        provider: str = 'google'
    ) -> Dict[str, str]:
        """
        Generate AI insights using the specified provider

        Args:
            profile: User profile
            month_data: Collected month data
            prev_month_data: Previous month data for comparison
            year: Year
            month: Month
            provider: AI provider ('google' or 'openai')

        Returns:
            Dictionary with AI-generated texts
        """
        self._initialize_ai(provider)

        # Build prompt with comparison data
        prompt = self._build_analysis_prompt(profile, month_data, prev_month_data, year, month)

        logger.info(f"Generating insights for user {profile.telegram_id} for {month}/{year}")

        try:
            # Call AI service
            if provider == 'google':
                # For Google, use the chat method with empty context
                response = await self.ai_service.chat(
                    message=prompt,
                    context=[],
                    user_context={'user_id': profile.telegram_id}
                )
            else:
                # For OpenAI, use the chat method
                response = await self.ai_service.chat(
                    message=prompt,
                    context=[],
                    user_context={'user_id': profile.telegram_id}
                )

            # Parse JSON response
            try:
                # Try to extract JSON from response
                if '```json' in response:
                    # Extract JSON from markdown code block
                    json_start = response.find('```json') + 7
                    json_end = response.find('```', json_start)
                    json_str = response[json_start:json_end].strip()
                elif '```' in response:
                    # Extract from generic code block
                    json_start = response.find('```') + 3
                    json_end = response.find('```', json_start)
                    json_str = response[json_start:json_end].strip()
                else:
                    json_str = response

                result = json.loads(json_str)

                # Validate result structure (only summary and analysis now)
                if not all(key in result for key in ['summary', 'analysis']):
                    raise ValueError("Missing required fields in AI response")

                # Convert lists to formatted strings if needed
                if isinstance(result['analysis'], list):
                    result['analysis'] = '\n\n'.join(f"• {item}" for item in result['analysis'])

                return {
                    'summary': result['summary'],
                    'analysis': result['analysis'],
                    'recommendations': ''  # Empty string for backwards compatibility
                }

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response was: {response[:500]}")

                # Fallback: split response into sections
                return self._fallback_parse_response(response)

        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")
            raise

    def _fallback_parse_response(self, response: str) -> Dict[str, str]:
        """
        Fallback parser if JSON parsing fails

        Args:
            response: AI response text

        Returns:
            Dictionary with parsed sections
        """
        # Try to split by common section markers
        sections = {
            'summary': '',
            'analysis': '',
            'recommendations': ''
        }

        lines = response.split('\n')
        current_section = None

        for line in lines:
            line_lower = line.lower()

            if any(marker in line_lower for marker in ['резюме', 'summary', 'итог']):
                current_section = 'summary'
            elif any(marker in line_lower for marker in ['анализ', 'analysis', 'разбор']):
                current_section = 'analysis'
            elif any(marker in line_lower for marker in ['рекоменд', 'recommend', 'совет']):
                current_section = 'recommendations'
            elif current_section and line.strip():
                sections[current_section] += line + '\n'

        # If parsing failed, put everything in summary
        if not sections['summary'] and not sections['analysis']:
            sections['summary'] = response[:500]
            sections['analysis'] = response[500:1500] if len(response) > 500 else ''
            sections['recommendations'] = response[1500:] if len(response) > 1500 else ''

        return sections

    async def generate_insight(
        self,
        profile: Profile,
        year: Optional[int] = None,
        month: Optional[int] = None,
        provider: str = 'google',
        force_regenerate: bool = False
    ) -> Optional[MonthlyInsight]:
        """
        Generate or retrieve monthly insight for a user

        Args:
            profile: User profile
            year: Year (default: current year)
            month: Month (default: current month)
            provider: AI provider to use
            force_regenerate: Force regeneration even if insight exists

        Returns:
            MonthlyInsight instance or None if generation failed
        """
        # Default to current month if not specified
        if year is None or month is None:
            now = timezone.now()
            year = year or now.year
            month = month or now.month

        # Check if insight already exists
        existing_insight = await asyncio.to_thread(
            lambda: MonthlyInsight.objects.filter(
                profile=profile,
                year=year,
                month=month
            ).first()
        )

        if existing_insight and not force_regenerate:
            logger.info(f"Returning existing insight for {profile.telegram_id} {month}/{year}")
            return existing_insight

        try:
            # Collect month data
            month_data = await self._collect_month_data(profile, year, month)

            # Check if there's enough data
            if month_data['total_expenses'] == 0 or len(month_data['expenses']) < 3:
                logger.info(f"Not enough data for insights: {len(month_data['expenses'])} expenses")
                return None

            # Collect previous month data for comparison
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1

            try:
                prev_month_data = await self._collect_month_data(profile, prev_year, prev_month)
                # Only use comparison if previous month has meaningful data
                if prev_month_data['total_expenses'] == 0 or len(prev_month_data['expenses']) < 3:
                    prev_month_data = None
                    logger.info(f"Previous month ({prev_month}/{prev_year}) has insufficient data for comparison")
            except Exception as e:
                logger.warning(f"Failed to collect previous month data: {e}")
                prev_month_data = None

            # Generate AI insights with comparison and fallback
            ai_insights = None
            fallback_used = False

            try:
                ai_insights = await self._generate_ai_insights(
                    profile, month_data, prev_month_data, year, month, provider
                )
            except Exception as e:
                logger.error(f"Primary AI provider ({provider}) failed: {e}")

                # Try fallback to OpenAI if primary was Google
                if provider == 'google':
                    try:
                        logger.warning(f"Attempting fallback to OpenAI for user {profile.telegram_id}")
                        ai_insights = await self._generate_ai_insights(
                            profile, month_data, prev_month_data, year, month, 'openai'
                        )
                        fallback_used = True
                        provider = 'openai'  # Update provider for storage

                        # Notify admin about fallback
                        await self._notify_admin_fallback(profile.telegram_id, year, month, 'google', 'openai')
                    except Exception as fallback_error:
                        logger.error(f"OpenAI fallback also failed: {fallback_error}")
                        # Notify admin about complete failure
                        await self._notify_admin_failure(profile.telegram_id, year, month)
                        raise
                else:
                    # Primary was OpenAI, no fallback available
                    await self._notify_admin_failure(profile.telegram_id, year, month)
                    raise

            # Create or update insight
            if existing_insight:
                # Update existing
                existing_insight.total_expenses = month_data['total_expenses']
                existing_insight.total_incomes = month_data['total_incomes']
                existing_insight.expenses_count = len(month_data['expenses'])
                existing_insight.top_categories = month_data['top_categories']
                existing_insight.ai_summary = ai_insights['summary']
                existing_insight.ai_analysis = ai_insights['analysis']
                existing_insight.ai_recommendations = ai_insights['recommendations']
                existing_insight.ai_model_used = self.ai_model
                existing_insight.ai_provider = provider
                existing_insight.regeneration_count += 1
                existing_insight.last_regenerated_at = timezone.now()

                await asyncio.to_thread(existing_insight.save)
                logger.info(f"Updated insight for {profile.telegram_id} {month}/{year}")

                return existing_insight
            else:
                # Create new
                insight = await asyncio.to_thread(
                    MonthlyInsight.objects.create,
                    profile=profile,
                    year=year,
                    month=month,
                    total_expenses=month_data['total_expenses'],
                    total_incomes=month_data['total_incomes'],
                    expenses_count=len(month_data['expenses']),
                    top_categories=month_data['top_categories'],
                    ai_summary=ai_insights['summary'],
                    ai_analysis=ai_insights['analysis'],
                    ai_recommendations=ai_insights['recommendations'],
                    ai_model_used=self.ai_model,
                    ai_provider=provider
                )

                logger.info(f"Created new insight for {profile.telegram_id} {month}/{year}")
                return insight

        except Exception as e:
            logger.error(f"Error generating monthly insight: {e}", exc_info=True)
            return None

    async def get_insight(
        self,
        profile: Profile,
        year: Optional[int] = None,
        month: Optional[int] = None
    ) -> Optional[MonthlyInsight]:
        """
        Get existing monthly insight

        Args:
            profile: User profile
            year: Year (default: current year)
            month: Month (default: current month)

        Returns:
            MonthlyInsight instance or None
        """
        if year is None or month is None:
            now = timezone.now()
            year = year or now.year
            month = month or now.month

        insight = await asyncio.to_thread(
            lambda: MonthlyInsight.objects.filter(
                profile=profile,
                year=year,
                month=month
            ).first()
        )

        return insight

    async def mark_as_viewed(self, insight: MonthlyInsight):
        """Mark insight as viewed by user"""
        if not insight.is_viewed:
            insight.is_viewed = True
            insight.viewed_at = timezone.now()
            await asyncio.to_thread(insight.save)

    async def rate_insight(self, insight: MonthlyInsight, rating: int):
        """
        Rate the insight

        Args:
            insight: MonthlyInsight instance
            rating: Rating (1-5)
        """
        if 1 <= rating <= 5:
            insight.user_rating = rating
            await asyncio.to_thread(insight.save)
            logger.info(f"Insight {insight.id} rated {rating} stars")

    async def _notify_admin_fallback(self, user_id: int, year: int, month: int,
                                    primary_provider: str, fallback_provider: str):
        """
        Notify admin about AI provider fallback with throttling

        Args:
            user_id: User telegram ID
            year: Year
            month: Month
            primary_provider: Provider that failed
            fallback_provider: Provider used as fallback
        """
        global _last_fallback_notification

        now = timezone.now()
        key = f"{primary_provider}_to_{fallback_provider}"

        # Check if we already notified recently (throttling)
        if key in _last_fallback_notification:
            time_since_last = (now - _last_fallback_notification[key]).total_seconds() / 3600
            if time_since_last < NOTIFICATION_THROTTLE_HOURS:
                logger.debug(f"Skipping admin fallback notification (throttled, last: {time_since_last:.1f}h ago)")
                return

        # Update last notification time
        _last_fallback_notification[key] = now

        try:
            from ..services.admin_notifier import notify_admin

            message = (
                f"⚠️ <b>AI Provider Fallback</b>\n\n"
                f"<b>User:</b> {user_id}\n"
                f"<b>Period:</b> {month}/{year}\n"
                f"<b>Primary provider failed:</b> {primary_provider}\n"
                f"<b>Fallback used:</b> {fallback_provider}\n\n"
                f"Check logs for details."
            )

            await notify_admin(message, level='warning')
            logger.info(f"Admin notified about fallback from {primary_provider} to {fallback_provider}")
        except Exception as e:
            logger.error(f"Failed to notify admin about fallback: {e}")

    async def _notify_admin_failure(self, user_id: int, year: int, month: int):
        """
        Notify admin about complete AI generation failure with throttling

        Args:
            user_id: User telegram ID
            year: Year
            month: Month
        """
        global _last_failure_notification

        now = timezone.now()
        key = f"failure_{year}_{month}"

        # Check if we already notified recently (throttling)
        if key in _last_failure_notification:
            time_since_last = (now - _last_failure_notification[key]).total_seconds() / 3600
            if time_since_last < NOTIFICATION_THROTTLE_HOURS:
                logger.debug(f"Skipping admin failure notification (throttled, last: {time_since_last:.1f}h ago)")
                return

        # Update last notification time
        _last_failure_notification[key] = now

        try:
            from ..services.admin_notifier import notify_admin

            message = (
                f"🔴 <b>AI Insights Generation Failed</b>\n\n"
                f"<b>User:</b> {user_id}\n"
                f"<b>Period:</b> {month}/{year}\n"
                f"<b>Status:</b> All AI providers failed\n\n"
                f"User will receive monthly report without AI insights.\n"
                f"Check logs and AI service status."
            )

            await notify_admin(message, level='critical')
            logger.info(f"Admin notified about complete AI failure for {user_id} {month}/{year}")
        except Exception as e:
            logger.error(f"Failed to notify admin about failure: {e}")
