from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from expenses.models import PromoCode


def test_promocode_clean_rejects_invalid_date_range():
    promo = PromoCode(
        code="SPRING",
        discount_type="percent",
        discount_value=Decimal("20"),
        valid_from=timezone.now(),
        valid_until=timezone.now() - timedelta(days=1),
    )

    with pytest.raises(ValidationError) as exc_info:
        promo.clean()

    assert 'valid_until' in exc_info.value.message_dict


def test_promocode_clean_rejects_non_positive_days_discount():
    promo = PromoCode(
        code="BONUS0",
        discount_type="days",
        discount_value=Decimal("0"),
        valid_from=timezone.now(),
    )

    with pytest.raises(ValidationError) as exc_info:
        promo.clean()

    assert 'discount_value' in exc_info.value.message_dict
