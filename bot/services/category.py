"""
Сервис для работы с категориями расходов
"""
from typing import List, Optional
from expenses.models import ExpenseCategory, Profile
from asgiref.sync import sync_to_async
from django.db.models import Sum, Count
import logging

logger = logging.getLogger(__name__)


@sync_to_async
def get_or_create_category(user_id: int, category_name: str) -> ExpenseCategory:
    """Получить категорию по имени или вернуть категорию 'Прочие расходы'"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(telegram_id=user_id)
    
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
    
    # Если категория не найдена, возвращаем "Прочие расходы"
    # Сначала пытаемся найти существующую категорию "Прочие расходы"
    other_category = ExpenseCategory.objects.filter(
        profile=profile,
        name__icontains='прочие'
    ).first()
    
    if not other_category:
        # Если нет категории "Прочие расходы", создаем её
        other_category = ExpenseCategory.objects.create(
            name='💰 Прочие расходы',
            icon='',
            profile=profile
        )
    
    return other_category


@sync_to_async
def get_user_categories(user_id: int) -> List[ExpenseCategory]:
    """Получить все категории пользователя"""
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        # Если профиля нет, создаем его
        profile = Profile.objects.create(telegram_id=user_id)
    
    # Получаем категории пользователя (с refresh из БД)
    from django.db import connection
    connection.ensure_connection()
    
    categories = ExpenseCategory.objects.filter(
        profile=profile
    ).order_by('name')
    
    # Force evaluation of queryset
    categories_count = categories.count()
    logger.info(f"get_user_categories for user {user_id}: found {categories_count} categories in DB")
    
    # Сортируем так, чтобы "Прочие расходы" были в конце
    categories_list = list(categories)
    regular_categories = []
    other_category = None
    
    for cat in categories_list:
        if 'прочие расходы' in cat.name.lower():
            other_category = cat
        else:
            regular_categories.append(cat)
    
    # Возвращаем сначала обычные категории, затем "Прочие расходы"
    if other_category:
        regular_categories.append(other_category)
    
    return regular_categories


@sync_to_async
def create_category(user_id: int, name: str, icon: str = '💰') -> ExpenseCategory:
    """Создать новую категорию"""
    from django.db import transaction
    
    with transaction.atomic():
        try:
            profile = Profile.objects.get(telegram_id=user_id)
        except Profile.DoesNotExist:
            profile = Profile.objects.create(telegram_id=user_id)
        
        # Если иконка предоставлена, добавляем её к названию
        if icon and icon.strip():
            category_name = f"{icon} {name}"
        else:
            category_name = name
        
        category = ExpenseCategory.objects.create(
            name=category_name,
            icon='',  # Поле icon больше не используем
            profile=profile
        )
        
        logger.info(f"Created category '{category_name}' (id: {category.id}) for user {user_id}")
        
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


async def update_category_name(user_id: int, category_id: int, new_name: str) -> bool:
    """Обновить название категории"""
    # Просто сохраняем то, что ввел пользователь, без разделения на эмодзи и текст
    result = await update_category(user_id, category_id, name=new_name.strip(), icon='')
    return result is not None


@sync_to_async
def delete_category(user_id: int, category_id: int) -> bool:
    """Удалить категорию"""
    from django.db import transaction
    
    try:
        with transaction.atomic():
            category = ExpenseCategory.objects.get(
                id=category_id,
                profile__telegram_id=user_id
            )
            category.delete()
            logger.info(f"Deleted category {category_id} for user {user_id}")
        return True
    except ExpenseCategory.DoesNotExist:
        logger.warning(f"Category {category_id} not found for user {user_id}")
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
    except Profile.DoesNotExist:
        # Создаем профиль если его нет
        profile = Profile.objects.create(telegram_id=telegram_id)
        logger.info(f"Created new profile for user {telegram_id}")
    
    try:
        
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
            ('Прочие расходы', '💰')
        ]
        
        # Создаем категории с эмодзи в поле name
        categories = []
        for name, icon in default_categories:
            # Сохраняем эмодзи вместе с названием
            category_with_icon = f"{icon} {name}"
            category = ExpenseCategory(
                profile=profile,
                name=category_with_icon,
                icon='',  # Поле icon больше не используем
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


@sync_to_async
def migrate_categories_with_emojis():
    """Мигрировать существующие категории - добавить эмодзи в поле name"""
    from expenses.models import ExpenseCategory
    
    # Получаем все категории без эмодзи в начале названия
    categories = ExpenseCategory.objects.all()
    
    for category in categories:
        # Проверяем, есть ли уже эмодзи в начале
        import re
        emoji_pattern = r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]'
        
        if not re.match(emoji_pattern, category.name):
            # Если эмодзи нет, добавляем
            if category.icon and category.icon.strip():
                # Если есть иконка в поле icon, используем её
                category.name = f"{category.icon} {category.name}"
            else:
                # Иначе подбираем по названию
                icon = get_icon_for_category(category.name)
                category.name = f"{icon} {category.name}"
            
            # Очищаем поле icon
            category.icon = ''
            category.save()
    
    return True


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


