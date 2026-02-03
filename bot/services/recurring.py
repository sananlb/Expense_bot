"""
Сервис для работы с ежемесячными платежами
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from expenses.models import RecurringPayment, Profile, Expense, UserSettings
from asgiref.sync import sync_to_async, async_to_sync
from django.db import transaction
import logging
from bot.utils.category_helpers import get_category_display_name

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
            # Используем язык профиля для отображения категории
            lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
            description = get_category_display_name(income_category, lang_code)
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
            # Используем язык профиля для отображения категории
            lang_code = profile.language_code if hasattr(profile, 'language_code') else 'ru'
            description = get_category_display_name(expense_category, lang_code)
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
    
    # Получаем последний день текущего месяца
    import calendar
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    
    # Если сегодня последний день месяца, обрабатываем все операции 
    # запланированные на дни больше или равные текущему дню
    if current_day == last_day_of_month:
        # Обрабатываем операции на текущий день и все дни > last_day_of_month
        # Это покрывает случаи февраля (29-30 число → 28/29 февраля)
        payments = RecurringPayment.objects.filter(
            day_of_month__gte=current_day,
            is_active=True
        ).select_related('profile', 'expense_category', 'income_category')
    else:
        # Обычная обработка для дней, которые не являются последним днем месяца
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
            # Получаем настройки пользователя для конвертации валют
            user_settings = UserSettings.objects.filter(profile=payment.profile).first()
            auto_convert = user_settings.auto_convert_currency if user_settings else False

            # Конвертируем если нужно
            if auto_convert and payment.currency != payment.profile.currency:
                from .conversion_helper import maybe_convert_amount
                convert_result = async_to_sync(maybe_convert_amount)(
                    amount=payment.amount,
                    input_currency=payment.currency,
                    user_currency=payment.profile.currency,
                    auto_convert_enabled=True,
                    operation_date=today,
                    profile=payment.profile
                )
                final_amount, final_currency, orig_amount, orig_currency, rate = convert_result
            else:
                final_amount = payment.amount
                final_currency = payment.currency
                orig_amount = orig_currency = rate = None

            # Создаем операцию в зависимости от типа
            if payment.operation_type == RecurringPayment.OPERATION_TYPE_INCOME:
                # Создаем доход
                from expenses.models import Income
                operation = Income.objects.create(
                    profile=payment.profile,
                    category=payment.income_category,
                    amount=final_amount,
                    currency=final_currency,
                    original_amount=orig_amount,
                    original_currency=orig_currency,
                    exchange_rate_used=rate,
                    description=f"[Ежемесячный] {payment.description}",
                    income_date=today
                )
                operation_type = 'income'

                # Сбрасываем флаг напоминания о внесении операций при автоматическом доходе
                from expenses.tasks import clear_expense_reminder
                clear_expense_reminder(payment.profile.telegram_id)
            else:
                # Создаем расход
                operation = Expense.objects.create(
                    profile=payment.profile,
                    category=payment.expense_category,
                    amount=final_amount,
                    currency=final_currency,
                    original_amount=orig_amount,
                    original_currency=orig_currency,
                    exchange_rate_used=rate,
                    description=f"[Ежемесячный] {payment.description}",
                    expense_date=today,
                    expense_time=datetime.now().time()
                )
                operation_type = 'expense'

                # Сбрасываем флаг напоминания о внесении трат при автоматическом платеже
                from expenses.tasks import clear_expense_reminder
                clear_expense_reminder(payment.profile.telegram_id)

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
    from datetime import date
    import calendar
    
    today = date.today()
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    
    # Если запрашивают день больше чем есть в текущем месяце,
    # возвращаем платежи для последнего дня месяца и всех дней >= last_day_of_month
    if day > last_day_of_month:
        return list(RecurringPayment.objects.filter(
            day_of_month__gte=last_day_of_month,
            is_active=True
        ).select_related('profile', 'category'))
    
    return list(RecurringPayment.objects.filter(
        day_of_month=day,
        is_active=True
    ).select_related('profile', 'category'))