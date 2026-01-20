"""
Pytest configuration and fixtures for ExpenseBot tests.

This file provides:
- Django setup for tests
- Common fixtures for Profile, Category, Expense, etc.
- Mock fixtures for AI services, Redis, etc.
- Async test support
"""
import os
import sys
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')

import django
django.setup()

from django.utils import timezone


# =============================================================================
# Django Model Fixtures
# =============================================================================

@pytest.fixture
def profile_data() -> dict:
    """Base data for creating a test profile."""
    return {
        'telegram_id': 123456789,
        'language_code': 'ru',
        'currency': 'RUB',
        'is_active': True,
    }


@pytest.fixture
def expense_category_data() -> dict:
    """Base data for creating a test expense category."""
    return {
        'name': '🍔 Еда',
        'name_ru': 'Еда',
        'name_en': 'Food',
        'icon': '🍔',
        'original_language': 'ru',
        'is_active': True,
        'is_translatable': True,
    }


@pytest.fixture
def income_category_data() -> dict:
    """Base data for creating a test income category."""
    return {
        'name': '💰 Зарплата',
        'name_ru': 'Зарплата',
        'name_en': 'Salary',
        'icon': '💰',
        'original_language': 'ru',
        'is_active': True,
        'is_translatable': True,
    }


@pytest.fixture
def expense_data() -> dict:
    """Base data for creating a test expense."""
    return {
        'amount': Decimal('1500.00'),
        'currency': 'RUB',
        'description': 'Обед в кафе',
        'expense_date': date.today(),
        'ai_categorized': False,
    }


@pytest.fixture
def income_data() -> dict:
    """Base data for creating a test income."""
    return {
        'amount': Decimal('50000.00'),
        'currency': 'RUB',
        'description': 'Зарплата за ноябрь',
        'income_date': date.today(),
    }


# =============================================================================
# Database Fixtures (require @pytest.mark.django_db)
# =============================================================================

@pytest.fixture
@pytest.mark.django_db
def test_profile(profile_data):
    """Create a test profile in the database."""
    from expenses.models import Profile
    profile, _ = Profile.objects.get_or_create(
        telegram_id=profile_data['telegram_id'],
        defaults=profile_data
    )
    return profile


@pytest.fixture
@pytest.mark.django_db
def test_expense_category(test_profile, expense_category_data):
    """Create a test expense category in the database."""
    from expenses.models import ExpenseCategory
    category, _ = ExpenseCategory.objects.get_or_create(
        profile=test_profile,
        name=expense_category_data['name'],
        defaults=expense_category_data
    )
    return category


@pytest.fixture
@pytest.mark.django_db
def test_income_category(test_profile, income_category_data):
    """Create a test income category in the database."""
    from expenses.models import IncomeCategory
    category, _ = IncomeCategory.objects.get_or_create(
        profile=test_profile,
        name=income_category_data['name'],
        defaults=income_category_data
    )
    return category


@pytest.fixture
@pytest.mark.django_db
def test_expense(test_profile, test_expense_category, expense_data):
    """Create a test expense in the database."""
    from expenses.models import Expense
    expense = Expense.objects.create(
        profile=test_profile,
        category=test_expense_category,
        **expense_data
    )
    return expense


@pytest.fixture
@pytest.mark.django_db
def test_income(test_profile, test_income_category, income_data):
    """Create a test income in the database."""
    from expenses.models import Income
    income = Income.objects.create(
        profile=test_profile,
        category=test_income_category,
        **income_data
    )
    return income


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_bot() -> Mock:
    """Mock aiogram Bot instance."""
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=Mock(message_id=12345))
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    return bot


@pytest.fixture
def mock_message() -> Mock:
    """Mock aiogram Message instance."""
    message = AsyncMock()
    message.from_user = Mock(id=123456789, language_code='ru')
    message.chat = Mock(id=123456789, type='private')
    message.text = 'Test message'
    message.message_id = 12345
    message.date = datetime.now()
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query() -> Mock:
    """Mock aiogram CallbackQuery instance."""
    callback = AsyncMock()
    callback.from_user = Mock(id=123456789, language_code='ru')
    callback.message = Mock(
        chat=Mock(id=123456789),
        message_id=12345,
        text='Previous message'
    )
    callback.data = 'test_callback'
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_redis():
    """Mock Redis cache."""
    with patch('django.core.cache.cache') as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        yield mock_cache


@pytest.fixture
def mock_ai_service():
    """Mock AI categorization service."""
    mock = AsyncMock()
    mock.categorize_expense.return_value = {
        'category': 'Еда',
        'confidence': 0.95,
        'category_id': 1,
    }
    mock.categorize_income.return_value = {
        'category': 'Зарплата',
        'confidence': 0.98,
        'category_id': 1,
    }
    return mock


@pytest.fixture
def mock_celery_task():
    """Mock Celery task."""
    with patch('celery.current_app.send_task') as mock_task:
        mock_task.return_value = Mock(id='test-task-id')
        yield mock_task


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def today() -> date:
    """Return today's date."""
    return date.today()


@pytest.fixture
def yesterday() -> date:
    """Return yesterday's date."""
    return date.today() - timedelta(days=1)


@pytest.fixture
def last_month_start() -> date:
    """Return the first day of last month."""
    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_day_prev_month = first_day_this_month - timedelta(days=1)
    return last_day_prev_month.replace(day=1)


@pytest.fixture
def current_month_start() -> date:
    """Return the first day of current month."""
    return date.today().replace(day=1)


# =============================================================================
# Async Fixtures
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Test Data Generators
# =============================================================================

@pytest.fixture
def generate_expenses():
    """Factory fixture to generate multiple expenses."""
    def _generate(profile, category, count: int = 5, base_amount: Decimal = Decimal('100')):
        from expenses.models import Expense
        expenses = []
        for i in range(count):
            expense = Expense.objects.create(
                profile=profile,
                category=category,
                amount=base_amount + Decimal(i * 50),
                currency='RUB',
                description=f'Test expense {i+1}',
                expense_date=date.today() - timedelta(days=i),
            )
            expenses.append(expense)
        return expenses
    return _generate


@pytest.fixture
def generate_incomes():
    """Factory fixture to generate multiple incomes."""
    def _generate(profile, category, count: int = 3, base_amount: Decimal = Decimal('10000')):
        from expenses.models import Income
        incomes = []
        for i in range(count):
            income = Income.objects.create(
                profile=profile,
                category=category,
                amount=base_amount + Decimal(i * 5000),
                currency='RUB',
                description=f'Test income {i+1}',
                income_date=date.today() - timedelta(days=i * 7),
            )
            incomes.append(income)
        return incomes
    return _generate


# =============================================================================
# Localization Fixtures
# =============================================================================

@pytest.fixture
def ru_locale():
    """Set Russian locale for tests."""
    return 'ru'


@pytest.fixture
def en_locale():
    """Set English locale for tests."""
    return 'en'


@pytest.fixture
def get_text_mock():
    """Mock get_text function that returns the key."""
    def _mock_get_text(key: str, lang: str = 'ru', **kwargs) -> str:
        return key
    return _mock_get_text
