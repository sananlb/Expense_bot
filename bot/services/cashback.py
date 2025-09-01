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
        
        # Проверяем, включен ли кешбэк
        if hasattr(profile, 'settings') and hasattr(profile.settings, 'cashback_enabled'):
            if not profile.settings.cashback_enabled:
                return Decimal('0')
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
        
        # Проверяем, включен ли кешбэк
        if hasattr(profile, 'settings') and hasattr(profile.settings, 'cashback_enabled'):
            if not profile.settings.cashback_enabled:
                return Decimal('0')
    except Profile.DoesNotExist:
        return Decimal('0')
    
    # Сначала проверяем кешбэк для конкретной категории
    category_cashbacks = Cashback.objects.filter(
        profile=profile,
        category_id=category_id,
        month=month
    )
    
    # Если есть кешбэк для конкретной категории - используем максимальный из них
    if category_cashbacks.exists():
        max_cashback_amount = Decimal('0')
        for cashback in category_cashbacks:
            # Преобразуем amount в Decimal для корректного умножения
            cashback_amount = Decimal(str(amount)) * (cashback.cashback_percent / 100)
            
            # Учитываем лимит
            if cashback.limit_amount:
                cashback_amount = min(cashback_amount, cashback.limit_amount)
            
            # Берем максимальный кешбэк
            max_cashback_amount = max(max_cashback_amount, cashback_amount)
        return max_cashback_amount
    
    # Если нет кешбэка для конкретной категории, проверяем кешбэк на все категории
    all_categories_cashbacks = Cashback.objects.filter(
        profile=profile,
        category_id=None,  # None означает все категории
        month=month
    )
    
    # Выбираем максимальный кешбэк из доступных
    max_cashback_amount = Decimal('0')
    for cashback in all_categories_cashbacks:
        # Преобразуем amount в Decimal для корректного умножения
        cashback_amount = Decimal(str(amount)) * (cashback.cashback_percent / 100)
        
        # Учитываем лимит
        if cashback.limit_amount:
            cashback_amount = min(cashback_amount, cashback.limit_amount)
        
        # Берем максимальный кешбэк
        max_cashback_amount = max(max_cashback_amount, cashback_amount)
    
    return max_cashback_amount


def format_cashback_note(cashbacks: List[Cashback], month: int, lang: str = 'ru') -> str:
    """Форматировать красивую заметку о кешбэках с группировкой по банкам"""
    from bot.utils import get_text, translate_category_name
    
    # Названия месяцев
    month_names = {
        1: get_text('january', lang).capitalize(),
        2: get_text('february', lang).capitalize(),
        3: get_text('march', lang).capitalize(),
        4: get_text('april', lang).capitalize(),
        5: get_text('may', lang).capitalize(),
        6: get_text('june', lang).capitalize(),
        7: get_text('july', lang).capitalize(),
        8: get_text('august', lang).capitalize(),
        9: get_text('september', lang).capitalize(),
        10: get_text('october', lang).capitalize(),
        11: get_text('november', lang).capitalize(),
        12: get_text('december', lang).capitalize()
    }
    
    text = f"💳 <b>{get_text('cashbacks_for', lang)} {month_names[month]}</b>\n\n"
    
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
                # Переводим название категории на язык пользователя
                category_name = translate_category_name(cb.category.name, lang)
                text += f"• {category_name}"
                if cb.description:
                    text += f" ({cb.description})"
            else:
                text += f"• {get_text('all_categories', lang)}"
                if cb.description:
                    text += f" ({cb.description})"
            
            text += f" - {percent_str}%"
            
            if cb.limit_amount:
                limit_text = get_text('limit', lang)
                text += f" ({limit_text} {cb.limit_amount:,.0f} ₽)"
            
            text += "\n"
        
        text += "\n"  # Пустая строка между банками
    
    return text.rstrip()  # Убираем лишний перенос в конце


# Старые функции для совместимости
@sync_to_async
def get_cashbacks_for_month(user_id: int, month: int, lang: str = 'ru') -> List[Dict]:
    """Получить кешбэки пользователя на месяц (устаревшая)"""
    from bot.utils import get_text
    cashbacks = get_user_cashbacks(user_id, month)
    
    result = []
    for cb in cashbacks:
        result.append({
            'id': cb.id,
            'category': cb.category.name if cb.category else get_text('all_categories', lang),
            'icon': cb.category.icon if cb.category else '🌐',
            'bank': cb.bank_name,
            'percent': cb.cashback_percent,
            'month': cb.month
        })
    
    return result