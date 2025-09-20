#!/usr/bin/env python
"""
Скрипт для исправления отсутствующих эмодзи в категориях доходов

Проблема: категории доходов для русскоязычных пользователей создавались без эмодзи
в поле name из-за ошибки в функции create_default_income_categories.

Этот скрипт находит такие категории и добавляет эмодзи к их названиям.
"""

import os
import sys
import django
from django.db import transaction

# Настройка Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import IncomeCategory, Profile, DEFAULT_INCOME_CATEGORIES
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def has_emoji_at_start(text):
    """Проверяет, начинается ли текст с эмодзи"""
    if not text:
        return False

    emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
    return bool(re.match(emoji_pattern, text))


def fix_income_categories_emojis():
    """Исправляет отсутствующие эмодзи в категориях доходов"""

    # Создаем словарь для сопоставления названий категорий с эмодзи
    default_categories_dict = dict(DEFAULT_INCOME_CATEGORIES)

    # Дополнительные сопоставления для различных вариантов названий
    category_emoji_map = {
        'зарплата': '💼',
        'премии и бонусы': '🎁',
        'фриланс': '💻',
        'инвестиции': '📈',
        'проценты по вкладам': '🏦',
        'аренда недвижимости': '🏠',
        'возвраты и компенсации': '💸',
        'кешбэк': '💳',
        'подарки': '🎉',
        'прочие доходы': '💰',
        # Английские варианты
        'salary': '💼',
        'bonuses': '🎁',
        'freelance': '💻',
        'investments': '📈',
        'bank interest': '🏦',
        'rent income': '🏠',
        'refunds': '💸',
        'cashback': '💳',
        'gifts': '🎉',
        'other income': '💰',
    }

    fixed_count = 0
    total_checked = 0

    with transaction.atomic():
        # Получаем все категории доходов
        categories = IncomeCategory.objects.select_related('profile').all()

        for category in categories:
            total_checked += 1

            # Проверяем, есть ли эмодзи в начале названия
            if not has_emoji_at_start(category.name):
                logger.info(f"Найдена категория без эмодзи: '{category.name}' (user: {category.profile.telegram_id})")

                # Пытаемся найти подходящий эмодзи
                category_name_lower = category.name.lower().strip()

                # Сначала ищем точное соответствие
                emoji = None
                if category_name_lower in category_emoji_map:
                    emoji = category_emoji_map[category_name_lower]
                else:
                    # Ищем частичное соответствие
                    for name, emj in category_emoji_map.items():
                        if name in category_name_lower or category_name_lower in name:
                            emoji = emj
                            break

                # Если не нашли соответствие, используем эмодзи из поля icon
                if not emoji and category.icon:
                    emoji = category.icon

                # Если все еще нет эмодзи, используем стандартный
                if not emoji:
                    emoji = '💰'

                # Обновляем название категории
                new_name = f"{emoji} {category.name}"

                logger.info(f"Обновляем категорию: '{category.name}' -> '{new_name}'")

                category.name = new_name
                category.save()

                fixed_count += 1

    logger.info(f"Завершено. Проверено: {total_checked}, исправлено: {fixed_count}")
    return fixed_count


def main():
    """Главная функция"""
    logger.info("Начинаем исправление эмодзи в категориях доходов...")

    try:
        fixed_count = fix_income_categories_emojis()

        if fixed_count > 0:
            logger.info(f"✅ Успешно исправлено {fixed_count} категорий доходов")
        else:
            logger.info("✅ Все категории доходов уже имеют эмодзи")

    except Exception as e:
        logger.error(f"❌ Ошибка при исправлении категорий: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())