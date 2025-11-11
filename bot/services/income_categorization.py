"""
AI категоризация доходов - использует общую логику из ai_categorization.py
"""
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
from asgiref.sync import sync_to_async

from expenses.models import IncomeCategory, Income, IncomeCategoryKeyword, Profile
from .ai_categorization import categorizer as base_categorizer
from bot.utils.category_helpers import get_category_display_name
from bot.utils.income_category_definitions import (
    get_income_category_display_name as get_income_category_display_for_key,
    normalize_income_category_key,
    strip_leading_emoji,
)

logger = logging.getLogger(__name__)


def ensure_unique_income_keyword(
    profile: Profile,
    category: IncomeCategory,
    word: str,
    defaults: Optional[Dict[str, Any]] = None
) -> tuple[IncomeCategoryKeyword, bool, int]:
    """
    Гарантирует строгую уникальность ключевого слова дохода.

    ВАЖНО: Одно слово может быть только в ОДНОЙ категории дохода пользователя!

    Алгоритм:
    1. Нормализует слово (lower, strip)
    2. УДАЛЯЕТ слово из ВСЕХ категорий доходов пользователя
    3. Создает/получает слово в целевой категории
    4. Логирует удаления

    Args:
        profile: Профиль пользователя
        category: Целевая категория дохода
        word: Ключевое слово
        defaults: Дефолтные значения для создания (опционально)

    Returns:
        (keyword, created, removed_count):
            - keyword: объект IncomeCategoryKeyword
            - created: True если слово создано, False если существовало
            - removed_count: количество удаленных дубликатов

    Example:
        Пользователь вводит: "зарплата 50000"
        Система находит: категория "Фриланс" (там есть "зарплата")
        Пользователь меняет на: "Основная работа"

        ensure_unique_income_keyword() делает:
        1. Удаляет "зарплата" из "Фриланс"
        2. Создает "зарплата" в "Основная работа"
        3. Теперь "зарплата" только в "Основная работа"
    """
    # 1. Нормализовать слово
    word = word.lower().strip()

    # 2. Удалить из ВСЕХ категорий доходов профиля (строгая уникальность!)
    # Сначала получаем информацию ДО удаления для детального логирования
    existing_keywords = IncomeCategoryKeyword.objects.filter(
        category__profile=profile,
        keyword=word
    ).select_related('category')

    # Собираем информацию о том, откуда удаляем
    removed_from_categories = []
    for kw in existing_keywords:
        cat_name = kw.category.name or kw.category.name_ru or kw.category.name_en or f'ID:{kw.category.id}'
        removed_from_categories.append(cat_name)

    # Удаляем
    deleted = existing_keywords.delete()
    removed_count = deleted[0]

    # 3. Создать/получить в целевой категории
    keyword, created = IncomeCategoryKeyword.objects.get_or_create(
        category=category,
        keyword=word,
        defaults=defaults or {'usage_count': 0}
    )

    # 4. Логировать удаления для отладки с ПОЛНОЙ информацией
    target_cat_name = category.name or category.name_ru or category.name_en or f'ID:{category.id}'

    if removed_count > 0:
        logger.info(
            f"[INCOME KEYWORD MOVE] User {profile.telegram_id}: '{word}' "
            f"removed from {removed_from_categories} ({removed_count} duplicates) → "
            f"moved to '{target_cat_name}'"
        )
    elif created:
        logger.info(
            f"[INCOME KEYWORD NEW] User {profile.telegram_id}: '{word}' "
            f"created in '{target_cat_name}'"
        )

    return keyword, created, removed_count


async def categorize_income(text: str, user_id: int, profile: Optional[Profile] = None) -> Optional[Dict[str, Any]]:
    """
    Категоризация дохода через AI
    
    Returns:
        {
            'amount': Decimal,
            'description': str,
            'category': str,
            'confidence': float,
            'currency': str
        }
    """
    if not profile:
        logger.warning(f"No profile provided for user {user_id}")
        return None

    lang_code = getattr(profile, 'language_code', None) or 'ru'
    
    # Сначала проверяем ключевые слова
    category_from_keywords = await find_category_by_keywords(text, profile)
    if category_from_keywords:
        # Если нашли по ключевым словам, парсим только сумму через AI
        categories = await get_user_income_categories(profile)
        result = await base_categorizer.categorize(text, user_id, profile)
        if result:
            result['category'] = get_category_display_name(category_from_keywords, lang_code)
            result['confidence'] = 1.0  # Максимальная уверенность для ключевых слов
            return result
    
    # Получаем категории пользователя
    categories = await get_user_income_categories(profile)
    
    # Подготовка контекста для AI
    user_context = await build_user_context(profile)
    
    # Используем базовый категоризатор с типом income
    # Модифицируем промпт для доходов
    base_categorizer.operation_type = 'income'
    
    try:
        # Вызываем базовую функцию категоризации
        result = await base_categorizer.categorize(text, user_id, profile)
        
        if result:
            result['category'] = await find_best_matching_category(
                result.get('category', ''), categories
            )
            return result
            
    finally:
        # Возвращаем тип обратно
        base_categorizer.operation_type = 'expense'
    
    return None


@sync_to_async
def find_category_by_keywords(text: str, profile: Profile) -> Optional[IncomeCategory]:
    """
    Поиск категории по ключевым словам

    ВАЖНО: Использует строгую уникальность - одно слово = одна категория!
    Если нашли совпадение, сразу возвращаем (никаких весов!)
    """
    text_lower = text.lower()

    # Получаем все ключевые слова для категорий пользователя
    keywords = IncomeCategoryKeyword.objects.filter(
        category__profile=profile,
        category__is_active=True
    ).select_related('category')

    # СТРОГАЯ УНИКАЛЬНОСТЬ: одно слово может быть только в одной категории
    # Поэтому если нашли совпадение - сразу возвращаем, без сравнения весов!
    for keyword_obj in keywords:
        if keyword_obj.keyword.lower() in text_lower:
            # Нашли совпадение! Благодаря строгой уникальности это единственная категория с этим словом
            # Обновляем статистику использования
            keyword_obj.usage_count += 1
            keyword_obj.save(update_fields=['usage_count', 'last_used'])  # last_used обновится auto_now

            return keyword_obj.category

    # Ничего не найдено
    return None


@sync_to_async
def get_user_income_categories(profile: Profile) -> List[str]:
    """
    Получение списка категорий доходов пользователя
    """
    lang_code = getattr(profile, 'language_code', None) or 'ru'
    categories = IncomeCategory.objects.filter(
        profile=profile,
        is_active=True
    )
    
    return [
        get_category_display_name(category, lang_code)
        for category in categories
    ]


@sync_to_async
def build_user_context(profile: Profile) -> Dict[str, Any]:
    """
    Построение контекста пользователя для AI
    """
    # Последние использованные категории
    from bot.utils.language import get_user_language
    
    recent_incomes = Income.objects.filter(
        profile=profile
    ).order_by('-income_date', '-income_time')[:10]
    
    # Получаем язык пользователя
    lang = get_user_language(profile.telegram_id) if hasattr(profile, 'telegram_id') else 'ru'
    
    recent_categories = list(set([
        get_category_display_name(income.category, lang)
        for income in recent_incomes 
        if income.category
    ]))[:5]
    
    return {
        'recent_categories': recent_categories,
        'currency': profile.currency or 'RUB',
        'operation_type': 'income'
    }


async def find_best_matching_category(suggested: str, available: List[str]) -> str:
    """Поиск наиболее подходящей категории из доступных"""
    if not available:
        return suggested or get_income_category_display_for_key('other', 'ru')

    normalized_suggested_key = normalize_income_category_key(suggested)
    available_map = {}
    for cat in available:
        key = normalize_income_category_key(cat)
        if key and key not in available_map:
            available_map[key] = cat

    if normalized_suggested_key:
        if normalized_suggested_key in available_map:
            return available_map[normalized_suggested_key]
        for lang in ('ru', 'en'):
            candidate_name = get_income_category_display_for_key(normalized_suggested_key, lang)
            if candidate_name in available:
                return candidate_name

    cleaned_suggested = strip_leading_emoji(suggested).lower()
    if cleaned_suggested:
        for cat in available:
            if cleaned_suggested == strip_leading_emoji(cat).lower():
                return cat
        for cat in available:
            cleaned_cat = strip_leading_emoji(cat).lower()
            if cleaned_suggested in cleaned_cat or cleaned_cat in cleaned_suggested:
                return cat

    other_candidates = [
        get_income_category_display_for_key('other', 'ru'),
        get_income_category_display_for_key('other', 'en'),
    ]
    for candidate in other_candidates:
        if candidate in available:
            return candidate

    return available[0] if available else suggested or get_income_category_display_for_key('other', 'ru')

@sync_to_async
def learn_from_income_category_change_sync(
    income: Income,
    old_category: Optional[IncomeCategory],
    new_category: IncomeCategory
) -> None:
    """
    Обучение системы при изменении категории дохода пользователем (синхронная версия)

    ВАЖНО: Использует строгую уникальность - одно слово только в одной категории!
    """
    if not income.description:
        return

    description_lower = income.description.lower()

    # Извлекаем ключевые слова из описания
    words = description_lower.split()

    total_removed = 0
    for word in words:
        if len(word) < 3:  # Пропускаем короткие слова
            continue

        # ПАТТЕРН СТРОГОЙ УНИКАЛЬНОСТИ:
        # Удаляет из ВСЕХ категорий → создает в целевой
        keyword, created, removed = ensure_unique_income_keyword(
            profile=income.profile,
            category=new_category,
            word=word
        )

        total_removed += removed

        # Увеличиваем счетчик использований
        if not created:
            keyword.usage_count += 1
            keyword.save()

    if total_removed > 0:
        logger.info(
            f"Removed {total_removed} duplicate keywords while learning from income category change: "
            f"{old_category} -> {new_category} for '{income.description}'"
        )
    else:
        logger.info(f"Learned from income category change: {old_category} -> {new_category} for '{income.description}'")


async def learn_from_income_category_change(
    income: Income,
    old_category: Optional[IncomeCategory],
    new_category: IncomeCategory
) -> None:
    """
    Обучение системы при изменении категории дохода пользователем
    """
    await learn_from_income_category_change_sync(income, old_category, new_category)


@sync_to_async
def generate_keywords_for_income_category_sync(
    category: IncomeCategory,
    category_name: str
) -> List[str]:
    """
    Сохранение ключевых слов для категории доходов (синхронная версия)

    ВАЖНО: Использует строгую уникальность - одно слово только в одной категории!
    """
    # Базовые ключевые слова по умолчанию
    default_keywords = {
        'Зарплата': ['зарплата', 'зп', 'оклад', 'получка', 'аванс'],
        'Премии и бонусы': ['премия', 'бонус', 'поощрение', 'награда'],
        'Фриланс': ['фриланс', 'заказ', 'проект', 'гонорар', 'работа'],
        'Инвестиции': ['дивиденды', 'инвестиции', 'акции', 'облигации', 'прибыль'],
        'Проценты по вкладам': ['проценты', 'вклад', 'депозит', 'накопления'],
        'Аренда недвижимости': ['аренда', 'квартира', 'сдача', 'арендатор'],
        'Возвраты и компенсации': ['возврат', 'компенсация', 'возмещение', 'налоговый вычет'],
        'Кешбэк': ['кешбек', 'кэшбэк', 'cashback', 'возврат с покупок'],
        'Подарки': ['подарок', 'подарили', 'презент', 'дарение'],
        'Прочие доходы': ['доход', 'получил', 'заработал', 'прибыль']
    }

    keywords = default_keywords.get(category_name, ['доход'])

    total_removed = 0
    for keyword in keywords:
        # ПАТТЕРН СТРОГОЙ УНИКАЛЬНОСТИ:
        # Удаляет из ВСЕХ категорий → создает в целевой
        _, _, removed = ensure_unique_income_keyword(
            profile=category.profile,
            category=category,
            word=keyword
        )
        total_removed += removed

    if total_removed > 0:
        logger.info(
            f"Removed {total_removed} duplicate keywords while generating default keywords "
            f"for income category '{category_name}'"
        )

    # ВАЖНО: Возвращаем список ключевых слов для вызывающей функции
    return keywords


async def generate_keywords_for_income_category(
    category: IncomeCategory,
    category_name: str,
    ai_provider: str = 'auto'
) -> List[str]:
    """
    Генерация ключевых слов для новой категории доходов через AI
    """
    from .ai_service import ai_service
    
    prompt = f"""Сгенерируй список из 10-15 ключевых слов на русском языке для категории доходов "{category_name}".
Это слова, которые люди часто используют при описании таких доходов.
Верни только список слов через запятую, без нумерации и пояснений.

Пример для категории "Зарплата": зарплата, зп, оклад, получка, аванс, расчет, выплата, перевод от работодателя
Пример для категории "Фриланс": фриланс, заказ, проект, гонорар, оплата работы, клиент заплатил

Категория: {category_name}"""
    
    try:
        response = await ai_service.process_request(
            prompt=prompt,
            user_id=category.profile.telegram_id,
            request_type='keyword_generation',
            provider=ai_provider
        )
        
        if response and response.get('success'):
            keywords_text = response.get('result', '')
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
            
            # Сохраняем ключевые слова через синхронную функцию
            await save_income_category_keywords(category, keywords[:15])
            
            logger.info(f"Generated {len(keywords)} keywords for income category '{category_name}'")
            return keywords
            
    except Exception as e:
        logger.error(f"Error generating keywords for income category: {e}")
    
    # Используем базовые ключевые слова
    return await generate_keywords_for_income_category_sync(category, category_name)


@sync_to_async
def save_income_category_keywords(category: IncomeCategory, keywords: List[str]) -> None:
    """
    Сохранение ключевых слов для категории

    ВАЖНО: Использует строгую уникальность - одно слово только в одной категории!
    """
    total_removed = 0
    for keyword in keywords:
        # ПАТТЕРН СТРОГОЙ УНИКАЛЬНОСТИ:
        # Удаляет из ВСЕХ категорий → создает в целевой
        _, _, removed = ensure_unique_income_keyword(
            profile=category.profile,
            category=category,
            word=keyword
        )
        total_removed += removed

    if total_removed > 0:
        logger.info(
            f"Removed {total_removed} duplicate keywords while saving AI-generated keywords "
            f"for income category '{category.name}'"
        )
