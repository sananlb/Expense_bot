"""
Сервисный слой лимитов трат (модель Budget).

Поддерживает два вида месячных лимитов:
  * категорийный лимит — Budget с заполненной category;
  * общий лимит на все траты профиля — Budget с category IS NULL.

Лимит информирует пользователя (процент в подтверждении траты, шкала в обзоре
месяца, уведомления о порогах), но НЕ блокирует создание траты.

Все обращения к Django ORM выполняются внутри одного синхронного блока,
обёрнутого в sync_to_async, чтобы избежать SynchronousOnlyOperation при
ленивой загрузке FK (см. memory/async_patterns.md).
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from asgiref.sync import sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

from expenses.models import Budget, Expense, ExpenseCategory, Profile

from .conversion_helper import get_user_local_date
from .subscription import check_subscription

logger = logging.getLogger(__name__)

# Пороги уведомлений (проценты) по типу лимита.
TOTAL_LIMIT_THRESHOLDS = [80, 100]   # общий лимит: предупреждение и превышение
CATEGORY_LIMIT_THRESHOLDS = [100]    # категорийный лимит: только превышение

PERIOD_MONTHLY = 'monthly'
MAX_LIMIT_AMOUNT = Decimal('9999999999.99')


@dataclass
class LimitStatus:
    """Состояние лимита на момент создания/просмотра траты."""
    budget: Budget
    spent: Decimal                       # потрачено за календарный месяц (вкл. текущую трату)
    percent: int                         # floor(spent / limit * 100)
    exceeded: bool                       # spent >= limit
    crossed_thresholds: list = field(default_factory=list)  # пороги, пересечённые ЭТОЙ тратой

    @property
    def is_total(self) -> bool:
        """True если это общий лимит на все траты (без категории)."""
        return self.budget.category_id is None

    @property
    def remaining(self) -> Decimal:
        """Остаток лимита (может быть отрицательным при превышении)."""
        return self.budget.amount - self.spent


def _month_bounds(target: date) -> tuple:
    """Возвращает (первый день месяца, первый день следующего месяца)
    для фильтрации трат по календарному месяцу даты target."""
    first_day = target.replace(day=1)
    if first_day.month == 12:
        next_first = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_first = first_day.replace(month=first_day.month + 1)
    return first_day, next_first


def _thresholds_for(budget: Budget) -> list:
    """Пороги уведомлений для данного лимита."""
    return TOTAL_LIMIT_THRESHOLDS if budget.category_id is None else CATEGORY_LIMIT_THRESHOLDS


def _compute_spent(telegram_id: int, budget: Budget, today: date) -> Decimal:
    """Сумма трат за календарный месяц `today` в валюте лимита.
    Для категорийного лимита — только по его категории. Синхронная функция."""
    first_day, next_first = _month_bounds(today)
    qs = Expense.objects.filter(
        profile__telegram_id=telegram_id,
        currency=budget.currency,
        expense_date__gte=first_day,
        expense_date__lt=next_first,
    )
    if budget.category_id is not None:
        qs = qs.filter(category_id=budget.category_id)
    total = qs.aggregate(total=Sum('amount'))['total']
    return total or Decimal('0')


def _build_status(telegram_id: int, budget: Budget, today: date, expense=None) -> LimitStatus:
    """Собирает LimitStatus. Синхронная функция (вызывается внутри sync-блока).

    crossed_thresholds вычисляется только если переданная трata `expense`
    действительно влияет на текущий месячный остаток этого лимита:
      * её дата в том же календарном месяце, что и today;
      * её валюта совпадает с валютой лимита;
      * (для категорийного) её категория совпадает с категорией лимита.
    Иначе spent_before == spent и порог не считается пересечённым этой тратой.
    """
    spent = _compute_spent(telegram_id, budget, today)
    limit_amount = budget.amount

    percent = int((spent / limit_amount) * 100) if limit_amount > 0 else 0
    exceeded = limit_amount > 0 and spent >= limit_amount

    crossed: list = []
    if expense is not None and limit_amount > 0:
        first_day, next_first = _month_bounds(today)
        affects = (
            getattr(expense, 'profile_id', None) == budget.profile_id
            and getattr(expense, 'currency', None) == budget.currency
            and first_day <= getattr(expense, 'expense_date', today) < next_first
        )
        if affects and budget.category_id is not None:
            affects = getattr(expense, 'category_id', None) == budget.category_id

        if affects:
            spent_before = spent - expense.amount
            for threshold in _thresholds_for(budget):
                trigger = limit_amount * Decimal(threshold) / Decimal(100)
                if spent_before < trigger <= spent:
                    crossed.append(threshold)

    return LimitStatus(
        budget=budget,
        spent=spent,
        percent=percent,
        exceeded=exceeded,
        crossed_thresholds=crossed,
    )


def _validate_category_ownership(profile: Profile, category_id: int) -> ExpenseCategory:
    """Проверяет, что категория принадлежит профилю или члену его семьи.
    Возвращает категорию или кидает ValueError. Синхронная функция.
    Зеркалит логику bot/services/expense.create_expense."""
    try:
        category = ExpenseCategory.objects.select_related('profile').get(id=category_id)
    except ExpenseCategory.DoesNotExist:
        raise ValueError(f"Категория с ID {category_id} не существует")

    is_valid = False
    if category.profile_id == profile.id:
        is_valid = True
    elif profile.household_id is not None:
        if category.profile.household_id == profile.household_id:
            is_valid = True

    if not is_valid:
        logger.warning(
            "Budget category ownership mismatch: profile=%s category=%s",
            profile.id, category_id,
        )
        raise ValueError("Нельзя установить лимит на категорию другого пользователя")
    return category


@sync_to_async
def get_limit(profile_id: int, category_id: Optional[int]) -> Optional[Budget]:
    """Возвращает активный месячный лимит профиля (категорийный или общий) либо None.

    category_id=None означает общий лимит на все траты.
    """
    qs = Budget.objects.select_related('profile', 'category').filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    if category_id is None:
        qs = qs.filter(category__isnull=True)
    else:
        qs = qs.filter(category_id=category_id)
    return qs.order_by('-updated_at', '-id').first()


@sync_to_async
def get_active_limits_map(profile_id: int) -> dict:
    """Все активные месячные лимиты профиля, ключ — category_id (None = общий лимит).

    Используется для отрисовки шкал в обзоре месяца одним запросом.
    """
    result: dict = {}
    qs = Budget.objects.select_related('profile', 'category').filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    for budget in qs:
        result[budget.category_id] = budget
    return result


async def set_limit(profile_id: int, category_id: Optional[int], amount: Decimal) -> Budget:
    """Создаёт/обновляет активный месячный лимит.

    Требует активной подписки. Деактивирует предыдущий активный лимит того же
    типа и создаёт новую строку в одной транзакции (Codex review #3).

    Args:
        profile_id: telegram_id владельца.
        category_id: id категории или None для общего лимита.
        amount: сумма лимита (> 0).

    Returns:
        Созданный объект Budget.

    Raises:
        ValueError: при ошибке валидации (сумма, подписка, чужая категория).
    """
    try:
        amount = Decimal(str(amount))
    except (TypeError, ValueError):
        raise ValueError("Введите корректную сумму лимита")

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Сумма лимита должна быть больше нуля")
    if amount > MAX_LIMIT_AMOUNT:
        raise ValueError(f"Сумма лимита не должна превышать {MAX_LIMIT_AMOUNT}")
    if amount.quantize(Decimal('0.01')) != amount:
        raise ValueError("Сумма лимита должна содержать не более двух знаков после запятой")

    # Проверка подписки вне ORM-блока (использует собственные async-запросы).
    has_subscription = await check_subscription(profile_id)
    if not has_subscription:
        raise ValueError("Лимиты доступны по подписке")

    def _do_set() -> Budget:
        with transaction.atomic():
            # Блокируем строку профиля, чтобы сериализовать параллельные
            # установки лимита (Codex review: select_for_update по Budget не
            # держит lock, когда активной строки ещё нет).
            profile = Profile.objects.select_for_update().get(telegram_id=profile_id)

            if category_id is not None:
                _validate_category_ownership(profile, category_id)

            # Деактивируем ЛЮБОЙ активный лимит этого типа, не только monthly:
            # частичные unique-constraint не различают period_type, поэтому
            # оставшийся активный weekly/daily-лимит заблокировал бы создание
            # (Codex review HIGH).
            stale_qs = Budget.objects.filter(
                profile=profile,
                is_active=True,
            )
            if category_id is None:
                stale_qs = stale_qs.filter(category__isnull=True)
            else:
                stale_qs = stale_qs.filter(category_id=category_id)
            stale_qs.update(is_active=False)

            today = get_user_local_date(profile)
            budget = Budget.objects.create(
                profile=profile,
                category_id=category_id,
                amount=amount,
                currency=profile.currency or 'RUB',
                period_type=PERIOD_MONTHLY,
                start_date=today,
                is_active=True,
            )
            return budget

    try:
        budget = await sync_to_async(_do_set)()
    except IntegrityError:
        # Гонка с параллельной установкой — один повтор (Codex review #3).
        logger.warning("IntegrityError on set_limit, retrying once: profile=%s category=%s",
                       profile_id, category_id)
        budget = await sync_to_async(_do_set)()

    logger.info("Budget limit set: profile=%s category=%s amount=%s %s",
                profile_id, category_id, budget.amount, budget.currency)
    return budget


@sync_to_async
def remove_limit(profile_id: int, category_id: Optional[int]) -> bool:
    """Деактивирует активный месячный лимит. Возвращает True, если что-то изменилось."""
    qs = Budget.objects.filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    if category_id is None:
        qs = qs.filter(category__isnull=True)
    else:
        qs = qs.filter(category_id=category_id)
    updated = qs.update(is_active=False)
    if updated:
        logger.info("Budget limit removed: profile=%s category=%s", profile_id, category_id)
    return updated > 0


async def get_limit_status(profile_id: int, category_id: Optional[int],
                           expense=None) -> Optional[LimitStatus]:
    """Возвращает состояние лимита (потрачено/процент/пересечённые пороги) либо None.

    Args:
        profile_id: telegram_id владельца.
        category_id: id категории или None для общего лимита.
        expense: объект только что созданной траты для расчёта crossed_thresholds.
                 Если None — пороги не вычисляются (только текущий процент).
    """
    def _do() -> Optional[LimitStatus]:
        qs = Budget.objects.select_related('profile', 'category').filter(
            profile__telegram_id=profile_id,
            is_active=True,
            period_type=PERIOD_MONTHLY,
        )
        if category_id is None:
            qs = qs.filter(category__isnull=True)
        else:
            qs = qs.filter(category_id=category_id)
        budget = qs.order_by('-updated_at', '-id').first()
        if budget is None:
            return None
        today = get_user_local_date(budget.profile)
        return _build_status(profile_id, budget, today, expense=expense)

    return await sync_to_async(_do)()


@sync_to_async
def get_expense_limit_statuses(profile_id: int, expense) -> dict:
    """Возвращает статусы категорийного и общего лимитов для новой траты.

    Оба лимита загружаются и рассчитываются внутри одного sync-блока. Ключи
    результата: category_id для категорийного лимита и None для общего.
    """
    profile = Profile.objects.get(telegram_id=profile_id)
    today = get_user_local_date(profile)
    category_id = getattr(expense, 'category_id', None)

    budget_filter = Q(category__isnull=True)
    if category_id is not None:
        budget_filter |= Q(category_id=category_id)

    budgets = Budget.objects.select_related('profile', 'category').filter(
        budget_filter,
        profile=profile,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    return {
        budget.category_id: _build_status(profile_id, budget, today, expense=expense)
        for budget in budgets
    }
