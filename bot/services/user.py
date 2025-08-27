"""
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
    
    # Базовые категории с переводами
    if lang == 'en':
        default_categories = [
            ('Supermarkets', '🛒'),
            ('Other Products', '🫑'),
            ('Restaurants and Cafes', '🍽️'),
            ('Gas Stations', '⛽'),
            ('Taxi', '🚕'),
            ('Public Transport', '🚌'),
            ('Car', '🚗'),
            ('Housing', '🏠'),
            ('Pharmacies', '💊'),
            ('Medicine', '🏥'),
            ('Sports', '🏃'),
            ('Sports Goods', '🏀'),
            ('Clothes and Shoes', '👔'),
            ('Flowers', '🌹'),
            ('Entertainment', '🎭'),
            ('Education', '📚'),
            ('Gifts', '🎁'),
            ('Travel', '✈️'),
            ('Communication and Internet', '📱'),
            ('Other Expenses', '💰')
        ]
    else:
        default_categories = [
            ('Супермаркеты', '🛒'),
            ('Другие продукты', '🫑'),
            ('Рестораны и кафе', '🍽️'),
            ('АЗС', '⛽'),
            ('Такси', '🚕'),
            ('Общественный транспорт', '🚌'),
            ('Автомобиль', '🚗'),
            ('Жилье', '🏠'),
            ('Аптеки', '💊'),
            ('Медицина', '🏥'),
            ('Спорт', '🏃'),
            ('Спортивные товары', '🏀'),
            ('Одежда и обувь', '👔'),
            ('Цветы', '🌹'),
            ('Развлечения', '🎭'),
            ('Образование', '📚'),
            ('Подарки', '🎁'),
            ('Путешествия', '✈️'),
            ('Связь и интернет', '📱'),
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