"""Роутеры для разных функций бота"""
from .start import router as start_router
from .menu import router as menu_router
from .expense import router as expense_router
from .cashback import router as cashback_router
from .categories import router as category_router
from .recurring import router as recurring_router
from .settings import router as settings_router
from .reports import router as reports_router
from .info import router as info_router
from .chat import router as chat_router
from .subscription import router as subscription_router
from .referral import router as referral_router
from .top5 import router as top5_router
from .household import router as household_router
from .blogger_stats import router as blogger_stats_router
from .inline_router import router as inline_router

__all__ = [
    "start_router",
    "menu_router",
    "expense_router",
    "cashback_router",
    "category_router",
    "recurring_router",
    "settings_router",
    "reports_router",
    "info_router",
    "chat_router",
    "subscription_router",
    "referral_router",
    "top5_router",
    "household_router",
    "blogger_stats_router",
    "inline_router",
]
