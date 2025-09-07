"""
Сервис для управления мультиязычными категориями
"""
import re
import logging
from typing import Optional, List, Set
from asgiref.sync import sync_to_async

from expenses.models import Profile, ExpenseCategory, CategoryKeyword
from bot.utils.default_categories import UNIFIED_CATEGORIES
from bot.services.ai_service import ai_service

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Определение языка текста"""
    # Убираем эмодзи и специальные символы
    clean_text = re.sub(r'[^\w\s\-а-яА-ЯёЁa-zA-Z]', '', text)
    
    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', clean_text))
    has_latin = bool(re.search(r'[a-zA-Z]', clean_text))
    
    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    else:
        return 'mixed'


def extract_emoji(text: str) -> Optional[str]:
    """Извлечь эмодзи из текста"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    emojis = emoji_pattern.findall(text)
    return emojis[0] if emojis else None


def remove_emoji(text: str) -> str:
    """Удалить эмодзи из текста"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


async def translate_with_ai(text: str, from_lang: str, to_lang: str) -> str:
    """Перевести текст с помощью AI"""
    try:
        from_lang_name = 'русского' if from_lang == 'ru' else 'английского'
        to_lang_name = 'английский' if to_lang == 'en' else 'русский'
        
        prompt = f"""
        Переведи название категории расходов с {from_lang_name} на {to_lang_name}.
        Текст: {text}
        
        Верни ТОЛЬКО перевод без кавычек и объяснений.
        """
        
        response = await ai_service.generate(prompt, max_tokens=50)
        return response.strip().strip('"\'')
    except Exception as e:
        logger.error(f"Ошибка при переводе категории: {e}")
        return text  # Возвращаем оригинал если перевод не удался


async def generate_keywords_with_ai(category_name: str, language: str) -> List[str]:
    """Генерация ключевых слов с помощью AI"""
    try:
        lang_name = 'русском' if language == 'ru' else 'английском'
        
        prompt = f"""
        Для категории расходов "{category_name}" на {lang_name} языке 
        сгенерируй 5-10 ключевых слов, которые помогут автоматически 
        определять эту категорию по описанию траты.
        
        Например, для категории "Продукты": магазин, супермаркет, продукты, еда
        
        Верни слова через запятую, без нумерации.
        """
        
        response = await ai_service.generate(prompt, max_tokens=100)
        keywords = [k.strip() for k in response.split(',')]
        return keywords[:10]  # Ограничиваем количество
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов: {e}")
        return []


@sync_to_async
def create_default_categories(profile_id: int):
    """Создание категорий по умолчанию с мультиязычной поддержкой"""
    try:
        profile = Profile.objects.get(telegram_id=profile_id)
        
        for cat_data in UNIFIED_CATEGORIES:
            # Создаем категорию
            category = ExpenseCategory.objects.create(
                profile=profile,
                name=f"{cat_data['icon']} {cat_data['name_ru']}",  # Для совместимости
                name_ru=cat_data['name_ru'],
                name_en=cat_data['name_en'],
                icon=cat_data['icon'],
                original_language='mixed',  # Стандартные категории доступны на обоих языках
                is_translatable=True
            )
            
            # Создаем ключевые слова для русского языка
            for keyword in cat_data.get('keywords_ru', []):
                CategoryKeyword.objects.create(
                    category=category,
                    keyword=keyword.lower(),
                    language='ru'
                )
            
            # Создаем ключевые слова для английского языка
            for keyword in cat_data.get('keywords_en', []):
                CategoryKeyword.objects.create(
                    category=category,
                    keyword=keyword.lower(),
                    language='en'
                )
                
        logger.info(f"Созданы категории по умолчанию для пользователя {profile_id}")
        
    except Profile.DoesNotExist:
        logger.error(f"Профиль {profile_id} не найден")
    except Exception as e:
        logger.error(f"Ошибка при создании категорий по умолчанию: {e}")


async def create_user_category(profile_id: int, category_name: str) -> Optional[ExpenseCategory]:
    """Создание пользовательской категории с автопереводом"""
    try:
        profile = await sync_to_async(Profile.objects.get)(telegram_id=profile_id)
        user_lang = profile.language_code or 'ru'
        
        # Извлекаем эмодзи если есть
        emoji = extract_emoji(category_name)
        text = remove_emoji(category_name).strip()
        
        if not text:
            return None
        
        # Определяем язык введенного текста
        detected_lang = detect_language(text)
        
        # Создаем категорию
        category = ExpenseCategory()
        category.profile = profile
        category.icon = emoji or '📦'
        
        if detected_lang == user_lang or detected_lang == 'mixed':
            # Текст на языке пользователя или смешанный - переводим
            if user_lang == 'ru':
                category.name_ru = text
                category.name_en = await translate_with_ai(text, 'ru', 'en')
            else:
                category.name_en = text
                category.name_ru = await translate_with_ai(text, 'en', 'ru')
            
            category.original_language = user_lang
            category.is_translatable = True
            
            # Генерируем ключевые слова для обоих языков
            keywords_ru = await generate_keywords_with_ai(category.name_ru, 'ru')
            keywords_en = await generate_keywords_with_ai(category.name_en, 'en')
            
        else:
            # Текст на другом языке - НЕ переводим
            if detected_lang == 'ru':
                category.name_ru = text
                category.name_en = None
                category.original_language = 'ru'
            elif detected_lang == 'en':
                category.name_en = text
                category.name_ru = None
                category.original_language = 'en'
            
            category.is_translatable = False
            
            # Генерируем ключевые слова только на языке пользователя
            if user_lang == 'ru':
                keywords_ru = await generate_keywords_with_ai(text, 'ru')
                keywords_en = []
            else:
                keywords_en = await generate_keywords_with_ai(text, 'en')
                keywords_ru = []
        
        # Обновляем поле name для совместимости
        category.name = f"{category.icon} {text}"
        
        await sync_to_async(category.save)()
        
        # Сохраняем ключевые слова
        for keyword in keywords_ru:
            await sync_to_async(CategoryKeyword.objects.create)(
                category=category,
                keyword=keyword.lower(),
                language='ru'
            )
        
        for keyword in keywords_en:
            await sync_to_async(CategoryKeyword.objects.create)(
                category=category,
                keyword=keyword.lower(),
                language='en'
            )
        
        logger.info(f"Создана категория '{text}' для пользователя {profile_id}")
        return category
        
    except Profile.DoesNotExist:
        logger.error(f"Профиль {profile_id} не найден")
        return None
    except Exception as e:
        logger.error(f"Ошибка при создании категории: {e}")
        return None


def normalize_text_for_search(text: str) -> Set[str]:
    """Нормализует текст для поиска"""
    # Удаляем эмодзи и специальные символы
    text = re.sub(r'[^\w\s\-а-яА-ЯёЁa-zA-Z]', ' ', text)
    text = text.lower().strip()
    
    # Токенизация
    tokens = re.findall(r'[\wа-яА-ЯёЁa-zA-Z]+', text)
    
    # Удаляем стоп-слова
    stop_words = {'и', 'в', 'на', 'по', 'для', 'с', 'от', 'до', 'из', 
                  'and', 'or', 'the', 'for', 'with', 'from', 'to', 'at'}
    
    return {token for token in tokens if token and token not in stop_words}


async def find_category_by_name(profile: Profile, search_text: str) -> Optional[ExpenseCategory]:
    """Поиск категории по названию с улучшенным алгоритмом"""
    
    # Нормализуем поисковый запрос
    search_tokens = normalize_text_for_search(search_text)
    if not search_tokens:
        return None
    
    categories = await sync_to_async(list)(
        profile.categories.filter(is_active=True)
    )
    
    best_match = None
    best_score = 0
    
    for category in categories:
        # Собираем все варианты названий категории
        names_to_check = []
        
        if category.name_ru:
            names_to_check.append(category.name_ru)
        if category.name_en:
            names_to_check.append(category.name_en)
        if category.name:
            names_to_check.append(category.name)
        
        # Проверяем каждое название
        for name in names_to_check:
            if not name:
                continue
            
            # Нормализуем название категории
            category_tokens = normalize_text_for_search(name)
            
            # Вычисляем пересечение токенов
            common_tokens = search_tokens & category_tokens
            
            if common_tokens:
                # Вычисляем score как отношение общих токенов к общему количеству
                score = len(common_tokens) / max(len(search_tokens), len(category_tokens))
                
                # Бонус за полное совпадение хотя бы одного токена
                if search_tokens.issubset(category_tokens) or category_tokens.issubset(search_tokens):
                    score += 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = category
    
    # Возвращаем лучшее совпадение, если score достаточно высокий
    return best_match if best_score >= 0.5 else None