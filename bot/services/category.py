"""
Сервис для работы с категориями расходов
"""
from typing import List, Optional, Set
from expenses.models import ExpenseCategory, Profile, CategoryKeyword
from asgiref.sync import sync_to_async
from django.db.models import Sum, Count
from bot.utils.db_utils import get_or_create_user_profile_sync
import logging

logger = logging.getLogger(__name__)


@sync_to_async
def get_or_create_category(user_id: int, category_name: str) -> ExpenseCategory:
    """Получить категорию по имени или вернуть категорию 'Прочие расходы'"""
    logger.info(f"Looking for category '{category_name}' for user {user_id}")
    
    profile = get_or_create_user_profile_sync(user_id)
    
    # Словарь для сопоставления категорий из парсера с реальными категориями
    category_mapping = {
        'азс': ['азс', 'заправка', 'топливо'],
        'супермаркеты': ['супермаркет', 'продукты', 'магазин'],
        'продукты': ['продукты', 'еда', 'супермаркет', 'другие продукты'],
        'кафе и рестораны': ['кафе', 'ресторан', 'рестораны', 'еда', 'обед', 'кофе'],
        'кафе': ['кафе', 'ресторан', 'рестораны'],  # Добавляем отдельное сопоставление для "кафе"
        'транспорт': ['транспорт', 'такси', 'метро', 'автобус'],
        'здоровье': ['здоровье', 'аптека', 'медицина', 'лекарства'],
        'одежда и обувь': ['одежда', 'обувь', 'вещи'],
        'развлечения': ['развлечения', 'кино', 'театр', 'отдых'],
        'дом и жкх': ['жкх', 'квартира', 'коммуналка', 'дом'],
        'связь и интернет': ['связь', 'интернет', 'телефон', 'мобильный'],
        'образование': ['образование', 'курсы', 'учеба', 'обучение'],
        'автомобиль': ['автомобиль', 'машина', 'авто', 'бензин'],
        'подарки': ['подарки', 'подарок', 'цветы'],
        'путешествия': ['путешествия', 'отпуск', 'поездка', 'тур'],
        'другое': ['другое', 'прочее', 'разное'],  # Добавляем сопоставление для "другое"
    }
    
    # Ищем среди категорий пользователя
    # Сначала точное совпадение (игнорируя эмодзи в начале)
    all_categories = ExpenseCategory.objects.filter(profile=profile)
    
    # Проверяем точное совпадение без учета эмодзи
    for cat in all_categories:
        # Убираем эмодзи из начала названия для сравнения
        import re
        name_without_emoji = re.sub(r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+\s*', '', cat.name)
        if name_without_emoji.lower() == category_name.lower():
            # Безопасное логирование для Windows
            safe_name = cat.name.encode('ascii', 'ignore').decode('ascii').strip()
            if not safe_name:
                safe_name = "category with emoji"
            logger.info(f"Found exact match (ignoring emoji): {safe_name}")
            return cat
    
    # Если не нашли точное, ищем частичное совпадение
    # Например, "кафе" найдет "Кафе и рестораны"
    for cat in all_categories:
        name_lower = cat.name.lower()
        category_name_lower = category_name.lower()
        
        # Проверяем, содержит ли категория искомое название
        if category_name_lower in name_lower:
            safe_name = cat.name.encode('ascii', 'ignore').decode('ascii').strip()
            if not safe_name:
                safe_name = "category with emoji"
            logger.info(f"Found partial match: {safe_name}")
            return cat
        
        # Проверяем каждое слово из искомой категории
        words = category_name_lower.split()
        if any(word in name_lower for word in words if len(word) > 3):
            safe_name = cat.name.encode('ascii', 'ignore').decode('ascii').strip()
            if not safe_name:
                safe_name = "category with emoji"
            logger.info(f"Found word match: {safe_name}")
            return cat
    
    # Пробуем найти через словарь сопоставления
    category_name_lower = category_name.lower()
    for cat_group, keywords in category_mapping.items():
        if category_name_lower in keywords:
            # Ищем категорию пользователя, содержащую ключевое слово группы
            for keyword in [cat_group] + keywords:
                # Пробуем разные варианты поиска для лучшей совместимости с кириллицей
                category = ExpenseCategory.objects.filter(
                    profile=profile,
                    name__icontains=keyword
                ).first()
                if category:
                    safe_name = category.name.encode('ascii', 'ignore').decode('ascii').strip()
                    if not safe_name:
                        safe_name = "category with emoji"
                    logger.info(f"Found category '{safe_name}' through mapping keyword '{keyword}'")
                    return category
                
                # Также пробуем поиск в верхнем регистре для кириллицы
                category = ExpenseCategory.objects.filter(
                    profile=profile,
                    name__icontains=keyword.upper()
                ).first()
                if category:
                    safe_name = category.name.encode('ascii', 'ignore').decode('ascii').strip()
                    if not safe_name:
                        safe_name = "category with emoji"
                    logger.info(f"Found category '{safe_name}' through mapping keyword (uppercase) '{keyword.upper()}'")
                    return category
    
    # Дополнительная проверка: если category_name это "кафе", ищем любую категорию со словом "кафе"
    if 'кафе' in category_name.lower():
        for cat in all_categories:
            if 'кафе' in cat.name.lower() or 'ресторан' in cat.name.lower():
                safe_name = cat.name.encode('ascii', 'ignore').decode('ascii').strip()
                if not safe_name:
                    safe_name = "category with emoji"
                logger.info(f"Found category '{safe_name}' by cafe/restaurant keyword")
                return cat
    
    # Если категория не найдена, возвращаем "Прочие расходы"
    logger.warning(f"Category '{category_name}' not found for user {user_id}, using default")
    
    # Сначала пытаемся найти существующую категорию "Прочие расходы"
    other_category = ExpenseCategory.objects.filter(
        profile=profile,
        name__icontains='прочие'
    ).first()
    
    if not other_category:
        # Если нет категории "Прочие расходы", создаем её
        other_category, created = ExpenseCategory.objects.get_or_create(
            name='💰 Прочие расходы',
            profile=profile,
            defaults={'icon': ''}
        )
        if created:
            logger.info(f"Created default category 'Прочие расходы' for user {user_id}")
    
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


async def create_category(user_id: int, name: str, icon: str = '💰') -> ExpenseCategory:
    """Создать новую категорию"""
    from django.db import transaction
    
    @sync_to_async
    def _create_category():
        with transaction.atomic():
            try:
                profile = Profile.objects.get(telegram_id=user_id)
            except Profile.DoesNotExist:
                profile = Profile.objects.create(telegram_id=user_id)
            
            # Проверяем лимит категорий (максимум 50)
            categories_count = ExpenseCategory.objects.filter(profile=profile).count()
            if categories_count >= 50:
                logger.warning(f"User {user_id} reached categories limit (50)")
                raise ValueError("Достигнут лимит категорий (максимум 50)")
            
            # Если иконка предоставлена, добавляем её к названию
            if icon and icon.strip():
                category_name = f"{icon} {name}"
            else:
                category_name = name
            
            # Проверяем, нет ли уже такой категории
            existing = ExpenseCategory.objects.filter(
                profile=profile,
                name=category_name
            ).first()
            
            if existing:
                logger.warning(f"Category '{category_name}' already exists for user {user_id}")
                return existing, False
            
            category = ExpenseCategory.objects.create(
                name=category_name,
                icon='',  # Поле icon больше не используем
                profile=profile
            )
            
            logger.info(f"Created category '{category_name}' (id: {category.id}) for user {user_id}")
            return category, True
    
    category, is_new = await _create_category()
    
    # Если создана новая категория, запускаем асинхронную оптимизацию ключевых слов
    if is_new:
        # Запускаем в фоне, не ждём завершения
        import asyncio
        asyncio.create_task(optimize_keywords_for_new_category(user_id, category.id))
    
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
    result = await update_category(user_id, category_id, name=new_name.strip())
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
def create_default_categories(user_id: int) -> bool:
    """
    Создать базовые категории для нового пользователя
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        True если категории созданы, False если уже существуют
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        # Создаем профиль если его нет
        profile = Profile.objects.create(telegram_id=user_id)
        logger.info(f"Created new profile for user {user_id}")
    
    try:
        
        # Проверяем, есть ли уже категории у пользователя
        if ExpenseCategory.objects.filter(profile=profile).exists():
            return False
            
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
            from expenses.models import DEFAULT_CATEGORIES
            default_categories = DEFAULT_CATEGORIES
        
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
        profile = Profile.objects.create(telegram_id=user_id)
        return create_default_categories(user_id)
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


@sync_to_async
def add_category_keyword(user_id: int, category_id: int, keyword: str) -> bool:
    """Добавить ключевое слово к категории"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        
        # Проверяем, нет ли уже такого ключевого слова
        keyword_lower = keyword.lower().strip()
        if CategoryKeyword.objects.filter(
            category=category,
            keyword__iexact=keyword_lower
        ).exists():
            logger.warning(f"Keyword '{keyword}' already exists for category {category_id}")
            return False
        
        CategoryKeyword.objects.create(
            category=category,
            keyword=keyword_lower
        )
        logger.info(f"Added keyword '{keyword}' to category {category_id}")
        return True
        
    except ExpenseCategory.DoesNotExist:
        logger.error(f"Category {category_id} not found for user {user_id}")
        return False


@sync_to_async
def remove_category_keyword(user_id: int, category_id: int, keyword: str) -> bool:
    """Удалить ключевое слово из категории"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        
        deleted_count, _ = CategoryKeyword.objects.filter(
            category=category,
            keyword__iexact=keyword.strip()
        ).delete()
        
        if deleted_count > 0:
            logger.info(f"Removed keyword '{keyword}' from category {category_id}")
            return True
        else:
            logger.warning(f"Keyword '{keyword}' not found in category {category_id}")
            return False
            
    except ExpenseCategory.DoesNotExist:
        logger.error(f"Category {category_id} not found for user {user_id}")
        return False


@sync_to_async
def get_category_keywords(user_id: int, category_id: int) -> List[str]:
    """Получить все ключевые слова категории"""
    try:
        category = ExpenseCategory.objects.get(
            id=category_id,
            profile__telegram_id=user_id
        )
        
        keywords = CategoryKeyword.objects.filter(
            category=category
        ).values_list('keyword', flat=True)
        
        return list(keywords)
        
    except ExpenseCategory.DoesNotExist:
        logger.error(f"Category {category_id} not found for user {user_id}")
        return []


@sync_to_async
def auto_learn_keywords(user_id: int) -> dict:
    """
    Автоматически обучаться на основе трат пользователя.
    Анализирует описания трат и добавляет часто встречающиеся слова
    как ключевые слова к соответствующим категориям.
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        # Получаем последние 100 трат с категориями
        from expenses.models import Expense
        expenses = Expense.objects.filter(
            profile=profile,
            category__isnull=False
        ).select_related('category').order_by('-created_at')[:100]
        
        # Словарь для подсчета слов по категориям
        category_words = {}
        
        for expense in expenses:
            category_name = expense.category.name
            if category_name not in category_words:
                category_words[category_name] = {}
            
            # Разбиваем описание на слова
            words = expense.description.lower().split()
            for word in words:
                # Фильтруем короткие слова и цифры
                if len(word) > 3 and not word.isdigit():
                    if word not in category_words[category_name]:
                        category_words[category_name][word] = 0
                    category_words[category_name][word] += 1
        
        # Добавляем популярные слова как ключевые
        added_keywords = {}
        for category_name, words in category_words.items():
            # Берем слова, которые встречаются минимум 3 раза
            popular_words = [word for word, count in words.items() if count >= 3]
            
            if popular_words:
                category = ExpenseCategory.objects.get(
                    profile=profile,
                    name=category_name
                )
                
                added = []
                for word in popular_words[:5]:  # Максимум 5 слов на категорию
                    # Проверяем, нет ли уже такого ключевого слова
                    if not CategoryKeyword.objects.filter(
                        category=category,
                        keyword__iexact=word
                    ).exists():
                        CategoryKeyword.objects.create(
                            category=category,
                            keyword=word
                        )
                        added.append(word)
                
                if added:
                    added_keywords[category_name] = added
        
        return added_keywords
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return {}


async def optimize_keywords_for_new_category(user_id: int, new_category_id: int):
    """
    Оптимизирует ключевые слова для новой категории используя AI
    Запускается асинхронно в фоне при создании категории
    """
    try:
        from bot.services.gemini_ai_service import gemini_service
        
        # Получаем все категории пользователя с их ключевыми словами
        @sync_to_async
        def get_categories_with_keywords():
            profile = Profile.objects.get(telegram_id=user_id)
            categories = []
            
            for cat in ExpenseCategory.objects.filter(profile=profile):
                keywords = list(CategoryKeyword.objects.filter(
                    category=cat
                ).values_list('keyword', flat=True))
                
                categories.append({
                    'id': cat.id,
                    'name': cat.name,
                    'keywords': keywords
                })
            
            return categories
        
        all_categories = await get_categories_with_keywords()
        
        # Находим новую категорию
        new_category = None
        for cat in all_categories:
            if cat['id'] == new_category_id:
                new_category = cat
                break
        
        if not new_category:
            logger.error(f"New category {new_category_id} not found")
            return
        
        # Получаем рекомендации от AI
        optimized = await gemini_service.optimize_category_keywords(
            new_category['name'],
            all_categories
        )
        
        # Применяем изменения
        @sync_to_async
        def apply_keyword_changes():
            from django.db import transaction
            with transaction.atomic():
                for cat_name, changes in optimized.items():
                    # Находим категорию по имени
                    category = None
                    for cat in all_categories:
                        if cat['name'] == cat_name:
                            category_obj = ExpenseCategory.objects.get(id=cat['id'])
                            break
                    else:
                        # Пробуем найти по частичному совпадению
                        for cat in all_categories:
                            if cat_name.lower() in cat['name'].lower() or cat['name'].lower() in cat_name.lower():
                                category_obj = ExpenseCategory.objects.get(id=cat['id'])
                                break
                        else:
                            continue
                    
                    # Добавляем новые ключевые слова
                    for keyword in changes.get('add', []):
                        CategoryKeyword.objects.get_or_create(
                            category=category_obj,
                            keyword=keyword.lower().strip()
                        )
                    
                    # Удаляем ключевые слова
                    for keyword in changes.get('remove', []):
                        CategoryKeyword.objects.filter(
                            category=category_obj,
                            keyword__iexact=keyword.strip()
                        ).delete()
        
        await apply_keyword_changes()
        logger.info(f"Keywords optimized for new category {new_category['name']} (user {user_id})")
        
    except Exception as e:
        logger.error(f"Error optimizing keywords for new category: {e}")


async def learn_from_category_change(user_id: int, expense_id: int, new_category_id: int, description: str):
    """
    Обучается на основе изменения категории расхода пользователем
    Добавляет ключевые слова из описания в новую категорию
    """
    try:
        from expenses.models import Expense
        import re
        
        @sync_to_async
        def add_keywords_from_description():
            # Получаем категорию
            category = ExpenseCategory.objects.get(id=new_category_id)
            
            # Извлекаем слова из описания
            words = re.findall(r'\w+', description.lower())
            
            # Фильтруем слова
            meaningful_words = []
            for word in words:
                if len(word) > 3 and not word.isdigit():
                    # Проверяем, не является ли это суммой или числом
                    try:
                        float(word)
                        continue
                    except:
                        meaningful_words.append(word)
            
            # Добавляем только первые 2-3 значимых слова
            added_keywords = []
            for word in meaningful_words[:3]:
                # Проверяем, нет ли уже такого ключевого слова
                keyword, created = CategoryKeyword.objects.get_or_create(
                    category=category,
                    keyword=word
                )
                if created:
                    added_keywords.append(word)
            
            return added_keywords
        
        added = await add_keywords_from_description()
        
        if added:
            logger.info(f"Learned keywords {added} for category {new_category_id} from expense {expense_id}")
        
    except Exception as e:
        logger.error(f"Error learning from category change: {e}")


