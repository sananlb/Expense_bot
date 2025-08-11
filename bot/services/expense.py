"""
Service for expense management
"""
from asgiref.sync import sync_to_async
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging

from expenses.models import Expense, Profile, ExpenseCategory, Cashback
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from bot.utils.db_utils import get_or_create_user_profile_sync

logger = logging.getLogger(__name__)


@sync_to_async
def create_expense(
    user_id: int,
    amount: Decimal,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    expense_date: Optional[date] = None,
    ai_categorized: bool = False,
    ai_confidence: Optional[float] = None,
    currency: str = 'RUB'
) -> Optional[Expense]:
    """
    Создать новую трату
    
    Args:
        user_id: ID пользователя в Telegram
        amount: Сумма траты
        category_id: ID категории (опционально)
        description: Описание траты
        expense_date: Дата траты (по умолчанию сегодня)
        ai_categorized: Категория определена AI
        ai_confidence: Уверенность AI в категории
        
    Returns:
        Expense instance или None при ошибке
    """
    profile = get_or_create_user_profile_sync(user_id)
    
    try:
        if expense_date is None:
            expense_date = date.today()
        
        # Проверяем лимит расходов в день (максимум 100)
        today_expenses_count = Expense.objects.filter(
            profile=profile,
            expense_date=expense_date
        ).count()
        
        if today_expenses_count >= 100:
            logger.warning(f"User {user_id} reached daily expenses limit (100)")
            raise ValueError("Достигнут лимит записей в день (максимум 100). Попробуйте завтра.")
        
        # Проверяем длину описания (максимум 500 символов)
        if description and len(description) > 500:
            logger.warning(f"User {user_id} provided too long description: {len(description)} chars")
            raise ValueError("Описание слишком длинное (максимум 500 символов)")
            
        expense = Expense.objects.create(
            profile=profile,
            category_id=category_id,
            amount=amount,
            currency=currency,
            description=description,
            expense_date=expense_date,
            ai_categorized=ai_categorized,
            ai_confidence=ai_confidence
        )
        
        logger.info(f"Created expense {expense.id} for user {user_id}")
        return expense
    except ValueError:
        raise  # Пробрасываем ValueError дальше
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        return None


# Alias for backward compatibility
add_expense = create_expense


@sync_to_async
def get_user_expenses(
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    limit: int = 50
) -> List[Expense]:
    """
    Получить траты пользователя
    
    Args:
        user_id: ID пользователя в Telegram
        start_date: Начальная дата
        end_date: Конечная дата
        category_id: Фильтр по категории
        limit: Максимальное количество записей
        
    Returns:
        Список трат
    """
    profile = get_or_create_user_profile_sync(user_id)
    
    try:
        queryset = Expense.objects.filter(profile=profile)
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
            
        return list(queryset.select_related('category').order_by('-expense_date', '-created_at')[:limit])
        
        pass
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return []


@sync_to_async
def get_expenses_summary(
    user_id: int,
    start_date: date,
    end_date: date
) -> Dict:
    """
    Получить сводку трат за период
    
    Args:
        user_id: ID пользователя в Telegram
        start_date: Начальная дата
        end_date: Конечная дата
        
    Returns:
        Словарь со сводкой:
        {
            'total': Decimal,
            'count': int,
            'by_category': List[Dict],
            'currency': str,
            'potential_cashback': Decimal
        }
    """
    logger.info(f"get_expenses_summary called: user_id={user_id}, start={start_date}, end={end_date}")
    profile = get_or_create_user_profile_sync(user_id)
    logger.info(f"Profile found/created: {profile.id} for telegram_id={profile.telegram_id}")
    
    try:
        expenses = Expense.objects.filter(
            profile=profile,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )
        logger.info(f"Query: profile={profile.id}, date>={start_date}, date<={end_date}, found={expenses.count()} expenses")
        
        # Общая сумма и количество
        total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        count = expenses.count()
        
        # По категориям
        by_category = expenses.values(
            'category__id',
            'category__name',
            'category__icon'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Преобразуем в список словарей
        categories_list = []
        for cat in by_category:
            categories_list.append({
                'id': cat['category__id'],
                'name': cat['category__name'] or 'Без категории',
                'icon': cat['category__icon'] or '',
                'total': cat['total'],
                'count': cat['count']
            })
            
        # Рассчитываем потенциальный кешбэк
        potential_cashback = Decimal('0')
        current_month = start_date.month
        
        # Получаем кешбэки для текущего месяца
        cashbacks = Cashback.objects.filter(
            profile=profile,
            month=current_month
        ).select_related('category')
        
        # Словарь кешбэков по категориям
        cashback_map = {}
        for cb in cashbacks:
            if cb.category_id not in cashback_map:
                cashback_map[cb.category_id] = []
            cashback_map[cb.category_id].append(cb)
            
        # Рассчитываем кешбэк для каждой категории
        for cat in categories_list:
            if cat['id'] in cashback_map:
                # Берем максимальный кешбэк из доступных
                max_cashback = max(cashback_map[cat['id']], key=lambda x: x.cashback_percent)
                
                # Проверяем лимит
                if max_cashback.limit_amount:
                    cashback_amount = min(
                        cat['total'] * max_cashback.cashback_percent / 100,
                        max_cashback.limit_amount
                    )
                else:
                    cashback_amount = cat['total'] * max_cashback.cashback_percent / 100
                    
                potential_cashback += cashback_amount
                
        return {
            'total': total,
            'count': count,
            'by_category': categories_list,
            'currency': profile.currency or 'RUB',
            'potential_cashback': potential_cashback
        }
        
    except Exception as e:
        logger.error(f"Error getting expenses summary: {e}")
        return {
            'total': Decimal('0'),
            'count': 0,
            'by_category': [],
            'currency': 'RUB',
            'potential_cashback': Decimal('0')
        }


@sync_to_async
def get_expenses_by_period(
    user_id: int,
    period: str = 'month'
) -> Dict:
    """
    Получить траты за стандартный период
    
    Args:
        user_id: ID пользователя в Telegram
        period: Период ('today', 'week', 'month', 'year')
        
    Returns:
        Словарь со сводкой
    """
    today = date.today()
    
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
        # По умолчанию - текущий месяц
        start_date = today.replace(day=1)
        end_date = today
        
    return get_expenses_summary(user_id, start_date, end_date)


@sync_to_async
def update_expense(
    user_id: int,
    expense_id: int,
    **kwargs
) -> bool:
    """
    Обновить трату
    
    Args:
        user_id: ID пользователя в Telegram
        expense_id: ID траты
        **kwargs: Поля для обновления
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return False
    
    try:
        expense = Expense.objects.get(id=expense_id, profile=profile)
        
        # Запоминаем старую категорию для обучения системы
        old_category_id = expense.category_id if expense.category else None
        
        # Проверяем, изменилась ли категория
        category_changed = False
        new_category_id = kwargs.get('category_id')
        if new_category_id and new_category_id != old_category_id:
            category_changed = True
        
        # Обновляем только переданные поля
        for field, value in kwargs.items():
            if hasattr(expense, field):
                setattr(expense, field, value)
                
        expense.save()
        logger.info(f"Updated expense {expense_id} for user {user_id}")
        
        # Если категория изменилась, запускаем фоновую задачу для обновления весов
        if category_changed and old_category_id:
            from expense_bot.celery_tasks import update_keywords_weights
            update_keywords_weights.delay(
                expense_id=expense_id,
                old_category_id=old_category_id,
                new_category_id=new_category_id
            )
            logger.info(f"Triggered keywords weights update for expense {expense_id}")
        
        return True
        
    except Expense.DoesNotExist:
        logger.error(f"Expense {expense_id} not found for user {user_id}")
        return False
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        return False


@sync_to_async
def get_expense_by_id(expense_id: int, telegram_id: int) -> Optional[Expense]:
    """
    Получить трату по ID
    
    Args:
        expense_id: ID траты
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Expense instance или None
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        return Expense.objects.select_related('category').get(id=expense_id, profile=profile)
    except (Profile.DoesNotExist, Expense.DoesNotExist):
        return None
    except Exception as e:
        logger.error(f"Error getting expense by id: {e}")
        return None


@sync_to_async
def get_user_expenses(
    telegram_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    limit: int = 50
) -> List[Expense]:
    """
    Получить траты пользователя с фильтрацией
    
    Args:
        telegram_id: ID пользователя в Telegram
        start_date: Начальная дата (включительно)
        end_date: Конечная дата (включительно)
        category_id: ID категории для фильтрации
        limit: Максимальное количество записей
        
    Returns:
        Список трат
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        
        queryset = Expense.objects.filter(profile=profile)
        
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
            
        return list(queryset.select_related('category').order_by('-expense_date', '-expense_time')[:limit])
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return []
    except Exception as e:
        logger.error(f"Error getting user expenses: {e}")
        return []


@sync_to_async
def find_similar_expenses(
    telegram_id: int,
    description: str,
    days_back: int = 365
) -> List[Dict[str, Any]]:
    """
    Найти похожие траты за последний период
    
    Args:
        telegram_id: ID пользователя в Telegram
        description: Описание для поиска
        days_back: Количество дней назад для поиска (по умолчанию год)
        
    Returns:
        Список похожих трат с уникальными суммами
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        
        # Определяем период поиска
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Нормализуем описание для поиска
        search_desc = description.lower().strip()
        
        # Ищем траты с похожим описанием
        queryset = Expense.objects.filter(
            profile=profile,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )
        
        # Фильтруем по описанию (точное совпадение или содержит)
        similar_expenses = []
        for expense in queryset.select_related('category'):
            if expense.description:
                exp_desc = expense.description.lower().strip()
                # Проверяем точное совпадение или вхождение
                if exp_desc == search_desc or search_desc in exp_desc or exp_desc in search_desc:
                    similar_expenses.append(expense)
        
        # Группируем по уникальным суммам и категориям
        unique_amounts = {}
        for expense in similar_expenses:
            key = (float(expense.amount), expense.currency, expense.category.name if expense.category else 'Прочие расходы')
            if key not in unique_amounts:
                unique_amounts[key] = {
                    'amount': float(expense.amount),
                    'currency': expense.currency,
                    'category': expense.category.name if expense.category else 'Прочие расходы',
                    'count': 1,
                    'last_date': expense.expense_date
                }
            else:
                unique_amounts[key]['count'] += 1
                if expense.expense_date > unique_amounts[key]['last_date']:
                    unique_amounts[key]['last_date'] = expense.expense_date
        
        # Сортируем по частоте использования и дате
        result = sorted(
            unique_amounts.values(),
            key=lambda x: (x['count'], x['last_date']),
            reverse=True
        )
        
        return result[:5]  # Возвращаем топ-5 вариантов
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return []
    except Exception as e:
        logger.error(f"Error finding similar expenses: {e}")
        return []


@sync_to_async
def delete_expense(telegram_id: int, expense_id: int) -> bool:
    """
    Удалить трату
    
    Args:
        telegram_id: ID пользователя в Telegram
        expense_id: ID траты
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return False
    
    try:
        expense = Expense.objects.get(id=expense_id, profile=profile)
        expense.delete()
        
        logger.info(f"Deleted expense {expense_id} for user {telegram_id}")
        return True
        
    except Expense.DoesNotExist:
        logger.error(f"Expense {expense_id} not found for user {telegram_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


@sync_to_async
def get_last_expense(telegram_id: int) -> Optional[Expense]:
    """
    Получить последнюю трату пользователя
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        Expense instance или None
    """
    profile = get_or_create_user_profile_sync(user_id)
    
    try:
        return Expense.objects.filter(profile=profile).order_by('-created_at').first()
    except Exception as e:
        logger.error(f"Error getting last expense: {e}")
        return None


async def get_today_summary(user_id: int) -> Dict[str, Any]:
    """Get today's expense summary with multi-currency support"""
    from expenses.models import Profile
    
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        today = date.today()
        
        expenses = await sync_to_async(list)(
            Expense.objects.filter(
                profile=profile,
                expense_date=today
            ).select_related('category')
        )
        
        # Group by currency
        currency_totals = {}
        for expense in expenses:
            currency = expense.currency or 'RUB'
            if currency not in currency_totals:
                currency_totals[currency] = Decimal('0')
            currency_totals[currency] += expense.amount
        
        # Get user's primary currency
        user_currency = profile.currency or 'RUB'
        
        # Keep currencies separate
        # Total will be shown per currency
        single_currency = len(currency_totals) == 1
        # For single currency, use that total
        if single_currency and user_currency in currency_totals:
            total = float(currency_totals[user_currency])
        else:
            # For multiple currencies, show main currency total
            total = float(currency_totals.get(user_currency, 0))
        
        # Group by category and currency
        categories_by_currency = {}
        for expense in expenses:
            if expense.category:
                currency = expense.currency or 'RUB'
                if currency not in categories_by_currency:
                    categories_by_currency[currency] = {}
                
                cat_key = expense.category.id
                if cat_key not in categories_by_currency[currency]:
                    categories_by_currency[currency][cat_key] = {
                        'name': expense.category.name,
                        'icon': expense.category.icon,
                        'amount': Decimal('0'),
                        'currency': currency
                    }
                categories_by_currency[currency][cat_key]['amount'] += expense.amount
        
        # Combine categories from all currencies
        all_categories = []
        for currency, cats in categories_by_currency.items():
            for cat in cats.values():
                all_categories.append(cat)
        
        # Sort by amount (note: mixed currencies, but at least shows all)
        sorted_categories = sorted(
            all_categories,
            key=lambda x: x['amount'],
            reverse=True
        )
        
        return {
            'total': total,
            'count': len(expenses),
            'categories': sorted_categories,
            'currency': user_currency,
            'currency_totals': {k: float(v) for k, v in currency_totals.items()},
            'single_currency': single_currency
        }
        
    except Profile.DoesNotExist:
        return {'total': 0, 'count': 0, 'categories': [], 'currency': 'RUB', 'currency_totals': {}, 'single_currency': True}
    except Exception as e:
        logger.error(f"Error getting today summary: {e}")
        return {'total': 0, 'count': 0, 'categories': [], 'currency': 'RUB', 'currency_totals': {}, 'single_currency': True}


@sync_to_async
def get_last_expense_by_description(telegram_id: int, description: str) -> Optional[Expense]:
    """
    Найти последнюю трату пользователя по описанию
    
    Args:
        telegram_id: ID пользователя
        description: Описание для поиска
        
    Returns:
        Последняя трата с похожим описанием или None
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        # Ищем точное совпадение или частичное вхождение
        expense = Expense.objects.filter(
            profile=profile,
            description__icontains=description.strip()
        ).select_related('category').order_by('-expense_date', '-created_at').first()
        return expense
    except Profile.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error finding expense by description: {e}")
        return None


@sync_to_async
def get_last_expenses(telegram_id: int, limit: int = 30) -> List[Expense]:
    """
    Получить последние расходы пользователя
    
    Args:
        telegram_id: ID пользователя
        limit: Максимальное количество записей
        
    Returns:
        Список расходов
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        expenses = Expense.objects.filter(profile=profile).order_by('-expense_date', '-created_at')[:limit]
        return list(expenses)
    except Profile.DoesNotExist:
        return []
    except Exception as e:
        logger.error(f"Error getting last expenses: {e}")
        return []


async def get_month_summary(user_id: int, month: int, year: int) -> Dict[str, Any]:
    """Get monthly expense summary with multi-currency support"""
    from expenses.models import Profile
    
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        
        expenses = await sync_to_async(list)(
            Expense.objects.filter(
                profile=profile,
                expense_date__month=month,
                expense_date__year=year
            ).select_related('category')
        )
        
        # Group by currency
        currency_totals = {}
        for expense in expenses:
            currency = expense.currency or 'RUB'
            if currency not in currency_totals:
                currency_totals[currency] = Decimal('0')
            currency_totals[currency] += expense.amount
        
        # Get user's primary currency
        user_currency = profile.currency or 'RUB'
        
        # Keep currencies separate
        # Total will be shown per currency
        single_currency = len(currency_totals) == 1
        # For single currency, use that total
        if single_currency and user_currency in currency_totals:
            total = float(currency_totals[user_currency])
        else:
            # For multiple currencies, show main currency total
            total = float(currency_totals.get(user_currency, 0))
        
        # Group by category and currency
        categories_by_currency = {}
        for expense in expenses:
            if expense.category:
                currency = expense.currency or 'RUB'
                if currency not in categories_by_currency:
                    categories_by_currency[currency] = {}
                
                cat_key = expense.category.id
                if cat_key not in categories_by_currency[currency]:
                    categories_by_currency[currency][cat_key] = {
                        'name': expense.category.name,
                        'icon': expense.category.icon,
                        'amount': Decimal('0'),
                        'currency': currency
                    }
                categories_by_currency[currency][cat_key]['amount'] += expense.amount
        
        # Combine categories from all currencies
        all_categories = []
        for currency, cats in categories_by_currency.items():
            for cat in cats.values():
                all_categories.append(cat)
        
        # Sort by amount (note: mixed currencies, but at least shows all)
        sorted_categories = sorted(
            all_categories,
            key=lambda x: x['amount'],
            reverse=True
        )
        
        return {
            'total': total,
            'count': len(expenses),
            'categories': sorted_categories,
            'currency': user_currency,
            'currency_totals': {k: float(v) for k, v in currency_totals.items()},
            'single_currency': single_currency
        }
        
    except Profile.DoesNotExist:
        return {'total': 0, 'count': 0, 'categories': [], 'currency': 'RUB', 'currency_totals': {}, 'single_currency': True}
    except Exception as e:
        logger.error(f"Error getting month summary: {e}")
        return {'total': 0, 'count': 0, 'categories': [], 'currency': 'RUB', 'currency_totals': {}, 'single_currency': True}