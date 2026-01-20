"""
Тесты для верификации edge cases из user_scenarios_edge_cases.md и user_scenarios_ADDENDUM.md

Проверяемые изменения:
1. Cashback: процент <=99 (MaxValueValidator)
2. Cashback: уникальность (profile, bank_name, month, category)
3. Recurring: дни 1-30
4. Recurring: лимит описания <=200 символов
5. Household: max_members default 5, is_active
6. FamilyInvite: is_valid() проверки
7. Персональность Recurring/Cashback (нет household поля)
"""

import sys
import os
import unittest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
import django
django.setup()

from django.core.exceptions import ValidationError
from expenses.models import Cashback, Household, FamilyInvite, RecurringPayment


class TestCashbackValidation(unittest.TestCase):
    """Тесты для Cashback модели"""

    def test_cashback_percent_max_99(self):
        """Cashback процент должен быть <=99"""
        # Проверяем что модель имеет MaxValueValidator(99)
        cashback = Cashback()
        cashback.cashback_percent = Decimal('100')

        with self.assertRaises(ValidationError) as context:
            cashback.full_clean()

        # Должна быть ошибка валидации для cashback_percent
        error_dict = context.exception.message_dict
        self.assertIn('cashback_percent', error_dict)

    def test_cashback_percent_valid_99(self):
        """Cashback процент 99 должен быть валидным"""
        cashback = Cashback()
        cashback.cashback_percent = Decimal('99')

        # При full_clean будут другие ошибки (profile обязателен),
        # но cashback_percent не должен вызывать ошибку
        try:
            cashback.full_clean()
            self.fail("Should raise ValidationError for missing fields")
        except ValidationError as e:
            # Ошибка cashback_percent НЕ должна быть среди ошибок
            error_dict = e.message_dict if hasattr(e, 'message_dict') else {}
            self.assertNotIn('cashback_percent', error_dict,
                           "99% должен быть валидным значением")

    def test_cashback_unique_together(self):
        """Проверка unique_together для (profile, bank_name, month, category)"""
        meta = Cashback._meta
        self.assertIn(('profile', 'bank_name', 'month', 'category'), meta.unique_together)


class TestRecurringValidation(unittest.TestCase):
    """Тесты для RecurringPayment модели"""

    def test_recurring_day_min_1(self):
        """День месяца должен быть >= 1"""
        recurring = RecurringPayment()
        recurring.day_of_month = 0

        with self.assertRaises(ValidationError) as context:
            recurring.full_clean()

        error_dict = context.exception.message_dict
        self.assertIn('day_of_month', error_dict)

    def test_recurring_day_max_30(self):
        """День месяца должен быть <= 30"""
        recurring = RecurringPayment()
        recurring.day_of_month = 31

        with self.assertRaises(ValidationError) as context:
            recurring.full_clean()

        error_dict = context.exception.message_dict
        self.assertIn('day_of_month', error_dict)

    def test_recurring_day_valid_range(self):
        """Дни 1-30 должны быть валидными"""
        for day in [1, 15, 30]:
            recurring = RecurringPayment()
            recurring.day_of_month = day
            try:
                recurring.full_clean()
            except ValidationError as e:
                error_dict = e.message_dict if hasattr(e, 'message_dict') else {}
                self.assertNotIn('day_of_month', error_dict,
                               f"День {day} должен быть валидным")

    def test_recurring_description_max_length(self):
        """Описание должно быть <= 200 символов"""
        field = RecurringPayment._meta.get_field('description')
        self.assertEqual(field.max_length, 200)


class TestHouseholdValidation(unittest.TestCase):
    """Тесты для Household модели"""

    def test_household_max_members_default(self):
        """max_members по умолчанию должен быть 5"""
        field = Household._meta.get_field('max_members')
        self.assertEqual(field.default, 5)

    def test_household_is_active_default(self):
        """is_active по умолчанию должен быть True"""
        field = Household._meta.get_field('is_active')
        self.assertEqual(field.default, True)

    def test_can_add_member_method_exists(self):
        """Метод can_add_member должен существовать"""
        self.assertTrue(hasattr(Household, 'can_add_member'))
        self.assertTrue(callable(getattr(Household, 'can_add_member')))


class TestFamilyInviteValidation(unittest.TestCase):
    """Тесты для FamilyInvite модели"""

    def test_is_valid_method_exists(self):
        """Метод is_valid должен существовать"""
        self.assertTrue(hasattr(FamilyInvite, 'is_valid'))
        self.assertTrue(callable(getattr(FamilyInvite, 'is_valid')))

    def test_invite_expired(self):
        """Просроченное приглашение должно быть невалидным"""
        invite = FamilyInvite()
        invite.is_active = True
        invite.used_by = None
        invite.expires_at = timezone.now() - timedelta(hours=1)  # Expired

        self.assertFalse(invite.is_valid())

    def test_invite_used_check_exists(self):
        """Проверка что is_valid проверяет used_by"""
        # Проверяем что в коде is_valid есть проверка used_by
        import inspect
        source = inspect.getsource(FamilyInvite.is_valid)
        self.assertIn('used_by', source)

    def test_invite_inactive(self):
        """Неактивное приглашение должно быть невалидным"""
        invite = FamilyInvite()
        invite.is_active = False  # Inactive
        invite.used_by = None
        invite.expires_at = timezone.now() + timedelta(hours=1)

        self.assertFalse(invite.is_valid())

    def test_invite_valid(self):
        """Валидное приглашение должно пройти проверку"""
        invite = FamilyInvite()
        invite.is_active = True
        invite.used_by = None
        invite.expires_at = timezone.now() + timedelta(hours=1)

        self.assertTrue(invite.is_valid())


class TestCashbackPersonality(unittest.TestCase):
    """Тесты для проверки что Cashback персональный (нет household)"""

    def test_cashback_has_no_household_field(self):
        """Cashback не должен иметь поле household"""
        field_names = [f.name for f in Cashback._meta.get_fields()]
        self.assertNotIn('household', field_names)

    def test_cashback_has_profile_field(self):
        """Cashback должен иметь поле profile"""
        field_names = [f.name for f in Cashback._meta.get_fields()]
        self.assertIn('profile', field_names)


class TestRecurringPersonality(unittest.TestCase):
    """Тесты для проверки что RecurringPayment персональный (нет household)"""

    def test_recurring_has_no_household_field(self):
        """RecurringPayment не должен иметь поле household"""
        field_names = [f.name for f in RecurringPayment._meta.get_fields()]
        self.assertNotIn('household', field_names)

    def test_recurring_has_profile_field(self):
        """RecurringPayment должен иметь поле profile"""
        field_names = [f.name for f in RecurringPayment._meta.get_fields()]
        self.assertIn('profile', field_names)


class TestAmountLimitsInCode(unittest.TestCase):
    """Тесты для проверки лимитов сумм в коде (не через async validate_amount)"""

    def test_amount_limits_documented(self):
        """Проверяем что лимиты определены в validators.py"""
        # Читаем файл и проверяем наличие лимитов
        import bot.utils.validators as validators
        import inspect
        source = inspect.getsource(validators.validate_amount)

        # Проверяем что в коде есть проверка <= 0
        self.assertIn('amount <= 0', source)

        # Проверяем что в коде есть проверка > 999999999
        self.assertIn('999999999', source)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
