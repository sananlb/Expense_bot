"""
Функции для работы с тратами и доходами через function calling в AI
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from asgiref.sync import sync_to_async
from expenses.models import Expense, Profile, Income, IncomeCategory
from django.db.models import Sum, Avg, Max, Min, Count, Q
from collections import defaultdict
from bot.utils.category_helpers import get_category_display_name
from bot.utils.language import get_user_language, translate_category_name
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
        logger.info(f"[get_max_expense_day] Starting for user_id={user_id}, period_days={period_days}")
        try:
            # Используем get_or_create для автоматического создания профиля
            profile, created = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            if created:
                logger.info(f"[get_max_expense_day] Created new profile for user {user_id}")
            else:
                logger.info(f"[get_max_expense_day] Profile found: id={profile.id}, telegram_id={profile.telegram_id}")
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
            
            from bot.utils import get_text, translate_category_name
            
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
            from bot.utils import get_text, translate_category_name
            lang = profile.language_code or 'ru'
            
            # Группируем по категориям
            by_category = expenses.values('category__name').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            categories = []
            for cat in by_category:
                category_name = cat['category__name'] or get_text('no_category', lang)
                # Переводим название категории
                if cat['category__name']:
                    category_name = translate_category_name(category_name, lang)
                    
                categories.append({
                    'name': category_name,
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
    ) -> Dict[str, Any]:
        """
        Получить статистику по категориям
        
        Args:
            user_id: ID пользователя
            period_days: Период в днях
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
            # Определяем период: явные даты имеют приоритет
            if start_date and end_date:
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
        Поиск трат по тексту

        Args:
            user_id: ID пользователя
            query: Поисковый запрос
            limit: Максимальное количество результатов
            start_date: Начальная дата периода (YYYY-MM-DD)
            end_date: Конечная дата периода (YYYY-MM-DD)
            period: Период ('last_week', 'last_month', 'week', 'month', etc.)
        """
        try:
            from bot.utils.date_utils import get_period_dates

            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )

            # Определяем даты периода
            if period:
                # Если задан период, используем его
                period_start, period_end = get_period_dates(period)
                start_date = period_start.isoformat()
                end_date = period_end.isoformat()

            logger.info(f"search_expenses: profile_id={profile.id}, query='{query}', limit={limit}, period={start_date} to {end_date}")

            # Поиск по описанию и категориям
            # Сначала пробуем стандартный поиск
            queryset = Expense.objects.filter(profile=profile)

            # Добавляем фильтрацию по датам если указаны
            if start_date:
                from datetime import datetime
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(expense_date__gte=start_dt)
                except ValueError:
                    logger.warning(f"Invalid start_date format: {start_date}")

            if end_date:
                from datetime import datetime
                try:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(expense_date__lte=end_dt)
                except ValueError:
                    logger.warning(f"Invalid end_date format: {end_date}")

            expenses = queryset.filter(
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(category__name_ru__icontains=query) |
                Q(category__name_en__icontains=query)
            ).select_related('category').order_by('-expense_date', '-expense_time')[:limit]

            # Если ничего не найдено и запрос содержит кириллицу - используем альтернативный метод
            # (SQLite плохо работает с icontains для кириллицы)
            if len(expenses) == 0 and any(ord(c) > 127 for c in query):
                # Получаем все траты пользователя с учетом дат и фильтруем в Python
                all_expenses = queryset.select_related('category').order_by('-expense_date', '-expense_time')

                query_lower = query.lower()
                filtered_expenses = []

                for exp in all_expenses:
                    # Проверяем описание
                    if exp.description and query_lower in exp.description.lower():
                        filtered_expenses.append(exp)
                        continue
                    # Проверяем категорию в разных полях
                    if exp.category:
                        if exp.category.name and query_lower in exp.category.name.lower():
                            filtered_expenses.append(exp)
                            continue
                        if exp.category.name_ru and query_lower in exp.category.name_ru.lower():
                            filtered_expenses.append(exp)
                            continue
                        if exp.category.name_en and query_lower in exp.category.name_en.lower():
                            filtered_expenses.append(exp)
                            continue

                expenses = filtered_expenses[:limit]
                logger.info(f"search_expenses: fallback search found {len(expenses)} expenses")

            logger.info(f"search_expenses: found {len(expenses)} expenses for query '{query}'")

            # Получаем язык пользователя
            lang = profile.language_code or 'ru'

            results = []
            total_amount = 0
            for exp in expenses:
                amount = float(exp.amount)
                total_amount += amount
                results.append({
                    'date': exp.expense_date.isoformat(),
                    'time': exp.expense_time.strftime('%H:%M') if exp.expense_time else None,
                    'amount': amount,
                    'category': get_category_display_name(exp.category, lang) if exp.category else 'Без категории',
                    'description': exp.description,
                    'currency': exp.currency
                })

            return {
                'success': True,
                'query': query,
                'count': len(results),
                'total': total_amount,
                'results': results
            }
            
        except Profile.DoesNotExist:
            from bot.utils import get_text
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
                    # 'category': exp.category.name if exp.category else 'Без категории',
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
            weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            weekday = weekdays[max_expense.expense_date.weekday()]
            
            return {
                'success': True,
                'date': max_expense.expense_date.isoformat(),
                'weekday': weekday,
                'time': max_expense.expense_time.strftime('%H:%M') if max_expense.expense_time else None,
                'amount': float(max_expense.amount),
                'category': get_category_display_name(max_expense.category, 'ru') if max_expense.category else 'Без категории',
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

            from expenses.models import ExpenseCategory
            from django.db.models import Q

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

            qs = Expense.objects.filter(
                profile=profile,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            )

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

            qs = qs.filter(q_filter)

            logger.info(f"get_category_total: filtered queryset, found {qs.count()} expenses")

            from django.db.models import Sum
            total = qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            count = qs.count()

            logger.info(f"get_category_total: result - total={total}, count={count}")

            # Если нашли траты, покажем первые несколько для отладки
            if count > 0:
                for exp in qs[:3]:
                    logger.info(f"  - Expense: amount={exp.amount}, date={exp.expense_date}, category='{exp.category.name if exp.category else 'None'}', desc='{exp.description}'")

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
                    'category': get_category_display_name(exp.category, 'ru') if exp.category else 'Без категории',
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
    #                 'category': exp.category.name if exp.category else 'Без категории',
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
    def check_budget_status(user_id: int, budget_amount: float) -> Dict[str, Any]:
        """
        Проверить статус бюджета
        """
        try:
            profile, _ = Profile.objects.get_or_create(
                telegram_id=user_id,
                defaults={'language_code': 'ru'}
            )
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
                    'category': get_category_display_name(exp.category, lang) if exp.category else 'Без категории',
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
            today = date.today()
            
            # Определяем даты периода
            if period == 'today':
                start_date = end_date = today
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
            from bot.utils import get_text, translate_category_name
            lang = profile.language_code or 'ru'
            
            # Группируем по категориям
            by_category = incomes.values('category__name').annotate(
                total=Sum('amount')
            ).order_by('-total')
            
            categories = []
            for cat in by_category:
                category_name = cat['category__name'] or get_text('no_category', lang)
                # Переводим название категории
                if cat['category__name']:
                    category_name = translate_category_name(category_name, lang)
                    
                categories.append({
                    'name': category_name,
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
                    'category': get_category_display_name(income.category, lang) if income.category else 'Без категории',
                    'description': income.description,
                    'currency': income.currency
                })
            
            return {
                'success': True,
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
            profile = Profile.objects.get(telegram_id=user_id)
            
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
                    'description': inc.description or get_category_display_name(inc.category, 'ru') if inc.category else 'Доход',
                    'category': get_category_display_name(inc.category, 'ru') if inc.category else 'Без категории'
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

            profile = Profile.objects.get(telegram_id=user_id)

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
                'income': {
                    'amount': float(max_income.amount),
                    'description': max_income.description or 'Доход',
                    'category': get_category_display_name(max_income.category, 'ru') if max_income.category else 'Без категории',
                    'date': max_income.income_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error in get_max_single_income: {e}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    @sync_to_async
    def get_income_category_statistics(user_id: int) -> Dict[str, Any]:
        """
        Статистика доходов по категориям (аналог get_category_statistics)
        """
        try:
            profile = Profile.objects.get(telegram_id=user_id)
            today = date.today()
            month_ago = today - timedelta(days=30)
            
            stats = Income.objects.filter(
                profile=profile,
                income_date__gte=month_ago
            ).values('category__name').annotate(
                total=Sum('amount'),
                count=Count('id')
            ).order_by('-total')
            
            categories = []
            total_income = Decimal('0')
            
            for stat in stats:
                category_name = stat['category__name'] or 'Без категории'
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
                'period_days': 30
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
            profile = Profile.objects.get(telegram_id=user_id)
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
    def search_incomes(user_id: int, query: str) -> Dict[str, Any]:
        """
        Поиск доходов по описанию
        """
        try:
            profile = Profile.objects.get(telegram_id=user_id)
            
            incomes = Income.objects.filter(
                profile=profile,
                description__icontains=query
            ).order_by('-income_date')[:20]
            
            results = []
            for inc in incomes:
                results.append({
                    'date': inc.income_date.isoformat(),
                    'amount': float(inc.amount),
                    'description': inc.description or 'Доход',
                    'category': get_category_display_name(inc.category, 'ru') if inc.category else 'Без категории'
                })
            
            return {
                'success': True,
                'query': query,
                'count': len(results),
                'incomes': results
            }
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
            profile = Profile.objects.get(telegram_id=user_id)
            
            incomes = Income.objects.filter(profile=profile)
            
            weekday_stats = {}
            weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
            
            for i, day_name in enumerate(weekdays):
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
            profile = Profile.objects.get(telegram_id=user_id)
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
        Проверка достижения целевого дохода (аналог check_budget_status)
        """
        try:
            profile = Profile.objects.get(telegram_id=user_id)
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
    def compare_income_periods(user_id: int) -> Dict[str, Any]:
        """
        Сравнение доходов за разные периоды
        """
        try:
            profile = Profile.objects.get(telegram_id=user_id)
            today = date.today()
            
            # Текущий месяц
            current_month_start = today.replace(day=1)
            current_month_income = Income.objects.filter(
                profile=profile,
                income_date__gte=current_month_start,
                income_date__lte=today
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            # Прошлый месяц
            if today.month == 1:
                prev_month_start = today.replace(year=today.year-1, month=12, day=1)
                prev_month_end = today.replace(year=today.year-1, month=12, day=31)
            else:
                prev_month_start = today.replace(month=today.month-1, day=1)
                prev_month_end = (current_month_start - timedelta(days=1))
            
            prev_month_income = Income.objects.filter(
                profile=profile,
                income_date__gte=prev_month_start,
                income_date__lte=prev_month_end
            ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
            
            change = current_month_income - prev_month_income
            change_percent = ((change / prev_month_income) * 100) if prev_month_income > 0 else 0
            
            return {
                'success': True,
                'current_month': float(current_month_income),
                'previous_month': float(prev_month_income),
                'change': float(change),
                'change_percent': float(change_percent),
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
            profile = Profile.objects.get(telegram_id=user_id)
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
            profile = Profile.objects.get(telegram_id=user_id)
            
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
                    'description': inc.description or 'Доход',
                    'category': get_category_display_name(inc.category, 'ru') if inc.category else 'Без категории'
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
            profile = Profile.objects.get(telegram_id=user_id)
            today = date.today()
            
            # Определяем период
            if period == 'today':
                start_date = end_date = today
            elif period == 'week':
                start_date = today - timedelta(days=7)
                end_date = today
            elif period == 'month':
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'year':
                start_date = today.replace(month=1, day=1)
                end_date = today
            else:
                start_date = today - timedelta(days=30)
                end_date = today
            
            # Ищем категорию
            from expenses.models import IncomeCategory
            categories = IncomeCategory.objects.filter(
                name__icontains=category,
                profile=profile
            )
            
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
            
            return {
                'success': True,
                'category': categories[0].name,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total': float(total),
                'count': count,
                'average': float(total / count) if count > 0 else 0
            }
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
            profile = Profile.objects.get(telegram_id=user_id)
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
                    'description': inc.description or 'Доход',
                    'category': get_category_display_name(inc.category, 'ru') if inc.category else 'Без категории'
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
            profile = Profile.objects.get(telegram_id=user_id)
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
                    'category': get_category_display_name(exp.category, lang) if exp.category else 'Без категории',
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
                    'category': get_category_display_name(income.category, lang) if income.category else 'Без категории',
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
            today = date.today()
            
            # Определяем даты периода
            if period == 'today':
                start_date = end_date = today
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
                            'name': cat['category__name'] or 'Без категории',
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
                            'name': cat['category__name'] or 'Без категории',
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
        "name": "get_income_by_category",
        "description": "Get income statistics by categories",
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
