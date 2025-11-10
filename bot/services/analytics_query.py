"""
Analytics Query System - Safe, flexible database queries via JSON specification.
This module provides a fallback mechanism for complex user queries not covered
by explicit functions, using validated JSON specs compiled to Django ORM.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Literal, Union
from pydantic import BaseModel, Field, validator, root_validator
from django.db.models import Q, Sum, Count, Avg, Max, Min, QuerySet, F
from django.db.models.functions import TruncDate, ExtractWeekDay
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async

from expenses.models import Expense, Income, Profile, ExpenseCategory, IncomeCategory
from bot.utils.language import get_text

logger = logging.getLogger(__name__)


# Constants for validation
MAX_LIMIT = 100
MAX_DATE_RANGE_DAYS = 365
ALLOWED_ENTITIES = ['expenses', 'incomes', 'operations']
ALLOWED_GROUP_BY = ['none', 'date', 'category', 'weekday']
ALLOWED_AGGREGATES = ['sum', 'count', 'avg', 'max', 'min']
ALLOWED_SORT_BY = ['sum', 'avg', 'max', 'min', 'amount', 'date', 'count']
ALLOWED_SORT_DIR = ['asc', 'desc']
ALLOWED_PERIODS = ['today', 'yesterday', 'day_before_yesterday', 'week', 'month', 'year',
                   'last_week', 'last_month', 'last_year', 'week_before_last', 'month_before_last']

# Projection fields whitelist for each entity
ALLOWED_PROJECTIONS = {
    'expenses': ['date', 'amount', 'category', 'description', 'currency'],
    'incomes': ['date', 'amount', 'category', 'description', 'currency'],
    'operations': ['date', 'amount', 'type', 'category', 'description', 'currency']
}


class DateFilter(BaseModel):
    """Date filter specification."""
    between: Optional[List[str]] = Field(None, min_items=2, max_items=2)
    period: Optional[Literal['today', 'yesterday', 'day_before_yesterday', 'week', 'month', 'year',
                             'last_week', 'last_month', 'last_year', 'week_before_last', 'month_before_last']] = None

    @validator('between')
    def validate_between(cls, v):
        if v:
            try:
                start = datetime.fromisoformat(v[0]).date()
                end = datetime.fromisoformat(v[1]).date()

                # Ensure start <= end
                if start > end:
                    raise ValueError("Start date must be before or equal to end date")

                # Limit date range to 1 year
                if (end - start).days > MAX_DATE_RANGE_DAYS:
                    raise ValueError(f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days")

                # Don't allow future dates
                today = date.today()
                if end > today:
                    v[1] = today.isoformat()

            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid date format: {e}")
        return v

    @root_validator(skip_on_failure=True)
    def validate_exclusive(cls, values):
        if values.get('between') and values.get('period'):
            raise ValueError("Cannot specify both 'between' and 'period'")
        if not values.get('between') and not values.get('period'):
            # Default to current month if no date filter specified
            values['period'] = 'month'
        return values


class CategoryFilter(BaseModel):
    """Category filter specification."""
    equals: Optional[str] = None
    contains: Optional[str] = None
    id: Optional[int] = Field(None, gt=0)

    @root_validator(skip_on_failure=True)
    def validate_exclusive(cls, values):
        specified = sum(1 for v in [values.get('equals'), values.get('contains'), values.get('id')] if v)
        if specified > 1:
            raise ValueError("Can only specify one of: equals, contains, or id")
        return values


class AmountFilter(BaseModel):
    """Amount filter specification."""
    gte: Optional[float] = Field(None, ge=0)
    lte: Optional[float] = Field(None, ge=0)

    @root_validator(skip_on_failure=True)
    def validate_range(cls, values):
        gte = values.get('gte')
        lte = values.get('lte')
        if gte is not None and lte is not None and gte > lte:
            raise ValueError("gte must be less than or equal to lte")
        return values


class TextFilter(BaseModel):
    """Text search filter specification."""
    contains: str = Field(..., min_length=1, max_length=100)


class SortSpec(BaseModel):
    """Sort specification."""
    by: Literal['sum', 'avg', 'max', 'min', 'amount', 'date', 'count']
    dir: Literal['asc', 'desc'] = 'desc'


class FiltersSpec(BaseModel):
    """Filters specification."""
    date: Optional[DateFilter] = None
    category: Optional[CategoryFilter] = None
    amount: Optional[AmountFilter] = None
    text: Optional[TextFilter] = None


class AnalyticsQuerySpec(BaseModel):
    """Main analytics query specification."""
    version: Literal[1] = 1  # For future compatibility
    entity: Literal['expenses', 'incomes', 'operations']
    filters: Optional[FiltersSpec] = Field(default_factory=FiltersSpec)
    group_by: Optional[Literal['none', 'date', 'category', 'weekday']] = 'none'
    aggregate: Optional[List[Literal['sum', 'count', 'avg', 'max', 'min']]] = Field(
        default_factory=lambda: ['sum', 'count']
    )
    sort: Optional[List[SortSpec]] = Field(default_factory=list, max_items=3)
    limit: int = Field(default=10, ge=1, le=MAX_LIMIT)
    projection: Optional[List[str]] = None

    @validator('projection')
    def validate_projection(cls, v, values):
        if v and 'entity' in values:
            entity = values['entity']
            allowed = ALLOWED_PROJECTIONS.get(entity, [])
            invalid = set(v) - set(allowed)
            if invalid:
                raise ValueError(f"Invalid projection fields for {entity}: {invalid}")
        return v

    @validator('sort')
    def validate_sort_compatibility(cls, v, values):
        group_by = values.get('group_by', 'none')
        if v and group_by == 'none':
            # For non-grouped queries, can only sort by direct fields
            for sort_spec in v:
                if sort_spec.by in ['sum', 'avg', 'max', 'min', 'count']:
                    raise ValueError(f"Cannot sort by {sort_spec.by} without grouping")
        return v


class AnalyticsQueryExecutor:
    """Executes validated analytics queries safely."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.profile = None

    def _get_profile(self) -> Profile:
        """Get user profile (without creating)."""
        if not self.profile:
            try:
                self.profile = Profile.objects.get(telegram_id=self.user_id)
            except Profile.DoesNotExist:
                raise ValueError(f"Profile not found for user {self.user_id}")
        return self.profile

    def _apply_date_filter(self, qs: QuerySet, date_filter: DateFilter) -> QuerySet:
        """Apply date filtering to queryset."""
        if date_filter.between:
            start = datetime.fromisoformat(date_filter.between[0]).date()
            end = datetime.fromisoformat(date_filter.between[1]).date()

            # Limit to user registration date if needed
            profile = self._get_profile()
            if profile.created_at:
                reg_date = profile.created_at.date()
                one_year_ago = date.today() - timedelta(days=365)
                earliest_allowed = max(reg_date, one_year_ago)

                if start < earliest_allowed:
                    start = earliest_allowed

            # Apply filter based on entity type
            if hasattr(qs.model, 'expense_date'):
                qs = qs.filter(expense_date__gte=start, expense_date__lte=end)
            elif hasattr(qs.model, 'income_date'):
                qs = qs.filter(income_date__gte=start, income_date__lte=end)

        elif date_filter.period:
            from bot.utils.date_utils import get_period_dates

            # Используем единую функцию для получения дат периода
            start_date, end_date = get_period_dates(date_filter.period)

            if hasattr(qs.model, 'expense_date'):
                qs = qs.filter(expense_date__gte=start_date, expense_date__lte=end_date)
            elif hasattr(qs.model, 'income_date'):
                qs = qs.filter(income_date__gte=start_date, income_date__lte=end_date)

        return qs

    def _apply_category_filter(self, qs: QuerySet, cat_filter: CategoryFilter) -> QuerySet:
        """Apply category filtering to queryset."""
        if cat_filter.id:
            qs = qs.filter(category_id=cat_filter.id)
        elif cat_filter.equals:
            # Search in all name fields for exact match
            qs = qs.filter(
                Q(category__name=cat_filter.equals) |
                Q(category__name_ru=cat_filter.equals) |
                Q(category__name_en=cat_filter.equals)
            )
        elif cat_filter.contains:
            # Search in all name fields and description
            qs = qs.filter(
                Q(category__name__icontains=cat_filter.contains) |
                Q(category__name_ru__icontains=cat_filter.contains) |
                Q(category__name_en__icontains=cat_filter.contains) |
                Q(description__icontains=cat_filter.contains)
            )
        return qs

    def _apply_amount_filter(self, qs: QuerySet, amount_filter: AmountFilter) -> QuerySet:
        """Apply amount filtering to queryset."""
        if amount_filter.gte is not None:
            qs = qs.filter(amount__gte=amount_filter.gte)
        if amount_filter.lte is not None:
            qs = qs.filter(amount__lte=amount_filter.lte)
        return qs

    def _apply_text_filter(self, qs: QuerySet, text_filter: TextFilter) -> QuerySet:
        """Apply text search filtering to queryset."""
        # Search in all safe fields including multilingual category names
        qs = qs.filter(
            Q(description__icontains=text_filter.contains) |
            Q(category__name__icontains=text_filter.contains) |
            Q(category__name_ru__icontains=text_filter.contains) |
            Q(category__name_en__icontains=text_filter.contains)
        )
        return qs

    def _apply_filters(self, qs: QuerySet, filters: FiltersSpec) -> QuerySet:
        """Apply all filters to queryset."""
        if filters.date:
            qs = self._apply_date_filter(qs, filters.date)
        if filters.category:
            qs = self._apply_category_filter(qs, filters.category)
        if filters.amount:
            qs = self._apply_amount_filter(qs, filters.amount)
        if filters.text:
            qs = self._apply_text_filter(qs, filters.text)
        return qs

    def _apply_grouping(self, qs: QuerySet, spec: AnalyticsQuerySpec) -> QuerySet:
        """Apply grouping and aggregation to queryset."""
        if spec.group_by == 'date':
            # Group by date (avoid SQLite UDF issues by using direct date field)
            if hasattr(qs.model, 'expense_date'):
                qs = qs.annotate(group_date=F('expense_date'))
            else:
                qs = qs.annotate(group_date=F('income_date'))
            qs = qs.values('group_date')

        elif spec.group_by == 'category':
            # Group by category
            qs = qs.values('category__name', 'category__id')

        elif spec.group_by == 'weekday':
            # Group by weekday
            if hasattr(qs.model, 'expense_date'):
                qs = qs.annotate(weekday=ExtractWeekDay('expense_date'))
            else:
                qs = qs.annotate(weekday=ExtractWeekDay('income_date'))
            qs = qs.values('weekday')

        # Apply aggregations
        if spec.group_by != 'none':
            agg_dict = {}
            for agg in spec.aggregate:
                if agg == 'sum':
                    agg_dict['total'] = Sum('amount')
                elif agg == 'count':
                    agg_dict['count'] = Count('id')
                elif agg == 'avg':
                    agg_dict['average'] = Avg('amount')
                elif agg == 'max':
                    agg_dict['maximum'] = Max('amount')
                elif agg == 'min':
                    agg_dict['minimum'] = Min('amount')

            if agg_dict:
                qs = qs.annotate(**agg_dict)

        return qs

    def _apply_sorting(self, qs: QuerySet, spec: AnalyticsQuerySpec) -> QuerySet:
        """Apply sorting to queryset."""
        if not spec.sort:
            return qs

        order_fields = []
        for sort_spec in spec.sort:
            field = sort_spec.by

            # Map sort field to actual field name
            if spec.group_by != 'none':
                # For grouped queries
                field_map = {
                    'sum': 'total',
                    'count': 'count',
                    'avg': 'average',
                    'max': 'maximum',
                    'min': 'minimum',
                    'date': 'group_date',
                }
                field = field_map.get(field, field)
            else:
                # For non-grouped queries
                if field == 'date':
                    field = 'expense_date' if hasattr(qs.model, 'expense_date') else 'income_date'

            # Add direction prefix
            if sort_spec.dir == 'desc':
                field = f'-{field}'

            order_fields.append(field)

        if order_fields:
            qs = qs.order_by(*order_fields)

        return qs

    @transaction.atomic
    def execute(self, spec: AnalyticsQuerySpec) -> Dict[str, Any]:
        """Execute the analytics query and return results."""
        try:
            profile = self._get_profile()

            # Get base queryset based on entity with proper household support
            if spec.entity == 'expenses':
                qs = Expense.objects.filter(profile=profile)
                # Check for household scope
                if profile.household and hasattr(profile, 'settings') and profile.settings.view_scope == 'household':
                    household_profiles = profile.household.profiles.all()
                    qs = Expense.objects.filter(profile__in=household_profiles)
                qs = qs.select_related('category', 'profile')
            elif spec.entity == 'incomes':
                qs = Income.objects.filter(profile=profile)
                # Check for household scope
                if profile.household and hasattr(profile, 'settings') and profile.settings.view_scope == 'household':
                    household_profiles = profile.household.profiles.all()
                    qs = Income.objects.filter(profile__in=household_profiles)
                qs = qs.select_related('category', 'profile')
            elif spec.entity == 'operations':
                # Combined expenses and incomes - handle separately
                return self._execute_operations(spec, profile)
            else:
                raise ValueError(f"Unknown entity: {spec.entity}")

            # Apply filters
            qs = self._apply_filters(qs, spec.filters)

            # Apply grouping and aggregation
            if spec.group_by != 'none':
                qs = self._apply_grouping(qs, spec)

            # Apply sorting
            qs = self._apply_sorting(qs, spec)

            # Apply limit
            qs = qs[:spec.limit]

            # Format results
            results = self._format_results(qs, spec)

            return {
                'success': True,
                'entity': spec.entity,
                'group_by': spec.group_by,
                'results': results,
                'count': len(results)
            }

        except Exception as e:
            logger.error(f"Error executing analytics query: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Query execution failed',
                'message': str(e)
            }

    def _execute_operations(self, spec: AnalyticsQuerySpec, profile: Profile) -> Dict[str, Any]:
        """Execute combined operations query (expenses + incomes)."""
        # This is more complex and would need special handling
        # For MVP, we'll limit operations to simple list queries
        if spec.group_by != 'none':
            return {
                'success': False,
                'error': 'Grouping not supported for operations entity',
                'message': 'Please query expenses or incomes separately for grouped results'
            }

        # Get expenses and incomes with household support
        expenses = Expense.objects.filter(profile=profile)
        incomes = Income.objects.filter(profile=profile)

        # Check for household scope
        if profile.household and profile.settings.view_scope == 'household':
            household_profiles = profile.household.profiles.all()
            expenses = Expense.objects.filter(profile__in=household_profiles)
            incomes = Income.objects.filter(profile__in=household_profiles)

        expenses = expenses.select_related('category', 'profile')
        incomes = incomes.select_related('category', 'profile')

        # Apply filters
        expenses = self._apply_filters(expenses, spec.filters)
        incomes = self._apply_filters(incomes, spec.filters)

        # Combine and sort efficiently
        operations = []

        # Limit each queryset before evaluation
        limited_expenses = expenses.order_by('-expense_date')[:spec.limit]
        limited_incomes = incomes.order_by('-income_date')[:spec.limit]

        user_lang = profile.language_code or 'ru'

        for expense in limited_expenses:
            operations.append({
                'type': 'expense',
                'date': expense.expense_date,
                'amount': float(expense.amount),
                'category': expense.category.get_display_name(user_lang) if expense.category else None,
                'description': expense.description,
                'currency': expense.currency
            })

        for income in limited_incomes:
            operations.append({
                'type': 'income',
                'date': income.income_date,
                'amount': float(income.amount),
                'category': income.category.get_display_name(user_lang) if income.category else None,
                'description': income.description,
                'currency': income.currency
            })

        # Sort combined list
        if spec.sort:
            for sort_spec in reversed(spec.sort):
                reverse = sort_spec.dir == 'desc'
                if sort_spec.by == 'date':
                    operations.sort(key=lambda x: x['date'], reverse=reverse)
                elif sort_spec.by == 'amount':
                    operations.sort(key=lambda x: x['amount'], reverse=reverse)

        # Apply limit to combined results
        operations = operations[:spec.limit]

        return {
            'success': True,
            'entity': 'operations',
            'group_by': 'none',
            'results': operations,
            'count': len(operations)
        }

    def _format_results(self, qs: QuerySet, spec: AnalyticsQuerySpec) -> List[Dict]:
        """Format query results for output."""
        profile = self._get_profile()
        user_lang = profile.language_code or 'ru'
        results = []

        if spec.group_by != 'none':
            # Grouped results
            for item in qs:
                result = {}

                if spec.group_by == 'date':
                    result['date'] = item['group_date'].isoformat() if item['group_date'] else None
                elif spec.group_by == 'category':
                    # Получаем мультиязычное название категории
                    category_id = item['category__id']
                    if category_id:
                        try:
                            if spec.entity == 'expenses':
                                from expenses.models import ExpenseCategory
                                category = ExpenseCategory.objects.get(id=category_id)
                            else:  # incomes
                                from expenses.models import IncomeCategory
                                category = IncomeCategory.objects.get(id=category_id)
                            result['category'] = category.get_display_name(user_lang)
                        except:
                            result['category'] = item.get('category__name', '')
                    else:
                        result['category'] = get_text(user_lang, 'no_category')
                    result['category_id'] = category_id
                elif spec.group_by == 'weekday':
                    weekday_keys = ['', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    weekday_num = item['weekday']
                    if weekday_num and 0 < weekday_num < len(weekday_keys):
                        result['weekday'] = get_text(user_lang, weekday_keys[weekday_num])
                    else:
                        result['weekday'] = None
                    result['weekday_num'] = weekday_num

                # Add aggregations
                if 'total' in item:
                    result['total'] = float(item['total'] or 0)
                if 'count' in item:
                    result['count'] = item['count']
                if 'average' in item:
                    result['average'] = float(item['average'] or 0)
                if 'maximum' in item:
                    result['maximum'] = float(item['maximum'] or 0)
                if 'minimum' in item:
                    result['minimum'] = float(item['minimum'] or 0)

                results.append(result)
        else:
            # Non-grouped results (list mode)
            for item in qs:
                result = {}

                # Add projected fields
                if spec.projection:
                    for field in spec.projection:
                        if field == 'date':
                            if hasattr(item, 'expense_date'):
                                result['date'] = item.expense_date.isoformat()
                            elif hasattr(item, 'income_date'):
                                result['date'] = item.income_date.isoformat()
                        elif field == 'amount':
                            result['amount'] = float(item.amount)
                        elif field == 'category':
                            result['category'] = item.category.get_display_name(user_lang) if item.category else None
                        elif field == 'description':
                            result['description'] = item.description
                        elif field == 'currency':
                            result['currency'] = item.currency
                else:
                    # Default projection
                    if hasattr(item, 'expense_date'):
                        result['date'] = item.expense_date.isoformat()
                    elif hasattr(item, 'income_date'):
                        result['date'] = item.income_date.isoformat()

                    result['amount'] = float(item.amount)
                    result['category'] = item.category.get_display_name(user_lang) if item.category else None
                    result['description'] = item.description

                results.append(result)

        return results


async def execute_analytics_query(user_id: int, spec_json: str) -> Dict[str, Any]:
    """
    Main entry point for executing analytics queries.

    Args:
        user_id: Telegram user ID
        spec_json: JSON string with query specification

    Returns:
        Query results or error dict
    """
    try:
        # Parse JSON
        try:
            spec_dict = json.loads(spec_json)
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': 'Invalid JSON format',
                'message': str(e)
            }

        # Validate specification
        try:
            spec = AnalyticsQuerySpec(**spec_dict)
        except Exception as e:
            return {
                'success': False,
                'error': 'Invalid query specification',
                'message': str(e)
            }

        # Log the query for monitoring (without sensitive data)
        logger.info(f"Analytics query from user {user_id}: entity={spec.entity}, group_by={spec.group_by}, limit={spec.limit}")

        # Execute query
        executor = AnalyticsQueryExecutor(user_id)
        # Use sync_to_async to run the synchronous execute method
        from asgiref.sync import sync_to_async
        execute_sync = sync_to_async(executor.execute)
        result = await execute_sync(spec)

        # Log result stats
        if result.get('success'):
            logger.info(f"Analytics query successful: {result.get('count')} results")
        else:
            logger.warning(f"Analytics query failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Unexpected error in analytics query: {e}", exc_info=True)
        return {
            'success': False,
            'error': 'Internal error',
            'message': 'An unexpected error occurred'
        }
