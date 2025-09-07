"""
Service for budget management
"""
from asgiref.sync import sync_to_async
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
import logging

from expenses.models import Budget, Profile, ExpenseCategory, Expense
from django.db.models import Sum
from bot.utils.category_helpers import get_category_display_name

logger = logging.getLogger(__name__)


@sync_to_async
def create_budget(
    telegram_id: int,
    category_id: int,
    amount: Decimal,
    period_type: str = 'monthly',
    start_date: date = None
) -> Optional[Budget]:
    """
    Создать бюджет для категории
    
    Args:
        telegram_id: ID пользователя в Telegram
        category_id: ID категории
        amount: Сумма бюджета
        period_type: Тип периода (monthly, weekly, daily)
        start_date: Дата начала (по умолчанию текущая дата)
        
    Returns:
        Budget instance или None при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        category = ExpenseCategory.objects.get(id=category_id, profile=profile)
        
        if start_date is None:
            start_date = date.today()
            
        # Деактивируем предыдущие бюджеты для этой категории
        Budget.objects.filter(
            profile=profile,
            category=category,
            is_active=True
        ).update(is_active=False)
        
        # Создаем новый бюджет
        budget = Budget.objects.create(
            profile=profile,
            category=category,
            amount=amount,
            period_type=period_type,
            start_date=start_date,
            is_active=True
        )
        
        logger.info(f"Created budget for category {category_id} user {telegram_id}")
        return budget
        
    except (Profile.DoesNotExist, ExpenseCategory.DoesNotExist):
        logger.error(f"Profile or category not found for budget creation")
        return None
    except Exception as e:
        logger.error(f"Error creating budget: {e}")
        return None


@sync_to_async
def get_user_budgets(user_id: int, active_only: bool = True) -> List[Budget]:
    """
    Получить бюджеты пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        active_only: Только активные бюджеты
        
    Returns:
        Список бюджетов
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        queryset = Budget.objects.filter(profile=profile)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
            
        return list(queryset.select_related('category').order_by('category__name'))
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error getting budgets: {e}")
        return []


@sync_to_async
def check_budget_status(user_id: int, category_id: int) -> Dict:
    """
    Проверить статус бюджета для категории
    
    Args:
        telegram_id: ID пользователя в Telegram
        category_id: ID категории
        
    Returns:
        Словарь с информацией о бюджете:
        {
            'has_budget': bool,
            'budget_amount': Decimal,
            'spent': Decimal,
            'remaining': Decimal,
            'percentage': float,
            'exceeded': bool
        }
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        # Получаем активный бюджет для категории
        budget = Budget.objects.filter(
            profile=profile,
            category_id=category_id,
            is_active=True
        ).first()
        
        if not budget:
            return {
                'has_budget': False,
                'budget_amount': Decimal('0'),
                'spent': Decimal('0'),
                'remaining': Decimal('0'),
                'percentage': 0.0,
                'exceeded': False
            }
            
        # Определяем период для подсчета расходов
        start_date = budget.start_date
        end_date = date.today()
        
        if budget.period_type == 'monthly':
            # Начало текущего месяца
            start_date = date.today().replace(day=1)
        elif budget.period_type == 'weekly':
            # Начало текущей недели
            today = date.today()
            start_date = today - timedelta(days=today.weekday())
        elif budget.period_type == 'daily':
            # Сегодня
            start_date = date.today()
            
        # Подсчитываем расходы за период
        spent = Expense.objects.filter(
            profile=profile,
            category_id=category_id,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        remaining = budget.amount - spent
        percentage = float(spent / budget.amount * 100) if budget.amount > 0 else 0.0
        exceeded = spent > budget.amount
        
        return {
            'has_budget': True,
            'budget_amount': budget.amount,
            'spent': spent,
            'remaining': remaining,
            'percentage': percentage,
            'exceeded': exceeded
        }
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return {
            'has_budget': False,
            'budget_amount': Decimal('0'),
            'spent': Decimal('0'),
            'remaining': Decimal('0'),
            'percentage': 0.0,
            'exceeded': False
        }
    except Exception as e:
        logger.error(f"Error checking budget status: {e}")
        return {
            'has_budget': False,
            'budget_amount': Decimal('0'),
            'spent': Decimal('0'),
            'remaining': Decimal('0'),
            'percentage': 0.0,
            'exceeded': False
        }


@sync_to_async
def delete_budget(user_id: int, budget_id: int) -> bool:
    """
    Удалить (деактивировать) бюджет
    
    Args:
        telegram_id: ID пользователя в Telegram
        budget_id: ID бюджета
        
    Returns:
        True если успешно, False при ошибке
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        budget = Budget.objects.get(id=budget_id, profile=profile)
        
        # Деактивируем бюджет
        budget.is_active = False
        budget.save()
        
        logger.info(f"Deactivated budget {budget_id} for user {user_id}")
        return True
        
    except (Profile.DoesNotExist, Budget.DoesNotExist):
        logger.error(f"Budget {budget_id} not found for user {user_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting budget: {e}")
        return False


@sync_to_async
def check_all_budgets(user_id: int) -> List[Dict]:
    """
    Проверить статус всех активных бюджетов пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        Список словарей с информацией о бюджетах
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        budgets = Budget.objects.filter(
            profile=profile,
            is_active=True
        ).select_related('category')
        
        results = []
        for budget in budgets:
            status = check_budget_status(user_id, budget.category_id)
            # Получаем язык пользователя
            lang = getattr(profile, 'language_code', 'ru') if profile else 'ru'
            # Используем мультиязычную систему для отображения категории
            status['category_name'] = get_category_display_name(budget.category, lang)
            status['category_icon'] = budget.category.icon
            status['budget_id'] = budget.id
            results.append(status)
            
        return results
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return []
    except Exception as e:
        logger.error(f"Error checking all budgets: {e}")
        return []