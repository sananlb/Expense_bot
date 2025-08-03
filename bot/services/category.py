"""
Сервис для работы с категориями расходов
"""
from typing import List, Optional
from expenses.models import ExpenseCategory, Profile
from asgiref.sync import sync_to_async
from django.db.models import Sum, Count


@sync_to_async
def get_or_create_category(user_id: int, category_name: str) -> ExpenseCategory:
    """Получить или создать категорию по имени"""
    profile = Profile.objects.get(telegram_id=user_id)
    
    # Ищем среди категорий пользователя
    # Сначала точное совпадение
    category = ExpenseCategory.objects.filter(
        profile=profile,
        name__iexact=category_name
    ).first()
    
    if category:
        return category
    
    # Если не нашли точное, ищем частичное совпадение
    # Например, "кафе" найдет "Кафе и рестораны"
    categories = ExpenseCategory.objects.filter(
        profile=profile,
        name__icontains=category_name
    )
    
    if categories.exists():
        return categories.first()
    
    # Если категория не найдена, создаем новую
    # Определяем иконку по имени
    icon = get_icon_for_category(category_name)
    
    category = ExpenseCategory.objects.create(
        name=category_name.capitalize(),
        icon=icon,
        profile=profile
    )
    
    return category


@sync_to_async
def get_user_categories(user_id: int) -> List[ExpenseCategory]:
    """Получить все категории пользователя"""
    profile = Profile.objects.get(telegram_id=user_id)
    
    # Получаем категории пользователя
    categories = ExpenseCategory.objects.filter(
        profile=profile
    ).order_by('name')
    
    return list(categories)


@sync_to_async
def create_category(user_id: int, name: str, icon: str = '💰') -> ExpenseCategory:
    """Создать новую категорию"""
    profile = Profile.objects.get(telegram_id=user_id)
    
    category = ExpenseCategory.objects.create(
        name=name,
        icon=icon,
        profile=profile
    )
    
    return category


@sync_to_async
def update_category(user_id: int, category_id: int, **kwargs) -> Optional[ExpenseCategory]:
    """Обновить категорию"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        
        # Обновляем только переданные поля
        for field, value in kwargs.items():
            if hasattr(category, field):
                setattr(category, field, value)
        
        category.save()
        return category
    except ExpenseCategory.DoesNotExist:
        return None


@sync_to_async
def delete_category(user_id: int, category_id: int) -> bool:
    """Удалить категорию"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        category.delete()
        return True
    except ExpenseCategory.DoesNotExist:
        return False


@sync_to_async
def get_category_by_id(user_id: int, category_id: int) -> Optional[ExpenseCategory]:
    """Получить категорию по ID"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        return category
    except ExpenseCategory.DoesNotExist:
        return None


@sync_to_async
def create_default_categories(telegram_id: int) -> bool:
    """
    Создать базовые категории для нового пользователя
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        True если категории созданы, False если уже существуют
    """
    try:
        profile = Profile.objects.get(telegram_id=telegram_id)
        
        # Проверяем, есть ли уже категории у пользователя
        if ExpenseCategory.objects.filter(profile=profile).exists():
            return False
            
        # Базовые категории согласно ТЗ
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
        
        # Создаем категории
        categories = []
        for name, icon in default_categories:
            category = ExpenseCategory(
                profile=profile,
                name=name,
                icon=icon,
                is_active=True
            )
            categories.append(category)
            
        ExpenseCategory.objects.bulk_create(categories)
        return True
        
    except Profile.DoesNotExist:
        # Если профиля еще нет, создаем его
        profile = Profile.objects.create(telegram_id=telegram_id)
        return create_default_categories(telegram_id)
    except Exception as e:
        return False


def get_icon_for_category(category_name: str) -> str:
    """Подобрать иконку для категории по названию"""
    category_lower = category_name.lower()
    
    # Словарь соответствия категорий и иконок согласно ТЗ
    icon_map = {
        'супермаркет': '🛒',
        'продукт': '🥐',
        'ресторан': '☕',
        'кафе': '☕',
        'азс': '⛽',
        'заправка': '⛽',
        'такси': '🚕',
        'общественный транспорт': '🚌',
        'метро': '🚌',
        'автобус': '🚌',
        'автомобиль': '🚗',
        'машина': '🚗',
        'жилье': '🏠',
        'квартира': '🏠',
        'аптек': '💊',
        'лекарств': '💊',
        'медицин': '🏥',
        'врач': '🏥',
        'спорт': '⚽',
        'фитнес': '⚽',
        'спортивн': '🏃',
        'одежда': '👕',
        'обувь': '👟',
        'цвет': '🌸',
        'букет': '🌸',
        'развлечен': '🎭',
        'кино': '🎬',
        'образован': '📚',
        'курс': '📚',
        'подарк': '🎁',
        'подарок': '🎁',
        'путешеств': '✈️',
        'отпуск': '✈️',
        'связь': '📱',
        'интернет': '📱',
        'телефон': '📱',
        'прочее': '💰',
        'другое': '💰'
    }
    
    # Ищем подходящую иконку
    for key, icon in icon_map.items():
        if key in category_lower:
            return icon
    
    return '💰'  # Иконка по умолчанию


