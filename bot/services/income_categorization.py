"""
AI категоризация доходов - использует ai_selector для выбора провайдера
"""
import logging
from typing import Optional, Dict, Any, List
from asgiref.sync import sync_to_async

from expenses.models import IncomeCategory, Income, IncomeCategoryKeyword, Profile
from .ai_selector import get_service, get_fallback_chain, AISelector
from bot.utils.category_helpers import get_category_display_name
from bot.utils.income_category_definitions import (
    get_income_category_display_name as get_income_category_display_for_key,
    normalize_income_category_key,
    strip_leading_emoji,
)
from bot.utils.logging_safe import log_safe_id, summarize_text
from bot.utils.keyword_service import match_keyword_in_text, ensure_unique_keyword

# УДАЛЕНО: _keyword_matches_in_text() - мертвый код, заменен на match_keyword_in_text() из keyword_service.py

logger = logging.getLogger(__name__)


def ensure_unique_income_keyword(
    profile: Profile,
    category: IncomeCategory,
    word: str,
    defaults: Optional[Dict[str, Any]] = None
) -> tuple[IncomeCategoryKeyword, bool, int]:
    """
    DEPRECATED: Используйте ensure_unique_keyword(..., is_income=True) из bot.utils.keyword_service

    Эта функция не применяет полную нормализацию (emoji, пунктуация, stop words).
    Оставлена для обратной совместимости.

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
            "[INCOME KEYWORD MOVE] %s: %s removed from %s categories -> category_id=%s",
            log_safe_id(profile.telegram_id, "user"),
            summarize_text(word),
            removed_count,
            category.id,
        )
    elif created:
        logger.info(
            "[INCOME KEYWORD NEW] %s: %s created in category_id=%s",
            log_safe_id(profile.telegram_id, "user"),
            summarize_text(word),
            category.id,
        )

    return keyword, created, removed_count


async def categorize_income(text: str, user_id: int, profile: Optional[Profile] = None) -> Optional[Dict[str, Any]]:
    """
    Категоризация дохода через AI (использует ai_selector для выбора провайдера)

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
        logger.warning("No profile provided for %s", log_safe_id(user_id, "user"))
        return None

    lang_code = getattr(profile, 'language_code', None) or 'ru'

    # Сначала проверяем ключевые слова
    category_from_keywords = await find_category_by_keywords(text, profile)
    if category_from_keywords:
        # Если нашли по ключевым словам, парсим только сумму через AI
        result = await _categorize_income_with_ai(text, user_id, profile)
        if result:
            result['category'] = get_category_display_name(category_from_keywords, lang_code)
            result['confidence'] = 1.0  # Максимальная уверенность для ключевых слов
            return result

    # Получаем категории пользователя
    categories = await get_user_income_categories(profile)

    # Подготовка контекста для AI
    user_context = await build_user_context(profile)

    # Вызываем AI категоризацию через ai_selector
    result = await _categorize_income_with_ai(text, user_id, profile, categories, user_context)

    if result:
        result['category'] = await find_best_matching_category(
            result.get('category', ''), categories
        )
        return result

    return None


async def _categorize_income_with_ai(
    text: str,
    user_id: int,
    profile: Profile,
    categories: Optional[List[str]] = None,
    user_context: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Внутренняя функция категоризации дохода через AI (использует ai_selector)
    """
    import asyncio

    if categories is None:
        categories = await get_user_income_categories(profile)

    if user_context is None:
        user_context = await build_user_context(profile)

    fallback_currency = profile.currency or 'RUB'

    # Получаем AI сервис через ai_selector (использует настройки из .env)
    try:
        ai_service = get_service('categorization')
        logger.info("Using AI service for income categorization: %s", type(ai_service).__name__)
    except Exception as e:
        logger.error("Failed to get AI service: %s", e)
        return None

    # Вызываем categorize_expense (универсальный метод для категоризации)
    try:
        result = await asyncio.wait_for(
            ai_service.categorize_expense(
                text=text,
                amount=None,
                currency=user_context.get('currency', fallback_currency) if user_context else fallback_currency,
                categories=categories,
                user_context=user_context
            ),
            timeout=15.0
        )

        if result:
            logger.info(
                "AI categorization result for income %s: confidence=%s",
                summarize_text(text),
                result.get('confidence'),
            )
            return result

    except asyncio.TimeoutError:
        logger.warning("AI categorization timeout for %s", log_safe_id(user_id, "user"))
    except Exception as e:
        logger.error("AI categorization error for income for %s: %s", log_safe_id(user_id, "user"), e)

    # Пробуем fallback провайдеров
    fallback_providers = get_fallback_chain('categorization')
    for fallback_provider in fallback_providers:
        try:
            logger.info("Trying fallback provider for income categorization: %s", fallback_provider)
            fallback_service = AISelector(fallback_provider)

            result = await asyncio.wait_for(
                fallback_service.categorize_expense(
                    text=text,
                    amount=None,
                    currency=user_context.get('currency', fallback_currency) if user_context else fallback_currency,
                    categories=categories,
                    user_context=user_context
                ),
                timeout=15.0
            )

            if result:
                logger.info("Fallback provider succeeded for income categorization: %s", fallback_provider)
                return result

        except Exception as e:
            logger.warning("Fallback provider %s failed for income categorization: %s", fallback_provider, e)
            continue

    logger.warning("All AI providers failed for income categorization for %s", log_safe_id(user_id, "user"))
    return None


@sync_to_async
def find_category_by_keywords(text: str, profile: Profile) -> Optional[IncomeCategory]:
    """
    Поиск категории по ключевым словам

    ВАЖНО: Использует строгую уникальность - одно слово = одна категория!
    Если нашли совпадение, сразу возвращаем (никаких весов!)
    """
    # Получаем все ключевые слова для категорий пользователя
    keywords = IncomeCategoryKeyword.objects.filter(
        category__profile=profile,
        category__is_active=True
    ).select_related('category')

    # СТРОГАЯ УНИКАЛЬНОСТЬ: одно слово может быть только в одной категории
    # Поэтому если нашли совпадение - сразу возвращаем, без сравнения весов!
    for keyword_obj in keywords:
        # Используем централизованную функцию match_keyword_in_text
        # с улучшенной обработкой emoji и двухуровневым matching (exact + prefix)
        matched, match_type = match_keyword_in_text(keyword_obj.keyword, text)
        if matched:
            # Нашли совпадение! Благодаря строгой уникальности это единственная категория с этим словом
            # Обновляем статистику использования
            keyword_obj.usage_count += 1
            keyword_obj.save(update_fields=['usage_count', 'last_used'])  # last_used обновится auto_now

            logger.info(
                "[INCOME KEYWORD MATCH] %s: keyword=%s text=%s",
                match_type,
                summarize_text(keyword_obj.keyword),
                summarize_text(text),
            )
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
    recent_incomes = Income.objects.filter(
        profile=profile
    ).order_by('-income_date', '-income_time')[:10]

    # Получаем язык пользователя напрямую из профиля (он уже загружен)
    lang = getattr(profile, 'language_code', None) or 'ru'
    
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
    """
    Поиск наиболее подходящей категории доходов из доступных.

    ВАЖНО: Приоритет проверок (от высокого к низкому):
    1. Точное совпадение без эмодзи - для кастомных категорий с уточнениями
       Пример: "Зарплата (основная)" точно соответствует "💼 Зарплата (основная)"
    2. Частичное совпадение - для похожих названий
       Пример: "зарплата" найдет "💼 Зарплата (основная)"
    3. Category key - для дефолтных категорий на разных языках
       Пример: "Salary" найдет "💼 Зарплата" через ключ "salary"
    4. Fallback на категорию "other" или первую доступную

    Такой порядок позволяет AI точно указывать кастомные категории,
    избегая коллапса дубликатов с одинаковым category_key.
    """
    if not available:
        return suggested or get_income_category_display_for_key('other', 'ru')

    # 1. ПРИОРИТЕТ: Точное совпадение без эмодзи (для кастомных категорий с уточнениями)
    # Это позволяет AI различать "Зарплата (основная)" и "Зарплата (подработка)"
    cleaned_suggested = strip_leading_emoji(suggested).lower()
    if cleaned_suggested:
        for cat in available:
            if cleaned_suggested == strip_leading_emoji(cat).lower():
                logger.info(
                    "[INCOME CATEGORY MATCH] AI suggested %s -> exact match -> %s",
                    summarize_text(suggested),
                    summarize_text(cat),
                )
                return cat

    # 2. Частичное совпадение (для похожих названий)
    # Срабатывает если точного нет, но есть вхождение
    if cleaned_suggested:
        for cat in available:
            cleaned_cat = strip_leading_emoji(cat).lower()
            if cleaned_suggested in cleaned_cat or cleaned_cat in cleaned_suggested:
                logger.info(
                    "[INCOME CATEGORY MATCH] AI suggested %s -> partial match -> %s",
                    summarize_text(suggested),
                    summarize_text(cat),
                )
                return cat

    # 3. Category key нормализация (для дефолтных категорий на разных языках)
    # Срабатывает когда AI возвращает общее название типа "Salary"/"Зарплата"
    normalized_suggested_key = normalize_income_category_key(suggested)
    available_map = {}
    for cat in available:
        key = normalize_income_category_key(cat)
        if key and key not in available_map:
            # Сохраняем первую категорию с этим ключом (для дубликатов)
            available_map[key] = cat

    if normalized_suggested_key:
        # Проверяем есть ли категория с таким ключом
        if normalized_suggested_key in available_map:
            matched_category = available_map[normalized_suggested_key]
            logger.info(
                "[INCOME CATEGORY MATCH] AI suggested %s -> key %s -> %s",
                summarize_text(suggested),
                normalized_suggested_key,
                summarize_text(matched_category),
            )
            return matched_category

        # Пробуем найти через отображение ключа в название на разных языках
        for lang in ('ru', 'en'):
            candidate_name = get_income_category_display_for_key(normalized_suggested_key, lang)
            if candidate_name in available:
                logger.info(
                    "[INCOME CATEGORY MATCH] AI suggested %s -> key %s -> lang %s -> %s",
                    summarize_text(suggested),
                    normalized_suggested_key,
                    lang,
                    summarize_text(candidate_name),
                )
                return candidate_name

    # 4. Fallback: ищем категорию "Прочие доходы" или возвращаем первую доступную
    other_candidates = [
        cat for cat in available
        if normalize_income_category_key(cat) == 'other'
    ]
    if other_candidates:
        logger.warning(
            "[INCOME CATEGORY FALLBACK] AI suggested %s -> using 'other' category %s",
            summarize_text(suggested),
            summarize_text(other_candidates[0]),
        )
        return other_candidates[0]

    # Последний шанс - возвращаем первую доступную категорию (если есть)
    if available:
        logger.warning(
            "[INCOME CATEGORY FALLBACK] AI suggested %s -> using first available %s",
            summarize_text(suggested),
            summarize_text(available[0]),
        )
        return available[0]

    # Совсем крайний случай (available пустой - но мы проверили это в начале)
    return suggested or get_income_category_display_for_key('other', 'ru')

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
        keyword, created, removed = ensure_unique_keyword(
            profile=income.profile,
            category=new_category,
            word=word,
            is_income=True
        )

        total_removed += removed

        # Увеличиваем счетчик использований
        if keyword and not created:
            keyword.usage_count += 1
            keyword.save()

    if total_removed > 0:
        logger.info(
            "Removed %s duplicate keywords while learning from income category change: %s -> %s for %s",
            total_removed,
            getattr(old_category, "id", None),
            new_category.id,
            summarize_text(income.description),
        )
    else:
        logger.info(
            "Learned from income category change: %s -> %s for %s",
            getattr(old_category, "id", None),
            new_category.id,
            summarize_text(income.description),
        )


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
        'Аренда недвижимости': ['аренда', 'квартира', 'сдача', 'арендатор', 'шале'],
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
        _, _, removed = ensure_unique_keyword(
            profile=category.profile,
            category=category,
            word=keyword,
            is_income=True
        )
        total_removed += removed

    if total_removed > 0:
        logger.info(
            "Removed %s duplicate keywords while generating default keywords for income category %s",
            total_removed,
            summarize_text(category_name),
        )

    # ВАЖНО: Возвращаем список ключевых слов для вызывающей функции
    return keywords


async def generate_keywords_for_income_category(
    category: IncomeCategory,
    category_name: str,
    ai_provider: str = 'auto'
) -> List[str]:
    """
    Генерация ключевых слов для новой категории доходов.

    NOTE: AI-генерация отключена, используем только базовые ключевые слова.
    Это более надёжно и не требует вызова AI для простой задачи.
    """
    # Используем базовые ключевые слова (более надёжно, чем AI)
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
        _, _, removed = ensure_unique_keyword(
            profile=category.profile,
            category=category,
            word=keyword,
            is_income=True
        )
        total_removed += removed

    if total_removed > 0:
        logger.info(
            f"Removed {total_removed} duplicate keywords while saving AI-generated keywords "
            f"for income category '{category.name}'"
        )
