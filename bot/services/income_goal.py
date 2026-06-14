"""Сервисный слой месячных целей по доходам."""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from asgiref.sync import sync_to_async
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

from expenses.models import Income, IncomeBudget, IncomeCategory, Profile

from .conversion_helper import get_user_local_date
from .subscription import check_subscription

logger = logging.getLogger(__name__)

GOAL_THRESHOLDS = [100]
PERIOD_MONTHLY = 'monthly'
MAX_GOAL_AMOUNT = Decimal('9999999999.99')


@dataclass
class GoalStatus:
    """Состояние цели на момент просмотра или создания дохода."""

    goal: IncomeBudget
    received: Decimal
    percent: int
    achieved: bool
    crossed_thresholds: list[int] = field(default_factory=list)

    @property
    def is_total(self) -> bool:
        """True для общей цели дохода."""
        return self.goal.category_id is None

    @property
    def remaining(self) -> Decimal:
        """Сумма, которую осталось получить; после достижения равна нулю."""
        return max(self.goal.amount - self.received, Decimal('0'))


def _month_bounds(target: date) -> tuple[date, date]:
    """Возвращает границы календарного месяца для target."""
    first_day = target.replace(day=1)
    if first_day.month == 12:
        next_first = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_first = first_day.replace(month=first_day.month + 1)
    return first_day, next_first


def _compute_received(telegram_id: int, goal: IncomeBudget, today: date) -> Decimal:
    """Считает доходы текущего месяца в валюте цели."""
    first_day, next_first = _month_bounds(today)
    incomes = Income.objects.filter(
        profile__telegram_id=telegram_id,
        currency=goal.currency,
        income_date__gte=first_day,
        income_date__lt=next_first,
    )
    if goal.category_id is not None:
        incomes = incomes.filter(category_id=goal.category_id)
    return incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0')


def _build_status(
    telegram_id: int,
    goal: IncomeBudget,
    today: date,
    income=None,
) -> GoalStatus:
    """Собирает статус и определяет пересечение 100% конкретным доходом."""
    received = _compute_received(telegram_id, goal, today)
    amount = goal.amount
    percent = int(received / amount * 100) if amount > 0 else 0
    achieved = amount > 0 and received >= amount

    crossed: list[int] = []
    if income is not None and amount > 0:
        first_day, next_first = _month_bounds(today)
        income_date = getattr(income, 'income_date', None)
        affects = (
            getattr(income, 'profile_id', None) == goal.profile_id
            and getattr(income, 'currency', None) == goal.currency
            and income_date is not None
            and first_day <= income_date < next_first
        )
        if affects and goal.category_id is not None:
            affects = getattr(income, 'category_id', None) == goal.category_id

        if affects:
            received_before = received - income.amount
            for threshold in GOAL_THRESHOLDS:
                trigger = amount * Decimal(threshold) / Decimal(100)
                if received_before < trigger <= received:
                    crossed.append(threshold)

    return GoalStatus(
        goal=goal,
        received=received,
        percent=percent,
        achieved=achieved,
        crossed_thresholds=crossed,
    )


def _validate_category_ownership(
    profile: Profile,
    category_id: int,
) -> IncomeCategory:
    """Проверяет принадлежность категории дохода профилю или его семье."""
    try:
        category = IncomeCategory.objects.select_related('profile').get(
            id=category_id,
            is_active=True,
        )
    except IncomeCategory.DoesNotExist as exc:
        raise ValueError(f"Категория дохода с ID {category_id} не существует") from exc

    is_valid = category.profile_id == profile.id
    if not is_valid and profile.household_id is not None:
        is_valid = category.profile.household_id == profile.household_id

    if not is_valid:
        logger.warning(
            "Income goal category ownership mismatch: profile=%s category=%s",
            profile.id,
            category_id,
        )
        raise ValueError("Нельзя установить цель на категорию другого пользователя")
    return category


@sync_to_async
def get_goal(
    profile_id: int,
    category_id: Optional[int],
) -> Optional[IncomeBudget]:
    """Возвращает активную месячную цель либо None."""
    goals = IncomeBudget.objects.select_related('profile', 'category').filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    if category_id is None:
        goals = goals.filter(category__isnull=True)
    else:
        goals = goals.filter(category_id=category_id)
    return goals.order_by('-updated_at', '-id').first()


@sync_to_async
def get_active_goals_map(profile_id: int) -> dict[Optional[int], IncomeBudget]:
    """Возвращает все активные месячные цели одним запросом."""
    result: dict[Optional[int], IncomeBudget] = {}
    goals = IncomeBudget.objects.select_related('profile', 'category').filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    for goal in goals:
        result[goal.category_id] = goal
    return result


async def set_goal(
    profile_id: int,
    category_id: Optional[int],
    amount: Decimal,
) -> IncomeBudget:
    """Создаёт новую активную месячную цель, деактивируя предыдущую."""
    try:
        amount = Decimal(str(amount))
    except (TypeError, ValueError) as exc:
        raise ValueError("Введите корректную сумму цели") from exc

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Сумма цели должна быть больше нуля")
    if amount > MAX_GOAL_AMOUNT:
        raise ValueError(f"Сумма цели не должна превышать {MAX_GOAL_AMOUNT}")
    if amount.quantize(Decimal('0.01')) != amount:
        raise ValueError("Сумма цели должна содержать не более двух знаков после запятой")

    if not await check_subscription(profile_id):
        raise ValueError("Цели доступны по подписке")

    def _do_set() -> IncomeBudget:
        with transaction.atomic():
            profile = Profile.objects.select_for_update().get(telegram_id=profile_id)
            if category_id is not None:
                _validate_category_ownership(profile, category_id)

            stale_goals = IncomeBudget.objects.filter(
                profile=profile,
                is_active=True,
            )
            if category_id is None:
                stale_goals = stale_goals.filter(category__isnull=True)
            else:
                stale_goals = stale_goals.filter(category_id=category_id)
            stale_goals.update(is_active=False)

            return IncomeBudget.objects.create(
                profile=profile,
                category_id=category_id,
                amount=amount,
                currency=profile.currency or 'RUB',
                period_type=PERIOD_MONTHLY,
                start_date=get_user_local_date(profile),
                is_active=True,
            )

    try:
        goal = await sync_to_async(_do_set)()
    except IntegrityError:
        logger.warning(
            "IntegrityError on set_goal, retrying once: profile=%s category=%s",
            profile_id,
            category_id,
        )
        goal = await sync_to_async(_do_set)()

    logger.info(
        "Income goal set: profile=%s category=%s amount=%s %s",
        profile_id,
        category_id,
        goal.amount,
        goal.currency,
    )
    return goal


@sync_to_async
def remove_goal(profile_id: int, category_id: Optional[int]) -> bool:
    """Деактивирует активную месячную цель."""
    goals = IncomeBudget.objects.filter(
        profile__telegram_id=profile_id,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    if category_id is None:
        goals = goals.filter(category__isnull=True)
    else:
        goals = goals.filter(category_id=category_id)
    updated = goals.update(is_active=False)
    if updated:
        logger.info(
            "Income goal removed: profile=%s category=%s",
            profile_id,
            category_id,
        )
    return updated > 0


async def get_goal_status(
    profile_id: int,
    category_id: Optional[int],
    income=None,
) -> Optional[GoalStatus]:
    """Возвращает прогресс цели и пересечение порога конкретным доходом."""

    def _do() -> Optional[GoalStatus]:
        goals = IncomeBudget.objects.select_related('profile', 'category').filter(
            profile__telegram_id=profile_id,
            is_active=True,
            period_type=PERIOD_MONTHLY,
        )
        if category_id is None:
            goals = goals.filter(category__isnull=True)
        else:
            goals = goals.filter(category_id=category_id)
        goal = goals.order_by('-updated_at', '-id').first()
        if goal is None:
            return None
        return _build_status(
            profile_id,
            goal,
            get_user_local_date(goal.profile),
            income=income,
        )

    return await sync_to_async(_do)()


@sync_to_async
def get_income_goal_statuses(profile_id: int, income) -> dict[Optional[int], GoalStatus]:
    """Считает категорийную и общую цели для нового дохода одним блоком."""
    profile = Profile.objects.get(telegram_id=profile_id)
    today = get_user_local_date(profile)
    category_id = getattr(income, 'category_id', None)

    goal_filter = Q(category__isnull=True)
    if category_id is not None:
        goal_filter |= Q(category_id=category_id)

    goals = IncomeBudget.objects.select_related('profile', 'category').filter(
        goal_filter,
        profile=profile,
        is_active=True,
        period_type=PERIOD_MONTHLY,
    )
    return {
        goal.category_id: _build_status(profile_id, goal, today, income=income)
        for goal in goals
    }
