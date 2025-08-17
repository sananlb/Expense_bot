"""
Функции для работы с тратами через function calling в AI
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from asgiref.sync import sync_to_async
from expenses.models import Expense, UserProfile
from django.db.models import Sum, Avg, Max, Min, Count, Q
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ExpenseFunctions:
    """Класс с функциями для анализа трат, вызываемыми через AI function calling"""
    
    @staticmethod
    @sync_to_async
    def get_max_expense_day(user_id: int, period_days: int = 60) -> Dict[str, Any]:
        """
        Найти день с максимальными тратами
        
        Args:
            user_id: ID пользователя Telegram
            period_days: Период в днях для анализа
            
        Returns:
            Информация о дне с максимальными тратами
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Получаем траты за период
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).values('expense_date').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            if not expenses:
                return {
                    'success': False,
                    'message': 'Нет трат за указанный период'
                }
            
            max_day = expenses.first()
            
            # Получаем детали трат за этот день
            day_expenses = Expense.objects.filter(
                profile=profile,
                expense_date=max_day['expense_date']
            ).select_related('category')
            
            details = []
            for exp in day_expenses:
                details.append({
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    'category': exp.category.name if exp.category else 'Без категории',
                    'description': exp.description
                })
            
            return {
                'success': True,
                'date': max_day['expense_date'].isoformat(),
                'total': float(max_day['total']),
                'currency': 'RUB',
                'expenses_count': len(details),
                'details': details
            }
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
            }
        except Exception as e:
            logger.error(f"Error in get_max_expense_day: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
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
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            today = date.today()
            
            # Определяем даты периода
            if period == 'today':
                start_date = end_date = today
            elif period == 'yesterday':
                start_date = end_date = today - timedelta(days=1)
            elif period == 'week':
                start_date = today - timedelta(days=today.weekday())
                end_date = today
            elif period == 'month':
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'year':
                start_date = today.replace(month=1, day=1)
                end_date = today
            else:
                return {
                    'success': False,
                    'message': f'Неизвестный период: {period}'
                }
            
            # Получаем траты
            expenses = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )
            
            total = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = expenses.count()
            
            # Группируем по категориям
            by_category = expenses.values('category__name').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            categories = []
            for cat in by_category:
                categories.append({
                    'name': cat['category__name'] or 'Без категории',
                    'amount': float(cat['total'])
                })
            
            return {
                'success': True,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'currency': 'RUB',
                'count': count,
                'categories': categories[:5]  # Топ-5 категорий
            }
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
            }
        except Exception as e:
            logger.error(f"Error in get_period_total: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_category_statistics(user_id: int, period_days: int = 30) -> Dict[str, Any]:
        """
        Получить статистику по категориям
        
        Args:
            user_id: ID пользователя
            period_days: Период в днях
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            # Получаем траты по категориям
            stats = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
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
                    'name': stat['category__name'] or 'Без категории',
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
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
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
            profile = UserProfile.objects.get(telegram_id=user_id)
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
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
            }
        except Exception as e:
            logger.error(f"Error in get_daily_totals: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def search_expenses(user_id: int, query: str, limit: int = 20) -> Dict[str, Any]:
        """
        Поиск трат по тексту
        
        Args:
            user_id: ID пользователя
            query: Поисковый запрос
            limit: Максимальное количество результатов
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            
            # Поиск по описанию и категориям
            expenses = Expense.objects.filter(
                profile=profile
            ).filter(
                Q(description__icontains=query) | 
                Q(category__name__icontains=query)
            ).select_related('category').order_by('-expense_date', '-expense_time')[:limit]
            
            results = []
            for exp in expenses:
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    'category': exp.category.name if exp.category else 'Без категории',
                    'description': exp.description,
                    'currency': exp.currency
                })
            
            return {
                'success': True,
                'query': query,
                'count': len(results),
                'results': results
            }
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
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
            profile = UserProfile.objects.get(telegram_id=user_id)
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
                'period_days': period_days,
                'total': float(total),
                'count': count,
                'days_with_expenses': days_with_expenses,
                'average_per_day': float(total / period_days) if period_days > 0 else 0,
                'average_per_active_day': float(total / days_with_expenses) if days_with_expenses > 0 else 0,
                'average_per_expense': float(total / count) if count > 0 else 0,
                'currency': 'RUB'
            }
            
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'message': 'Профиль пользователя не найден'
            }
        except Exception as e:
            logger.error(f"Error in get_average_expenses: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    @staticmethod
    @sync_to_async
    def get_expenses_list(user_id: int, start_date: str = None, end_date: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Получить список трат за период
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            
            # Парсим даты
            if start_date:
                start = datetime.fromisoformat(start_date).date()
            else:
                start = date.today() - timedelta(days=7)
            
            if end_date:
                end = datetime.fromisoformat(end_date).date()
            else:
                end = date.today()
            
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
                    'category': exp.category.name if exp.category else 'Без категории',
                    'description': exp.description
                })
            
            return {
                'success': True,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'count': len(results),
                'total': float(total),
                'expenses': results
            }
        except Exception as e:
            logger.error(f"Error in get_expenses_list: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_max_single_expense(user_id: int, period_days: int = 60) -> Dict[str, Any]:
        """
        Найти самую большую единичную трату
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
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
            
            return {
                'success': True,
                'date': max_expense.expense_date.isoformat(),
                'time': max_expense.expense_time.strftime('%H:%M') if max_expense.expense_time else None,
                'amount': float(max_expense.amount),
                'category': max_expense.category.name if max_expense.category else 'Без категории',
                'description': max_expense.description,
                'currency': max_expense.currency
            }
        except Exception as e:
            logger.error(f"Error in get_max_single_expense: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_category_total(user_id: int, category: str, period: str = 'month') -> Dict[str, Any]:
        """
        Получить траты по конкретной категории
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            today = date.today()
            
            # Определяем период
            if period == 'week':
                start_date = today - timedelta(days=today.weekday())
            elif period == 'month':
                start_date = today.replace(day=1)
            elif period == 'year':
                start_date = today.replace(month=1, day=1)
            else:
                start_date = today - timedelta(days=30)
            
            expenses = Expense.objects.filter(
                profile=profile,
                category__name__icontains=category,
                expense_date__gte=start_date,
                expense_date__lte=today
            )
            
            total = expenses.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = expenses.count()
            
            return {
                'success': True,
                'category': category,
                'period': period,
                'total': float(total),
                'count': count,
                'average': float(total / count) if count > 0 else 0,
                'currency': 'RUB'
            }
        except Exception as e:
            logger.error(f"Error in get_category_total: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def compare_periods(user_id: int, period1: str = 'this_month', period2: str = 'last_month') -> Dict[str, Any]:
        """
        Сравнить траты за два периода
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            today = date.today()
            
            # Определяем первый период
            if period1 == 'this_week':
                p1_start = today - timedelta(days=today.weekday())
                p1_end = today
            elif period1 == 'this_month':
                p1_start = today.replace(day=1)
                p1_end = today
            else:
                p1_start = today - timedelta(days=7)
                p1_end = today
            
            # Определяем второй период
            if period2 == 'last_week':
                p2_end = p1_start - timedelta(days=1)
                p2_start = p2_end - timedelta(days=6)
            elif period2 == 'last_month':
                p2_end = p1_start - timedelta(days=1)
                p2_start = p2_end.replace(day=1)
            else:
                p2_end = p1_start - timedelta(days=1)
                p2_start = p2_end - timedelta(days=6)
            
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
    def get_expenses_by_amount_range(user_id: int, min_amount: float = None, max_amount: float = None, limit: int = 50) -> Dict[str, Any]:
        """
        Получить траты в диапазоне сумм
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            
            expenses = Expense.objects.filter(profile=profile)
            
            if min_amount is not None:
                expenses = expenses.filter(amount__gte=min_amount)
            if max_amount is not None:
                expenses = expenses.filter(amount__lte=max_amount)
            
            expenses = expenses.select_related('category').order_by('-amount', '-expense_date')[:limit]
            
            results = []
            for exp in expenses:
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'amount': float(exp.amount),
                    'category': exp.category.name if exp.category else 'Без категории',
                    'description': exp.description
                })
            
            return {
                'success': True,
                'min_amount': min_amount,
                'max_amount': max_amount,
                'count': len(results),
                'expenses': results
            }
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
            profile = UserProfile.objects.get(telegram_id=user_id)
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
            profile = UserProfile.objects.get(telegram_id=user_id)
            end_date = date.today()
            start_date = end_date - timedelta(days=period_days)
            
            weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
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
            for i, day_name in enumerate(weekdays):
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
            profile = UserProfile.objects.get(telegram_id=user_id)
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
    
    @staticmethod
    @sync_to_async
    def check_budget_status(user_id: int, budget_amount: float) -> Dict[str, Any]:
        """
        Проверить статус бюджета
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            today = date.today()
            month_start = today.replace(day=1)
            
            # Текущие траты
            current_total = Expense.objects.filter(
                profile=profile,
                expense_date__gte=month_start,
                expense_date__lte=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            current_total = float(current_total)
            remaining = budget_amount - current_total
            percent_used = (current_total / budget_amount * 100) if budget_amount > 0 else 0
            
            # Прогноз
            days_passed = today.day
            if today.month == 12:
                next_month = today.replace(year=today.year+1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month+1, day=1)
            days_in_month = (next_month - month_start).days
            
            avg_per_day = current_total / days_passed if days_passed > 0 else 0
            predicted_total = avg_per_day * days_in_month
            
            will_exceed = predicted_total > budget_amount
            
            return {
                'success': True,
                'budget': budget_amount,
                'spent': current_total,
                'remaining': remaining,
                'percent_used': round(percent_used, 1),
                'predicted_total': round(predicted_total, 2),
                'will_exceed': will_exceed,
                'status': 'превышение' if will_exceed else 'в рамках бюджета'
            }
        except Exception as e:
            logger.error(f"Error in check_budget_status: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_recent_expenses(user_id: int, limit: int = 10) -> Dict[str, Any]:
        """
        Получить последние траты
        """
        try:
            profile = UserProfile.objects.get(telegram_id=user_id)
            
            expenses = Expense.objects.filter(
                profile=profile
            ).select_related('category').order_by('-expense_date', '-expense_time', '-id')[:limit]
            
            results = []
            for exp in expenses:
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': float(exp.amount),
                    'category': exp.category.name if exp.category else 'Без категории',
                    'description': exp.description,
                    'currency': exp.currency
                })
            
            return {
                'success': True,
                'count': len(results),
                'expenses': results
            }
        except Exception as e:
            logger.error(f"Error in get_recent_expenses: {e}")
            return {'success': False, 'message': str(e)}


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
        "description": "Get expenses statistics by categories",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "Telegram user ID"
                },
                "period_days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30)"
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
    }
]