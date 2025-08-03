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
    
    # Базовые категории согласно ТЗ - у каждого пользователя свои
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
        ('Прочее', '💰')
    ]
    
    for name, icon in default_categories:
        ExpenseCategory.objects.get_or_create(
            profile=profile,
            name=name,
            defaults={
                'icon': icon,
            }
        )