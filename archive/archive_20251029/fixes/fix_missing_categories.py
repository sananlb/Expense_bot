#!/usr/bin/env python
"""
Скрипт для исправления недостающих категорий у пользователей
Запуск: python fix_missing_categories.py
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from bot.services.category import create_default_categories_sync, create_default_income_categories
from expenses.models import Profile
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fix_user_categories(telegram_id: int):
    """Исправляет категории для конкретного пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        logger.info(f"Обработка пользователя {telegram_id} (язык: {profile.language_code})")

        # Создаем expense категории
        expense_result = create_default_categories_sync(telegram_id)
        if expense_result:
            logger.info(f"✅ Созданы expense категории для {telegram_id}")
        else:
            logger.info(f"ℹ️  Expense категории уже существуют для {telegram_id}")

        # Создаем income категории (асинхронная функция)
        async def create_income():
            return await create_default_income_categories(telegram_id)

        income_result = asyncio.run(create_income())
        if income_result:
            logger.info(f"✅ Созданы income категории для {telegram_id}")
        else:
            logger.info(f"ℹ️  Income категории уже существуют для {telegram_id}")

        return True

    except Profile.DoesNotExist:
        logger.error(f"❌ Профиль не найден для пользователя {telegram_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке {telegram_id}: {e}")
        return False


def main():
    """Основная функция"""
    # Список пользователей с неполными категориями (из SQL запросов)
    users_to_fix = [
        6254047783,  # 0 expense, 0 income
        1076311591,  # 1 expense, 0 income
        8239680156,  # 1 expense, 10 income (полный набор)
        881292737,   # 16 expense (полный), 9 income
    ]

    logger.info("=" * 60)
    logger.info("НАЧАЛО ИСПРАВЛЕНИЯ КАТЕГОРИЙ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ")
    logger.info("=" * 60)

    success_count = 0
    error_count = 0

    for user_id in users_to_fix:
        logger.info(f"\n{'=' * 60}")
        if fix_user_categories(user_id):
            success_count += 1
        else:
            error_count += 1

    logger.info(f"\n{'=' * 60}")
    logger.info("ИТОГИ:")
    logger.info(f"  ✅ Успешно обработано: {success_count}")
    logger.info(f"  ❌ Ошибок: {error_count}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
