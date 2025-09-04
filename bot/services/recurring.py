"""
Сервис для работы с ежемесячными платежами
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from expenses.models import RecurringPayment, Profile, Expense
from asgiref.sync import sync_to_async
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


@sync_to_async
def get_user_recurring_payments(user_id: int, active_only: bool = False) -> List[RecurringPayment]:
    """Получить ежемесячные платежи пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        return []
    
    payments = RecurringPayment.objects.filter(profile=profile)
    
    if active_only:
        payments = payments.filter(is_active=True)
    
    return list(payments.select_related('expense_category', 'income_category').order_by('day_of_month'))


@sync_to_async
def create_recurring_payment(user_id: int, category_id: int, amount: float, 
                           description: Optional[str], day_of_month: int, 
                           is_income: bool = False) -> RecurringPayment:
    """Создать новую регулярную операцию (доход или расход)"""
    from expenses.models import ExpenseCategory, IncomeCategory
    profile = Profile.objects.get(telegram_id=user_id)
    
    # Проверяем лимит регулярных операций (максимум 50)
    recurring_count = RecurringPayment.objects.filter(profile=profile).count()
    if recurring_count >= 50:
        raise ValueError("Достигнут лимит регулярных операций (максимум 50)")
    
    # Определяем тип операции и категории
    if is_income:
        operation_type = RecurringPayment.OPERATION_TYPE_INCOME
        # Получаем категорию дохода
        income_category = IncomeCategory.objects.get(id=category_id, profile=profile)
        expense_category = None
        
        # Если описание не указано, используем название категории
        if not description:
            description = income_category.name
            # Капитализируем первую букву
            if description:
                description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    else:
        operation_type = RecurringPayment.OPERATION_TYPE_EXPENSE
        # Получаем категорию расхода
        expense_category = ExpenseCategory.objects.get(id=category_id, profile=profile)
        income_category = None
        
        # Если описание не указано, используем название категории
        if not description:
            description = expense_category.name
            # Капитализируем первую букву
            if description:
                description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Капитализируем первую букву описания (на случай если пришло без капитализации)
    if description:
        description = description[0].upper() + description[1:] if len(description) > 1 else description.upper()
    
    # Проверяем длину описания (максимум 200 символов по модели)
    if description and len(description) > 200:
        raise ValueError("Описание слишком длинное (максимум 200 символов)")
    
    payment = RecurringPayment.objects.create(
        profile=profile,
        operation_type=operation_type,
        expense_category=expense_category,
        income_category=income_category,
        amount=Decimal(str(amount)),
        description=description,
        day_of_month=day_of_month,
        currency=profile.currency
    )
    
    # Перезагружаем с select_related
    return RecurringPayment.objects.select_related('expense_category', 'income_category').get(id=payment.id)


@sync_to_async
def update_recurring_payment(user_id: int, payment_id: int, **kwargs) -> Optional[RecurringPayment]:
    """Обновить регулярный платеж"""
    try:
        payment = RecurringPayment.objects.get(
            id=payment_id,
            profile__telegram_id=user_id
        )
        
        for field, value in kwargs.items():
            if hasattr(payment, field):
                setattr(payment, field, value)
        
        payment.save()
        return payment
    except RecurringPayment.DoesNotExist:
        return None


@sync_to_async
def delete_recurring_payment(user_id: int, payment_id: int) -> bool:
    """Удалить регулярный платеж"""
    try:
        payment = RecurringPayment.objects.get(
            id=payment_id,
            profile__telegram_id=user_id
        )
        payment.delete()
        return True
    except RecurringPayment.DoesNotExist:
        return False


@sync_to_async
def get_recurring_payment_by_id(user_id: int, payment_id: int) -> Optional[RecurringPayment]:
    """Получить регулярный платеж по ID"""
    try:
        return RecurringPayment.objects.select_related('expense_category', 'income_category').get(
            id=payment_id,
            profile__telegram_id=user_id
        )
    except RecurringPayment.DoesNotExist:
        return None


@sync_to_async
@transaction.atomic
def process_recurring_payments_for_today() -> tuple[int, list]:
    """
    Обработать регулярные платежи на сегодня
    Возвращает количество обработанных платежей и список обработанных платежей
    """
    today = date.today()
    current_day = today.day
    
    # Если сегодня 31 число, обрабатываем платежи с day_of_month = 30
    if current_day == 31:
        current_day = 30
    
    # Получаем активные операции на сегодня
    payments = RecurringPayment.objects.filter(
        day_of_month=current_day,
        is_active=True
    ).select_related('profile', 'expense_category', 'income_category')
    
    processed_count = 0
    processed_payments = []
    
    for payment in payments:
        # Проверяем, не был ли уже обработан платеж сегодня
        if payment.last_processed == today:
            logger.info(f"Payment {payment.id} already processed today")
            continue
        
        try:
            # Создаем операцию в зависимости от типа
            if payment.operation_type == RecurringPayment.OPERATION_TYPE_INCOME:
                # Создаем доход
                from expenses.models import Income
                operation = Income.objects.create(
                    profile=payment.profile,
                    category=payment.income_category,
                    amount=payment.amount,
                    currency=payment.currency,
                    description=f"[Ежемесячный] {payment.description}",
                    income_date=today,
                    income_type='other'
                )
                operation_type = 'income'
            else:
                # Создаем расход
                operation = Expense.objects.create(
                    profile=payment.profile,
                    category=payment.expense_category,
                    amount=payment.amount,
                    currency=payment.currency,
                    description=f"[Ежемесячный] {payment.description}",
                    expense_date=today,
                    expense_time=datetime.now().time()
                )
                operation_type = 'expense'
            
            # Обновляем дату последней обработки
            payment.last_processed = today
            payment.save()
            
            processed_count += 1
            processed_payments.append({
                'user_id': payment.profile.telegram_id,
                'operation': operation,
                'operation_type': operation_type,
                'payment': payment
            })
            logger.info(f"Processed recurring {operation_type} {payment.id}: {payment.description}")
            
        except Exception as e:
            logger.error(f"Error processing recurring payment {payment.id}: {e}")
    
    return processed_count, processed_payments


@sync_to_async
def get_payments_for_day(day: int) -> List[RecurringPayment]:
    """Получить все активные платежи для определенного дня месяца"""
    # Если запрашивают 31 число, возвращаем платежи на 30 число
    if day == 31:
        day = 30
    
    return list(RecurringPayment.objects.filter(
        day_of_month=day,
        is_active=True
    ).select_related('profile', 'category'))