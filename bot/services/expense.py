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
from django.utils import timezone
from bot.utils.db_utils import get_or_create_user_profile_sync
from bot.utils.category_helpers import get_category_display_name

# Предзагрузка Celery задач для устранения "холодного старта"
# Импортируем заранее, чтобы при первом вызове не было задержки 6+ секунд
try:
    from expense_bot.celery_tasks import learn_keywords_on_create, update_keywords_weights
except ImportError:
    # На случай если Celery не установлен (например, в тестах)
    learn_keywords_on_create = None
    update_keywords_weights = None

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
        
        # Проверка 1: Не вносить траты в будущем
        if expense_date > date.today():
            logger.warning(f"User {user_id} tried to add expense in future: {expense_date}")
            raise ValueError("Нельзя вносить траты в будущем")
        
        # Проверка 2: Не вносить траты старше 1 года
        one_year_ago = date.today() - timedelta(days=365)
        if expense_date < one_year_ago:
            logger.warning(f"User {user_id} tried to add expense older than 1 year: {expense_date}")
            raise ValueError("Нельзя вносить траты старше 1 года")
        
        # Проверка 3: Не вносить траты до даты регистрации пользователя
        # Используем дату создания профиля как дату регистрации
        profile_created_date = profile.created_at.date() if profile.created_at else date.today()
        if expense_date < profile_created_date:
            logger.warning(f"User {user_id} tried to add expense before registration: {expense_date}, registered: {profile_created_date}")
            raise ValueError(f"Нельзя вносить траты до даты регистрации ({profile_created_date.strftime('%d.%m.%Y')})")
        
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

        # Проверка максимальной суммы (лимит БД: NUMERIC(12,2))
        MAX_AMOUNT = Decimal('9999999999.99')
        if amount > MAX_AMOUNT:
            logger.warning(f"User {user_id} tried to add expense with amount too large: {amount}")
            raise ValueError("⚠️ Сумма слишком велика")

        # Проверка 4: Валидация category_id (защита от использования чужих категорий)
        if category_id is not None:
            try:
                category = ExpenseCategory.objects.select_related('profile').get(id=category_id)

                # Проверяем что категория принадлежит пользователю или члену его семьи
                is_valid_category = False

                # Случай 1: Категория принадлежит самому пользователю
                if category.profile_id == profile.id:
                    is_valid_category = True
                # Случай 2: Пользователь в семейном бюджете, категория от члена семьи
                elif profile.household_id is not None:
                    # Проверяем что категория от члена той же семьи
                    if category.profile.household_id == profile.household_id:
                        is_valid_category = True
                        logger.debug(f"Category {category_id} belongs to household member, allowed")

                if not is_valid_category:
                    logger.warning(
                        f"User {user_id} (profile {profile.id}) tried to use category {category_id} "
                        f"belonging to another user (profile {category.profile_id})"
                    )
                    raise ValueError("Нельзя использовать категорию другого пользователя")

            except ExpenseCategory.DoesNotExist:
                logger.warning(f"User {user_id} tried to use non-existent category {category_id}")
                raise ValueError(f"Категория с ID {category_id} не существует")

        # Если дата указана вручную (не сегодня), устанавливаем время 12:00
        from datetime import time as datetime_time
        if expense_date and expense_date != date.today():
            expense_time = datetime_time(12, 0)  # 12:00 для трат задним числом
        else:
            expense_time = datetime.now().time()  # Текущее время для сегодняшних трат
            
        expense = Expense.objects.create(
            profile=profile,
            category_id=category_id,
            amount=amount,
            currency=currency,
            description=description,
            expense_date=expense_date,
            expense_time=expense_time,
            ai_categorized=ai_categorized,
            ai_confidence=ai_confidence
        )

        # Обновляем объект с загруженным profile для корректной работы
        expense.profile = profile

        # Если категория определена AI, обучаем систему (сохраняем слова в БД)
        if ai_categorized and category_id and description and learn_keywords_on_create:
            try:
                # Запускаем обучение в фоне через Celery (не блокирует пользователя!)
                learn_keywords_on_create.apply_async(
                    args=(expense.id, category_id),
                    countdown=0
                )
                logger.info(f"Triggered async keywords learning for new expense {expense.id}")
            except Exception as e:
                logger.warning(f"Failed to trigger keywords learning task: {e}")

        # Сбрасываем флаг напоминания о внесении трат
        from expenses.tasks import clear_expense_reminder
        clear_expense_reminder(user_id)

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
    limit: int = 200
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
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return []


# =============================================================================
# Helper functions for get_expenses_summary (refactored for lower complexity)
# =============================================================================

def _get_expenses_queryset(
    profile: Profile,
    start_date: date,
    end_date: date,
    household_mode: bool = False
):
    """
    Get expenses queryset with optional household mode.

    Returns:
        QuerySet of expenses and list of household profiles (or None)
    """
    if household_mode and profile.household:
        household_profiles = Profile.objects.filter(household=profile.household)
        expenses = Expense.objects.filter(
            profile__in=household_profiles,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).select_related('category')
        return expenses, household_profiles
    else:
        expenses = Expense.objects.filter(
            profile=profile,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).select_related('category')
        return expenses, None


def _group_expenses_by_category(
    expenses,
    user_lang: str
) -> tuple:
    """
    Group expenses by category and currency.

    Returns:
        Tuple of (expenses_by_currency, categories, total_count)
    """
    from bot.utils.language import get_text

    expenses_by_currency = {}
    categories = {}
    total_count = 0

    for expense in expenses:
        currency = expense.currency or 'RUB'

        # Currency statistics
        if currency not in expenses_by_currency:
            expenses_by_currency[currency] = {'total': Decimal('0'), 'count': 0}

        expenses_by_currency[currency]['total'] += expense.amount
        expenses_by_currency[currency]['count'] += 1
        total_count += 1

        # Category grouping
        if expense.category:
            cat_id = expense.category.id
            cat_icon = expense.category.icon or ''
            cat_name = get_category_display_name(expense.category, user_lang)
        else:
            cat_id = 0
            cat_name = get_text('no_category', user_lang)
            cat_icon = ''

        if cat_id not in categories:
            categories[cat_id] = {
                'id': cat_id,
                'name': cat_name,
                'icon': cat_icon,
                'amounts': {},
                'count': 0
            }

        if currency not in categories[cat_id]['amounts']:
            categories[cat_id]['amounts'][currency] = Decimal('0')

        categories[cat_id]['amounts'][currency] += expense.amount
        categories[cat_id]['count'] += 1

    return expenses_by_currency, categories, total_count


def _get_income_summary(
    profile: Profile,
    start_date: date,
    end_date: date,
    household_mode: bool = False
) -> Dict:
    """
    Get income summary for the period.

    Returns:
        Dict with income_total, income_count, by_income_category
    """
    from expenses.models import Income, IncomeCategory
    from bot.utils.language import get_text

    user_lang = profile.language_code or 'ru'

    if household_mode and profile.household:
        household_profiles = Profile.objects.filter(household=profile.household)
        incomes = Income.objects.filter(
            profile__in=household_profiles,
            income_date__gte=start_date,
            income_date__lte=end_date
        )
    else:
        incomes = Income.objects.filter(
            profile=profile,
            income_date__gte=start_date,
            income_date__lte=end_date
        )

    income_total = incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_count = incomes.count()

    # Group by income category
    by_income_category = incomes.values('category__id').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')

    income_categories_list = []
    for cat in by_income_category:
        category_id = cat['category__id']
        if category_id:
            try:
                category = IncomeCategory.objects.get(id=category_id)
                cat_name = category.get_display_name(user_lang)
            except IncomeCategory.DoesNotExist:
                cat_name = f"💰 {get_text('other_income', user_lang)}"
        else:
            cat_name = f"💰 {get_text('other_income', user_lang)}"

        icon = cat_name.split()[0] if cat_name else '💰'

        income_categories_list.append({
            'id': category_id or 0,
            'name': cat_name,
            'icon': icon,
            'total': cat['total'],
            'count': cat['count']
        })

    return {
        'income_total': income_total,
        'income_count': income_count,
        'by_income_category': income_categories_list
    }


def _calculate_personal_cashback(
    profile: Profile,
    categories_list: List[Dict],
    main_currency: str,
    current_month: int
) -> Decimal:
    """
    Calculate potential cashback for personal (non-household) mode.
    """
    potential_cashback = Decimal('0')

    cashbacks = Cashback.objects.filter(
        profile=profile,
        month=current_month
    ).select_related('category')

    cashback_map = {}
    for cb in cashbacks:
        if cb.category_id not in cashback_map:
            cashback_map[cb.category_id] = []
        cashback_map[cb.category_id].append(cb)

    for cat in categories_list:
        if cat['id'] in cashback_map:
            cat_total = cat['amounts'].get(main_currency, Decimal('0'))
            max_cashback = max(cashback_map[cat['id']], key=lambda x: x.cashback_percent)

            if max_cashback.limit_amount:
                cashback_amount = min(
                    cat_total * max_cashback.cashback_percent / 100,
                    max_cashback.limit_amount
                )
            else:
                cashback_amount = cat_total * max_cashback.cashback_percent / 100

            potential_cashback += cashback_amount

    return potential_cashback


def _calculate_household_cashback(
    expenses,
    main_currency: str,
    current_month: int
) -> Decimal:
    """
    Calculate potential cashback for household mode.
    """
    potential_cashback = Decimal('0')

    # Collect totals by category for each household member
    member_totals: Dict[int, Dict[int, Decimal]] = {}
    for exp in expenses:
        if (exp.currency or 'RUB') != main_currency:
            continue
        if not exp.category_id:
            continue

        pid = exp.profile_id
        cid = exp.category_id

        if pid not in member_totals:
            member_totals[pid] = {}
        if cid not in member_totals[pid]:
            member_totals[pid][cid] = Decimal('0')

        member_totals[pid][cid] += exp.amount

    # Apply each member's cashback rules
    for pid, cat_map in member_totals.items():
        cashbacks = Cashback.objects.filter(
            profile_id=pid,
            month=current_month
        ).select_related('category')

        per_cat: Dict[int, list] = {}
        for cb in cashbacks:
            key = cb.category_id
            if key not in per_cat:
                per_cat[key] = []
            per_cat[key].append(cb)

        for cid, total_sum in cat_map.items():
            if cid not in per_cat:
                continue

            max_cb = max(per_cat[cid], key=lambda x: x.cashback_percent)
            if max_cb.limit_amount:
                cb_amount = min(total_sum * max_cb.cashback_percent / 100, max_cb.limit_amount)
            else:
                cb_amount = total_sum * max_cb.cashback_percent / 100

            potential_cashback += cb_amount

    return potential_cashback


def _build_empty_summary() -> Dict:
    """Return empty summary dict for error cases."""
    return {
        'total': Decimal('0'),
        'count': 0,
        'by_category': [],
        'currency': 'RUB',
        'potential_cashback': Decimal('0'),
        'currency_totals': {},
        'income_total': Decimal('0'),
        'income_count': 0,
        'by_income_category': [],
        'balance': Decimal('0')
    }


@sync_to_async
def get_expenses_summary(
    user_id: int,
    start_date: date,
    end_date: date,
    household_mode: bool = False
) -> Dict:
    """
    Получить сводку трат за период
    
    Args:
        user_id: ID пользователя в Telegram
        start_date: Начальная дата
        end_date: Конечная дата
        household_mode: Включить режим семейного бюджета
        
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
    logger.info(f"get_expenses_summary called: user_id={user_id}, start={start_date}, end={end_date}, household={household_mode}")
    profile = get_or_create_user_profile_sync(user_id)
    logger.info(f"Profile found/created: {profile.id} for telegram_id={profile.telegram_id}")

    try:
        # Get user language for multilingual categories
        from bot.utils.language import get_user_language
        from asgiref.sync import async_to_sync
        user_lang = async_to_sync(get_user_language)(user_id)

        # Get expenses queryset
        expenses, household_profiles = _get_expenses_queryset(
            profile, start_date, end_date, household_mode
        )
        if household_profiles:
            logger.info(f"Household mode: found {household_profiles.count()} members, {expenses.count()} expenses")
        logger.info(f"Query: profile={profile.id}, date>={start_date}, date<={end_date}, found={expenses.count()} expenses")

        # Group expenses by category and currency
        expenses_by_currency, categories, total_count = _group_expenses_by_category(
            expenses, user_lang
        )

        # Convert categories to sorted list
        if categories:
            categories_list = sorted(
                categories.values(),
                key=lambda x: sum(x['amounts'].values()),
                reverse=True
            )
            logger.info(f"Categories with all currencies: {[(c['name'], c['amounts']) for c in categories_list]}")
        else:
            categories_list = []

        # Calculate currency totals
        currency_totals = {cur: data['total'] for cur, data in expenses_by_currency.items()}

        # Determine main currency and totals (for backward compatibility)
        if expenses_by_currency:
            main_currency = max(expenses_by_currency.items(), key=lambda x: x[1]['count'])[0]
            total = expenses_by_currency[main_currency]['total']
            count = total_count
        else:
            main_currency = 'RUB'
            total = Decimal('0')
            count = 0

        # Get income summary
        income_data = _get_income_summary(profile, start_date, end_date, household_mode)

        # Calculate balance
        balance = income_data['income_total'] - total

        # Calculate potential cashback
        current_month = start_date.month
        if household_mode and profile.household and expenses_by_currency:
            potential_cashback = _calculate_household_cashback(
                expenses, main_currency, current_month
            )
        else:
            potential_cashback = _calculate_personal_cashback(
                profile, categories_list, main_currency, current_month
            )

        return {
            'total': total,
            'count': count,
            'by_category': categories_list,
            'currency': main_currency,
            'potential_cashback': potential_cashback,
            'currency_totals': {k: float(v) for k, v in currency_totals.items()},
            'income_total': income_data['income_total'],
            'income_count': income_data['income_count'],
            'by_income_category': income_data['by_income_category'],
            'balance': balance
        }

    except Exception as e:
        logger.error(f"Error getting expenses summary: {e}")
        return _build_empty_summary()


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
        
        # Если категория изменилась, пересчитываем кешбек
        if category_changed:
            # Проверяем есть ли активная подписка
            from expenses.models import Subscription
            has_subscription = Subscription.objects.filter(
                profile=profile,
                is_active=True,
                end_date__gt=timezone.now()
            ).exists()
            
            if has_subscription:
                from .cashback import calculate_expense_cashback_sync
                # Пересчитываем кешбек для новой категории
                new_cashback = calculate_expense_cashback_sync(
                    user_id=user_id,
                    category_id=new_category_id,
                    amount=expense.amount,
                    month=expense.created_at.month
                )
                
                # Обновляем поле cashback_amount в трате
                expense.cashback_amount = new_cashback
                expense.save()
                logger.info(f"Updated cashback for expense {expense_id}: {new_cashback}")
        
        # Если категория изменилась, запускаем фоновую задачу для обновления весов
        if category_changed and old_category_id and update_keywords_weights:
            try:
                # Используем apply_async с countdown=0 для немедленного выполнения
                # Это быстрее чем .delay() и не блокирует вызывающий поток
                update_keywords_weights.apply_async(
                    args=(expense_id, old_category_id, new_category_id),
                    countdown=0
                )
                logger.info(f"Triggered keywords weights update for expense {expense_id}")
            except Exception as e:
                logger.warning(f"Failed to trigger keywords update task: {e}")
        
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
    limit: int = 200
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


def normalize_russian_word(word: str) -> str:
    """
    Простая нормализация русского слова - убирает типичные окончания.
    Это не полноценный стеммер, но достаточно для поиска.

    Примеры:
        капельницы -> капельниц
        капельница -> капельниц
        продукты -> продукт
        кофе -> кофе (не меняется)
    """
    word = word.lower().strip()
    if len(word) < 4:
        return word

    # Русские окончания (от длинных к коротким)
    endings = [
        # Существительные множественное число
        'ами', 'ями', 'ами', 'ях', 'ов', 'ев', 'ей', 'ий',
        # Существительные единственное число
        'ом', 'ем', 'ой', 'ей', 'ью', 'ия', 'ие', 'ье',
        # Прилагательные
        'ого', 'его', 'ому', 'ему', 'ым', 'им', 'ой', 'ей',
        'ая', 'яя', 'ое', 'ее', 'ые', 'ие',
        # Глаголы
        'ть', 'ла', 'ло', 'ли', 'ет', 'ит', 'ут', 'ют',
        # Короткие окончания (в конце, чтобы не срезать раньше времени)
        'ы', 'и', 'а', 'я', 'у', 'ю', 'е', 'о',
    ]

    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)]

    return word


def _calculate_similarity(word1: str, word2: str) -> float:
    """
    Вычисляет процент схожести двух слов используя расстояние Левенштейна.

    Args:
        word1: Первое слово
        word2: Второе слово

    Returns:
        Процент схожести (0.0 - 1.0)

    Examples:
        >>> _calculate_similarity("тралик", "тралики")
        0.857  # 85.7% схожести
        >>> _calculate_similarity("магнит", "магнитрон")
        0.778  # 77.8% схожести
    """
    if word1 == word2:
        return 1.0

    # Расстояние Левенштейна
    def levenshtein_distance(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # j+1 вместо j так как previous_row и current_row на 1 длиннее s2
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    distance = levenshtein_distance(word1.lower(), word2.lower())
    max_len = max(len(word1), len(word2))

    # Схожесть = 1 - (расстояние / максимальная длина)
    similarity = 1.0 - (distance / max_len)
    return similarity


@sync_to_async
def find_similar_expenses(
    telegram_id: int,
    description: str,
    days_back: int = 365
) -> List[Dict[str, Any]]:
    """
    Найти похожие траты за последний период с учетом схожести слов (85% порог).

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

        # Нормализуем описание для поиска - извлекаем только буквы, без пунктуации
        search_desc = description.lower().strip()
        import re
        search_words = re.findall(r'[а-яёa-z]+', search_desc)

        # Если нет слов для поиска - возвращаем пустой результат
        if not search_words:
            return []

        # Ищем траты с похожим описанием
        queryset = Expense.objects.filter(
            profile=profile,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )

        # Фильтруем по описанию с учетом схожести (85% порог)
        SIMILARITY_THRESHOLD = 0.85
        similar_expenses = []

        for expense in queryset.select_related('category'):
            if expense.description:
                exp_desc = expense.description.lower().strip()
                # Извлекаем слова без пунктуации
                exp_words = re.findall(r'[а-яёa-z]+', exp_desc)

                # Проверяем что все слова из поиска имеют похожие слова в описании траты
                match_found = True
                for search_word in search_words:
                    # Ищем хотя бы одно слово в описании с схожестью >= 85%
                    word_matched = False
                    for exp_word in exp_words:
                        similarity = _calculate_similarity(search_word, exp_word)
                        if similarity >= SIMILARITY_THRESHOLD:
                            word_matched = True
                            logger.info(
                                f"[SIMILAR EXPENSE] Match: '{search_word}' ~ '{exp_word}' "
                                f"(similarity: {similarity:.2%})"
                            )
                            break

                    if not word_matched:
                        match_found = False
                        break

                if match_found:
                    similar_expenses.append(expense)
        
        # Получаем язык пользователя для правильного отображения
        from bot.utils.language import get_user_language
        from asgiref.sync import async_to_sync
        user_lang = async_to_sync(get_user_language)(telegram_id)
        
        # Группируем по уникальным суммам и категориям
        unique_amounts = {}
        for expense in similar_expenses:
            category_display = expense.category.get_display_name(user_lang) if expense.category else ('Прочие расходы' if user_lang == 'ru' else 'Other Expenses')
            key = (float(expense.amount), expense.currency, category_display)
            if key not in unique_amounts:
                unique_amounts[key] = {
                    'amount': float(expense.amount),
                    'currency': expense.currency,
                    'category': category_display,
                    'count': 1,
                    'last_date': expense.expense_date
                }
            else:
                unique_amounts[key]['count'] += 1
                if expense.expense_date > unique_amounts[key]['last_date']:
                    unique_amounts[key]['last_date'] = expense.expense_date
        
        # Сортируем по дате последнего использования (последняя трата первой)
        result = sorted(
            unique_amounts.values(),
            key=lambda x: x['last_date'],
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
        
        @sync_to_async
        def get_today_expenses():
            return list(
                Expense.objects.filter(
                    profile=profile,
                    expense_date=today
                ).select_related('category')
            )
        
        expenses = await get_today_expenses()
        
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
        
        # Group by category with amounts per currency (consistent with get_expenses_summary)
        # Получаем язык пользователя для правильного отображения
        from bot.utils.language import get_user_language
        user_lang = await get_user_language(user_id)

        categories = {}
        for expense in expenses:
            if expense.category:
                currency = expense.currency or 'RUB'
                cat_key = expense.category.id

                # Create category entry if doesn't exist
                if cat_key not in categories:
                    categories[cat_key] = {
                        'id': cat_key,
                        'name': expense.category.get_display_name(user_lang),
                        'icon': expense.category.icon,
                        'amounts': {}  # Amounts per currency
                    }

                # Add amount to currency
                if currency not in categories[cat_key]['amounts']:
                    categories[cat_key]['amounts'][currency] = Decimal('0')
                categories[cat_key]['amounts'][currency] += expense.amount

        # Convert to list and sort by total amount across all currencies
        sorted_categories = sorted(
            categories.values(),
            key=lambda x: sum(x['amounts'].values()),
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


async def get_date_summary(user_id: int, target_date: date) -> Dict[str, Any]:
    """Get expense summary for a specific date with multi-currency support"""
    from expenses.models import Profile
    
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
        
        @sync_to_async
        def get_date_expenses():
            return list(
                Expense.objects.filter(
                    profile=profile,
                    expense_date=target_date
                ).select_related('category')
            )
        
        expenses = await get_date_expenses()
        
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
        single_currency = len(currency_totals) == 1
        # For single currency, use that total
        if single_currency and user_currency in currency_totals:
            total = float(currency_totals[user_currency])
        else:
            # For multiple currencies, show main currency total
            total = float(currency_totals.get(user_currency, 0))
        
        # Group by category with amounts per currency (consistent with get_expenses_summary)
        from bot.utils.language import get_user_language
        user_lang = await get_user_language(user_id)

        categories = {}
        for expense in expenses:
            if expense.category:
                currency = expense.currency or 'RUB'
                cat_key = expense.category.id

                # Create category entry if doesn't exist
                if cat_key not in categories:
                    categories[cat_key] = {
                        'id': cat_key,
                        'name': expense.category.get_display_name(user_lang),
                        'icon': expense.category.icon,
                        'amounts': {}  # Amounts per currency
                    }

                # Add amount to currency
                if currency not in categories[cat_key]['amounts']:
                    categories[cat_key]['amounts'][currency] = Decimal('0')
                categories[cat_key]['amounts'][currency] += expense.amount

        # Convert to list and sort by total amount across all currencies
        sorted_categories = sorted(
            categories.values(),
            key=lambda x: sum(x['amounts'].values()),
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
        logger.error(f"Error getting date summary for {target_date}: {e}")
        return {'total': 0, 'count': 0, 'categories': [], 'currency': 'RUB', 'currency_totals': {}, 'single_currency': True}


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

