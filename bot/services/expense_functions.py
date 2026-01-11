"""
Функции для работы с тратами и доходами через function calling в AI
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from asgiref.sync import sync_to_async
from expenses.models import Expense, Profile, Income, IncomeCategory, ExpenseCategory
from django.db.models import Sum, Avg, Max, Min, Count, Q
from collections import defaultdict
from bot.utils.category_helpers import get_category_display_name
from bot.utils.language import get_user_language, get_text
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions for search_expenses
# =============================================================================

def _parse_search_query(query: str) -> list:
    """
    Parse search query into parts.
    Handles: "кофе и круассаны", "кофе, булочки", etc.
    But preserves phrases with prepositions like "кофе с молоком".
    """
    import re

    query_parts = []

    # Split by explicit separators: " и ", " or ", ", "
    split_pattern = r'\s+и\s+|\s+or\s+|,\s*'
    potential_parts = re.split(split_pattern, query, flags=re.IGNORECASE)

    for part in potential_parts:
        part = part.strip()
        if part and len(part) >= 2:
            query_parts.append(part)

    # If only one part - try splitting by spaces (if no prepositions)
    if len(query_parts) == 1:
        single_query = query_parts[0]
        has_prepositions = re.search(
            r'\s+(с|в|на|для|из|от|до|по|при|за|над|под|между)\s+',
            single_query, re.IGNORECASE
        )
        if not has_prepositions:
            words = single_query.split()
            meaningful_words = [w for w in words if len(w) >= 3]
            if len(meaningful_words) > 1:
                query_parts = meaningful_words

    return query_parts


def _apply_date_filters(queryset, start_date: str, end_date: str):
    """Apply date filters to queryset."""
    from datetime import datetime as dt

    if start_date:
        try:
            start_dt = dt.strptime(start_date, '%Y-%m-%d').date()
            queryset = queryset.filter(expense_date__gte=start_dt)
        except ValueError:
            logger.warning(f"Invalid start_date format: {start_date}")

    if end_date:
        try:
            end_dt = dt.strptime(end_date, '%Y-%m-%d').date()
            queryset = queryset.filter(expense_date__lte=end_dt)
        except ValueError:
            logger.warning(f"Invalid end_date format: {end_date}")

    return queryset


def _build_search_filter(query_parts: list):
    """Build Q filter for expense search."""
    from functools import reduce
    from operator import or_

    q_filters = []
    for qpart in query_parts:
        q_filters.append(
            Q(description__icontains=qpart) |
            Q(category__name__icontains=qpart) |
            Q(category__name_ru__icontains=qpart) |
            Q(category__name_en__icontains=qpart)
        )

    if q_filters:
        return reduce(or_, q_filters)
    return None


def _fuzzy_search_expenses(queryset, query_parts: list, limit: int) -> list:
    """
    Perform fuzzy search on expenses when standard search returns nothing.
    """
    import re
    from bot.services.expense import normalize_russian_word, _calculate_similarity

    FUZZY_SEARCH_LIMIT = 500
    SIMILARITY_THRESHOLD = 0.75

    all_expenses = queryset.select_related('category').order_by(
        '-expense_date', '-expense_time'
    )[:FUZZY_SEARCH_LIMIT]

    query_parts_lower = [qp.lower() for qp in query_parts]
    query_parts_normalized = [normalize_russian_word(qp.lower()) for qp in query_parts]

    filtered_expenses = []

    for exp in all_expenses:
        if _expense_matches_query(exp, query_parts_lower, query_parts_normalized, SIMILARITY_THRESHOLD):
            filtered_expenses.append(exp)
            if len(filtered_expenses) >= limit:
                break

    return filtered_expenses


def _expense_matches_query(
    exp,
    query_parts_lower: list,
    query_parts_normalized: list,
    threshold: float
) -> bool:
    """Check if expense matches any of the query parts."""
    import re
    from bot.services.expense import normalize_russian_word, _calculate_similarity

    for query_lower, query_normalized in zip(query_parts_lower, query_parts_normalized):
        # Check description
        if exp.description:
            desc_lower = exp.description.lower()

            # Exact match
            if query_lower in desc_lower or query_normalized in desc_lower:
                return True

            # Fuzzy match on words
            desc_words = re.findall(r'[а-яёa-z]+', desc_lower)
            for word in desc_words:
                word_normalized = normalize_russian_word(word)
                if query_normalized == word_normalized:
                    return True
                if len(query_normalized) >= 3 and len(word_normalized) >= 3:
                    similarity = _calculate_similarity(query_normalized, word_normalized)
                    if similarity >= threshold:
                        return True

        # Check category
        if exp.category:
            for cat_name in [exp.category.name, exp.category.name_ru, exp.category.name_en]:
                if cat_name:
                    cat_lower = cat_name.lower()
                    if query_lower in cat_lower or query_normalized in cat_lower:
                        return True

    return False


def _format_search_results(expenses, lang: str) -> tuple:
    """Format expenses for search results."""
    results = []
    total_amount = 0.0

    for exp in expenses:
        amount = float(exp.amount)
        total_amount += amount
        results.append({
            'date': exp.expense_date.isoformat(),
            'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
            'amount': amount,
            'category': get_category_display_name(exp.category, lang) if exp.category else get_text('no_category', lang),
            'description': exp.description,
            'currency': exp.currency
        })

    return results, total_amount


def _get_previous_period(start_date: date, end_date: date, period: str) -> tuple[date, date]:
    """
    Определяет предыдущий период на основе текущего периода.

    Для месяцев возвращает предыдущий календарный месяц (полный).
    Для других периодов - период такой же длины перед текущим.

    Args:
        start_date: Начало текущего периода
        end_date: Конец текущего периода
        period: Название периода (для определения типа)

    Returns:
        Tuple (prev_start_date, prev_end_date)
    """
    period_lower = period.lower() if period else ''

    # Список названий месяцев на разных языках
    month_names = {
        'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
        'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    }

    # Проверяем, является ли период месяцем
    is_month_period = (
        # Явно указан месяц по названию
        period_lower in month_names or
        # Период типа "month" или "last_month"
        period_lower in ('month', 'this_month', 'last_month') or
        # Начинается с 1-го числа месяца И это не год/сезон/числовой период
        (start_date.day == 1 and
         period_lower not in ('year', 'this_year', 'last_year',
                              'зима', 'весна', 'лето', 'осень',
                              'winter', 'spring', 'summer', 'autumn', 'fall',
                              'зимой', 'весной', 'летом', 'осенью') and
         not period_lower.isdigit())  # И это не числовой период типа "30"
    )

    if is_month_period:
        # Для месяцев используем календарную логику
        # Последний день предыдущего месяца
        prev_end_date = start_date - timedelta(days=1)
        # Первый день предыдущего месяца
        prev_start_date = prev_end_date.replace(day=1)
        return prev_start_date, prev_end_date
    else:
        # Для других периодов (год, сезон, неделя, кастомные даты) - берем период такой же длины
        period_days = (end_date - start_date).days + 1
        prev_start_date = start_date - timedelta(days=period_days)
        prev_end_date = end_date - timedelta(days=period_days)
        return prev_start_date, prev_end_date


class ExpenseFunctions:
    """Класс с функциями для анализа трат, вызываемыми через AI function calling"""
    
    @staticmethod
    @sync_to_async
    def get_max_expense_day(user_id: int, period: str = None, period_days: int = None) -> Dict[str, Any]:
        """
        Найти день с максимальными тратами

        Args:
            user_id: ID пользователя Telegram
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
            period_days: Период в днях для анализа (используется если period не задан)

        Returns:
            Информация о дне с максимальными тратами
        """
        logger.info(f"[get_max_expense_day] Starting for user_id={user_id}, period={period}, period_days={period_days}")
        try:
            from bot.utils.date_utils import get_period_dates

            # Используем get_or_create для автоматического создания профиля
            profile, created = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            if created:
                logger.info(f"[get_max_expense_day] Created new profile for user {user_id}")
            else:
                logger.info(f"[get_max_expense_day] Profile found: id={profile.id}, telegram_id={profile.telegram_id}")

            # Определяем период
            if period:
                start_date, end_date = get_period_dates(period)
            elif period_days:
                end_date = date.today()
                start_date = end_date - timedelta(days=period_days)
            else:
                # По умолчанию последние 60 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=60)
            
            # Получаем траты за период
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).values('expense_date').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            logger.info(f"[get_max_expense_day] Found {len(expenses)} days with expenses")
            
            # Получаем язык пользователя
            lang = profile.language_code or 'ru'
            
            if not expenses:
                from bot.utils import get_text
                return {
                    'success': False,
                    'message': get_text('no_expenses_period', lang)
                }
            
            max_day = expenses.first()
            
            # Получаем детали трат за этот день
            day_expenses = Expense.objects.filter(
                profile=profile,
                expense_date=max_day['expense_date']
            ).select_related('category')

            from bot.utils import get_text

            details = []
            for exp in day_expenses:
                category_name = get_category_display_name(exp.category, lang) if exp.category else get_text('no_category', lang)
                    
                details.append({
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    'category': category_name,
                    'description': exp.description
                })
            
            # Добавляем день недели
            weekday_num = max_day['expense_date'].weekday()
            weekday = get_text(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][weekday_num], lang)
            
            return {
                'success': True,
                'date': max_day['expense_date'].isoformat(),
                'weekday': weekday,
                'total': float(max_day['total']),
                'currency': 'RUB',
                'count': len(details),
                'details': details
            }
            
        except Profile.DoesNotExist:
            logger.error(f"[get_max_expense_day] Profile not found for telegram_id={user_id}")
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"[get_max_expense_day] Unexpected error for user {user_id}: {e}", exc_info=True)
            from bot.utils import get_text
            lang = 'ru'  # Default language for errors
            try:
                profile = Profile.objects.get(telegram_id=user_id)
                lang = profile.language_code or 'ru'
            except:
                pass
            return {
                'success': False,
                'message': f"{get_text('error', lang)}: {str(e)}"
            }
    
    @staticmethod
    @sync_to_async
    def get_period_total(user_id: int, period: str = 'today') -> Dict[str, Any]:
        """
        Получить сумму трат за период

        Args:
            user_id: ID пользователя
            period: Период (today, yesterday, week, month, year)
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[get_period_total] Called with user_id={user_id}, period='{period}'")

        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            logger.info(f"[get_period_total] Profile found/created: telegram_id={profile.telegram_id}, language_code='{profile.language_code}'")
            # Используем единую функцию для определения дат периода
            from bot.utils.date_utils import get_period_dates
            try:
                start_date, end_date = get_period_dates(period)
            except Exception:
                from bot.utils import get_text
                lang = profile.language_code or 'ru'
                return {
                    'success': False,
                    'message': f"{get_text('unknown_period', lang)}: {period}"
                }
            
            # Получаем траты
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )
            
            total = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = expenses.count()
            
            # Получаем язык пользователя
            from bot.utils import get_text
            lang = profile.language_code or 'ru'

            # Группируем по категориям (используем category__id вместо category__name)
            by_category = expenses.values('category__id').annotate(
                total=Sum('amount')
            ).order_by('-total')

            categories = []
            for cat in by_category:
                category_id = cat['category__id']
                if category_id:
                    try:
                        category = ExpenseCategory.objects.get(id=category_id)
                        category_name = category.get_display_name(lang)
                    except ExpenseCategory.DoesNotExist:
                        category_name = get_text('no_category', lang)
                else:
                    category_name = get_text('no_category', lang)

                categories.append({
                    'name': category_name,
                    'amount': float(cat['total'])
                })

            result = {
                'success': True,
                'user_id': user_id,  # Добавляем user_id для определения языка
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'currency': 'RUB',
                'count': count,
                'categories': categories[:5]  # Топ-5 категорий
            }
            logger.info(f"[get_period_total] Returning result with user_id={result['user_id']}, period='{result['period']}', total={result['total']}")
            return result

        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_period_total: {e}")
            from bot.utils import get_text
            lang = 'ru'
            try:
                profile = Profile.objects.get(telegram_id=user_id)
                lang = profile.language_code or 'ru'
            except:
                pass
            return {
                'success': False,
                'message': f"{get_text('error', lang)}: {str(e)}"
            }
    
    @staticmethod
    @sync_to_async
    def get_category_statistics(
        user_id: int,
        period_days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Получить статистику по категориям

        Args:
            user_id: ID пользователя
            period_days: Период в днях (используется как fallback)
            start_date: Начальная дата в формате ISO (YYYY-MM-DD)
            end_date: Конечная дата в формате ISO (YYYY-MM-DD)
            period: Название периода ('декабрь', 'last_month', 'week', etc.)
                    Имеет приоритет над period_days
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Определяем период: приоритет period > start_date/end_date > period_days
            if period:
                # Используем get_period_dates для парсинга периода
                from bot.utils.date_utils import get_period_dates
                try:
                    start_dt, end_dt = get_period_dates(period)
                except Exception:
                    # Если period не распознан, fallback на period_days
                    end_dt = date.today()
                    start_dt = end_dt - timedelta(days=period_days)
            elif start_date and end_date:
                try:
                    from datetime import datetime as _dt
                    start_dt = _dt.fromisoformat(str(start_date)).date()
                    end_dt = _dt.fromisoformat(str(end_date)).date()
                except Exception:
                    end_dt = date.today()
                    start_dt = end_dt - timedelta(days=period_days)
            else:
                end_dt = date.today()
                start_dt = end_dt - timedelta(days=period_days)
            
            # Получаем траты по категориям
            stats = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_dt,
                expense_date__lte=end_dt
            ).values('category__name').annotate(
                total=Sum('amount'),
                count=Count('id'),
                avg=Avg('amount'),
                max=Max('amount')
            ).order_by('-total')
            
            categories = []
            total_sum = Decimal('0')
            
            for stat in stats:
                total_sum += stat['total']
                categories.append({
                    'name': stat['category__name'] or get_text('no_category', profile.language_code or 'ru'),
                    'total': float(stat['total']),
                    'count': stat['count'],
                    'average': float(stat['avg']),
                    'max': float(stat['max'])
                })
            
            # Добавляем проценты
            for cat in categories:
                cat['percentage'] = round((cat['total'] / float(total_sum)) * 100, 1) if total_sum > 0 else 0
            
            return {
                'success': True,
                'period_days': period_days,
                'start_date': start_dt.isoformat(),
                'end_date': end_dt.isoformat(),
                'total': float(total_sum),
                'currency': 'RUB',
                'categories': categories
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_category_statistics: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_daily_totals(user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получить суммы трат по дням
        
        Args:
            user_id: ID пользователя
            days: Количество дней
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Получаем траты по дням
            daily = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).values('expense_date').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('expense_date')
            
            # Формируем результат
            daily_data = {}
            for day in daily:
                daily_data[day['expense_date'].isoformat()] = {
                    'amount': float(day['total']),
                    'count': day['count']
                }
            
            # Заполняем пропущенные дни нулями
            current = start_date
            while current <= end_date:
                date_str = current.isoformat()
                if date_str not in daily_data:
                    daily_data[date_str] = {'amount': 0.0, 'count': 0}
                current += timedelta(days=1)
            
            # Статистика
            amounts = [d['amount'] for d in daily_data.values() if d['amount'] > 0]
            
            return {
                'success': True,
                'days': days,
                'daily_totals': daily_data,
                'statistics': {
                    'average': sum(amounts) / len(amounts) if amounts else 0,
                    'max': max(amounts) if amounts else 0,
                    'min': min(amounts) if amounts else 0,
                    'total': sum(amounts)
                },
                'currency': 'RUB'
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_daily_totals: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def search_expenses(user_id: int, query: str, limit: int = 20, start_date: str = None, end_date: str = None, period: str = None) -> Dict[str, Any]:
        """
        Search expenses by text query.

        Args:
            user_id: User ID
            query: Search query
            limit: Maximum number of results
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            period: Period ('last_week', 'last_month', 'week', 'month', etc.)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Determine period dates
            if period:
                period_start, period_end = get_period_dates(period)
                start_date = period_start.isoformat()
                end_date = period_end.isoformat()

            logger.info(f"search_expenses: profile_id={profile.id}, query='{query}', limit={limit}, period={start_date} to {end_date}")

            # Parse query into parts
            query_parts = _parse_search_query(query)
            logger.info(f"search_expenses: parsed query parts: {query_parts}")

            # Build base queryset with date filters
            queryset = Expense.objects.filter(profile=profile)
            queryset = _apply_date_filters(queryset, start_date, end_date)

            # Try standard SQL search first
            search_filter = _build_search_filter(query_parts)
            if search_filter:
                expenses = list(
                    queryset.filter(search_filter)
                    .select_related('category')
                    .order_by('-expense_date', '-expense_time')[:limit]
                )
            else:
                expenses = []

            # If nothing found - use fuzzy search
            if not expenses:
                expenses = _fuzzy_search_expenses(queryset, query_parts, limit)
                logger.info(f"search_expenses: extended search found {len(expenses)} expenses")

            logger.info(f"search_expenses: found {len(expenses)} expenses for query '{query}'")

            # Format results
            lang = profile.language_code or 'ru'
            results, total_amount = _format_search_results(expenses, lang)

            # Вычисляем сравнение с предыдущим периодом (только если указан period)
            previous_comparison = None
            if period and start_date and end_date:
                try:
                    current_start = datetime.fromisoformat(start_date).date()
                    current_end = datetime.fromisoformat(end_date).date()

                    # Определяем предыдущий период
                    prev_start_date, prev_end_date = _get_previous_period(current_start, current_end, period)

                    logger.info(f"search_expenses: comparing with previous period {prev_start_date} to {prev_end_date}")

                    # Получаем траты за предыдущий период с теми же фильтрами
                    prev_queryset = Expense.objects.filter(
                        profile=profile,
                        expense_date__gte=prev_start_date,
                        expense_date__lte=prev_end_date
                    )

                    if search_filter:
                        prev_expenses = list(
                            prev_queryset.filter(search_filter)
                            .select_related('category')
                            .order_by('-expense_date', '-expense_time')
                        )
                    else:
                        prev_expenses = []

                    # Если не нашли - пробуем fuzzy поиск
                    if not prev_expenses and query_parts:
                        prev_expenses = _fuzzy_search_expenses(prev_queryset, query_parts, limit=1000)

                    prev_count = len(prev_expenses)
                    prev_total = sum(exp.amount for exp in prev_expenses) if prev_expenses else Decimal('0')

                    logger.info(f"search_expenses: previous period - total={prev_total}, count={prev_count}")

                    # Если в предыдущем периоде были траты, вычисляем изменение
                    if prev_total > 0:
                        difference = Decimal(str(total_amount)) - prev_total
                        percent_change = ((Decimal(str(total_amount)) - prev_total) / prev_total) * 100

                        previous_comparison = {
                            'previous_total': float(prev_total),
                            'previous_count': prev_count,
                            'difference': float(difference),
                            'percent_change': round(float(percent_change), 1),
                            'trend': 'увеличение' if difference > 0 else 'уменьшение' if difference < 0 else 'без изменений',
                            'previous_period': {
                                'start': prev_start_date.isoformat(),
                                'end': prev_end_date.isoformat()
                            }
                        }
                        logger.info(f"search_expenses: comparison - difference={difference}, percent_change={percent_change}%")
                    else:
                        logger.info(f"search_expenses: no expenses in previous period, skipping comparison")

                except Exception as e:
                    logger.warning(f"search_expenses: failed to calculate comparison: {e}")

            result = {
                'success': True,
                'query': query,
                'count': len(results),
                'total': total_amount,
                'results': results
            }

            # Добавляем сравнение только если оно есть
            if previous_comparison:
                result['previous_comparison'] = previous_comparison

            # Добавляем даты периода для отображения
            if start_date and end_date:
                result['start_date'] = start_date
                result['end_date'] = end_date

            # Добавляем период если указан
            if period:
                result['period'] = period

            return result

        except Profile.DoesNotExist:
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in search_expenses: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_average_expenses(user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Получить средние траты
        
        Args:
            user_id: ID пользователя
            period_days: Период для расчета
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Получаем все траты за период
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )
            
            total = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = expenses.count()
            
            # Считаем количество дней с тратами
            days_with_expenses = expenses.values('expense_date').distinct().count()
            
            return {
                'success': True,
                'user_id': user_id,
                'period_days': period_days,
                'total': float(total),
                'count': count,
                'days_with_expenses': days_with_expenses,
                'average_per_day': float(total / period_days) if period_days > 0 else 0,
                'average_per_active_day': float(total / days_with_expenses) if days_with_expenses > 0 else 0,
                'average_per_expense': float(total / count) if count > 0 else 0,
                'currency': 'RUB'
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_average_expenses: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_expenses_list(user_id: int, start_date: str = None, end_date: str = None, limit: int = 200) -> Dict[str, Any]:
        """
        Получить список трат за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            # Парсим даты
            if start_date:
                start = datetime.fromisoformat(start_date).date()
            else:
                # Используем дату регистрации пользователя как начальную дату
                if hasattr(profile, 'created_at') and profile.created_at:
                    start = profile.created_at.date()
                else:
                    # Если нет даты регистрации, берем последние 7 дней
                    start = date.today() - timedelta(days=7)
            
            if end_date:
                end = datetime.fromisoformat(end_date).date()
            else:
                end = date.today()
            
            # Сначала получаем общее количество трат за период
            total_count = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start,
                expense_date__lte=end
            ).count()
            
            # Затем получаем траты с лимитом
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start,
                expense_date__lte=end
            ).select_related('category').order_by('-expense_date', '-expense_time')[:limit]
            
            results = []
            total = Decimal('0')
            for exp in expenses:
                total += exp.amount
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    # Убираем категорию для уменьшения объема данных
                    # 'category': exp.category.name if exp.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': exp.description
                })
            
            response = {
                'success': True,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'count': len(results),
                'total': float(total),
                'expenses': results
            }
            
            # Добавляем информацию об ограничении, если оно сработало
            if total_count > limit:
                response['limit_reached'] = True
                response['total_count'] = total_count
                response['limit_message'] = f'💡 <i>Показаны последние {limit} трат из {total_count} за выбранный период</i>'
            
            return response
        except Exception as e:
            logger.error(f"Error in get_expenses_list: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_max_single_expense(user_id: int, period: str = None, period_days: int = None) -> Dict[str, Any]:
        """
        Найти самую большую единичную трату

        Args:
            user_id: ID пользователя
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
            period_days: Количество дней (используется если period не задан)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Определяем период
            if period:
                start_date, end_date = get_period_dates(period)
            elif period_days:
                end_date = date.today()
                start_date = end_date - timedelta(days=period_days)
            else:
                # По умолчанию последние 60 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=60)

            max_expense = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('-amount').first()
            
            if not max_expense:
                return {
                    'success': False,
                    'message': 'Нет трат за указанный период'
                }
            
            # Добавляем день недели
            from bot.utils.language import get_text
            user_lang = profile.language_code or 'ru'
            weekday_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday = get_text(weekday_keys[max_expense.expense_date.weekday()], user_lang)

            return {
                'success': True,
                'user_id': user_id,
                'date': max_expense.expense_date.isoformat(),
                'weekday': weekday,
                'time': max_expense.expense_time.strftime('%H:%M') if max_expense.expense_time else None,
                'amount': float(max_expense.amount),
                'category': get_category_display_name(max_expense.category, profile.language_code or 'ru') if max_expense.category else get_text('no_category', profile.language_code or 'ru'),
                'description': max_expense.description,
                'currency': max_expense.currency
            }
        except Exception as e:
            logger.error(f"Error in get_max_single_expense: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_min_single_expense(user_id: int, period: str = None, period_days: int = None) -> Dict[str, Any]:
        """
        Найти самую маленькую единичную трату

        Args:
            user_id: ID пользователя
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
            period_days: Количество дней (используется если period не задан)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Определяем период
            if period:
                start_date, end_date = get_period_dates(period)
            elif period_days:
                end_date = date.today()
                start_date = end_date - timedelta(days=period_days)
            else:
                # По умолчанию последние 60 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=60)

            min_expense = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('amount').first()

            if not min_expense:
                return {
                    'success': False,
                    'message': 'Нет трат за указанный период'
                }

            # Добавляем день недели
            from bot.utils.language import get_text
            user_lang = profile.language_code or 'ru'
            weekday_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekday = get_text(weekday_keys[min_expense.expense_date.weekday()], user_lang)

            return {
                'success': True,
                'date': min_expense.expense_date.isoformat(),
                'weekday': weekday,
                'time': min_expense.expense_time.strftime('%H:%M') if min_expense.expense_time else None,
                'amount': float(min_expense.amount),
                'category': get_category_display_name(min_expense.category, profile.language_code or 'ru') if min_expense.category else get_text('no_category', profile.language_code or 'ru'),
                'description': min_expense.description,
                'currency': min_expense.currency
            }
        except Exception as e:
            logger.error(f"Error in get_min_single_expense: {e}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    @sync_to_async
    def get_category_total(user_id: int, category: str, period: str = 'month') -> Dict[str, Any]:
        """
        Получить траты по конкретной категории с сравнением с предыдущим периодом
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Используем единую функцию для определения дат периода
            from bot.utils.date_utils import get_period_dates
            try:
                start_date, end_date = get_period_dates(period)
            except Exception:
                # Если период не распознан, используем последние 30 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=30)

            logger.info(f"get_category_total: searching for category='{category}', user={user_id}, period={period}")
            logger.info(f"get_category_total: date range {start_date} to {end_date}")

            # Пытаемся найти категорию пользователя по имени
            # Ищем в нескольких полях для лучшего совпадения
            cat_q = Q(name__icontains=category)
            # Также ищем в мультиязычных полях
            cat_q |= Q(name_ru__icontains=category)
            cat_q |= Q(name_en__icontains=category)

            # Учитываем что может быть передано название без эмодзи
            # Например "продукты" вместо "🥕 Продукты"
            cat_obj = ExpenseCategory.objects.filter(
                profile=profile
            ).filter(cat_q).first()

            if cat_obj:
                logger.info(f"get_category_total: found category obj: id={cat_obj.id}, name='{cat_obj.name}', name_ru='{cat_obj.name_ru}', name_en='{cat_obj.name_en}'")
            else:
                logger.info(f"get_category_total: category not found for query '{category}'")

            # Если точное совпадение не найдено, пробуем более гибкий поиск
            if not cat_obj:
                # Удаляем эмодзи из запроса если они есть и ищем снова
                import re
                clean_category = re.sub(r'[^\w\s]', '', category, flags=re.UNICODE).strip()
                logger.info(f"get_category_total: trying cleaned category='{clean_category}'")
                if clean_category and clean_category != category:
                    cat_q = Q(name__icontains=clean_category)
                    cat_q |= Q(name_ru__icontains=clean_category)
                    cat_q |= Q(name_en__icontains=clean_category)
                    cat_obj = ExpenseCategory.objects.filter(
                        profile=profile
                    ).filter(cat_q).first()
                    if cat_obj:
                        logger.info(f"get_category_total: found with cleaned search: id={cat_obj.id}, name='{cat_obj.name}'")

                # Дополнительно выведем все категории пользователя для отладки
                all_cats = ExpenseCategory.objects.filter(profile=profile)
                logger.info(f"get_category_total: user has {all_cats.count()} categories total")
                for cat in all_cats[:10]:  # Первые 10 для отладки
                    logger.info(f"  - Category: name='{cat.name}', name_ru='{cat.name_ru}', name_en='{cat.name_en}'")

            # Универсальное правило: ищем как по категории, так и по описанию
            q_filter = Q()

            # Если есть категория пользователя - добавляем в фильтр
            if cat_obj:
                q_filter |= Q(category=cat_obj)

            # Также ищем по всем полям названий категории
            q_filter |= Q(category__name__icontains=category)
            q_filter |= Q(category__name_ru__icontains=category)
            q_filter |= Q(category__name_en__icontains=category)

            # И ищем упоминание категории в описании траты
            q_filter |= Q(description__icontains=category)

            # Получаем траты за текущий период
            qs = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).filter(q_filter)

            logger.info(f"get_category_total: filtered queryset, found {qs.count()} expenses")

            from django.db.models import Sum
            total = qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = qs.count()

            logger.info(f"get_category_total: result - total={total}, count={count}")

            # Если нашли траты, покажем первые несколько для отладки
            if count > 0:
                for exp in qs[:3]:
                    logger.info(f"  - Expense: amount={exp.amount}, date={exp.expense_date}, category='{exp.category.name if exp.category else 'None'}', desc='{exp.description}'")

            # Вычисляем сравнение с предыдущим периодом
            previous_comparison = None

            # Определяем предыдущий период (для месяцев - календарный предыдущий месяц)
            prev_start_date, prev_end_date = _get_previous_period(start_date, end_date, period)

            logger.info(f"get_category_total: comparing with previous period {prev_start_date} to {prev_end_date}")

            # Получаем траты за предыдущий период с теми же фильтрами категории
            prev_qs = Expense.objects.filter(
                profile=profile,
                expense_date__gte=prev_start_date,
                expense_date__lte=prev_end_date
            ).filter(q_filter)

            prev_total = prev_qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            prev_count = prev_qs.count()

            logger.info(f"get_category_total: previous period - total={prev_total}, count={prev_count}")

            # Если в предыдущем периоде были траты, вычисляем изменение
            if prev_total > 0:
                difference = total - prev_total
                percent_change = ((total - prev_total) / prev_total) * 100

                previous_comparison = {
                    'previous_total': float(prev_total),
                    'previous_count': prev_count,
                    'difference': float(difference),
                    'percent_change': round(float(percent_change), 1),
                    'trend': 'увеличение' if difference > 0 else 'уменьшение' if difference < 0 else 'без изменений',
                    'previous_period': {
                        'start': prev_start_date.isoformat(),
                        'end': prev_end_date.isoformat()
                    }
                }
                logger.info(f"get_category_total: comparison - difference={difference}, percent_change={percent_change}%")
            else:
                logger.info(f"get_category_total: no expenses in previous period, skipping comparison")

            result = {
                'success': True,
                'category': category,
                'period': period,
                'total': float(total),
                'count': count,
                'average': float(total / count) if count > 0 else 0,
                'currency': 'RUB',
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }

            # Добавляем сравнение только если оно есть
            if previous_comparison:
                result['previous_comparison'] = previous_comparison

            return result

        except Exception as e:
            logger.error(f"Error in get_category_total: {e}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    @sync_to_async
    def get_category_total_by_dates(user_id: int, category: str, start_date: str, end_date: str) -> Dict[str, Any]:
        # Deprecated and removed per product decision. Keep stub for backward compatibility if called inadvertently.
        return {
            'success': False,
            'message': 'get_category_total_by_dates is deprecated; use get_category_statistics with period_days.'
        }
    
    @staticmethod
    @sync_to_async
    def compare_periods(user_id: int, period1: str = 'this_month', period2: str = 'last_month') -> Dict[str, Any]:
        """
        Сравнить траты за два периода
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Используем get_period_dates для обоих периодов
            from bot.utils.date_utils import get_period_dates

            # Определяем первый период
            # Для текущих периодов используем алиасы
            if period1 == 'this_week':
                period1 = 'week'
            elif period1 == 'this_month':
                period1 = 'month'

            p1_start, p1_end = get_period_dates(period1)

            # Определяем второй период
            p2_start, p2_end = get_period_dates(period2)
            
            # Получаем суммы
            total1 = Expense.objects.filter(
                profile=profile,
                expense_date__gte=p1_start,
                expense_date__lte=p1_end
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            total2 = Expense.objects.filter(
                profile=profile,
                expense_date__gte=p2_start,
                expense_date__lte=p2_end
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            difference = total1 - total2
            if total2 > 0:
                percent_change = ((total1 - total2) / total2) * 100
            else:
                percent_change = 100 if total1 > 0 else 0
            
            return {
                'success': True,
                'period1': {
                    'name': period1,
                    'start': p1_start.isoformat(),
                    'end': p1_end.isoformat(),
                    'total': float(total1)
                },
                'period2': {
                    'name': period2,
                    'start': p2_start.isoformat(),
                    'end': p2_end.isoformat(),
                    'total': float(total2)
                },
                'difference': float(difference),
                'percent_change': round(percent_change, 1),
                'trend': 'увеличение' if difference > 0 else 'уменьшение' if difference < 0 else 'без изменений'
            }
        except Exception as e:
            logger.error(f"Error in compare_periods: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_expenses_by_amount_range(user_id: int, min_amount: float = None, max_amount: float = None, limit: int = 200) -> Dict[str, Any]:
        """
        Получить траты в диапазоне сумм
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            expenses_query = Expense.objects.filter(profile=profile).select_related('category')
            
            if min_amount is not None:
                expenses_query = expenses_query.filter(amount__gte=min_amount)
            if max_amount is not None:
                expenses_query = expenses_query.filter(amount__lte=max_amount)
            
            # Сначала получаем общее количество трат
            total_count = expenses_query.count()
            
            # Затем получаем траты с лимитом
            expenses = expenses_query.select_related('category').order_by('-amount', '-expense_date')[:limit]
            
            results = []
            for exp in expenses:
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'amount': float(exp.amount),
                    'category': get_category_display_name(exp.category, profile.language_code or 'ru') if exp.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': exp.description
                })
            
            response = {
                'success': True,
                'min_amount': min_amount,
                'max_amount': max_amount,
                'count': len(results),
                'expenses': results
            }
            
            # Добавляем информацию об ограничении, если оно сработало
            if total_count > limit:
                response['limit_reached'] = True
                response['total_count'] = total_count
                response['limit_message'] = f'💡 <i>Показаны {limit} трат из {total_count} в заданном диапазоне сумм</i>'
            
            return response
        except Exception as e:
            logger.error(f"Error in get_expenses_by_amount_range: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_expense_trend(user_id: int, group_by: str = 'month', periods: int = 6) -> Dict[str, Any]:
        """
        Получить динамику трат
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            
            trends = []
            
            if group_by == 'month':
                for i in range(periods):
                    # Вычисляем месяц
                    month_date = today - timedelta(days=i*30)
                    month_start = month_date.replace(day=1)
                    
                    # Последний день месяца
                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year+1, month=1, day=1) - timedelta(days=1)
                    else:
                        month_end = month_start.replace(month=month_start.month+1, day=1) - timedelta(days=1)
                    
                    total = Expense.objects.filter(
                        profile=profile,
                        expense_date__gte=month_start,
                        expense_date__lte=month_end
                    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                    
                    trends.append({
                        'period': month_start.strftime('%Y-%m'),
                        'total': float(total)
                    })
            
            trends.reverse()  # От старых к новым
            
            return {
                'success': True,
                'user_id': user_id,
                'group_by': group_by,
                'trends': trends
            }
        except Exception as e:
            logger.error(f"Error in get_expense_trend: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_weekday_statistics(user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Статистика трат по дням недели
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)

            from bot.utils.language import get_text
            user_lang = profile.language_code or 'ru'
            weekday_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            stats = {i: {'total': 0, 'count': 0} for i in range(7)}

            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )

            for exp in expenses:
                weekday = exp.expense_date.weekday()
                stats[weekday]['total'] += float(exp.amount)
                stats[weekday]['count'] += 1

            result = []
            for i in range(7):
                day_name = get_text(weekday_keys[i], user_lang)
                avg = stats[i]['total'] / stats[i]['count'] if stats[i]['count'] > 0 else 0
                result.append({
                    'weekday': day_name,
                    'total': stats[i]['total'],
                    'count': stats[i]['count'],
                    'average': round(avg, 2)
                })
            
            max_day = max(result, key=lambda x: x['total'])
            
            return {
                'success': True,
                'period_days': period_days,
                'statistics': result,
                'max_spending_day': max_day['weekday']
            }
        except Exception as e:
            logger.error(f"Error in get_weekday_statistics: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def predict_month_expense(user_id: int) -> Dict[str, Any]:
        """
        Прогноз трат на текущий месяц
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            month_start = today.replace(day=1)
            days_passed = today.day
            
            # Сколько дней в месяце
            if today.month == 12:
                next_month = today.replace(year=today.year+1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month+1, day=1)
            days_in_month = (next_month - month_start).days
            
            # Текущие траты
            current_total = Expense.objects.filter(
                profile=profile,
                expense_date__gte=month_start,
                expense_date__lte=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            # Средние траты в день
            avg_per_day = current_total / days_passed if days_passed > 0 else Decimal('0')
            
            # Прогноз
            predicted_total = avg_per_day * days_in_month
            
            return {
                'success': True,
                'current_total': float(current_total),
                'days_passed': days_passed,
                'days_in_month': days_in_month,
                'average_per_day': float(avg_per_day),
                'predicted_total': float(predicted_total),
                'currency': 'RUB'
            }
        except Exception as e:
            logger.error(f"Error in predict_month_expense: {e}")
            return {'success': False, 'message': str(e)}
    
    # Функция get_month_expenses закомментирована
    # @staticmethod
    # @sync_to_async
    # def get_month_expenses(user_id: int, month: str = None, year: int = None) -> Dict[str, Any]:
    #     """
    #     Получить все траты за конкретный месяц
    #     
    #     Args:
    #         user_id: ID пользователя Telegram
    #         month: Название месяца ('январь', 'февраль', ..., 'август', ...) или номер (1-12)
    #         year: Год (если не указан, берется текущий)
    #         
    #     Returns:
    #         Список всех трат за указанный месяц
    #     """
    #     try:
    #         profile, _ = Profile.objects.get_or_create(
    #             telegram_id=user_id,
    #             defaults={'language_code': 'ru'}
    #         )
    #         
    #         # Определяем месяц и год
    #         today = date.today()
    #         if year is None:
    #             year = today.year
    #             
    #         # Маппинг названий месяцев
    #         month_names = {
    #             'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
    #             'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
    #             'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
    #             'january': 1, 'february': 2, 'march': 3, 'april': 4,
    #             'may': 5, 'june': 6, 'july': 7, 'august': 8,
    #             'september': 9, 'october': 10, 'november': 11, 'december': 12
    #         }
    #         
    #         if month is None:
    #             month_num = today.month
    #         elif isinstance(month, str):
    #             month_lower = month.lower()
    #             month_num = month_names.get(month_lower, None)
    #             if month_num is None:
    #                 try:
    #                     month_num = int(month)
    #                 except:
    #                     month_num = today.month
    #         else:
    #             month_num = month
    #             
    #         # Определяем границы месяца
    #         month_start = date(year, month_num, 1)
    #         if month_num == 12:
    #             month_end = date(year + 1, 1, 1) - timedelta(days=1)
    #         else:
    #             month_end = date(year, month_num + 1, 1) - timedelta(days=1)
    #         
    #         # Получаем все траты за месяц
    #         expenses = Expense.objects.filter(
    #             profile=profile,
    #             expense_date__gte=month_start,
    #             expense_date__lte=month_end
    #         ).select_related('category').order_by('-expense_date', '-expense_time')
    #         
    #         # Формируем список трат
    #         expenses_list = []
    #         total_amount = Decimal('0')
    #         categories_total = defaultdict(Decimal)
    #         
    #         for exp in expenses:
    #             expense_data = {
    #                 'date': exp.expense_date.isoformat(),
    #                 'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
    #                 'amount': float(exp.amount),
    #                 'category': exp.category.name if exp.category else get_text('no_category', profile.language_code or 'ru'),
    #                 'category_icon': exp.category.icon if exp.category else '💰',
    #                 'description': exp.description,
    #                 'currency': exp.currency
    #             }
    #             expenses_list.append(expense_data)
    #             total_amount += exp.amount
    #             if exp.category:
    #                 categories_total[exp.category.name] += exp.amount
    #         
    #         # Статистика по категориям
    #         category_stats = [
    #             {
    #                 'category': cat,
    #                 'total': float(total),
    #                 'percentage': float(total / total_amount * 100) if total_amount > 0 else 0
    #             }
    #             for cat, total in sorted(categories_total.items(), key=lambda x: x[1], reverse=True)
    #         ]
    #         
    #         # Названия месяцев для вывода
    #         month_display_names = [
    #             'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
    #             'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'
    #         ]
    #         
    #         return {
    #             'success': True,
    #             'month': month_display_names[month_num - 1],
    #             'year': year,
    #             'period_start': month_start.isoformat(),
    #             'period_end': month_end.isoformat(),
    #             'total_amount': float(total_amount),
    #             'currency': 'RUB',
    #             'expenses_count': len(expenses_list),
    #             'expenses': expenses_list,
    #             'category_statistics': category_stats
    #         }
    #         
    #     except Exception as e:
    #         logger.error(f"Error in get_month_expenses: {e}")
    #         return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_recent_expenses(user_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        Получить последние траты
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            expenses = Expense.objects.filter(
                profile=profile
            ).select_related('category').order_by('-expense_date', '-expense_time', '-id')[:limit]
            
            # Получаем язык пользователя
            lang = profile.language_code or 'ru'
            
            results = []
            for exp in expenses:
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    'category': get_category_display_name(exp.category, lang) if exp.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': exp.description,
                    'currency': exp.currency
                })
            
            return {
                'success': True,
                'user_id': user_id,
                'count': len(results),
                'expenses': results
            }
        except Exception as e:
            logger.error(f"Error in get_recent_expenses: {e}")
            return {'success': False, 'message': str(e)}
    
    # ================================
    # INCOME FUNCTIONS
    # ================================
    
    @staticmethod
    @sync_to_async
    def get_income_total(user_id: int, period: str = 'month') -> Dict[str, Any]:
        """
        Получить общую сумму доходов за период
        
        Args:
            user_id: ID пользователя
            period: Период (today, week, month, year)
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Используем get_period_dates для определения периода
            from bot.utils.date_utils import get_period_dates
            try:
                start_date, end_date = get_period_dates(period)
            except Exception as e:
                from bot.utils import get_text
                lang = profile.language_code or 'ru'
                return {
                    'success': False,
                    'message': f"{get_text('unknown_period', lang)}: {period}"
                }
            
            # Получаем доходы
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            )
            
            total = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = incomes.count()
            
            # Получаем язык пользователя
            from bot.utils import get_text
            lang = profile.language_code or 'ru'

            # Группируем по категориям (используем category__id вместо category__name)
            by_category = incomes.values('category__id').annotate(
                total=Sum('amount')
            ).order_by('-total')

            categories = []
            for cat in by_category:
                category_id = cat['category__id']
                if category_id:
                    try:
                        from expenses.models import IncomeCategory
                        category = IncomeCategory.objects.get(id=category_id)
                        category_name = category.get_display_name(lang)
                    except IncomeCategory.DoesNotExist:
                        category_name = get_text('no_category', lang)
                else:
                    category_name = get_text('no_category', lang)

                categories.append({
                    'name': category_name,
                    'amount': float(cat['total'])
                })
            
            return {
                'success': True,
                'user_id': user_id,  # Добавляем user_id для определения языка
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'currency': 'RUB',
                'count': count,
                'categories': categories[:5]  # Топ-5 категорий
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_income_total: {e}")
            from bot.utils import get_text
            lang = 'ru'
            try:
                profile = Profile.objects.get(telegram_id=user_id)
                lang = profile.language_code or 'ru'
            except:
                pass
            return {
                'success': False,
                'message': f"{get_text('error', lang)}: {str(e)}"
            }
    
    @staticmethod
    @sync_to_async
    def get_income_by_category(user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Получить статистику доходов по категориям
        
        Args:
            user_id: ID пользователя
            period_days: Период в днях
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Получаем доходы по категориям
            stats = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            ).values('category__name').annotate(
                total=Sum('amount'),
                count=Count('id'),
                avg=Avg('amount'),
                max=Max('amount')
            ).order_by('-total')
            
            categories = []
            total_sum = Decimal('0')
            
            for stat in stats:
                total_sum += stat['total']
                categories.append({
                    'name': stat['category__name'] or get_text('no_category', profile.language_code or 'ru'),
                    'total': float(stat['total']),
                    'count': stat['count'],
                    'average': float(stat['avg']),
                    'max': float(stat['max'])
                })
            
            # Добавляем проценты
            for cat in categories:
                cat['percentage'] = round((cat['total'] / float(total_sum)) * 100, 1) if total_sum > 0 else 0
            
            return {
                'success': True,
                'period_days': period_days,
                'total': float(total_sum),
                'currency': 'RUB',
                'categories': categories
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
            return {
                'success': False,
                'message': get_text('profile_not_found', 'ru')
            }
        except Exception as e:
            logger.error(f"Error in get_income_by_category: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_recent_incomes(user_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        Получить последние доходы
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            incomes = Income.objects.filter(
                profile=profile
            ).select_related('category').order_by('-income_date', '-income_time', '-id')[:limit]
            
            # Получаем язык пользователя
            lang = profile.language_code or 'ru'
            
            results = []
            for income in incomes:
                results.append({
                    'date': income.income_date.isoformat(),
                    'time': income.income_time.strftime('%H:%M') if income.income_time else None,
                    'amount': float(income.amount),
                    'category': get_category_display_name(income.category, lang) if income.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': income.description,
                    'currency': income.currency
                })
            
            return {
                'success': True,
                'user_id': user_id,
                'count': len(results),
                'incomes': results
            }
        except Exception as e:
            logger.error(f"Error in get_recent_incomes: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_max_income_day(user_id: int) -> Dict[str, Any]:
        """
        Найти день с максимальным доходом
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            # Группируем доходы по дням
            incomes = Income.objects.filter(profile=profile).values('income_date').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            if not incomes:
                return {
                    'success': True,
                    'message': 'Нет данных о доходах',
                    'date': None,
                    'total': 0
                }
            
            max_day = incomes[0]
            date_obj = max_day['income_date']
            
            # Получаем детали этого дня
            day_incomes = Income.objects.filter(
                profile=profile,
                income_date=date_obj
            ).order_by('-amount')
            
            details = []
            for inc in day_incomes[:10]:
                details.append({
                    'amount': float(inc.amount),
                    'description': inc.description or get_category_display_name(inc.category, profile.language_code or 'ru') if inc.category else get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(inc.category, profile.language_code or 'ru') if inc.category else get_text('no_category', profile.language_code or 'ru')
                })
            
            return {
                'success': True,
                'date': date_obj.isoformat(),
                'total': float(max_day['total']),
                'count': day_incomes.count(),
                'details': details
            }
        except Exception as e:
            logger.error(f"Error in get_max_income_day: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_income_period_total(user_id: int, period: str = 'month') -> Dict[str, Any]:
        """
        Получить общую сумму доходов за период (аналог get_period_total для расходов)
        """
        # Используем синхронную версию get_income_total без двойной обертки
        try:
            sync_fn = getattr(ExpenseFunctions.get_income_total, '__wrapped__', None)
            if sync_fn is not None:
                return sync_fn(user_id, period)
            # Fallback на прямую реализацию при отсутствии __wrapped__
            from datetime import date, timedelta
            from decimal import Decimal
            from django.db.models import Sum
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Используем единую функцию для определения дат периода
            from bot.utils.date_utils import get_period_dates
            try:
                start_date, end_date = get_period_dates(period)
            except Exception:
                return {'success': False, 'message': f'Unknown period: {period}'}
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            )
            total = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            return {
                'success': True,
                'user_id': user_id,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'currency': 'RUB'
            }
        except Exception as e:
            logger.error(f"Error in get_income_period_total: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_max_single_income(user_id: int, period: str = None, period_days: int = None) -> Dict[str, Any]:
        """
        Найти самый большой единичный доход

        Args:
            user_id: ID пользователя
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
            period_days: Количество дней (используется если period не задан)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Определяем период
            if period:
                start_date, end_date = get_period_dates(period)
            elif period_days:
                end_date = date.today()
                start_date = end_date - timedelta(days=period_days)
            else:
                # По умолчанию последние 60 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=60)

            max_income = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            ).order_by('-amount').first()

            if not max_income:
                return {
                    'success': True,
                    'message': f'Нет данных о доходах за последние {period_days} дней',
                    'income': None
                }

            return {
                'success': True,
                'user_id': user_id,
                'income': {
                    'amount': float(max_income.amount),
                    'description': max_income.description or get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(max_income.category, profile.language_code or 'ru') if max_income.category else get_text('no_category', profile.language_code or 'ru'),
                    'date': max_income.income_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error in get_max_single_income: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_min_single_income(user_id: int, period: str = None, period_days: int = None) -> Dict[str, Any]:
        """
        Найти самый маленький единичный доход

        Args:
            user_id: ID пользователя
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
            period_days: Количество дней (используется если period не задан)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Определяем период
            if period:
                start_date, end_date = get_period_dates(period)
            elif period_days:
                end_date = date.today()
                start_date = end_date - timedelta(days=period_days)
            else:
                # По умолчанию последние 60 дней
                end_date = date.today()
                start_date = end_date - timedelta(days=60)

            min_income = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            ).order_by('amount').first()

            if not min_income:
                return {
                    'success': True,
                    'message': f'Нет данных о доходах за указанный период',
                    'income': None
                }

            return {
                'success': True,
                'income': {
                    'amount': float(min_income.amount),
                    'description': min_income.description or get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(min_income.category, profile.language_code or 'ru') if min_income.category else get_text('no_category', profile.language_code or 'ru'),
                    'date': min_income.income_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error in get_min_single_income: {e}")
            return {'success': False, 'message': str(e)}

    @staticmethod
    @sync_to_async
    def get_income_category_statistics(
        user_id: int,
        period: Optional[str] = None,
        period_days: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Статистика доходов по категориям (аналог get_category_statistics)

        Args:
            user_id: ID пользователя
            period: Название периода ('декабрь', 'last_month', 'week', etc.)
                    Имеет приоритет над period_days
            period_days: Период в днях (используется как fallback)
            start_date: Начальная дата в формате ISO (YYYY-MM-DD)
            end_date: Конечная дата в формате ISO (YYYY-MM-DD)
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Определяем период: приоритет period > start_date/end_date > period_days
            if period:
                from bot.utils.date_utils import get_period_dates
                try:
                    start_dt, end_dt = get_period_dates(period)
                except Exception:
                    end_dt = date.today()
                    start_dt = end_dt - timedelta(days=period_days)
            elif start_date and end_date:
                try:
                    from datetime import datetime as _dt
                    start_dt = _dt.fromisoformat(str(start_date)).date()
                    end_dt = _dt.fromisoformat(str(end_date)).date()
                except Exception:
                    end_dt = date.today()
                    start_dt = end_dt - timedelta(days=period_days)
            else:
                end_dt = date.today()
                start_dt = end_dt - timedelta(days=period_days)

            stats = Income.objects.filter(
                profile=profile,
                income_date__gte=start_dt,
                income_date__lte=end_dt
            ).values('category__name').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')
            
            categories = []
            total_income = Decimal('0')
            
            for stat in stats:
                category_name = stat['category__name'] or get_text('no_category', profile.language_code or 'ru')
                amount = float(stat['total'])
                total_income += stat['total']
                categories.append({
                    'name': category_name,
                    'amount': amount,
                    'count': stat['count']
                })
            
            # Добавляем проценты
            for cat in categories:
                cat['percentage'] = round(cat['amount'] / float(total_income) * 100, 1) if total_income > 0 else 0
            
            return {
                'success': True,
                'categories': categories,
                'total': float(total_income),
                'start_date': start_dt.isoformat(),
                'end_date': end_dt.isoformat(),
                'currency': 'RUB'
            }
        except Exception as e:
            logger.error(f"Error in get_income_category_statistics: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_average_incomes(user_id: int) -> Dict[str, Any]:
        """
        Средние доходы за разные периоды
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            
            # За последние 30 дней
            month_ago = today - timedelta(days=30)
            month_incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=month_ago,
                income_date__lte=today
            )
            
            month_total = month_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            month_count = month_incomes.count()
            
            # За последние 7 дней
            week_ago = today - timedelta(days=7)
            week_incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=week_ago,
                income_date__lte=today
            )
            
            week_total = week_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            week_count = week_incomes.count()
            
            return {
                'success': True,
                'user_id': user_id,
                'daily_average': float(month_total / 30) if month_total else 0,
                'weekly_average': float(week_total) if week_total else 0,
                'monthly_average': float(month_total) if month_total else 0,
                'average_per_income': float(month_total / month_count) if month_count > 0 else 0,
                'incomes_per_month': month_count,
                'incomes_per_week': week_count
            }
        except Exception as e:
            logger.error(f"Error in get_average_incomes: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def search_incomes(user_id: int, query: str, period: Optional[str] = None) -> Dict[str, Any]:
        """
        Поиск доходов по описанию с опциональным периодом и сравнением
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Если указан период, используем его для фильтрации
            start_date = None
            end_date = None
            if period:
                from bot.utils.date_utils import get_period_dates
                start_date, end_date = get_period_dates(period)

            # Базовый фильтр
            incomes_qs = Income.objects.filter(
                profile=profile,
                description__icontains=query
            )

            # Добавляем фильтр по датам если указан период
            if start_date and end_date:
                incomes_qs = incomes_qs.filter(
                    income_date__gte=start_date,
                    income_date__lte=end_date
                )

            incomes = incomes_qs.order_by('-income_date')[:20]

            # Подсчёт общей суммы
            total_amount = sum(inc.amount for inc in incomes)

            results = []
            for inc in incomes:
                results.append({
                    'date': inc.income_date.isoformat(),
                    'amount': float(inc.amount),
                    'description': inc.description or get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(inc.category, profile.language_code or 'ru') if inc.category else get_text('no_category', profile.language_code or 'ru')
                })

            # Вычисляем сравнение с предыдущим периодом (только если указан period)
            previous_comparison = None
            if period and start_date and end_date:
                try:
                    current_start = start_date
                    current_end = end_date

                    # Определяем предыдущий период
                    prev_start_date, prev_end_date = _get_previous_period(current_start, current_end, period)

                    logger.info(f"search_incomes: comparing with previous period {prev_start_date} to {prev_end_date}")

                    # Получаем доходы за предыдущий период с тем же фильтром
                    prev_incomes = Income.objects.filter(
                        profile=profile,
                        description__icontains=query,
                        income_date__gte=prev_start_date,
                        income_date__lte=prev_end_date
                    )

                    prev_total = sum(inc.amount for inc in prev_incomes)
                    prev_count = prev_incomes.count()

                    logger.info(f"search_incomes: previous period - total={prev_total}, count={prev_count}")

                    # Добавляем сравнение только если в предыдущем периоде были доходы
                    if prev_total > 0:
                        difference = Decimal(str(total_amount)) - prev_total
                        percent_change = ((Decimal(str(total_amount)) - prev_total) / prev_total) * 100

                        # Определяем тренд
                        if difference > 0:
                            trend = 'увеличение'
                        elif difference < 0:
                            trend = 'уменьшение'
                        else:
                            trend = 'без изменений'

                        previous_comparison = {
                            'previous_period': {
                                'start': prev_start_date.isoformat(),
                                'end': prev_end_date.isoformat()
                            },
                            'previous_count': prev_count,
                            'previous_total': float(prev_total),
                            'difference': float(difference),
                            'percent_change': float(percent_change),
                            'trend': trend
                        }

                        logger.info(f"search_incomes: comparison - difference={difference}, percent_change={percent_change}%")
                    else:
                        logger.info(f"search_incomes: no incomes in previous period, skipping comparison")

                except Exception as e:
                    logger.warning(f"search_incomes: failed to calculate comparison: {e}")

            result = {
                'success': True,
                'query': query,
                'count': len(results),
                'total': float(total_amount),
                'incomes': results
            }

            # Добавляем сравнение только если оно есть
            if previous_comparison:
                result['previous_comparison'] = previous_comparison

            # Добавляем даты периода для отображения
            if start_date and end_date:
                result['start_date'] = start_date.isoformat()
                result['end_date'] = end_date.isoformat()

            # Добавляем период если указан
            if period:
                result['period'] = period

            return result
        except Exception as e:
            logger.error(f"Error in search_incomes: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_income_weekday_statistics(user_id: int) -> Dict[str, Any]:
        """
        Статистика доходов по дням недели
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            incomes = Income.objects.filter(profile=profile)

            from bot.utils.language import get_text
            user_lang = profile.language_code or 'ru'
            weekday_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

            weekday_stats = {}

            for i in range(7):
                day_name = get_text(weekday_keys[i], user_lang)
                day_incomes = incomes.filter(income_date__week_day=(i + 2) % 7 or 7)  # Django week_day: 1=Sunday
                total = day_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                count = day_incomes.count()

                weekday_stats[day_name] = {
                    'total': float(total),
                    'count': count,
                    'average': float(total / count) if count > 0 else 0
                }
            
            return {
                'success': True,
                'weekday_statistics': weekday_stats
            }
        except Exception as e:
            logger.error(f"Error in get_income_weekday_statistics: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def predict_month_income(user_id: int) -> Dict[str, Any]:
        """
        Прогноз доходов на текущий месяц
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            
            # Доходы с начала месяца
            month_start = today.replace(day=1)
            current_incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=month_start,
                income_date__lte=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            days_passed = today.day
            days_in_month = 30  # Упрощенно
            
            if days_passed > 0:
                daily_rate = current_incomes / days_passed
                predicted = daily_rate * days_in_month
            else:
                predicted = Decimal('0')
            
            return {
                'success': True,
                'current_total': float(current_incomes),
                'predicted_total': float(predicted),
                'days_passed': days_passed,
                'days_remaining': days_in_month - days_passed,
                'daily_rate': float(daily_rate) if days_passed > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error in predict_month_income: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def check_income_target(user_id: int, target_amount: float = 100000) -> Dict[str, Any]:
        """
        Проверка достижения целевого дохода
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            month_start = today.replace(day=1)
            
            current_income = Income.objects.filter(
                profile=profile,
                income_date__gte=month_start,
                income_date__lte=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            remaining = Decimal(str(target_amount)) - current_income
            percentage = (current_income / Decimal(str(target_amount)) * 100) if target_amount > 0 else 0
            
            return {
                'success': True,
                'target': target_amount,
                'current': float(current_income),
                'remaining': float(remaining),
                'percentage': float(percentage),
                'on_track': current_income >= Decimal(str(target_amount)),
                'message': f"Достигнуто {percentage:.1f}% от цели"
            }
        except Exception as e:
            logger.error(f"Error in check_income_target: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def compare_income_periods(user_id: int, period1: str = 'this_month', period2: str = 'last_month') -> Dict[str, Any]:
        """
        Сравнение доходов за разные периоды
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Используем get_period_dates для обоих периодов
            from bot.utils.date_utils import get_period_dates

            # Определяем первый период
            if period1 == 'this_week':
                period1 = 'week'
            elif period1 == 'this_month':
                period1 = 'month'

            p1_start, p1_end = get_period_dates(period1)

            # Определяем второй период
            p2_start, p2_end = get_period_dates(period2)

            # Получаем суммы доходов
            total1 = Income.objects.filter(
                profile=profile,
                income_date__gte=p1_start,
                income_date__lte=p1_end
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            total2 = Income.objects.filter(
                profile=profile,
                income_date__gte=p2_start,
                income_date__lte=p2_end
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

            change = total1 - total2
            if total2 > 0:
                change_percent = ((total1 - total2) / total2) * 100
            else:
                change_percent = 100 if total1 > 0 else 0

            return {
                'success': True,
                'period1': {
                    'name': period1,
                    'start': p1_start.isoformat(),
                    'end': p1_end.isoformat(),
                    'total': float(total1)
                },
                'period2': {
                    'name': period2,
                    'start': p2_start.isoformat(),
                    'end': p2_end.isoformat(),
                    'total': float(total2)
                },
                'change': float(change),
                'change_percent': round(change_percent, 1),
                'trend': 'увеличение' if change > 0 else 'уменьшение' if change < 0 else 'без изменений'
            }
        except Exception as e:
            logger.error(f"Error in compare_income_periods: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_income_trend(user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Тренд доходов за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            start_date = today - timedelta(days=days)
            
            daily_incomes = {}
            
            # Получаем доходы за период
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=today
            ).values('income_date').annotate(
                total=Sum('amount')
            ).order_by('income_date')
            
            # Заполняем все дни
            current_date = start_date
            trend_data = []
            
            while current_date <= today:
                day_total = 0
                for inc in incomes:
                    if inc['income_date'] == current_date:
                        day_total = float(inc['total'])
                        break
                
                trend_data.append({
                    'date': current_date.isoformat(),
                    'amount': day_total
                })
                current_date += timedelta(days=1)
            
            # Вычисляем среднее
            total = sum(d['amount'] for d in trend_data)
            average = total / len(trend_data) if trend_data else 0
            
            return {
                'success': True,
                'user_id': user_id,
                'period_days': days,
                'trend': trend_data,
                'total': total,
                'average': average
            }
        except Exception as e:
            logger.error(f"Error in get_income_trend: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_incomes_by_amount_range(user_id: int, min_amount: float = None, max_amount: float = None) -> Dict[str, Any]:
        """
        Получить доходы в диапазоне сумм
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            queryset = Income.objects.filter(profile=profile)
            
            if min_amount is not None:
                queryset = queryset.filter(amount__gte=Decimal(str(min_amount)))
            
            if max_amount is not None:
                queryset = queryset.filter(amount__lte=Decimal(str(max_amount)))
            
            incomes = queryset.order_by('-income_date')[:50]
            
            results = []
            for inc in incomes:
                results.append({
                    'date': inc.income_date.isoformat(),
                    'amount': float(inc.amount),
                    'description': inc.description or get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(inc.category, profile.language_code or 'ru') if inc.category else get_text('no_category', profile.language_code or 'ru')
                })
            
            total = queryset.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            return {
                'success': True,
                'min_amount': min_amount,
                'max_amount': max_amount,
                'count': len(results),
                'total': float(total),
                'incomes': results
            }
        except Exception as e:
            logger.error(f"Error in get_incomes_by_amount_range: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_income_category_total(user_id: int, category: str, period: str = 'month') -> Dict[str, Any]:
        """
        Сумма доходов по конкретной категории за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Используем get_period_dates для определения периода
            from bot.utils.date_utils import get_period_dates
            start_date, end_date = get_period_dates(period)
            
            # Ищем категорию
            from expenses.models import IncomeCategory
            from django.db.models import Q

            # Ищем в нескольких полях для лучшего совпадения
            cat_q = Q(name__icontains=category)
            # Также ищем в мультиязычных полях
            cat_q |= Q(name_ru__icontains=category)
            cat_q |= Q(name_en__icontains=category)

            categories = IncomeCategory.objects.filter(
                profile=profile
            ).filter(cat_q)
            
            if not categories:
                return {
                    'success': False,
                    'message': f'Категория "{category}" не найдена'
                }
            
            incomes = Income.objects.filter(
                profile=profile,
                category__in=categories,
                income_date__gte=start_date,
                income_date__lte=end_date
            )

            total = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = incomes.count()

            # Вычисляем сравнение с предыдущим периодом
            previous_comparison = None
            try:
                # Определяем предыдущий период
                prev_start_date, prev_end_date = _get_previous_period(start_date, end_date, period)

                logger.info(f"get_income_category_total: comparing with previous period {prev_start_date} to {prev_end_date}")

                # Получаем доходы за предыдущий период
                prev_incomes = Income.objects.filter(
                    profile=profile,
                    category__in=categories,
                    income_date__gte=prev_start_date,
                    income_date__lte=prev_end_date
                )

                prev_total = prev_incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                prev_count = prev_incomes.count()

                logger.info(f"get_income_category_total: previous period - total={prev_total}, count={prev_count}")

                # Добавляем сравнение только если в предыдущем периоде были доходы
                if prev_total > 0:
                    difference = Decimal(str(total)) - prev_total
                    percent_change = ((Decimal(str(total)) - prev_total) / prev_total) * 100

                    # Определяем тренд
                    if difference > 0:
                        trend = 'увеличение'
                    elif difference < 0:
                        trend = 'уменьшение'
                    else:
                        trend = 'без изменений'

                    previous_comparison = {
                        'previous_period': {
                            'start': prev_start_date.isoformat(),
                            'end': prev_end_date.isoformat()
                        },
                        'previous_count': prev_count,
                        'previous_total': float(prev_total),
                        'difference': float(difference),
                        'percent_change': float(percent_change),
                        'trend': trend
                    }

                    logger.info(f"get_income_category_total: comparison - difference={difference}, percent_change={percent_change}%")
                else:
                    logger.info(f"get_income_category_total: no incomes in previous period, skipping comparison")

            except Exception as e:
                logger.warning(f"get_income_category_total: failed to calculate comparison: {e}")

            result = {
                'success': True,
                'category': categories[0].name,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'count': count,
                'average': float(total / count) if count > 0 else 0,
                'currency': profile.currency or 'RUB'
            }

            # Добавляем сравнение только если оно есть
            if previous_comparison:
                result['previous_comparison'] = previous_comparison

            return result
        except Exception as e:
            logger.error(f"Error in get_income_category_total: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_incomes_list(user_id: int, start_date: str = None, end_date: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        Список доходов за период с датами
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            
            # Парсим даты
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
            else:
                # Используем дату регистрации пользователя как начальную дату
                if hasattr(profile, 'created_at') and profile.created_at:
                    start = profile.created_at.date()
                else:
                    # Если нет даты регистрации, берем последние 30 дней
                    start = today - timedelta(days=30)
            
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
            else:
                end = today
            
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start,
                income_date__lte=end
            ).order_by('-income_date', '-amount')[:limit]
            
            results = []
            total = Decimal('0')
            
            for inc in incomes:
                amount = float(inc.amount)
                total += inc.amount
                results.append({
                    'date': inc.income_date.isoformat(),
                    'amount': amount,
                    'description': inc.description or get_text('income', profile.language_code or 'ru'),
                    'category': get_category_display_name(inc.category, profile.language_code or 'ru') if inc.category else get_text('no_category', profile.language_code or 'ru')
                })
            
            return {
                'success': True,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'count': len(results),
                'total': float(total),
                'incomes': results,
                'limit_message': f"Показано {len(results)} из {limit} максимум" if len(results) == limit else None
            }
        except Exception as e:
            logger.error(f"Error in get_incomes_list: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_daily_income_totals(user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Суммы доходов по дням за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            today = date.today()
            start_date = today - timedelta(days=days)
            
            daily_totals = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=today
            ).values('income_date').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-income_date')
            
            results = []
            grand_total = Decimal('0')
            
            for day in daily_totals:
                amount = float(day['total'])
                grand_total += day['total']
                results.append({
                    'date': day['income_date'].isoformat(),
                    'total': amount,
                    'count': day['count']
                })
            
            return {
                'success': True,
                'period_days': days,
                'daily_totals': results,
                'grand_total': float(grand_total),
                'days_with_income': len(results),
                'average_per_day': float(grand_total / days) if days > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error in get_daily_income_totals: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_all_operations(user_id: int, start_date: str = None, end_date: str = None, limit: int = 200) -> Dict[str, Any]:
        """
        Получить все операции (доходы и расходы) за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            
            # Получаем язык пользователя
            lang = profile.language_code or 'ru'
            
            # Парсим даты
            if start_date:
                start = datetime.fromisoformat(start_date).date()
            else:
                start = date.today() - timedelta(days=30)
            
            if end_date:
                end = datetime.fromisoformat(end_date).date()
            else:
                end = date.today()
            
            # Получаем расходы
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start,
                expense_date__lte=end
            ).select_related('category')
            
            # Получаем доходы
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start,
                income_date__lte=end
            ).select_related('category')
            
            operations = []
            
            # Добавляем расходы
            for exp in expenses:
                operations.append({
                    'type': 'expense',
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': -float(exp.amount),  # Отрицательное значение для расходов
                    'category': get_category_display_name(exp.category, lang) if exp.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': exp.description,
                    'currency': exp.currency
                })
            
            # Добавляем доходы
            for income in incomes:
                operations.append({
                    'type': 'income',
                    'date': income.income_date.isoformat(),
                    'time': income.income_time.strftime('%H:%M') if income.income_time else None,
                    'amount': float(income.amount),  # Положительное значение для доходов
                    'category': get_category_display_name(income.category, lang) if income.category else get_text('no_category', profile.language_code or 'ru'),
                    'description': income.description,
                    'currency': income.currency
                })
            
            # Сортируем по дате и времени (новые первыми)
            operations.sort(key=lambda x: (x['date'], x['time'] or '00:00'), reverse=True)
            
            # Применяем лимит
            limited_operations = operations[:limit]
            
            # Считаем общий баланс
            total_income = sum(op['amount'] for op in operations if op['type'] == 'income')
            total_expense = abs(sum(op['amount'] for op in operations if op['type'] == 'expense'))
            net_balance = total_income - total_expense
            
            response = {
                'success': True,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'count': len(limited_operations),
                'total_operations': len(operations),
                'operations': limited_operations,
                'summary': {
                    'total_income': total_income,
                    'total_expense': total_expense,
                    'net_balance': net_balance,
                    'currency': 'RUB'
                }
            }
            
            # Добавляем информацию об ограничении, если оно сработало
            if len(operations) > limit:
                response['limit_reached'] = True
                response['limit_message'] = f'💡 <i>Показаны последние {limit} операций из {len(operations)} за выбранный период</i>'
            
            return response
            
        except Exception as e:
            logger.error(f"Error in get_all_operations: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_financial_summary(user_id: int, period: str = 'month') -> Dict[str, Any]:
        """
        Получить финансовую сводку (доходы, расходы, баланс) за период
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Используем get_period_dates для определения периода
            from bot.utils.date_utils import get_period_dates
            start_date, end_date = get_period_dates(period)
            
            # Получаем расходы
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )
            
            total_expenses = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            expense_count = expenses.count()
            
            # Получаем доходы
            incomes = Income.objects.filter(
                profile=profile,
                income_date__gte=start_date,
                income_date__lte=end_date
            )
            
            total_income = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            income_count = incomes.count()
            
            # Считаем баланс
            net_balance = total_income - total_expenses
            
            # Статистика по категориям расходов
            expense_categories = expenses.values('category__name').annotate(
                total=Sum('amount')
            ).order_by('-total')[:5]
            
            # Статистика по категориям доходов
            income_categories = incomes.values('category__name').annotate(
                total=Sum('amount')
            ).order_by('-total')[:5]
            
            return {
                'success': True,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'income': {
                    'total': float(total_income),
                    'count': income_count,
                    'categories': [
                        {
                            'name': cat['category__name'] or get_text('no_category', profile.language_code or 'ru'),
                            'amount': float(cat['total'])
                        }
                        for cat in income_categories
                    ]
                },
                'expenses': {
                    'total': float(total_expenses),
                    'count': expense_count,
                    'categories': [
                        {
                            'name': cat['category__name'] or get_text('no_category', profile.language_code or 'ru'),
                            'amount': float(cat['total'])
                        }
                        for cat in expense_categories
                    ]
                },
                'balance': {
                    'net': float(net_balance),
                    'status': 'profit' if net_balance > 0 else 'loss' if net_balance < 0 else 'break_even'
                },
                'currency': 'RUB'
            }
            
        except Exception as e:
            logger.error(f"Error in get_financial_summary: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }

    @staticmethod
    async def analytics_query(user_id: int, spec_json: str) -> Dict[str, Any]:
        """
        Execute analytics query via JSON specification.
        This is the fallback mechanism for complex queries not covered by explicit functions.

        Args:
            user_id: Telegram user ID
            spec_json: JSON string with query specification

        Returns:
            Query results or error dict
        """
        from bot.services.analytics_query import execute_analytics_query

        try:
            # Execute the query using the analytics query system
            result = await execute_analytics_query(user_id, spec_json)
            return result
        except Exception as e:
            logger.error(f"Error in analytics_query: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Query execution failed',
                'message': str(e)
            }


# Экспортируемые функции для function calling
expense_functions = [
    {
        "name": "get_max_expense_day",
        "description": "Find the day with maximum expenses",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 60)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_period_total",
        "description": "Get total expenses for a period (today, yesterday, week, month, year)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "week", "month", "year"],
                    "description": "Period to analyze"
                }
            },
            "required": ["user_id", "period"]
        }
    },
    {
        "name": "get_category_statistics",
        "description": "Get expenses statistics by categories for a specific period (month name, season, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period": {
                    "type": "string",
                    "description": "Period name: 'month', 'last_month', 'декабрь', 'november', 'зима', 'summer', etc."
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (YYYY-MM-DD)"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (fallback if period not specified, default: 30)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_daily_totals",
        "description": "Get daily expense totals",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to get (default: 30)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "search_expenses",
        "description": "Search expenses by text in description or category",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 20)"
                }
            },
            "required": ["user_id", "query"]
        }
    },
    {
        "name": "get_average_expenses",
        "description": "Get average expense statistics",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Period in days for calculation (default: 30)"
                }
            },
            "required": ["user_id"]
        }
    },
    # INCOME ANALYSIS FUNCTIONS
    {
        "name": "get_income_total",
        "description": "Get total income for a period (today, week, month, year)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month", "year"],
                    "description": "Period to analyze"
                }
            },
            "required": ["user_id", "period"]
        }
    },
    {
        "name": "get_income_category_statistics",
        "description": "Get income statistics by categories for a specific period (month name, season, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period": {
                    "type": "string",
                    "description": "Period name: 'month', 'last_month', 'декабрь', 'november', 'зима', 'summer', etc."
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (YYYY-MM-DD)"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (fallback if period not specified, default: 30)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_recent_incomes",
        "description": "Get recent income transactions",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_all_operations",
        "description": "Get all financial operations (both income and expenses) for a period",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (YYYY-MM-DD), optional"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (YYYY-MM-DD), optional"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of operations (default: 200)"
                }
            },
            "required": ["user_id"]
        }
    },
    {
        "name": "get_financial_summary",
        "description": "Get comprehensive financial summary with income, expenses and balance",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month", "year"],
                    "description": "Period to analyze"
                }
            },
            "required": ["user_id", "period"]
        }
    }
]
