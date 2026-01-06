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
    ExpenseCategory, IncomeCategory, UserSettings
)
from .ai_selector import get_service, get_model, get_provider_settings, get_fallback_chain

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

    def _initialize_ai(self, provider: str = 'deepseek'):
        """Initialize AI service based on provider"""
        if not self.ai_service or self.ai_provider != provider:
            # Clear cache to force new provider
            from .ai_selector import AISelector
            AISelector.clear_cache()

            # Get service using AISelector directly with provider type
            self.ai_service = AISelector(provider)
            self.ai_provider = provider
            self.ai_model = get_model('insights', provider)
            logger.info(f"Initialized AI service: {provider} with model {self.ai_model}")

    def _is_provider_available(self, provider: str) -> bool:
        """Check provider availability based on configured API keys"""
        try:
            settings = get_provider_settings(provider)
        except Exception as e:
            logger.warning(f"Failed to load provider settings for {provider}: {e}")
            return False
        return settings.get('api_keys_available', False)

    def _get_fallback_providers(self, primary_provider: str) -> List[str]:
        """Return an ordered list of fallback providers excluding the primary one from .env settings"""
        return get_fallback_chain('insights', primary_provider)

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

        # Determine scope (personal vs household) and primary currency
        try:
            settings_obj = await asyncio.to_thread(
                lambda: UserSettings.objects.filter(profile=profile).first()
            )
        except Exception:
            settings_obj = None

        household_mode = (
            bool(getattr(profile, 'household_id', None)) and
            settings_obj and getattr(settings_obj, 'view_scope', 'personal') == 'household'
        )
        primary_currency = getattr(profile, 'currency', None) or 'RUB'

        def build_filters(prefix: str, start: datetime.date, end: datetime.date) -> Dict[str, object]:
            filters: Dict[str, object] = {
                f"{prefix}_date__gte": start,
                f"{prefix}_date__lte": end,
                "currency": primary_currency
            }
            if household_mode and getattr(profile, 'household', None):
                filters['profile__household'] = profile.household
            else:
                filters['profile'] = profile
            return filters

        # Collect expenses
        expenses = await asyncio.to_thread(
            lambda: list(Expense.objects.filter(
                **build_filters('expense', start_date, end_date)
            ).select_related('category').order_by('-expense_date'))
        )

        # Collect incomes
        incomes = await asyncio.to_thread(
            lambda: list(Income.objects.filter(
                **build_filters('income', start_date, end_date)
            ).select_related('category').order_by('-income_date'))
        )

        # Calculate totals
        total_expenses = sum(e.amount for e in expenses)
        total_incomes = sum(i.amount for i in incomes)

        # Group by categories
        user_lang = profile.language_code or 'ru'
        expenses_by_category: Dict[int, Dict[str, Any]] = {}
        for expense in expenses:
            if expense.category:
                cat_id = expense.category.id
                cat_name = expense.category.get_display_name(user_lang)
                if cat_id not in expenses_by_category:
                    expenses_by_category[cat_id] = {
                        'id': cat_id,
                        'name': cat_name,
                        'amount': Decimal('0'),
                        'count': 0,
                        'items': []
                    }
                expenses_by_category[cat_id]['amount'] += expense.amount
                expenses_by_category[cat_id]['count'] += 1
                expenses_by_category[cat_id]['items'].append({
                    'date': expense.expense_date.strftime('%d.%m'),
                    'amount': float(expense.amount),
                    'description': (expense.description or '')[:50]
                })

        # Sort categories by amount
        sorted_categories = sorted(
            expenses_by_category.values(),
            key=lambda x: x['amount'],
            reverse=True
        )

        # Prepare top categories for storage
        top_categories = []
        expenses_by_category_named = {}
        for cat_data in sorted_categories:
            expenses_by_category_named[cat_data['name']] = {
                'amount': cat_data['amount'],
                'count': cat_data['count'],
                'items': cat_data['items']
            }

        for cat_data in sorted_categories[:10]:
            percentage = (cat_data['amount'] / total_expenses * 100) if total_expenses > 0 else 0
            top_categories.append({
                'category_id': cat_data.get('id'),
                'category': cat_data.get('name'),
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
            'expenses_by_category': expenses_by_category_named,
            'top_categories': top_categories,
            'balance': total_incomes - total_expenses
        }

    async def _collect_historical_data(
        self,
        profile: Profile,
        year: int,
        month: int,
        months_back: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Collect historical expense data for the last N months (excluding current month)

        Args:
            profile: User profile
            year: Current year
            month: Current month (1-12)
            months_back: Number of months to collect (default: 6)

        Returns:
            List of monthly summaries sorted by date (oldest first)
        """
        from dateutil.relativedelta import relativedelta

        # Determine scope and currency
        try:
            settings_obj = await asyncio.to_thread(
                lambda: UserSettings.objects.filter(profile=profile).first()
            )
        except Exception:
            settings_obj = None

        household_mode = (
            bool(getattr(profile, 'household_id', None)) and
            settings_obj and getattr(settings_obj, 'view_scope', 'personal') == 'household'
        )
        primary_currency = getattr(profile, 'currency', None) or 'RUB'

        # Build filters for single aggregated query
        current_date = datetime(year, month, 1).date()
        start_date = current_date - relativedelta(months=months_back)

        def expense_filters():
            filters: Dict[str, object] = {
                "expense_date__gte": start_date,
                "expense_date__lt": current_date,
                "currency": primary_currency
            }
            if household_mode and getattr(profile, 'household', None):
                filters["profile__household"] = profile.household
            else:
                filters["profile"] = profile
            return filters

        def income_filters():
            filters: Dict[str, object] = {
                "income_date__gte": start_date,
                "income_date__lt": current_date,
                "currency": primary_currency
            }
            if household_mode and getattr(profile, 'household', None):
                filters["profile__household"] = profile.household
            else:
                filters["profile"] = profile
            return filters

        expenses_data = await asyncio.to_thread(
            lambda: list(
                Expense.objects.filter(**expense_filters())
                .values('expense_date__year', 'expense_date__month')
                .annotate(total=Sum('amount'), count=Count('id'))
            )
        )

        incomes_data = await asyncio.to_thread(
            lambda: list(
                Income.objects.filter(**income_filters())
                .values('income_date__year', 'income_date__month')
                .annotate(total=Sum('amount'), count=Count('id'))
            )
        )

        expenses_by_month = {
            (item['expense_date__year'], item['expense_date__month']): item
            for item in expenses_data
        }
        incomes_by_month = {
            (item['income_date__year'], item['income_date__month']): item
            for item in incomes_data
        }

        historical_data: List[Dict[str, Any]] = []
        for i in range(1, months_back + 1):
            target_date = current_date - relativedelta(months=i)
            key = (target_date.year, target_date.month)

            exp_data = expenses_by_month.get(key, {'total': 0, 'count': 0})
            inc_data = incomes_by_month.get(key, {'total': 0, 'count': 0})

            historical_data.append({
                'year': target_date.year,
                'month': target_date.month,
                'total_expenses': float(exp_data.get('total') or 0),
                'total_incomes': float(inc_data.get('total') or 0),
                'expenses_count': exp_data.get('count') or 0,
                'top_categories': []
            })

        historical_data.sort(key=lambda x: (x['year'], x['month']))
        return historical_data

    def _build_analysis_prompt(
        self,
        profile: Profile,
        month_data: Dict[str, Any],
        prev_month_data: Optional[Dict[str, Any]],
        year: int,
        month: int,
        historical_data: Optional[List[Dict[str, Any]]] = None
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
        # Get user language
        user_lang = profile.language_code or 'ru'

        # Get month name in user's language
        from bot.utils.language import get_month_name as get_month_name_i18n
        month_name = get_month_name_i18n(month, user_lang)

        # Month names for historical data
        months_ru = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }
        months_en = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        months_dict = months_en if user_lang == 'en' else months_ru

        # Helper функция для форматирования сумм без лишних нулей
        def format_amount(amount):
            """Форматирует сумму: если целая, то без дробной части"""
            return f"{int(amount)}" if amount == int(amount) else f"{float(amount):.2f}"

        # Prepare category details
        category_details = []
        for cat_name, cat_data in list(month_data['expenses_by_category'].items())[:10]:
            percentage = (cat_data['amount'] / month_data['total_expenses'] * 100) if month_data['total_expenses'] > 0 else 0
            category_details.append(
                f"- {cat_name}: {format_amount(cat_data['amount'])} ₽ ({percentage:.1f}%, {cat_data['count']} трат)"
            )

        # Build comparison section if previous month data exists
        comparison_section = ""
        has_income = month_data['total_incomes'] > 0

        if prev_month_data:
            # Calculate previous month
            prev_month = month - 1 if month > 1 else 12
            prev_month_name = months_dict.get(prev_month, str(prev_month))

            # Calculate changes
            expense_change = month_data['total_expenses'] - prev_month_data['total_expenses']
            expense_change_pct = (expense_change / prev_month_data['total_expenses'] * 100) if prev_month_data['total_expenses'] > 0 else 0

            # Include income comparison only if current month has income
            expense_change_str = f"+{format_amount(expense_change)}" if expense_change >= 0 else format_amount(expense_change)
            if has_income:
                comparison_section = f"""
СРАВНЕНИЕ С ПРЕДЫДУЩИМ МЕСЯЦЕМ ({prev_month_name}):
- Расходы в прошлом месяце: {format_amount(prev_month_data['total_expenses'])} ₽
- Изменение расходов: {expense_change_str} ₽ ({expense_change_pct:+.1f}%)
- Доходы в прошлом месяце: {format_amount(prev_month_data['total_incomes'])} ₽
- Количество трат в прошлом месяце: {len(prev_month_data['expenses'])}
"""
            else:
                comparison_section = f"""
СРАВНЕНИЕ С ПРЕДЫДУЩИМ МЕСЯЦЕМ ({prev_month_name}):
- Расходы в прошлом месяце: {format_amount(prev_month_data['total_expenses'])} ₽
- Изменение расходов: {expense_change_str} ₽ ({expense_change_pct:+.1f}%)
- Количество трат в прошлом месяце: {len(prev_month_data['expenses'])}
"""

        # Build historical context section if available
        historical_section = ""
        # Only show history if we have at least 3 months with actual data
        valid_historical_data = [h for h in (historical_data or []) if h['total_expenses'] > 0]

        if valid_historical_data and len(valid_historical_data) >= 3:
            historical_lines = []
            for h in valid_historical_data:
                h_month_name = months_dict.get(h['month'], str(h['month']))

                # Format top categories (only show if exist)
                if h['top_categories']:
                    top_cats = ", ".join([f"{c['category']} ({format_amount(c['amount'])}₽)" for c in h['top_categories'][:2]])
                    historical_lines.append(
                        f"- {h_month_name} {h['year']}: {format_amount(h['total_expenses'])} ₽ (топ: {top_cats})"
                    )
                else:
                    historical_lines.append(
                        f"- {h_month_name} {h['year']}: {format_amount(h['total_expenses'])} ₽"
                    )

            historical_section = f"""
ИСТОРИЧЕСКИЙ КОНТЕКСТ (последние {len(valid_historical_data)} месяцев):
{chr(10).join(historical_lines)}
"""

        # Build expense details section (top 50 expenses for detailed analysis)
        expense_details_section = ""
        if len(month_data['expenses']) > 0:
            # Sort expenses by amount (highest first)
            sorted_expenses = sorted(month_data['expenses'], key=lambda x: x.amount, reverse=True)
            top_expenses = sorted_expenses[:50]  # Limit to top 50

            expense_lines = []
            for exp in top_expenses[:20]:  # Show only top 20 in prompt to save tokens
                exp_date = exp.expense_date.strftime('%d.%m')
                exp_desc = exp.description[:30] if exp.description else '(без описания)'
                exp_amount = format_amount(exp.amount)
                expense_lines.append(f"  - {exp_date}: {exp_desc} - {exp_amount}₽")

            if len(top_expenses) > 20:
                expense_lines.append(f"  ... и ещё {len(top_expenses) - 20} трат")

            expense_details_section = f"""
ДЕТАЛИ КРУПНЫХ ТРАТ:
{chr(10).join(expense_lines)}
"""

        # Analyze large expenses (significantly above average)
        large_expenses_section = ""
        if len(month_data['expenses']) >= 5:
            avg_expense = month_data['total_expenses'] / len(month_data['expenses'])
            # Find expenses significantly above average (2x or more)
            large = [
                exp for exp in month_data['expenses']
                if exp.amount >= avg_expense * 2
            ]

            if large:
                large_lines = []
                for exp in sorted(large, key=lambda x: x.amount, reverse=True)[:5]:
                    exp_date = exp.expense_date.strftime('%d.%m')
                    exp_desc = exp.description[:30] if exp.description else '(без описания)'
                    exp_amount = format_amount(exp.amount)
                    # Get category name
                    cat_name = exp.category.get_display_name(user_lang) if exp.category else '(без категории)'
                    large_lines.append(f"  - {exp_date}: {exp_desc} - {exp_amount}₽ [категория: {cat_name}]")

                large_expenses_section = f"""
КРУПНЫЕ ТРАТЫ (выше среднего):
Средняя трата: {format_amount(avg_expense)}₽
{chr(10).join(large_lines)}
"""

        # Analyze regular expenses (by description frequency)
        regular_expenses_section = ""
        if len(month_data['expenses']) >= 3:
            from collections import Counter

            # Count descriptions (normalized) with category info
            desc_counter = Counter()
            desc_amounts = {}
            desc_categories = {}  # Store category for each description

            for exp in month_data['expenses']:
                if exp.description:
                    # Normalize description (lowercase, trim)
                    desc_norm = exp.description.lower().strip()[:50]
                    desc_counter[desc_norm] += 1

                    if desc_norm not in desc_amounts:
                        desc_amounts[desc_norm] = []
                        desc_categories[desc_norm] = None  # Will be set when we find a category
                    desc_amounts[desc_norm].append(float(exp.amount))
                    # Update category if current expense has one and we don't have one yet
                    if desc_categories[desc_norm] is None and exp.category:
                        desc_categories[desc_norm] = exp.category.get_display_name(user_lang)

            # Find recurring expenses (2+ times)
            regular = [(desc, count) for desc, count in desc_counter.most_common(10) if count >= 2]

            if regular:
                regular_lines = []
                for desc, count in regular[:5]:
                    amounts = desc_amounts[desc]
                    avg_amount = sum(amounts) / len(amounts)
                    total_amount = sum(amounts)
                    cat_name = desc_categories.get(desc) or '(без категории)'
                    regular_lines.append(
                        f"  - \"{desc[:30]}\": {count}x, средняя {format_amount(avg_amount)}₽, всего {format_amount(total_amount)}₽ [категория: {cat_name}]"
                    )

                regular_expenses_section = f"""
РЕГУЛЯРНЫЕ РАСХОДЫ:
{chr(10).join(regular_lines)}
"""

        # Build financial summary section (only expenses if no income)
        if has_income:
            finance_section = f"""ДАННЫЕ ЗА ТЕКУЩИЙ МЕСЯЦ:
- Всего потрачено: {format_amount(month_data['total_expenses'])} ₽
- Всего доходов: {format_amount(month_data['total_incomes'])} ₽
- Баланс: {format_amount(month_data['balance'])} ₽
- Количество трат: {len(month_data['expenses'])}"""
        else:
            finance_section = f"""ДАННЫЕ ЗА ТЕКУЩИЙ МЕСЯЦ:
- Всего потрачено: {format_amount(month_data['total_expenses'])} ₽
- Количество трат: {len(month_data['expenses'])}"""

        # Build prompt based on user language
        if user_lang == 'en':
            prompt = f"""You are a financial analyst. Analyze the user's expenses for {month_name} {year}.

{finance_section}

EXPENSES BY CATEGORY:
{chr(10).join(category_details)}
{comparison_section}{historical_section}{expense_details_section}{large_expenses_section}{regular_expenses_section}
TASK:
Create a deep financial analysis in JSON format with two sections:

1. "summary" - brief monthly summary (3-4 sentences):
   - Main figures{"and comparison with previous month" if prev_month_data else ""}
   - {"Expense dynamics (growth/decline) and main reasons for this dynamic" if prev_month_data else "Overall expense picture"}
   - {"Context relative to historical data" if valid_historical_data and len(valid_historical_data) >= 3 else ""}

2. "analysis" - detailed analysis (3 points):
   - **{"Large expenses" if large_expenses_section else "Spending patterns"}:** Highlight the largest purchases, use category info provided in brackets
   - **{"Regular expenses" if regular_expenses_section else "Spending habits"}:** Indicate recurring expenses using category info provided in brackets
   - Specific recommendation on how to optimize expenses or what to pay attention to (WITHOUT title/header, just the advice text)

IMPORTANT:
- Write in English, concisely and to the point
- Use specific figures from data (amounts, percentages, dates)
- Use category information provided in [категория: ...] brackets - do NOT invent categories
- {"MUST compare with previous month where appropriate" if prev_month_data else ""}
- {"DO NOT mention income and balance, focus only on expenses" if not has_income else ""}
- Tone is friendly, motivating, but professional
- Response format: JSON with "summary", "analysis" fields
- In "analysis" field use array of 3 strings (each string is a separate point with bullet marker)"""
        else:
            prompt = f"""Ты финансовый аналитик. Проанализируй траты пользователя за {month_name} {year} года.

{finance_section}

РАСХОДЫ ПО КАТЕГОРИЯМ:
{chr(10).join(category_details)}
{comparison_section}{historical_section}{expense_details_section}{large_expenses_section}{regular_expenses_section}
ЗАДАНИЕ:
Создай глубокий анализ финансов в формате JSON с двумя разделами:

1. "summary" - краткое резюме месяца (3-4 предложения):
   - Основные цифры{"и сравнение с прошлым месяцем" if prev_month_data else ""}
   - {"Динамика трат (рост/снижение) и основные причины такой динамики" if prev_month_data else "Общая картина расходов"}
   - {"Контекст относительно исторических данных" if valid_historical_data and len(valid_historical_data) >= 3 else ""}

2. "analysis" - детальный анализ (3 пункта):
   - **{"Крупные траты" if large_expenses_section else "Паттерны трат"}:** Выдели самые большие покупки, используй категорию из скобок [категория: ...]
   - **{"Регулярные расходы" if regular_expenses_section else "Финансовые привычки"}:** Укажи повторяющиеся траты, используй категорию из скобок [категория: ...]
   - Конкретная рекомендация как оптимизировать расходы или на что обратить внимание (БЕЗ заголовка "Персональный совет:", только текст совета)

ВАЖНО:
- Пиши на русском языке, кратко и по делу
- Используй конкретные цифры из данных (суммы, проценты, даты)
- Используй информацию о категориях из скобок [категория: ...] — НЕ выдумывай категории
- {"ОБЯЗАТЕЛЬНО сравнивай с предыдущим месяцем где уместно" if prev_month_data else ""}
- {"НЕ упоминай доходы и баланс, фокусируйся только на расходах" if not has_income else ""}
- Тон дружелюбный, мотивирующий, но профессиональный
- Формат ответа: JSON с полями "summary", "analysis"
- В поле "analysis" используй массив из 3 строк (каждая строка - отдельный пункт с маркером)"""

        return prompt

    async def _generate_ai_insights(
        self,
        profile: Profile,
        month_data: Dict[str, Any],
        prev_month_data: Optional[Dict[str, Any]],
        year: int,
        month: int,
        provider: str = 'deepseek',
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, str]:
        """
        Generate AI insights using the specified provider

        Args:
            profile: User profile
            month_data: Collected month data
            prev_month_data: Previous month data for comparison
            year: Year
            month: Month
            provider: AI provider ('deepseek', 'openrouter', 'openai', etc.)

        Returns:
            Dictionary with AI-generated texts
        """
        self._initialize_ai(provider)

        # Build prompt with comparison data and historical context
        prompt = self._build_analysis_prompt(
            profile, month_data, prev_month_data, year, month, historical_data
        )

        logger.info(f"Generating insights for user {profile.telegram_id} for {month}/{year}")

        # Retry logic: try up to 2 times with same provider (different API keys)
        # before falling back to another provider
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Re-initialize AI service on retry (refresh instance and key rotation state)
                if attempt > 0:
                    logger.warning(f"Retrying {provider} (attempt {attempt + 1}/{max_retries}) for user {profile.telegram_id}")
                    self.ai_service = None
                    self._initialize_ai(provider)

                # Call AI service with function calling disabled
                # (insights generation requires JSON response, not function calls)
                response = await self.ai_service.chat(
                    message=prompt,
                    context=[],
                    user_context={'user_id': profile.telegram_id},
                    disable_functions=True  # IMPORTANT: Skip function calling for JSON response
                )

                # Check if response is an error message
                error_phrases = [
                    'извините',
                    'временно недоступен',
                    'service unavailable',
                    'error occurred',
                    'request timed out'
                ]
                if any(phrase in response.lower() for phrase in error_phrases):
                    raise Exception(f"AI returned error response: {response[:100]}")

                # If we got here, the call succeeded - break retry loop
                break

            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed for {provider}: {e}")
                if attempt < max_retries - 1:
                    continue  # Try again with next API key
                else:
                    # All retries exhausted, re-raise to trigger provider fallback
                    raise

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
                result['analysis'] = '\n\n'.join(result['analysis'])

            return {
                'summary': result['summary'],
                'analysis': result['analysis'],
                'recommendations': ''  # Empty string for backwards compatibility
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response was: {response[:500]}")

            # Check if response contains error message from AI service
            error_phrases = [
                'извините',
                'временно недоступен',
                'service unavailable',
                'error',
                'failed'
            ]

            if any(phrase in response.lower() for phrase in error_phrases):
                # AI service returned error - re-raise to trigger fallback provider
                logger.error("AI service returned error response, triggering provider fallback")
                raise Exception(f"AI provider returned error: {response[:200]}")

            # Otherwise try to parse response as text (non-JSON format)
            try:
                parsed = self._fallback_parse_response(response)
                if parsed and parsed.get('summary') and parsed.get('analysis'):
                    return parsed
                else:
                    raise ValueError("Fallback parsing returned empty result")
            except Exception as parse_error:
                # If parsing completely fails, re-raise to trigger provider fallback
                logger.error(f"Fallback parsing failed: {parse_error}")
                raise Exception(f"Failed to parse AI response: {e}")

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

    def _generate_basic_summary(
        self,
        month_data: Dict[str, Any],
        prev_month_data: Optional[Dict[str, Any]],
        year: int,
        month: int
    ) -> Dict[str, str]:
        """
        Generate basic summary when AI fails
        Returns minimal but useful information as fallback

        Args:
            month_data: Current month data
            prev_month_data: Previous month data (optional)
            year: Year
            month: Month

        Returns:
            Dictionary with summary and analysis
        """
        months_ru = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }
        month_name = months_ru.get(month, str(month))

        total = float(month_data['total_expenses'])
        count = len(month_data['expenses'])

        # Basic summary
        summary = f"За {month_name} вы потратили {total:,.0f} рублей ({count} трат).".replace(',', ' ')

        # Add comparison if available
        if prev_month_data:
            prev_total = float(prev_month_data['total_expenses'])
            change = total - prev_total
            change_pct = (change / prev_total * 100) if prev_total > 0 else 0

            if change > 0:
                summary += f" Это на {change:,.0f}₽ ({change_pct:.0f}%) больше, чем в прошлом месяце.".replace(',', ' ')
            elif change < 0:
                summary += f" Это на {abs(change):,.0f}₽ ({abs(change_pct):.0f}%) меньше, чем в прошлом месяце.".replace(',', ' ')
            else:
                summary += " Траты остались на том же уровне."

        # Basic analysis with 4 bullet points
        analysis_parts = []

        # Point 1: Top category or general note
        top_cats = list(month_data['expenses_by_category'].items())[:3]
        if top_cats:
            cat_name, cat_data = top_cats[0]
            cat_amount = float(cat_data['amount'])
            cat_pct = (cat_amount / total * 100) if total > 0 else 0
            analysis_parts.append(f"• Основная категория: {cat_name} ({cat_amount:,.0f}₽, {cat_pct:.0f}%)".replace(',', ' '))
        else:
            analysis_parts.append("• За этот месяц трат не было")

        # Point 2: Comparison observation
        if prev_month_data:
            change = total - float(prev_month_data['total_expenses'])
            if change > 0:
                analysis_parts.append("• Расходы выросли по сравнению с прошлым месяцем")
            elif change < 0:
                analysis_parts.append("• Расходы снизились по сравнению с прошлым месяцем")
            else:
                analysis_parts.append("• Расходы остались на том же уровне")
        else:
            analysis_parts.append("• Финансовое поведение в пределах нормы")

        # Point 3: Spending pattern
        avg_expense = total / count if count > 0 else 0
        analysis_parts.append(f"• Средняя трата: {avg_expense:,.0f}₽".replace(',', ' '))

        # Point 4: Generic advice
        analysis_parts.append("• Совет: продолжайте отслеживать расходы для контроля бюджета")

        analysis = '\n\n'.join(analysis_parts)

        return {
            'summary': summary,
            'analysis': analysis,
            'recommendations': ''  # Empty for backwards compatibility
        }

    async def generate_insight(
        self,
        profile: Profile,
        year: Optional[int] = None,
        month: Optional[int] = None,
        provider: str = 'deepseek',
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

        # Check if user has active subscription
        from expenses.models import Subscription
        has_active_subscription = await asyncio.to_thread(
            lambda: Subscription.objects.filter(
                profile=profile,
                is_active=True,
                end_date__gt=timezone.now()
            ).exists()
        )

        if not has_active_subscription:
            logger.info(f"User {profile.telegram_id} doesn't have active subscription, skipping insight generation")
            return None

        # Check if insight already exists
        existing_insight = await asyncio.to_thread(
            lambda: MonthlyInsight.objects.filter(
                profile=profile,
                year=year,
                month=month
            ).select_related('profile').first()
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

            # Collect historical data (last 3-6 months)
            historical_data = []
            try:
                historical_data = await self._collect_historical_data(profile, year, month, months_back=6)
                # Filter out months with insufficient data
                historical_data = [
                    h for h in historical_data
                    if h['total_expenses'] > 0 and h['expenses_count'] >= 3
                ]
                logger.info(f"Collected {len(historical_data)} months of historical data for user {profile.telegram_id}")
            except Exception as e:
                logger.warning(f"Failed to collect historical data: {e}")
                historical_data = []

            # Generate AI insights with comparison, historical context and fallback
            ai_insights = None

            primary_provider = provider
            try:
                ai_insights = await self._generate_ai_insights(
                    profile, month_data, prev_month_data, year, month, provider, historical_data
                )
            except Exception as e:
                logger.error(f"Primary AI provider ({provider}) failed: {e}")
                fallback_chain = self._get_fallback_providers(provider)

                for fallback_provider in fallback_chain:
                    try:
                        logger.warning(
                            f"Attempting fallback to {fallback_provider} for user {profile.telegram_id}"
                        )
                        ai_insights = await self._generate_ai_insights(
                            profile, month_data, prev_month_data, year, month, fallback_provider, historical_data
                        )
                        provider = fallback_provider
                        await self._notify_admin_fallback(
                            profile.telegram_id, year, month, primary_provider, fallback_provider
                        )
                        break
                    except Exception as fallback_error:
                        logger.error(
                            f"{fallback_provider} fallback also failed for user {profile.telegram_id}: {fallback_error}"
                        )

                if not ai_insights:
                    # All AI providers failed - use basic summary as final fallback
                    logger.error(f"All AI providers failed for user {profile.telegram_id}, using basic summary")
                    await self._notify_admin_failure(profile.telegram_id, year, month)
                    ai_insights = self._generate_basic_summary(month_data, prev_month_data, year, month)
                    provider = 'basic'  # Mark that we used basic fallback

            # Validate AI result before saving
            if not ai_insights or not ai_insights.get('summary') or not ai_insights.get('analysis'):
                logger.warning(f"AI response empty for user {profile.telegram_id}, using basic summary fallback")
                ai_insights = self._generate_basic_summary(month_data, prev_month_data, year, month)
                provider = 'basic'

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
            ).select_related('profile').first()
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
            from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2

            message = (
                f"⚠️ *AI Provider Fallback*\n\n"
                f"*User:* `{user_id}`\n"
                f"*Period:* {month}/{year}\n"
                f"*Primary provider failed:* {escape_markdown_v2(primary_provider)}\n"
                f"*Fallback used:* {escape_markdown_v2(fallback_provider)}\n\n"
                f"Check logs for details\\."
            )

            await send_admin_alert(message)
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
            from bot.services.admin_notifier import send_admin_alert, escape_markdown_v2

            message = (
                f"🔴 *AI Insights Generation Failed*\n\n"
                f"*User:* `{user_id}`\n"
                f"*Period:* {month}/{year}\n"
                f"*Status:* All AI providers failed\n\n"
                f"User will receive monthly report without AI insights\\.\n"
                f"Check logs and AI service status\\."
            )

            await send_admin_alert(message)
            logger.info(f"Admin notified about complete AI failure for {user_id} {month}/{year}")
        except Exception as e:
            logger.error(f"Failed to notify admin about failure: {e}")
