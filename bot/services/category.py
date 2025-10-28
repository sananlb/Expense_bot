"""
Сервис для работы с категориями расходов
"""
from typing import List, Optional, Set
from expenses.models import ExpenseCategory, Profile, CategoryKeyword
from asgiref.sync import sync_to_async
from django.db.models import Sum, Count, Q
from bot.utils.db_utils import get_or_create_user_profile_sync
from bot.utils.category_helpers import get_category_display_name, get_category_name_without_emoji
from difflib import get_close_matches
import logging
import re

logger = logging.getLogger(__name__)

EMOJI_PREFIX_RE = re.compile(
    r"[\U0001F000-\U0001F9FF"
    r"\U00002600-\U000027BF"
    r"\U0001F300-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\u2600-\u27BF"
    r"\u2300-\u23FF"
    r"\u2B00-\u2BFF"
    r"\u26A0-\u26FF"
    r"]+\s*"
)

def get_or_create_category_sync(user_id: int, category_name: str) -> ExpenseCategory:
    """Получить категорию по имени или вернуть категорию 'Прочие расходы'"""
    original_category_name = category_name or ''
    category_name = EMOJI_PREFIX_RE.sub('', original_category_name).strip()
    normalized_category_name = category_name.lower() if category_name else ""
    if original_category_name and original_category_name != category_name:
        if category_name:
            logger.debug(
                f"Normalized category name from '{original_category_name}' to '{category_name}'"
            )
        else:
            logger.debug(
                f"Category name '{original_category_name}' normalized to empty string"
            )
    effective_name = category_name or original_category_name
    logger.info(f"Looking for category '{effective_name}' for user {user_id}")

    profile = get_or_create_user_profile_sync(user_id)
    
    # Словарь для сопоставления категорий из парсера с реальными категориями
    category_mapping = {
        'продукты': ['продукты', 'еда', 'супермаркет', 'магазин', 'groceries'],
        'кафе и рестораны': ['кафе', 'ресторан', 'рестораны', 'обед', 'кофе', 'cafe', 'restaurant'],
        'транспорт': ['транспорт', 'такси', 'метро', 'автобус', 'транспорт', 'transport', 'taxi', 'bus'],
        'автомобиль': ['автомобиль', 'машина', 'авто', 'бензин', 'дизель', 'заправка', 'азс', 'топливо', 'car'],
        'жилье': ['жилье', 'квартира', 'дом', 'аренда', 'housing'],
        'аптеки': ['аптека', 'аптеки', 'лекарства', 'таблетки', 'витамины', 'pharmacy'],
        'медицина': ['медицина', 'врач', 'доктор', 'больница', 'клиника', 'medicine', 'doctor'],
        'красота': ['красота', 'салон', 'парикмахерская', 'косметика', 'маникюр', 'beauty'],
        'спорт и фитнес': ['спорт', 'фитнес', 'тренажерный зал', 'йога', 'бассейн', 'sports', 'fitness'],
        'одежда и обувь': ['одежда', 'обувь', 'вещи', 'одежда', 'clothes', 'shoes'],
        'развлечения': ['развлечения', 'кино', 'театр', 'концерт', 'отдых', 'entertainment'],
        'образование': ['образование', 'курсы', 'учеба', 'обучение', 'education'],
        'подарки': ['подарки', 'подарок', 'цветы', 'букет', 'gifts'],
        'путешествия': ['путешествия', 'отпуск', 'поездка', 'тур', 'travel'],
        'коммунальные услуги и подписки': ['коммуналка', 'жкх', 'квартплата', 'свет', 'вода', 'газ', 'интернет', 'связь', 'телефон', 'подписка', 'utilities', 'utilities and subscriptions'],
        'прочие расходы': ['другое', 'прочее', 'разное', 'other'],
    }
    
    # Ищем среди категорий пользователя
    # Сначала точное совпадение (игнорируя эмодзи в начале)
    all_categories = ExpenseCategory.objects.filter(profile=profile)
    
    # Проверяем точное совпадение без учета эмодзи
    import re
    for cat in all_categories:
        # Проверяем оба языковых поля
        for field_name in ['name_ru', 'name_en']:
            field_value = getattr(cat, field_name, None)
            if not field_value:
                continue
            
            # Убираем эмодзи из начала названия для сравнения
            name_without_emoji = re.sub(r'^[\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+\s*', '', field_value)
            if name_without_emoji.lower() == category_name.lower():
                # Безопасное логирование для Windows
                safe_name = field_value.encode('ascii', 'ignore').decode('ascii').strip()
                if not safe_name:
                    safe_name = f"category with emoji (id={cat.id})"
                logger.info(f"Found exact match in {field_name}: {safe_name}")
                return cat
    
    # Если не нашли точное, ищем частичное совпадение
    # Например, "кафе" найдет "Кафе и рестораны"
    category_name_lower = category_name.lower()
    for cat in all_categories:
        # Проверяем оба языковых поля
        for field_name in ['name_ru', 'name_en']:
            field_value = getattr(cat, field_name, None)
            if not field_value:
                continue
                
            name_lower = field_value.lower()
            
            # Проверяем, содержит ли категория искомое название
            if category_name_lower in name_lower:
                safe_name = field_value.encode('ascii', 'ignore').decode('ascii').strip()
                if not safe_name:
                    safe_name = f"category with emoji (id={cat.id})"
                logger.info(f"Found partial match in {field_name}: {safe_name}")
                return cat
            
            # Проверяем каждое слово из искомой категории
            words = category_name_lower.split()
            if any(word in name_lower for word in words if len(word) > 3):
                safe_name = field_value.encode('ascii', 'ignore').decode('ascii').strip()
                if not safe_name:
                    safe_name = f"category with emoji (id={cat.id})"
                logger.info(f"Found word match in {field_name}: {safe_name}")
                return cat
    
    # Пробуем найти через словарь сопоставления
    category_name_lower = category_name.lower()
    for cat_group, keywords in category_mapping.items():
        if category_name_lower in keywords:
            # Ищем категорию пользователя, содержащую ключевое слово группы
            for keyword in [cat_group] + keywords:
                # Пробуем разные варианты поиска для лучшей совместимости с кириллицей
                # Ищем в обоих языковых полях
                category = ExpenseCategory.objects.filter(
                    profile=profile
                ).filter(
                    Q(name_ru__icontains=keyword) | 
                    Q(name_en__icontains=keyword) |
                    Q(name__icontains=keyword)  # Fallback на старое поле
                ).first()
                
                if category:
                    display_name = get_category_display_name(category, 'ru')
                    safe_name = display_name.encode('ascii', 'ignore').decode('ascii').strip()
                    if not safe_name:
                        safe_name = f"category with emoji (id={category.id})"
                    logger.info(f"Found category '{safe_name}' through mapping keyword '{keyword}'")
                    return category
    
    # Дополнительная проверка: если category_name это "кафе", ищем любую категорию со словом "кафе"
    if 'кафе' in category_name.lower() or 'cafe' in category_name.lower():
        for cat in all_categories:
            # Проверяем оба языковых поля
            name_ru = cat.name_ru or ''
            name_en = cat.name_en or ''
            if ('кафе' in name_ru.lower() or 'ресторан' in name_ru.lower() or
                'cafe' in name_en.lower() or 'restaurant' in name_en.lower()):
                display_name = get_category_display_name(cat, 'ru')
                safe_name = display_name.encode('ascii', 'ignore').decode('ascii').strip()
                if not safe_name:
                    safe_name = f"category with emoji (id={cat.id})"
                logger.info(f"Found category '{safe_name}' by cafe/restaurant keyword")
                return cat
    
    # Дополнительная попытка: ищем ближайшее совпадение по названию
    if normalized_category_name:
        candidate_map = {}
        for cat in all_categories:
            for field_name in ('name_ru', 'name_en', 'name'):
                field_value = getattr(cat, field_name, None)
                if not field_value:
                    continue
                sanitized_value = EMOJI_PREFIX_RE.sub('', field_value).strip().lower()
                if sanitized_value:
                    candidate_map[sanitized_value] = cat
        if candidate_map:
            close_matches = get_close_matches(normalized_category_name, list(candidate_map.keys()), n=1, cutoff=0.72)
            if close_matches:
                matched_key = close_matches[0]
                category = candidate_map[matched_key]
                display_name = get_category_display_name(category, 'ru')
                safe_name = display_name.encode('ascii', 'ignore').decode('ascii').strip() or f"category id={category.id}"
                logger.info(f"Found category '{safe_name}' by fuzzy match (input='{original_category_name}', matched='{matched_key}')")
                return category

    # Если категория не найдена, возвращаем "Прочие расходы" / "Other Expenses"
    logger.warning(f"Category '{category_name}' not found for user {user_id}, using default")

    # Сначала пытаемся найти существующую категорию "Прочие расходы" / "Other Expenses"
    other_category = ExpenseCategory.objects.filter(
        profile=profile
    ).filter(
        Q(name_ru__icontains='прочие') |
        Q(name_en__icontains='other') |
        Q(name__icontains='прочие') |  # Fallback на старое поле
        Q(name__icontains='other')     # Fallback на старое поле для EN
    ).first()

    if not other_category:
        # Если нет категории "Прочие расходы" / "Other Expenses", создаем её
        # Определяем язык пользователя для правильного имени категории
        user_lang = profile.language_code or 'ru'

        if user_lang == 'en':
            category_name_display = '💰 Other Expenses'
            original_lang = 'en'
        else:
            category_name_display = '💰 Прочие расходы'
            original_lang = 'ru'

        other_category, created = ExpenseCategory.objects.get_or_create(
            name=category_name_display,
            profile=profile,
            defaults={
                'icon': '💰',
                'name_ru': 'Прочие расходы',
                'name_en': 'Other Expenses',
                'original_language': original_lang,
                'is_translatable': True
            }
        )
        if created:
            logger.info(f"Created default category '{category_name_display}' for user {user_id} (lang: {user_lang})")

    return other_category


get_or_create_category = sync_to_async(get_or_create_category_sync)


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
    )
    
    # Force evaluation of queryset
    categories_count = categories.count()
    logger.info(f"get_user_categories for user {user_id}: found {categories_count} categories in DB")
    
    # Сортируем так, чтобы "Прочие расходы" были в конце
    categories_list = list(categories)
    regular_categories = []
    other_category = None
    
    for cat in categories_list:
        # Проверяем оба языковых поля для определения "Прочих расходов"
        name_ru = (cat.name_ru or '').lower()
        name_en = (cat.name_en or '').lower()
        name_old = cat.name.lower()
        
        if 'прочие расходы' in name_ru or 'other expenses' in name_en or 'прочие расходы' in name_old:
            other_category = cat
        else:
            regular_categories.append(cat)
    
    # Сортируем по алфавиту по отображаемому названию без эмодзи, с учетом языка профиля
    user_lang = profile.language_code or 'ru'
    try:
        regular_categories.sort(key=lambda c: (get_category_name_without_emoji(c, user_lang) or '').lower())
    except Exception:
        # На случай ошибок в данных — fallback по старому полю name
        regular_categories.sort(key=lambda c: (c.name or '').lower())

    # Возвращаем сначала отсортированные обычные категории, затем "Прочие расходы"
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
            
            # Определяем язык категории
            import re
            from bot.utils.language import get_user_language
            
            # Определяем, на каком языке название
            has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', name))
            has_latin = bool(re.search(r'[a-zA-Z]', name))
            
            # Получаем язык пользователя
            user_lang = get_user_language(user_id)
            
            # Определяем оригинальный язык категории
            if has_cyrillic and not has_latin:
                original_language = 'ru'
            elif has_latin and not has_cyrillic:
                original_language = 'en'
            else:
                original_language = user_lang  # По умолчанию язык пользователя
            
            # Проверяем, нет ли уже такой категории (по мультиязычным полям)
            from django.db.models import Q
            existing = ExpenseCategory.objects.filter(
                profile=profile
            ).filter(
                Q(name_ru=name) | Q(name_en=name)
            ).first()
            
            if existing:
                logger.warning(f"Category '{name}' already exists for user {user_id}")
                return existing, False
            
            # Создаем категорию с правильными мультиязычными полями
            category = ExpenseCategory.objects.create(
                profile=profile,
                icon=icon if icon and icon.strip() else '',
                name_ru=name if original_language == 'ru' else None,
                name_en=name if original_language == 'en' else None,
                original_language=original_language,
                # Пользовательские категории не переводим автоматически
                is_translatable=False
            )
            
            logger.info(f"Created category '{name}' (id: {category.id}) for user {user_id}")
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
    import re
    from bot.utils.language import get_user_language
    
    # Извлекаем иконку и текст
    emoji_pattern = r'^([\U0001F000-\U0001F9FF\U00002600-\U000027BF\U0001F300-\U0001F64F\U0001F680-\U0001F6FF]+)\s*'
    match = re.match(emoji_pattern, new_name)
    
    if match:
        icon = match.group(1)
        name_without_icon = new_name[len(match.group(0)):].strip()
    else:
        icon = ''
        name_without_icon = new_name.strip()
    
    # Определяем язык нового названия
    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', name_without_icon))
    has_latin = bool(re.search(r'[a-zA-Z]', name_without_icon))
    
    # Получаем текущую категорию для определения какие поля обновлять
    try:
        category = await sync_to_async(ExpenseCategory.objects.get)(
            id=category_id,
            profile__telegram_id=user_id
        )
    except ExpenseCategory.DoesNotExist:
        return False
    
    # Определяем какое поле обновлять
    if has_cyrillic and not has_latin:
        result = await update_category(user_id, category_id,
                                      name_ru=name_without_icon,
                                      icon=icon,
                                      original_language='ru',
                                      is_translatable=False)
    elif has_latin and not has_cyrillic:
        result = await update_category(user_id, category_id,
                                      name_en=name_without_icon,
                                      icon=icon,
                                      original_language='en',
                                      is_translatable=False)
    else:
        # Смешанный язык - обновляем поле исходного языка
        if category.original_language == 'en':
            result = await update_category(user_id, category_id,
                                         name_en=name_without_icon,
                                         icon=icon,
                                         original_language='en',
                                         is_translatable=False)
        else:
            result = await update_category(user_id, category_id,
                                         name_ru=name_without_icon,
                                         icon=icon,
                                         original_language='ru',
                                         is_translatable=False)
    
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
def update_default_categories_language(user_id: int, new_lang: str) -> bool:
    """
    Обновить язык стандартных категорий при смене языка пользователя
    
    Args:
        user_id: ID пользователя
        new_lang: Новый язык ('ru' или 'en')
        
    Returns:
        True если обновление прошло успешно
    """
    from bot.utils.language import translate_category_name
    from expenses.models import DEFAULT_CATEGORIES
    import re
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        # Получаем все категории пользователя
        user_categories = ExpenseCategory.objects.filter(profile=profile)
        
        # Паттерн для извлечения эмодзи
        emoji_pattern = re.compile(
            r'^['
            r'\U0001F000-\U0001F9FF'  # Основные эмодзи
            r'\U00002600-\U000027BF'  # Разные символы
            r'\U0001F300-\U0001F5FF'  # Символы и пиктограммы
            r'\U0001F600-\U0001F64F'  # Эмоции
            r'\U0001F680-\U0001F6FF'  # Транспорт и символы
            r'\u2600-\u27BF'          # Разные символы (короткий диапазон)
            r'\u2300-\u23FF'          # Технические символы
            r'\u2B00-\u2BFF'          # Стрелки и символы
            r'\u26A0-\u26FF'          # Предупреждающие знаки
            r']+'
        )
        
        # Создаем список стандартных категорий для сравнения
        default_names_ru = {name for name, _ in DEFAULT_CATEGORIES}
        default_names_en = {
            'Groceries', 'Cafes and Restaurants', 'Transport',
            'Car', 'Housing', 'Pharmacies', 'Medicine', 'Beauty',
            'Sports and Fitness', 'Clothes and Shoes', 'Entertainment',
            'Education', 'Gifts', 'Travel',
            'Utilities and Subscriptions', 'Other Expenses'
        }
        
        updated_count = 0
        for category in user_categories:
            # Извлекаем эмодзи и текст
            match = emoji_pattern.match(category.name)
            if match:
                emoji = match.group()
                text = category.name[len(emoji):].strip()
            else:
                text = category.name.strip()
                emoji = ''
            
            # Проверяем, является ли это стандартной категорией
            is_default = text in default_names_ru or text in default_names_en
            
            if is_default:
                # Переводим только стандартные категории
                if new_lang == 'ru':
                    # Меняем на русский
                    if category.name_ru:
                        # У нас уже есть русское название, просто меняем язык по умолчанию
                        category.original_language = 'ru'
                    else:
                        # Переводим из английского если нужно (text уже без эмодзи)
                        translated_text = translate_category_name(text, 'ru')
                        # Убираем эмодзи из перевода если он там есть (функция может вернуть с эмодзи)
                        import re
                        emoji_strip_pattern = re.compile(
                            r'^['
                            r'\U0001F000-\U0001F9FF'
                            r'\U00002600-\U000027BF'
                            r'\U0001F300-\U0001F5FF'
                            r'\U0001F600-\U0001F64F'
                            r'\U0001F680-\U0001F6FF'
                            r'\u2600-\u27BF'
                            r'\u2300-\u23FF'
                            r'\u2B00-\u2BFF'
                            r'\u26A0-\u26FF'
                            r']+\s*'
                        )
                        translated_text = emoji_strip_pattern.sub('', translated_text).strip()
                        category.name_ru = translated_text
                        # Сохраняем эмодзи если его нет
                        if not category.icon and emoji:
                            category.icon = emoji
                        category.original_language = 'ru'
                else:
                    # Меняем на английский
                    if category.name_en:
                        # У нас уже есть английское название
                        category.original_language = 'en'
                    else:
                        # Переводим из русского если нужно (text уже без эмодзи)
                        translated_text = translate_category_name(text, 'en')
                        # Убираем эмодзи из перевода если он там есть
                        import re
                        emoji_strip_pattern = re.compile(
                            r'^['
                            r'\U0001F000-\U0001F9FF'
                            r'\U00002600-\U000027BF'
                            r'\U0001F300-\U0001F5FF'
                            r'\U0001F600-\U0001F64F'
                            r'\U0001F680-\U0001F6FF'
                            r'\u2600-\u27BF'
                            r'\u2300-\u23FF'
                            r'\u2B00-\u2BFF'
                            r'\u26A0-\u26FF'
                            r']+\s*'
                        )
                        translated_text = emoji_strip_pattern.sub('', translated_text).strip()
                        category.name_en = translated_text
                        # Сохраняем эмодзи если его нет
                        if not category.icon and emoji:
                            category.icon = emoji
                        category.original_language = 'en'
                
                category.save()
                updated_count += 1
                logger.info(f"Updated category language for '{text}' to '{new_lang}' for user {user_id}")
        
        logger.info(f"Updated {updated_count} default categories for user {user_id} to language '{new_lang}'")
        return True
        
    except Profile.DoesNotExist:
        logger.error(f"Profile not found for user {user_id}")
        return False
    except Exception as e:
        logger.error(f"Error updating categories language for user {user_id}: {e}")
        return False


def create_default_categories_sync(user_id: int) -> bool:
    """Создать базовые категории для нового пользователя."""
    profile, created = Profile.objects.get_or_create(telegram_id=user_id)
    if created:
        logger.info(f"Created new profile for user {user_id}")

    # Проверяем количество категорий - должно быть минимум 16 для считать инициализированным
    # Это защищает от race condition когда создалась только "Прочие расходы"
    existing_count = ExpenseCategory.objects.filter(profile=profile).count()
    if existing_count >= 16:
        logger.debug(f"User {user_id} already has {existing_count} categories, skipping default creation")
        return False

    try:
        lang = profile.language_code or 'ru'

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
            from expenses.models import DEFAULT_CATEGORIES
            default_categories = DEFAULT_CATEGORIES

        # Если есть несколько категорий (например только "Прочие расходы" от fallback),
        # все равно создаем все остальные
        if existing_count > 0:
            logger.info(f"User {user_id} has only {existing_count} categories (likely from fallback), creating remaining defaults")
            # Получаем названия уже существующих категорий
            existing_names = set(
                ExpenseCategory.objects.filter(profile=profile)
                .values_list('name', flat=True)
            )
            # Создаем только те категории, которых еще нет
            categories_to_create = []
            for name, icon in default_categories:
                full_name = f"{icon} {name}"
                if full_name not in existing_names:
                    categories_to_create.append(
                        ExpenseCategory(
                            profile=profile,
                            name=full_name,
                            icon='',
                            is_active=True
                        )
                    )
            if categories_to_create:
                ExpenseCategory.objects.bulk_create(categories_to_create)
                logger.info(f"Created {len(categories_to_create)} missing default categories for user {user_id}")
        else:
            # Создаем все категории с нуля
            categories = [
                ExpenseCategory(
                    profile=profile,
                    name=f"{icon} {name}",
                    icon='',
                    is_active=True
                )
                for name, icon in default_categories
            ]
            ExpenseCategory.objects.bulk_create(categories)
            logger.info(f"Created all {len(categories)} default categories for user {user_id}")

        return True
    except Exception as exc:
        logger.error(f"Failed to create default categories for {user_id}: {exc}")
        return False


create_default_categories = sync_to_async(create_default_categories_sync)


@sync_to_async
def create_default_income_categories(user_id: int) -> bool:
    """
    Создать базовые категории доходов для нового пользователя

    Args:
        user_id: ID пользователя в Telegram

    Returns:
        True если категории созданы, False если уже существуют
    """
    from expenses.models import IncomeCategory, Profile, DEFAULT_INCOME_CATEGORIES

    try:
        profile = Profile.objects.get(telegram_id=user_id)
    except Profile.DoesNotExist:
        # Создаем профиль если его нет
        profile = Profile.objects.create(telegram_id=user_id)
        logger.info(f"Created new profile for user {user_id}")

    try:
        # Проверяем количество категорий доходов - должно быть минимум 10 для считать инициализированным
        # Это защищает от race condition когда создалась только одна категория как fallback
        existing_count = IncomeCategory.objects.filter(profile=profile).count()
        if existing_count >= 10:
            logger.debug(f"User {user_id} already has {existing_count} income categories, skipping default creation")
            return False

        # Определяем язык пользователя
        lang = profile.language_code or 'ru'

        # Базовые категории доходов с переводами
        if lang == 'en':
            default_income_categories = [
                ('💼 Salary', '💼'),
                ('🎁 Bonuses', '🎁'),
                ('💻 Freelance', '💻'),
                ('📈 Investments', '📈'),
                ('🏦 Bank Interest', '🏦'),
                ('🏠 Rent Income', '🏠'),
                ('💸 Refunds', '💸'),
                ('💳 Cashback', '💳'),
                ('🎉 Gifts', '🎉'),
                ('💰 Other Income', '💰'),
            ]
        else:
            # Используем категории по умолчанию из модели
            default_income_categories = DEFAULT_INCOME_CATEGORIES

        # Если есть несколько категорий (например только fallback категория),
        # все равно создаем все остальные
        if existing_count > 0:
            logger.info(f"User {user_id} has only {existing_count} income categories (likely from fallback), creating remaining defaults")
            # Получаем названия уже существующих категорий
            existing_names = set(
                IncomeCategory.objects.filter(profile=profile)
                .values_list('name', flat=True)
            )
            # Создаем только те категории, которых еще нет
            categories_to_create = []
            for name, icon in default_income_categories:
                # Для английских категорий эмодзи уже включен в name
                # Для русских категорий нужно добавить эмодзи к названию
                if lang == 'en':
                    category_name = name  # Эмодзи уже включен
                else:
                    category_name = f"{icon} {name}"  # Добавляем эмодзи к русскому названию

                if category_name not in existing_names:
                    categories_to_create.append(
                        IncomeCategory(
                            profile=profile,
                            name=category_name,
                            icon=icon,
                            is_active=True,
                            is_default=False
                        )
                    )

            if categories_to_create:
                IncomeCategory.objects.bulk_create(categories_to_create)
                logger.info(f"Created {len(categories_to_create)} missing default income categories for user {user_id}")
        else:
            # Создаем все категории доходов с нуля
            categories = []
            for name, icon in default_income_categories:
                # Для английских категорий эмодзи уже включен в name
                # Для русских категорий нужно добавить эмодзи к названию
                if lang == 'en':
                    category_name = name  # Эмодзи уже включен
                else:
                    category_name = f"{icon} {name}"  # Добавляем эмодзи к русскому названию

                category = IncomeCategory(
                    profile=profile,
                    name=category_name,
                    icon=icon,
                    is_active=True,
                    is_default=False
                )
                categories.append(category)

            IncomeCategory.objects.bulk_create(categories)
            logger.info(f"Created all {len(categories)} default income categories for user {user_id}")

        return True

    except Exception as e:
        logger.error(f"Error creating default income categories: {e}")
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
            
            # Используем prefetch_related для загрузки всех keywords одним запросом
            for cat in ExpenseCategory.objects.filter(profile=profile).prefetch_related('categorykeyword_set'):
                keywords = list(cat.categorykeyword_set.values_list('keyword', flat=True))
                
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


