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

logger = logging.getLogger(__name__)


@sync_to_async
def create_expense(
    telegram_id: int,
    amount: Decimal,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    expense_date: Optional[date] = None,
    ai_categorized: bool = False,
    ai_confidence: Optional[float] = None,
    currency: str = 'RUB'
) -> Optional[Expense]:
    """
    Создать новый расход
    
    Args:
        telegram_id: ID пользователя в Telegram
        amount: Сумма расхода
        category_id: ID категории (опционально)
        description: Описание расхода
        expense_date: Дата расхода (по умолчанию сегодня)
        ai_categorized: Категория определена AI
        ai_confidence: Уверенность AI в категории
        
    Returns:
        Expense instance или None при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        
        if expense_date is None:
            expense_date = date.today()
            
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
        
        logger.info(f"Created expense {expense.id} for user {telegram_id}")
        return expense
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return None
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        return None


# Alias for backward compatibility
add_expense = create_expense


@sync_to_async
def get_user_expenses(
    telegram_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    limit: int = 50
) -> List[Expense]:
    """
    Получить расходы пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        start_date: Начальная дата
        end_date: Конечная дата
        category_id: Фильтр по категории
        limit: Максимальное количество записей
        
    Returns:
        Список расходов
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
            
        return list(queryset.select_related('category').order_by('-expense_date', '-created_at')[:limit])
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return []
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return []


@sync_to_async
def get_expenses_summary(
    telegram_id: int,
    start_date: date,
    end_date: date
) -> Dict:
    """
    Получить сводку расходов за период
    
    Args:
        telegram_id: ID пользователя в Telegram
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
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        expenses = Expense.objects.filter(
            profile=profile,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )
        
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
                'icon': cat['category__icon'] or '💰',
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
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return {
            'total': Decimal('0'),
            'count': 0,
            'by_category': [],
            'currency': 'RUB',
            'potential_cashback': Decimal('0')
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
    telegram_id: int,
    period: str = 'month'
) -> Dict:
    """
    Получить расходы за стандартный период
    
    Args:
        telegram_id: ID пользователя в Telegram
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
        
    return get_expenses_summary(telegram_id, start_date, end_date)


@sync_to_async
def update_expense(
    telegram_id: int,
    expense_id: int,
    **kwargs
) -> bool:
    """
    Обновить расход
    
    Args:
        telegram_id: ID пользователя в Telegram
        expense_id: ID расхода
        **kwargs: Поля для обновления
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        expense = Expense.objects.get(id=expense_id, profile=profile)
        
        # Обновляем только переданные поля
        for field, value in kwargs.items():
            if hasattr(expense, field):
                setattr(expense, field, value)
                
        expense.save()
        logger.info(f"Updated expense {expense_id} for user {telegram_id}")
        return True
        
    except (Profile.DoesNotExist, Expense.DoesNotExist):
        logger.error(f"Expense {expense_id} not found for user {telegram_id}")
        return False
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        return False


@sync_to_async
def delete_expense(telegram_id: int, expense_id: int) -> bool:
    """
    Удалить расход
    
    Args:
        telegram_id: ID пользователя в Telegram
        expense_id: ID расхода
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        expense = Expense.objects.get(id=expense_id, profile=profile)
        expense.delete()
        
        logger.info(f"Deleted expense {expense_id} for user {telegram_id}")
        return True
        
    except (Profile.DoesNotExist, Expense.DoesNotExist):
        logger.error(f"Expense {expense_id} not found for user {telegram_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


@sync_to_async
def get_last_expense(telegram_id: int) -> Optional[Expense]:
    """
    Получить последний расход пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Expense instance или None
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        return Expense.objects.filter(profile=profile).order_by('-created_at').first()
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {telegram_id}")
        return None
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
        
        # If all expenses are in user's currency, use simple total
        if len(currency_totals) == 1 and user_currency in currency_totals:
            total = float(currency_totals[user_currency])
            single_currency = True
        else:
            # Multiple currencies - show total in user's currency and list others
            total = float(currency_totals.get(user_currency, 0))
            single_currency = False
        
        # Group by category
        categories = {}
        for expense in expenses:
            if expense.category:
                cat_key = expense.category.id
                if cat_key not in categories:
                    categories[cat_key] = {
                        'name': expense.category.name,
                        'icon': expense.category.icon,
                        'amount': Decimal('0'),
                        'currency': user_currency
                    }
                # For now, sum in user's currency (will need conversion button later)
                if expense.currency == user_currency:
                    categories[cat_key]['amount'] += expense.amount
        
        # Sort by amount
        sorted_categories = sorted(
            categories.values(),
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
        
        # If all expenses are in user's currency, use simple total
        if len(currency_totals) == 1 and user_currency in currency_totals:
            total = float(currency_totals[user_currency])
            single_currency = True
        else:
            # Multiple currencies - show total in user's currency and list others
            total = float(currency_totals.get(user_currency, 0))
            single_currency = False
        
        # Group by category
        categories = {}
        for expense in expenses:
            if expense.category:
                cat_key = expense.category.id
                if cat_key not in categories:
                    categories[cat_key] = {
                        'name': expense.category.name,
                        'icon': expense.category.icon,
                        'amount': Decimal('0'),
                        'currency': user_currency
                    }
                # For now, sum in user's currency (will need conversion button later)
                if expense.currency == user_currency:
                    categories[cat_key]['amount'] += expense.amount
        
        # Sort by amount
        sorted_categories = sorted(
            categories.values(),
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