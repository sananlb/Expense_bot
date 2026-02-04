"""
Централизованный helper для автоконвертации валют при создании операций.
Используется в expense.py, income.py и recurring.py.
"""
import logging
from decimal import Decimal
from datetime import date
from typing import Optional, Tuple

import pytz
from django.utils import timezone

from .currency_conversion import currency_converter, CurrencyConverter

logger = logging.getLogger(__name__)


def get_user_local_date(profile) -> date:
    """
    Получает текущую дату в timezone пользователя.
    ВАЖНО: Использует timezone профиля, а не сервера!
    """
    try:
        user_tz = pytz.timezone(profile.timezone or 'UTC')
        return timezone.now().astimezone(user_tz).date()
    except Exception:
        return timezone.localdate()


async def maybe_convert_amount(
    amount: Decimal,
    input_currency: str,
    user_currency: str,
    auto_convert_enabled: bool,
    operation_date: Optional[date] = None,
    profile=None  # Для получения timezone
) -> Tuple[Decimal, str, Optional[Decimal], Optional[str], Optional[Decimal]]:
    """
    Конвертирует сумму если нужно.

    Args:
        amount: исходная сумма
        input_currency: валюта ввода
        user_currency: валюта пользователя по умолчанию
        auto_convert_enabled: включена ли автоконвертация
        operation_date: дата операции (для курса)
        profile: профиль пользователя (для timezone)

    Returns:
        Tuple[
            final_amount,           # Итоговая сумма
            final_currency,         # Итоговая валюта
            original_amount,        # Оригинальная сумма (или None)
            original_currency,      # Оригинальная валюта (или None)
            exchange_rate_used      # Использованный курс (или None)
        ]
    """
    # Приводим amount к Decimal если пришёл float/int
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    # Если валюты совпадают или автоконвертация выключена
    if input_currency == user_currency or not auto_convert_enabled:
        return amount, input_currency, None, None, None

    # Определяем дату для курса
    if operation_date is None:
        if profile:
            operation_date = get_user_local_date(profile)
        else:
            operation_date = timezone.localdate()

    # Проверяем: экзотика + историческая дата = нет источника
    is_from_exotic = input_currency in CurrencyConverter.CBRF_UNAVAILABLE
    is_to_exotic = user_currency in CurrencyConverter.CBRF_UNAVAILABLE
    is_exotic = is_from_exotic or is_to_exotic
    today = get_user_local_date(profile) if profile else timezone.localdate()
    is_historical = operation_date < today

    if is_exotic and is_historical:
        # Fawaz @latest не поддерживает исторические даты
        logger.warning(
            f"No historical rates for exotic currency {input_currency} "
            f"on {operation_date}, keeping original"
        )
        return amount, input_currency, None, None, None

    # Пытаемся конвертировать
    try:
        converted, rate = await currency_converter.convert_with_details(
            amount=amount,
            from_currency=input_currency,
            to_currency=user_currency,
            conversion_date=operation_date
        )

        if converted is not None and rate is not None:
            logger.info(
                f"Converted {amount} {input_currency} -> {converted} {user_currency} "
                f"(rate: {rate}, date: {operation_date})"
            )
            return converted, user_currency, amount, input_currency, rate
        else:
            # Graceful degradation
            logger.warning(
                f"Failed to convert {amount} {input_currency} to {user_currency}, "
                f"keeping original"
            )
            return amount, input_currency, None, None, None

    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return amount, input_currency, None, None, None
