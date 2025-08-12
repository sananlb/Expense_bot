"""
Сервис для работы с кешбэками
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from expenses.models import Cashback, Profile, Expense
from asgiref.sync import sync_to_async
from django.db.models import Sum, Q


@sync_to_async
def get_user_cashbacks(user_id: int, month: int = None) -> List[Cashback]:
    """Получить кешбэки пользователя за месяц"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        return []
    
    if month:
        cashbacks = Cashback.objects.filter(
            profile=profile,
            month=month
        ).select_related('category').order_by('bank_name', 'cashback_percent', 'id')
    else:
        cashbacks = Cashback.objects.filter(
            profile=profile
        ).select_related('category').order_by('bank_name', 'cashback_percent', 'id')
    
    return list(cashbacks)


@sync_to_async
def add_cashback(user_id: int, category_id: Optional[int], bank_name: str, 
                 cashback_percent: float, month: int, 
                 limit_amount: Optional[float] = None,
                 description: str = '') -> Cashback:
    """Добавить новый кешбэк"""
    profile = Profile.objects.get(telegram_id=user_id)
    
    # Проверяем, нет ли уже такого кешбэка
    existing = Cashback.objects.filter(
        profile=profile,
        category_id=category_id,
        bank_name=bank_name,
        month=month
    ).first()
    
    if existing:
        # Обновляем существующий
        existing.cashback_percent = Decimal(str(cashback_percent))
        existing.limit_amount = Decimal(str(limit_amount)) if limit_amount else None
        existing.description = description
        existing.save()
        # Перезагружаем с select_related
        return Cashback.objects.select_related('category').get(id=existing.id)
    
    # Создаем новый
    cashback = Cashback.objects.create(
        profile=profile,
        category_id=category_id,
        bank_name=bank_name,
        cashback_percent=Decimal(str(cashback_percent)),
        month=month,
        limit_amount=Decimal(str(limit_amount)) if limit_amount else None,
        description=description
    )
    
    # Перезагружаем с select_related
    return Cashback.objects.select_related('category').get(id=cashback.id)


@sync_to_async
def update_cashback(user_id: int, cashback_id: int, **kwargs) -> Optional[Cashback]:
    """Обновить кешбэк"""
    try:
        cashback = Cashback.objects.get(
            id=cashback_id,
            profile__telegram_id=user_id
        )
        
        for field, value in kwargs.items():
            if hasattr(cashback, field):
                setattr(cashback, field, value)
        
        cashback.save()
        return cashback
    except Cashback.DoesNotExist:
        return None


@sync_to_async
def delete_cashback(user_id: int, cashback_id: int) -> bool:
    """Удалить кешбэк"""
    try:
        cashback = Cashback.objects.get(
            id=cashback_id,
            profile__telegram_id=user_id
        )
        cashback.delete()
        return True
    except Cashback.DoesNotExist:
        return False


@sync_to_async
def get_cashback_by_id(user_id: int, cashback_id: int) -> Optional[Cashback]:
    """Получить кешбэк по ID"""
    try:
        return Cashback.objects.select_related('category').get(
            id=cashback_id,
            profile__telegram_id=user_id
        )
    except Cashback.DoesNotExist:
        return None


@sync_to_async
def calculate_potential_cashback(user_id: int, start_date: date, end_date: date) -> Decimal:
    """Рассчитать потенциальный кешбэк за период"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        return Decimal('0')
    
    # Получаем все расходы за период (исключая те, где кешбек отключен)
    expenses = Expense.objects.filter(
        profile=profile,
        expense_date__gte=start_date,
        expense_date__lte=end_date,
        cashback_excluded=False  # Учитываем только траты с кешбеком
    ).select_related('category')
    
    total_cashback = Decimal('0')
    
    # Группируем расходы по категориям и месяцам
    expenses_by_category_month = {}
    for expense in expenses:
        if expense.category:
            month = expense.expense_date.month
            key = (expense.category_id, month)
            if key not in expenses_by_category_month:
                expenses_by_category_month[key] = Decimal('0')
            expenses_by_category_month[key] += expense.amount
    
    # Получаем все кешбэки для категорий и месяцев
    for (category_id, month), amount in expenses_by_category_month.items():
        cashbacks = Cashback.objects.filter(
            profile=profile,
            category_id=category_id,
            month=month
        )
        
        for cashback in cashbacks:
            cashback_amount = amount * (cashback.cashback_percent / 100)
            
            # Учитываем лимит
            if cashback.limit_amount:
                cashback_amount = min(cashback_amount, cashback.limit_amount)
            
            total_cashback += cashback_amount
    
    return total_cashback


@sync_to_async
def calculate_expense_cashback(user_id: int, category_id: int, amount: Decimal, month: int) -> Decimal:
    """Рассчитать кешбэк для конкретной траты"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        return Decimal('0')
    
    # Получаем кешбэки для категории и месяца
    cashbacks = Cashback.objects.filter(
        profile=profile,
        category_id=category_id,
        month=month
    )
    
    total_cashback = Decimal('0')
    
    for cashback in cashbacks:
        # Преобразуем amount в Decimal для корректного умножения
        cashback_amount = Decimal(str(amount)) * (cashback.cashback_percent / 100)
        
        # Учитываем лимит
        if cashback.limit_amount:
            cashback_amount = min(cashback_amount, cashback.limit_amount)
        
        total_cashback += cashback_amount
    
    return total_cashback


def format_cashback_note(cashbacks: List[Cashback], month: int) -> str:
    """Форматировать красивую заметку о кешбэках с группировкой по банкам"""
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    text = f"💳 <b>Кешбэки на {month_names[month]}</b>\n\n"
    
    # Группируем кешбэки по банкам
    banks_dict = {}
    for cb in cashbacks:
        if cb.bank_name not in banks_dict:
            banks_dict[cb.bank_name] = []
        banks_dict[cb.bank_name].append(cb)
    
    # Выводим по банкам
    for bank_name, bank_cashbacks in banks_dict.items():
        text += f"<b>{bank_name}</b>\n"
        
        for cb in bank_cashbacks:
            # Форматируем процент без лишних нулей
            percent_str = f"{cb.cashback_percent:.1f}".rstrip('0').rstrip('.')
            
            # Формат: Категория (описание) - процент%
            if cb.category:
                text += f"• {cb.category.name}"
                if cb.description:
                    text += f" ({cb.description})"
            else:
                text += f"• 🌐 Все категории"
                if cb.description:
                    text += f" ({cb.description})"
            
            text += f" - {percent_str}%"
            
            if cb.limit_amount:
                text += f" (лимит {cb.limit_amount:,.0f} ₽)"
            
            text += "\n"
        
        text += "\n"  # Пустая строка между банками
    
    return text.rstrip()  # Убираем лишний перенос в конце


# Старые функции для совместимости
@sync_to_async
def get_cashbacks_for_month(user_id: int, month: int) -> List[Dict]:
    """Получить кешбэки пользователя на месяц (устаревшая)"""
    cashbacks = get_user_cashbacks(user_id, month)
    
    result = []
    for cb in cashbacks:
        result.append({
            'id': cb.id,
            'category': cb.category.name if cb.category else 'Все категории',
            'icon': cb.category.icon if cb.category else '🌐',
            'bank': cb.bank_name,
            'percent': cb.cashback_percent,
            'month': cb.month
        })
    
    return result