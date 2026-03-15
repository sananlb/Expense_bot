"""
Сервис для работы с категориями расходов
"""
from typing import List, Optional, Set
from expenses.models import ExpenseCategory, IncomeCategory, Profile, CategoryKeyword
from asgiref.sync import sync_to_async
from django.db.models import Sum, Count, Q
from bot.utils.db_utils import get_or_create_user_profile_sync
from bot.utils.category_helpers import get_category_display_name, get_category_name_without_emoji
from difflib import get_close_matches
import logging
# ВАЖНО: Импортируем из централизованного модуля (включает ZWJ для композитных эмодзи)
from bot.utils.emoji_utils import EMOJI_PREFIX_RE, normalize_category_for_matching, strip_leading_emoji
from bot.utils.logging_safe import log_safe_id, summarize_text

logger = logging.getLogger(__name__)


# =============================================================================
# Category mapping for parser-to-category matching
# =============================================================================

CATEGORY_MAPPING = {
    'продукты': ['продукты', 'еда', 'супермаркет', 'магазин', 'groceries', 'food', 'supermarket'],
    'кафе и рестораны': ['кафе', 'ресторан', 'рестораны', 'обед', 'кофе', 'cafe', 'cafes', 'restaurant', 'restaurants'],
    'транспорт': ['транспорт', 'такси', 'метро', 'автобус', 'транспорт', 'transport', 'taxi', 'bus', 'metro'],
    'автомобиль': ['автомобиль', 'машина', 'авто', 'бензин', 'дизель', 'заправка', 'азс', 'топливо', 'мойка', 'автомойка', 'car', 'gas station', 'fuel', 'petrol'],
    'жилье': ['жилье', 'квартира', 'дом', 'аренда', 'housing', 'rent', 'apartment'],
    'аптеки': ['аптека', 'аптеки', 'лекарства', 'таблетки', 'витамины', 'зубная паста', 'зубная', 'toothpaste', 'pharmacy', 'pharmacies', 'medicine'],
    'медицина': ['медицина', 'врач', 'доктор', 'больница', 'клиника', 'medicine', 'doctor', 'hospital', 'clinic'],
    'красота': ['красота', 'салон', 'парикмахерская', 'косметика', 'маникюр', 'beauty', 'salon', 'cosmetics'],
    'спорт и фитнес': ['спорт', 'фитнес', 'тренажерный зал', 'йога', 'бассейн', 'sports', 'fitness', 'gym', 'yoga'],
    'одежда и обувь': ['одежда', 'обувь', 'вещи', 'одежда', 'clothes', 'clothing', 'shoes', 'apparel'],
    'развлечения': ['развлечения', 'кино', 'театр', 'концерт', 'отдых', 'entertainment'],
    'образование': ['образование', 'курсы', 'учеба', 'обучение', 'education'],
    'подарки': ['подарки', 'подарок', 'цветы', 'букет', 'gifts'],
    'путешествия': ['путешествия', 'отпуск', 'поездка', 'тур', 'travel'],
    'коммуналка и подписки': [
        'коммуналка', 'жкх', 'квартплата', 'свет', 'вода', 'газ',
        'интернет', 'связь', 'телефон', 'подписка',
        'коммунальные услуги и подписки',
        'utilities', 'utilities and subscriptions'
    ],
    'прочие расходы': ['другое', 'прочее', 'разное', 'other'],
}


# =============================================================================
# Helper functions for get_or_create_category_sync
# =============================================================================

def _safe_category_name(cat, lang_code: str = 'ru') -> str:
    """Get safe ASCII-friendly category name for logging."""
    display_name = get_category_display_name(cat, lang_code)
    safe_name = display_name.encode('ascii', 'ignore').decode('ascii').strip()
    return safe_name if safe_name else f"category id={cat.id}"


def _find_exact_match(categories, category_name: str, lang_code: str):
    """Find category by exact name match (ignoring emoji prefix)."""
    category_name_lower = category_name.lower()

    for cat in categories:
        for field_name in ['name_ru', 'name_en']:
            field_value = getattr(cat, field_name, None)
            if not field_value:
                continue

            name_without_emoji = strip_leading_emoji(field_value)
            if name_without_emoji.lower() == category_name_lower:
                logger.info("Found exact category match in %s: category_id=%s", field_name, cat.id)
                return cat
    return None


def _find_partial_match(categories, category_name: str, lang_code: str):
    """Find category by partial name match."""
    category_name_lower = category_name.lower()

    for cat in categories:
        for field_name in ['name_ru', 'name_en']:
            field_value = getattr(cat, field_name, None)
            if not field_value:
                continue

            name_lower = field_value.lower()

            # Check if category contains the searched name
            if category_name_lower in name_lower:
                logger.info("Found partial category match in %s: category_id=%s", field_name, cat.id)
                return cat

            # Check each word from searched category
            words = category_name_lower.split()
            if any(word in name_lower for word in words if len(word) > 3):
                logger.info("Found word category match in %s: category_id=%s", field_name, cat.id)
                return cat
    return None


def _find_by_mapping(profile, category_name: str, lang_code: str):
    """Find category through category mapping keywords."""
    category_name_lower = category_name.lower()

    for cat_group, keywords in CATEGORY_MAPPING.items():
        if category_name_lower in keywords:
            for keyword in [cat_group] + keywords:
                category = ExpenseCategory.objects.filter(
                    profile=profile
                ).filter(
                    Q(name_ru__icontains=keyword) |
                    Q(name_en__icontains=keyword) |
                    Q(name__icontains=keyword)
                ).first()

                if category:
                    logger.info(
                        "Found category through mapping: category_id=%s keyword=%s",
                        category.id,
                        summarize_text(keyword),
                    )
                    return category
    return None


def _find_cafe_restaurant(categories, category_name: str, lang_code: str):
    """Special search for cafe/restaurant categories."""
    name_lower = category_name.lower()
    if 'кафе' not in name_lower and 'cafe' not in name_lower:
        return None

    for cat in categories:
        name_ru = (cat.name_ru or '').lower()
        name_en = (cat.name_en or '').lower()

        if ('кафе' in name_ru or 'ресторан' in name_ru or
            'cafe' in name_en or 'restaurant' in name_en):
            logger.info("Found cafe/restaurant category: category_id=%s", cat.id)
            return cat
    return None


def _find_fuzzy_match(categories, category_name: str, lang_code: str):
    """Find category by fuzzy string matching."""
    normalized = category_name.lower()
    if not normalized:
        return None

    candidate_map = {}
    for cat in categories:
        for field_name in ('name_ru', 'name_en', 'name'):
            field_value = getattr(cat, field_name, None)
            if not field_value:
                continue
            sanitized_value = EMOJI_PREFIX_RE.sub('', field_value).strip().lower()
            if sanitized_value:
                candidate_map[sanitized_value] = cat

    if not candidate_map:
        return None

    close_matches = get_close_matches(normalized, list(candidate_map.keys()), n=1, cutoff=0.72)
    if close_matches:
        matched_key = close_matches[0]
        category = candidate_map[matched_key]
        logger.info(
            "Found fuzzy category match: category_id=%s matched=%s",
            category.id,
            summarize_text(matched_key),
        )
        return category
    return None


def _get_or_create_default_category(profile, user_id: int):
    """Get or create the 'Other Expenses' default category."""
    user_lang = profile.language_code or 'ru'

    # Try to find existing "Other Expenses" category
    other_category = ExpenseCategory.objects.filter(
        profile=profile
    ).filter(
        Q(name_ru__icontains='прочие') |
        Q(name_en__icontains='other') |
        Q(name__icontains='прочие') |
        Q(name__icontains='other')
    ).first()

    if other_category:
        return other_category

    # Create new default category
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
        logger.info(
            "Created default category %s for %s (lang=%s)",
            summarize_text(category_name_display),
            log_safe_id(user_id, "user"),
            user_lang,
        )

    return other_category


def get_or_create_category_sync(user_id: int, category_name: str) -> ExpenseCategory:
    """
    Get category by name or return 'Other Expenses' default category.

    Search order:
    1. Exact match (ignoring emoji prefix)
    2. Partial match (substring)
    3. Category mapping keywords
    4. Cafe/restaurant special search
    5. Fuzzy string matching
    6. Fallback to 'Other Expenses'
    """
    # Normalize category name
    original_category_name = category_name or ''
    category_name = EMOJI_PREFIX_RE.sub('', original_category_name).strip()

    if original_category_name and original_category_name != category_name:
        logger.debug(
            "Normalized category name from %s to %s",
            summarize_text(original_category_name),
            summarize_text(category_name),
        )

    effective_name = category_name or original_category_name
    logger.info(
        "Looking for category %s for %s",
        summarize_text(effective_name),
        log_safe_id(user_id, "user"),
    )

    profile = get_or_create_user_profile_sync(user_id)
    lang_code = profile.language_code if profile and profile.language_code else 'ru'

    # Get all user categories once
    all_categories = list(ExpenseCategory.objects.filter(profile=profile))

    # Search strategies in order of priority
    result = _find_exact_match(all_categories, category_name, lang_code)
    if result:
        return result

    result = _find_partial_match(all_categories, category_name, lang_code)
    if result:
        return result

    result = _find_by_mapping(profile, category_name, lang_code)
    if result:
        return result

    result = _find_cafe_restaurant(all_categories, category_name, lang_code)
    if result:
        return result

    result = _find_fuzzy_match(all_categories, category_name, lang_code)
    if result:
        return result

    # Category not found - return default
    logger.warning(
        "Category %s not found for %s, using default",
        summarize_text(category_name),
        log_safe_id(user_id, "user"),
    )
    return _get_or_create_default_category(profile, user_id)


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
    logger.info(
        "get_user_categories for %s: found %s categories in DB",
        log_safe_id(user_id, "user"),
        categories_count,
    )
    
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
    from bot.utils.category_validators import (
        validate_category_name, detect_category_language,
        check_category_duplicate, validate_category_limit,
    )

    @sync_to_async
    def _create_category():
        with transaction.atomic():
            try:
                profile = Profile.objects.get(telegram_id=user_id)
            except Profile.DoesNotExist:
                profile = Profile.objects.create(telegram_id=user_id)

            validate_category_limit(ExpenseCategory, profile)

            clean_name = validate_category_name((name or '').strip())

            # Определяем язык категории
            user_lang = getattr(profile, 'language_code', None) or 'ru'
            original_language = detect_category_language(clean_name, user_lang)

            # Проверяем, нет ли уже такой категории
            display_name = f"{icon} {clean_name}".strip() if icon and icon.strip() else clean_name
            if check_category_duplicate(ExpenseCategory, profile, clean_name, display_name):
                raise ValueError("Категория с таким названием уже существует")

            # Создаем категорию с правильными мультиязычными полями
            category = ExpenseCategory.objects.create(
                profile=profile,
                icon=icon if icon and icon.strip() else '',
                name_ru=clean_name if original_language == 'ru' else None,
                name_en=clean_name if original_language == 'en' else None,
                original_language=original_language,
                # Пользовательские категории не переводим автоматически
                is_translatable=False
            )

            logger.info(
                "Created category %s (id=%s) for %s",
                summarize_text(clean_name),
                category.id,
                log_safe_id(user_id, "user"),
            )
            return category

    return await _create_category()


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
    """Обновить название категории.

    Raises:
        ValueError: если название невалидно, дубликат найден или категория не существует.
    """
    from bot.utils.category_validators import (
        validate_category_name, check_category_duplicate, detect_category_language,
    )

    # Извлекаем иконку и текст (поддерживает композитные эмодзи с ZWJ)
    match = EMOJI_PREFIX_RE.match(new_name)

    if match:
        icon = match.group(0).strip()
        name_without_icon = new_name[len(match.group(0)):].strip()
    else:
        icon = ''
        name_without_icon = new_name.strip()

    # Валидация имени (не требует ORM — можно в async контексте)
    name_without_icon = validate_category_name(name_without_icon)

    @sync_to_async
    def _update_category_name_sync():
        try:
            category = ExpenseCategory.objects.get(
                id=category_id,
                profile__telegram_id=user_id
            )
        except ExpenseCategory.DoesNotExist:
            raise ValueError("Категория не найдена")

        # Проверяем дубликаты перед обновлением
        display_name = f"{icon} {name_without_icon}".strip() if icon else name_without_icon
        if check_category_duplicate(
            ExpenseCategory, category.profile, name_without_icon, display_name,
            exclude_id=category_id,
        ):
            raise ValueError("Категория с таким названием уже существует")

        # Определяем язык нового названия
        original_language = detect_category_language(
            name_without_icon,
            category.original_language or 'ru',
        )

        # Определяем какое поле обновлять
        if original_language == 'ru':
            category.name_ru = name_without_icon
            category.original_language = 'ru'
        elif original_language == 'en':
            category.name_en = name_without_icon
            category.original_language = 'en'
        else:
            # Смешанный язык — сохраняем в поле текущего языка категории
            if category.original_language == 'en':
                category.name_en = name_without_icon
                category.original_language = 'en'
            else:
                category.name_ru = name_without_icon
                category.original_language = 'ru'

        category.icon = icon
        category.is_translatable = False
        category.save()
        return True

    return await _update_category_name_sync()


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
            logger.info("Deleted category %s for %s", category_id, log_safe_id(user_id, "user"))
        return True
    except ExpenseCategory.DoesNotExist:
        logger.warning("Category %s not found for %s", category_id, log_safe_id(user_id, "user"))
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
    from expenses.models import DEFAULT_CATEGORIES, DEFAULT_INCOME_CATEGORIES
    import re
    
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        
        expense_categories = ExpenseCategory.objects.filter(profile=profile)
        income_categories = IncomeCategory.objects.filter(profile=profile)

        # Используем централизованный EMOJI_PREFIX_RE (включает ZWJ для композитных эмодзи)
        
        default_names_ru = {name for name, _ in DEFAULT_CATEGORIES}
        default_names_en = {
            'Groceries', 'Cafes and Restaurants', 'Transport',
            'Car', 'Housing', 'Pharmacies', 'Medicine', 'Beauty',
            'Sports and Fitness', 'Clothes and Shoes', 'Entertainment',
            'Education', 'Gifts', 'Travel',
            'Utilities and Subscriptions', 'Savings', 'Other Expenses'
        }
        default_income_names_ru = {name for name, _ in DEFAULT_INCOME_CATEGORIES}
        default_income_names_en = {
            'Salary', 'Bonuses', 'Freelance', 'Investments',
            'Bank Interest', 'Rent Income', 'Refunds',
            'Gifts', 'Other Income'
        }
        
        def split_name(raw_name: str) -> tuple[str, str]:
            """Разделяет название на эмодзи и текст (поддерживает композитные эмодзи с ZWJ)"""
            raw_name = raw_name or ''
            match = EMOJI_PREFIX_RE.match(raw_name)
            if match:
                emoji = match.group().strip()  # Эмодзи без trailing пробелов
                text = raw_name[len(match.group()):].strip()
            else:
                emoji = ''
                text = raw_name.strip()
            return emoji, text
        
        def update_queryset(queryset, default_ru, default_en, category_type: str) -> int:
            updated = 0
            for category in queryset:
                emoji, text = split_name(category.name)
                if text not in default_ru and text not in default_en:
                    continue

                # ВСЕГДА заполняем оба языка при смене языка
                if new_lang == 'ru':
                    # Переключаемся на русский
                    if not category.name_ru:
                        # Переводим с английского если есть, иначе с текущего text
                        source_text = category.name_en or text
                        translated_text = translate_category_name(source_text, 'ru')
                        translated_text = strip_leading_emoji(translated_text)
                        category.name_ru = translated_text

                    # Если нет английского - создаём перевод
                    if not category.name_en:
                        source_text = category.name_ru or text
                        translated_text = translate_category_name(source_text, 'en')
                        translated_text = strip_leading_emoji(translated_text)
                        category.name_en = translated_text

                    category.original_language = 'ru'
                    if not category.icon and emoji:
                        category.icon = emoji
                else:
                    # Переключаемся на английский
                    if not category.name_en:
                        # Переводим с русского если есть, иначе с текущего text
                        source_text = category.name_ru or text
                        translated_text = translate_category_name(source_text, 'en')
                        translated_text = strip_leading_emoji(translated_text)
                        category.name_en = translated_text

                    # Если нет русского - создаём перевод
                    if not category.name_ru:
                        source_text = category.name_en or text
                        translated_text = translate_category_name(source_text, 'ru')
                        translated_text = strip_leading_emoji(translated_text)
                        category.name_ru = translated_text

                    category.original_language = 'en'
                    if not category.icon and emoji:
                        category.icon = emoji

                category.save()
                updated += 1
                logger.info(
                    "Updated %s category language for %s to %s for %s",
                    category_type,
                    summarize_text(text),
                    new_lang,
                    log_safe_id(user_id, "user"),
                )
            return updated
        
        expense_updated = update_queryset(expense_categories, default_names_ru, default_names_en, 'expense')
        income_updated = update_queryset(income_categories, default_income_names_ru, default_income_names_en, 'income')
        total_updated = expense_updated + income_updated
        
        logger.info(
            "Updated %s default categories for %s to language %s (expenses=%s, incomes=%s)",
            total_updated,
            log_safe_id(user_id, "user"),
            new_lang,
            expense_updated,
            income_updated,
        )
        return True
        
    except Profile.DoesNotExist:
        logger.error("Profile not found for %s", log_safe_id(user_id, "user"))
        return False
    except Exception as e:
        logger.error("Error updating categories language for %s: %s", log_safe_id(user_id, "user"), e)
        return False


def create_default_categories_sync(user_id: int) -> bool:
    """Создать базовые категории для нового пользователя."""
    profile, created = Profile.objects.get_or_create(telegram_id=user_id)
    if created:
        logger.info("Created new profile for %s", log_safe_id(user_id, "user"))

    # Проверяем количество категорий - защищаемся от race conditions, когда создалась только "Прочие расходы"
    existing_count = ExpenseCategory.objects.filter(profile=profile).count()

    try:
        lang = profile.language_code or 'ru'

        # Категории с ОБОИМИ языками сразу
        # Формат: (name_ru, name_en, icon)
        default_categories = [
            ('Продукты', 'Groceries', '🛒'),
            ('Кафе и рестораны', 'Cafes and Restaurants', '🍽️'),
            ('Транспорт', 'Transport', '🚕'),
            ('Автомобиль', 'Car', '🚗'),
            ('Жилье', 'Housing', '🏠'),
            ('Аптеки', 'Pharmacies', '💊'),
            ('Медицина', 'Medicine', '🏥'),
            ('Красота', 'Beauty', '💄'),
            ('Спорт и фитнес', 'Sports and Fitness', '🏃'),
            ('Одежда и обувь', 'Clothes and Shoes', '👔'),
            ('Развлечения', 'Entertainment', '🎭'),
            ('Образование', 'Education', '📚'),
            ('Подарки', 'Gifts', '🎁'),
            ('Путешествия', 'Travel', '✈️'),
            ('Коммуналка и подписки', 'Utilities and Subscriptions', '📱'),
            ('Накопления', 'Savings', '💎'),
            ('Прочие расходы', 'Other Expenses', '💰')
        ]

        required_count = len(default_categories)
        if existing_count >= required_count:
            logger.debug(
                "%s already has %s categories, skipping default creation",
                log_safe_id(user_id, "user"),
                existing_count,
            )
            return False

        # Если есть несколько категорий (например только "Прочие расходы" от fallback),
        # все равно создаем все остальные
        if existing_count > 0:
            logger.info(
                "%s has only %s categories (likely from fallback), creating remaining defaults",
                log_safe_id(user_id, "user"),
                existing_count,
            )
            # Получаем названия уже существующих категорий по мультиязычным полям
            existing_categories = ExpenseCategory.objects.filter(profile=profile)

            # Формируем сет существующих названий в зависимости от языка
            existing_names = set()
            for cat in existing_categories:
                if lang == 'ru' and cat.name_ru:
                    existing_names.add(cat.name_ru)
                elif lang == 'en' and cat.name_en:
                    existing_names.add(cat.name_en)
                # Fallback для старых категорий без мультиязычных полей
                elif cat.name:
                    # Убираем ВСЕ эмодзи из старого названия для сравнения
                    name_without_emoji = EMOJI_PREFIX_RE.sub('', cat.name).strip()
                    existing_names.add(name_without_emoji)

            # Создаем только те категории, которых еще нет
            categories_to_create = []
            for name_ru, name_en, icon in default_categories:
                # Проверяем оба языка для избежания дубликатов
                if name_ru not in existing_names and name_en not in existing_names:
                    # name для обратной совместимости зависит от языка пользователя
                    if lang == 'en':
                        full_name = f"{icon} {name_en}"
                    else:
                        full_name = f"{icon} {name_ru}"

                    categories_to_create.append(
                        ExpenseCategory(
                            profile=profile,
                            name=full_name,
                            name_ru=name_ru,
                            name_en=name_en,
                            original_language=lang,
                            is_translatable=True,
                            icon=icon,
                            is_active=True
                        )
                    )
            if categories_to_create:
                ExpenseCategory.objects.bulk_create(categories_to_create)
                logger.info(
                    "Created %s missing default categories for %s",
                    len(categories_to_create),
                    log_safe_id(user_id, "user"),
                )
        else:
            # Создаем все категории с нуля
            categories = []
            for name_ru, name_en, icon in default_categories:
                # name для обратной совместимости зависит от языка пользователя
                if lang == 'en':
                    full_name = f"{icon} {name_en}"
                else:
                    full_name = f"{icon} {name_ru}"

                categories.append(
                    ExpenseCategory(
                        profile=profile,
                        name=full_name,
                        name_ru=name_ru,
                        name_en=name_en,
                        original_language=lang,
                        is_translatable=True,
                        icon=icon,
                        is_active=True
                    )
                )
            ExpenseCategory.objects.bulk_create(categories)
            logger.info("Created all %s default categories for %s", len(categories), log_safe_id(user_id, "user"))

        return True
    except Exception as exc:
        logger.error("Failed to create default categories for %s: %s", log_safe_id(user_id, "user"), exc)
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
        logger.info("Created new profile for %s", log_safe_id(user_id, "user"))

    try:
        # Количество уже существующих категорий. Нужно чтобы добавить только недостающие.
        existing_count = IncomeCategory.objects.filter(profile=profile).count()

        # Определяем язык пользователя
        lang = profile.language_code or 'ru'

        # Базовые категории доходов с ОБОИМИ языками
        # Формат: (name_ru, name_en, icon)
        # original_language будет установлен в зависимости от языка пользователя
        default_income_categories = [
            ('Зарплата', 'Salary', '💼'),
            ('Премии и бонусы', 'Bonuses', '🎁'),
            ('Фриланс', 'Freelance', '💻'),
            ('Инвестиции', 'Investments', '📈'),
            ('Проценты по вкладам', 'Bank Interest', '🏦'),
            ('Аренда недвижимости', 'Rent Income', '🏠'),
            ('Возвраты и компенсации', 'Refunds', '💸'),
            ('Подарки', 'Gifts', '🎉'),
            ('Прочие доходы', 'Other Income', '💰'),
        ]

        required_count = len(default_income_categories)
        if existing_count >= required_count:
            logger.debug(
                "%s already has %s income categories, skipping default creation",
                log_safe_id(user_id, "user"),
                existing_count,
            )
            return False

        # Если есть несколько категорий (например только fallback категория),
        # все равно создаем все остальные
        if existing_count > 0:
            logger.info(
                "%s has only %s income categories (likely from fallback), creating remaining defaults",
                log_safe_id(user_id, "user"),
                existing_count,
            )
            # Получаем названия уже существующих категорий
            existing_names = set(
                IncomeCategory.objects.filter(profile=profile)
                .values_list('name', flat=True)
            )
            # Создаем только те категории, которых еще нет
            categories_to_create = []
            for name_ru, name_en, icon in default_income_categories:
                # name для обратной совместимости зависит от языка пользователя
                if lang == 'en':
                    category_name = f"{icon} {name_en}"
                else:
                    category_name = f"{icon} {name_ru}"

                if category_name not in existing_names:
                    categories_to_create.append(
                        IncomeCategory(
                            profile=profile,
                            name=category_name,
                            name_ru=name_ru,
                            name_en=name_en,
                            original_language=lang,  # Используем язык пользователя
                            is_translatable=True,
                            icon=icon,
                            is_active=True,
                            is_default=False
                        )
                    )

            if categories_to_create:
                IncomeCategory.objects.bulk_create(categories_to_create)
                logger.info(
                    "Created %s missing default income categories for %s",
                    len(categories_to_create),
                    log_safe_id(user_id, "user"),
                )
        else:
            # Создаем все категории доходов с нуля
            categories = []
            for name_ru, name_en, icon in default_income_categories:
                # name для обратной совместимости зависит от языка пользователя
                if lang == 'en':
                    category_name = f"{icon} {name_en}"
                else:
                    category_name = f"{icon} {name_ru}"

                category = IncomeCategory(
                    profile=profile,
                    name=category_name,
                    name_ru=name_ru,
                    name_en=name_en,
                    original_language=lang,  # Используем язык пользователя
                    is_translatable=True,
                    icon=icon,
                    is_active=True,
                    is_default=False
                )
                categories.append(category)

            IncomeCategory.objects.bulk_create(categories)
            logger.info(
                "Created all %s default income categories for %s",
                len(categories),
                log_safe_id(user_id, "user"),
            )

        return True

    except Exception as e:
        logger.error("Error creating default income categories for %s: %s", log_safe_id(user_id, "user"), e)
        return False


@sync_to_async
def migrate_categories_with_emojis():
    """Мигрировать существующие категории - добавить эмодзи в поле name"""
    from expenses.models import ExpenseCategory
    
    # Получаем все категории без эмодзи в начале названия
    categories = ExpenseCategory.objects.all()
    
    for category in categories:
        # Проверяем, есть ли уже эмодзи в начале (поддерживает композитные эмодзи с ZWJ)
        if not EMOJI_PREFIX_RE.match(category.name):
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
    """
    Добавить ключевое слово к категории.

    ВАЖНО: Ключевые слова должны быть уникальными - одно слово может быть только в одной категории!
    Если слово уже существует в другой категории пользователя, оно будет удалено оттуда.
    """
    try:
        category = ExpenseCategory.objects.select_related('profile').get(
            id=category_id,
            profile__telegram_id=user_id
        )

        keyword_lower = keyword.lower().strip()

        # ШАБЛОН УНИКАЛЬНОСТИ: Удаляем это слово из ВСЕХ категорий пользователя
        deleted = CategoryKeyword.objects.filter(
            category__profile=category.profile,
            keyword=keyword_lower
        ).delete()

        if deleted[0] > 0:
            logger.info(
                "Removed keyword %s from %s other categories to maintain uniqueness",
                summarize_text(keyword),
                deleted[0],
            )

        # Добавляем слово в целевую категорию
        CategoryKeyword.objects.create(
            category=category,
            keyword=keyword_lower
        )
        logger.info("Added keyword %s to category %s", summarize_text(keyword), category_id)
        return True

    except ExpenseCategory.DoesNotExist:
        logger.error("Category %s not found for %s", category_id, log_safe_id(user_id, "user"))
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
            logger.info("Removed keyword %s from category %s", summarize_text(keyword), category_id)
            return True
        else:
            logger.warning("Keyword %s not found in category %s", summarize_text(keyword), category_id)
            return False
            
    except ExpenseCategory.DoesNotExist:
        logger.error("Category %s not found for %s", category_id, log_safe_id(user_id, "user"))
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
        logger.error("Category %s not found for %s", category_id, log_safe_id(user_id, "user"))
        return []


@sync_to_async
def auto_learn_keywords(user_id: int) -> dict:
    """
    Автоматически обучаться на основе трат пользователя.
    Анализирует описания трат и добавляет часто встречающиеся слова
    как ключевые слова к соответствующим категориям.

    ВАЖНО: Ключевые слова должны быть уникальными - одно слово может быть только в одной категории!
    Если слово уже существует в другой категории, оно будет удалено оттуда.
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
        total_removed = 0

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
                    # ШАБЛОН УНИКАЛЬНОСТИ: Удаляем это слово из ВСЕХ категорий пользователя
                    deleted = CategoryKeyword.objects.filter(
                        category__profile=profile,
                        keyword=word
                    ).delete()

                    if deleted[0] > 0:
                        total_removed += deleted[0]
                        logger.debug(
                            "Removed keyword %s from %s other categories during auto-learn",
                            summarize_text(word),
                            deleted[0],
                        )

                    # Добавляем слово в целевую категорию
                    CategoryKeyword.objects.create(
                        category=category,
                        keyword=word
                    )
                    added.append(word)

                if added:
                    added_keywords[category_name] = added

        if total_removed > 0:
            logger.info("Auto-learn: removed %s duplicate keywords to maintain uniqueness", total_removed)

        return added_keywords
        
    except Profile.DoesNotExist:
        logger.error("Profile not found for %s", log_safe_id(user_id, "user"))
        return {}


async def optimize_keywords_for_new_category(user_id: int, new_category_id: int):
    """
    DEPRECATED: Эта функция не используется в production коде.

    Оптимизирует ключевые слова для новой категории используя AI.
    Требует переработки для использования ai_selector вместо устаревшего gemini_service.

    TODO: Если понадобится эта функциональность, переписать с использованием:
          - bot.services.ai_selector.get_service() вместо gemini_service
          - Универсальный AI провайдер (DeepSeek/Qwen/OpenAI)
    """
    logger.warning(
        "optimize_keywords_for_new_category called for %s, category %s. "
        "This function is deprecated and does nothing. Use manual keyword management instead.",
        log_safe_id(user_id, "user"),
        new_category_id,
    )


async def learn_from_category_change(user_id: int, expense_id: int, new_category_id: int, description: str, old_category_id: int = None):
    """
    Обучается на основе изменения категории расхода пользователем.

    ВАЖНО: Ключевые слова должны быть уникальными - одно слово может быть только в одной категории!

    Логика:
    1. Извлекаем слова из описания траты
    2. Удаляем эти слова из ВСЕХ категорий пользователя (включая старую категорию)
    3. Добавляем эти слова в новую категорию

    Args:
        user_id: ID пользователя
        expense_id: ID траты
        new_category_id: ID новой категории
        description: Описание траты
        old_category_id: ID старой категории (optional)
    """
    try:
        from expenses.models import Expense, Profile
        from expense_bot.celery_tasks import extract_words_from_description, cleanup_old_keywords

        @sync_to_async
        def update_keywords_for_category_change():
            # Получаем категорию и профиль
            new_category = ExpenseCategory.objects.get(id=new_category_id)
            profile = Profile.objects.get(telegram_id=user_id)

            # Извлекаем слова из описания используя общую функцию
            words = extract_words_from_description(description)

            # ШАБЛОН 1: Удаляем эти слова из ВСЕХ категорий пользователя
            removed_count = 0
            for word in words:
                if len(word) >= 3:  # Минимум 3 буквы
                    # Удаляем слово из всех категорий пользователя
                    deleted = CategoryKeyword.objects.filter(
                        category__profile=profile,
                        keyword=word.lower()
                    ).delete()
                    if deleted[0] > 0:
                        removed_count += deleted[0]
                        logger.debug(
                            "Removed keyword %s from %s categories",
                            summarize_text(word),
                            deleted[0],
                        )

            # ШАБЛОН 2: Добавляем слова в новую категорию
            added_keywords = []
            any_created = False  # Флаг что хотя бы одно новое слово создано
            for word in words:
                if len(word) >= 3:  # Минимум 3 буквы
                    keyword, created = CategoryKeyword.objects.get_or_create(
                        category=new_category,
                        keyword=word.lower(),
                        defaults={'usage_count': 1}
                    )

                    if created:
                        added_keywords.append(word)
                        any_created = True
                    else:
                        # Увеличиваем счетчик использований
                        # last_used обновляется автоматически (auto_now=True)
                        keyword.usage_count += 1
                        keyword.save()

            # Очистка старых ключевых слов только если добавили новые
            if any_created:
                cleanup_old_keywords(profile_id=profile.id, is_income=False)

            return added_keywords, removed_count

        added, removed = await update_keywords_for_category_change()

        if added:
            logger.info(
                "Learned %s keywords for category %s from manual change (expense %s)",
                len(added),
                new_category_id,
                expense_id,
            )
        if removed > 0:
            logger.info("Removed %s duplicate keywords from other categories", removed)

    except Exception as e:
        logger.error("Error learning from category change for %s: %s", log_safe_id(user_id, "user"), e)
