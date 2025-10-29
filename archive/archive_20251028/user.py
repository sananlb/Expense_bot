"""
⛔ DEPRECATED - DO NOT USE ⛔

This file is DEPRECATED and should NOT be used in production code.

Use instead:
- bot/utils/db_utils.py::get_or_create_user_profile_sync() for user creation
- bot/services/category.py::create_default_categories_sync() for creating default categories

This file contains OUTDATED category definitions (20 categories instead of 16).
It is kept only for reference and should be moved to archive.

Сервис для работы с пользователями
"""
from expenses.models import Profile, UserSettings, ExpenseCategory, DEFAULT_CATEGORIES
from asgiref.sync import sync_to_async


@sync_to_async
def get_or_create_user(telegram_id: int, **kwargs) -> tuple[Profile, bool]:
    """Получить или создать пользователя"""
    user, created = Profile.objects.get_or_create(
        telegram_id=telegram_id,
        defaults=kwargs
    )
    
    if not created:
        # Обновляем данные существующего пользователя
        for key, value in kwargs.items():
            if value is not None:
                setattr(user, key, value)
        user.save()
    
    # Создаем настройки если их нет
    UserSettings.objects.get_or_create(profile=user)
    
    # Добавляем флаг для определения нового пользователя
    user.is_new = created
    return user


@sync_to_async
def create_default_categories(profile_id: int):
    """Создает базовые категории для нового пользователя"""
    profile = Profile.objects.get(telegram_id=profile_id)
    
    # Определяем язык пользователя
    lang = profile.language_code or 'ru'
    
    # Базовые категории с переводами (унифицированные 16 категорий)
    if lang == 'en':
        default_categories = [
            ('Groceries', '🛒'),
            ('Cafes and Restaurants', '🍽️'),
            ('Transport', '🚕'),
            ('Car', '🚗'),
            ('Housing', '🏠'),
            ('Pharmacies', '💊'),
            ('Medicine', '🏥'),
            ('Beauty', '💄'),
            ('Sports and Fitness', '🏃'),
            ('Clothes and Shoes', '👔'),
            ('Entertainment', '🎭'),
            ('Education', '📚'),
            ('Gifts', '🎁'),
            ('Travel', '✈️'),
            ('Utilities and Subscriptions', '📱'),
            ('Other Expenses', '💰')
        ]
    else:
        default_categories = [
            ('Продукты', '🛒'),
            ('Кафе и рестораны', '🍽️'),
            ('Транспорт', '🚕'),
            ('Автомобиль', '🚗'),
            ('Жилье', '🏠'),
            ('Аптеки', '💊'),
            ('Медицина', '🏥'),
            ('Красота', '💄'),
            ('Спорт и фитнес', '🏃'),
            ('Одежда и обувь', '👔'),
            ('Развлечения', '🎭'),
            ('Образование', '📚'),
            ('Подарки', '🎁'),
            ('Путешествия', '✈️'),
            ('Коммунальные услуги и подписки', '📱'),
            ('Прочие расходы', '💰')
        ]
    
    for name, icon in default_categories:
        # Сохраняем эмодзи вместе с названием
        category_with_icon = f"{icon} {name}"
        ExpenseCategory.objects.get_or_create(
            profile=profile,
            name=category_with_icon,
            defaults={
                'icon': '',  # Поле icon больше не используем
            }
        )