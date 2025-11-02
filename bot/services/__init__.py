"""
Bot services
"""
from .profile import get_or_create_profile, update_profile_activity, get_profile_settings
from .category import (
    get_or_create_category,
    get_user_categories,
    create_category,
    update_category,
    delete_category,
    create_default_categories,
    get_icon_for_category
)
from .expense import (
    create_expense,
    get_user_expenses,
    get_expenses_summary,
    get_expenses_by_period,
    update_expense,
    delete_expense,
    get_last_expense
)
# from .pdf_report import generate_pdf_report  # Функция не существует

__all__ = [
    # Profile services
    'get_or_create_profile',
    'update_profile_activity',
    'get_profile_settings',
    # Category services
    'get_or_create_category',
    'get_user_categories',
    'create_category',
    'update_category',
    'delete_category',
    'create_default_categories',
    'get_icon_for_category',
    # Expense services
    'create_expense',
    'get_user_expenses',
    'get_expenses_summary',
    'get_expenses_by_period',
    'update_expense',
    'delete_expense',
    'get_last_expense',
    # PDF report service
    # 'generate_pdf_report'  # Функция не существует
]