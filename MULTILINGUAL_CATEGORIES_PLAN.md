# План реализации мультиязычных категорий для ExpenseBot

## 📋 Требования
1. **Двуязычные категории по умолчанию** - автоматически создаются на русском и английском
2. **Автоперевод пользовательских категорий** - если создана на языке пользователя
3. **Сохранение оригинального языка** - категории на другом языке не переводятся
4. **AI-генерация ключевых слов** - автоматически для обоих языков
5. **Корректное отображение** - категория показывается на текущем языке пользователя

## 🗄️ Новая структура БД

### Модель ExpenseCategory (обновленная)
```python
class ExpenseCategory(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='categories')
    
    # Основное название (как ввел пользователь)
    name = models.CharField(max_length=100)  # Сохраняем для совместимости
    
    # Мультиязычные названия
    name_ru = models.CharField(max_length=100, blank=True)
    name_en = models.CharField(max_length=100, blank=True)
    
    # Язык оригинала (для определения нужно ли переводить)
    original_language = models.CharField(max_length=10, choices=[('ru', 'Russian'), ('en', 'English'), ('mixed', 'Mixed')], default='ru')
    
    # Флаг: категория требует перевода
    is_translatable = models.BooleanField(default=True)
    
    icon = models.CharField(max_length=10, default='💰')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses_category'
        unique_together = ['profile', 'name']
        indexes = [
            models.Index(fields=['profile', 'name']),
            models.Index(fields=['profile', 'name_ru']),
            models.Index(fields=['profile', 'name_en']),
        ]
```

### Модель CategoryKeyword (обновленная)
```python
class CategoryKeyword(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='keywords')
    keyword = models.CharField(max_length=100, db_index=True)
    
    # Язык ключевого слова
    language = models.CharField(max_length=10, choices=[('ru', 'Russian'), ('en', 'English')], default='ru')
    
    usage_count = models.IntegerField(default=0)
    normalized_weight = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['category', 'keyword', 'language']
```

## 🔄 План миграции

### Этап 1: Подготовка структуры БД
1. Создать миграцию для добавления новых полей:
   - `name_ru`, `name_en` в ExpenseCategory
   - `original_language`, `is_translatable` в ExpenseCategory
   - `language` в CategoryKeyword

### Этап 2: Миграция существующих данных
```python
def migrate_existing_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('expenses', 'ExpenseCategory')
    
    for category in ExpenseCategory.objects.all():
        # Определяем язык категории
        text = category.name.replace(category.icon, '').strip()
        
        if has_cyrillic(text):
            category.name_ru = text
            category.original_language = 'ru'
            # Если категория стандартная - добавляем перевод
            if text in STANDARD_CATEGORIES_RU:
                category.name_en = get_translation(text, 'en')
                category.is_translatable = True
            else:
                category.is_translatable = False
        elif has_latin(text):
            category.name_en = text
            category.original_language = 'en'
            # Если категория стандартная - добавляем перевод
            if text in STANDARD_CATEGORIES_EN:
                category.name_ru = get_translation(text, 'ru')
                category.is_translatable = True
            else:
                category.is_translatable = False
        
        category.save()
```

### Этап 3: Миграция ключевых слов
```python
def migrate_keywords(apps, schema_editor):
    CategoryKeyword = apps.get_model('expenses', 'CategoryKeyword')
    
    for keyword in CategoryKeyword.objects.all():
        # Определяем язык ключевого слова
        if has_cyrillic(keyword.keyword):
            keyword.language = 'ru'
        else:
            keyword.language = 'en'
        keyword.save()
```

## 💻 Новая логика создания категорий

### Создание категорий по умолчанию
```python
# bot/utils/default_categories.py
DEFAULT_CATEGORIES = [
    {
        'icon': '🛒',
        'name_ru': 'Продукты',
        'name_en': 'Products',
        'keywords_ru': ['магазин', 'супермаркет', 'продукты', 'еда'],
        'keywords_en': ['store', 'supermarket', 'groceries', 'food']
    },
    {
        'icon': '🍽️',
        'name_ru': 'Кафе и рестораны',
        'name_en': 'Cafes and Restaurants',
        'keywords_ru': ['ресторан', 'кафе', 'бар', 'пицца', 'суши'],
        'keywords_en': ['restaurant', 'cafe', 'bar', 'pizza', 'sushi']
    },
    # ... остальные категории
]

async def create_default_categories(profile_id: int):
    profile = await sync_to_async(Profile.objects.get)(telegram_id=profile_id)
    
    for cat_data in DEFAULT_CATEGORIES:
        category = await sync_to_async(ExpenseCategory.objects.create)(
            profile=profile,
            name=f"{cat_data['icon']} {cat_data['name_' + profile.language_code]}",
            name_ru=cat_data['name_ru'],
            name_en=cat_data['name_en'],
            icon=cat_data['icon'],
            original_language='both',
            is_translatable=True
        )
        
        # Создаем ключевые слова для обоих языков
        for keyword in cat_data['keywords_ru']:
            await sync_to_async(CategoryKeyword.objects.create)(
                category=category,
                keyword=keyword,
                language='ru'
            )
        
        for keyword in cat_data['keywords_en']:
            await sync_to_async(CategoryKeyword.objects.create)(
                category=category,
                keyword=keyword,
                language='en'
            )
```

### Создание пользовательской категории
```python
# bot/services/category_manager.py
async def create_user_category(profile_id: int, category_name: str):
    profile = await sync_to_async(Profile.objects.get)(telegram_id=profile_id)
    user_lang = profile.language_code or 'ru'
    
    # Извлекаем эмодзи если есть
    emoji = extract_emoji(category_name)
    text = remove_emoji(category_name).strip()
    
    # Определяем язык введенного текста
    detected_lang = detect_language(text)
    
    # Создаем категорию
    category = ExpenseCategory()
    category.profile = profile
    category.icon = emoji or '📦'
    
    if detected_lang == user_lang:
        # Текст на языке пользователя - переводим
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
        # Текст на другом языке - НЕ переводим и НЕ дублируем
        if detected_lang == 'ru':
            category.name_ru = text
            category.name_en = None  # Оставляем пустым
            category.original_language = 'ru'
        elif detected_lang == 'en':
            category.name_en = text
            category.name_ru = None  # Оставляем пустым
            category.original_language = 'en'
        else:
            # Неизвестный язык - сохраняем в поле языка пользователя
            if user_lang == 'ru':
                category.name_ru = text
                category.name_en = None
                category.original_language = 'ru'
            else:
                category.name_en = text
                category.name_ru = None
                category.original_language = 'en'
        
        category.is_translatable = False
        
        # Генерируем ключевые слова только на языке пользователя
        keywords = await generate_keywords_with_ai(text, user_lang)
        if user_lang == 'ru':
            keywords_ru = keywords
            keywords_en = []
        else:
            keywords_en = keywords
            keywords_ru = []
    
    # Обновляем поле name для совместимости
    category.name = f"{category.icon} {text}"
    
    await sync_to_async(category.save)()
    
    # Сохраняем ключевые слова
    for keyword in keywords_ru:
        await sync_to_async(CategoryKeyword.objects.create)(
            category=category,
            keyword=keyword,
            language='ru'
        )
    
    for keyword in keywords_en:
        await sync_to_async(CategoryKeyword.objects.create)(
            category=category,
            keyword=keyword,
            language='en'
        )
    
    return category
```

## 🤖 AI интеграция

### Перевод категорий
```python
async def translate_with_ai(text: str, from_lang: str, to_lang: str) -> str:
    prompt = f"""
    Переведи название категории расходов с {from_lang} на {to_lang}.
    Текст: {text}
    
    Верни ТОЛЬКО перевод, без объяснений.
    """
    
    response = await ai_service.generate(prompt)
    return response.strip()
```

### Генерация ключевых слов
```python
async def generate_keywords_with_ai(category_name: str, language: str) -> List[str]:
    lang_name = 'русском' if language == 'ru' else 'английском'
    
    prompt = f"""
    Для категории расходов "{category_name}" на {lang_name} языке 
    сгенерируй 5-10 ключевых слов, которые помогут автоматически 
    определять эту категорию по описанию траты.
    
    Например, для категории "Продукты": магазин, супермаркет, продукты, еда
    
    Верни слова через запятую, без нумерации.
    """
    
    response = await ai_service.generate(prompt)
    keywords = [k.strip() for k in response.split(',')]
    return keywords[:10]  # Ограничиваем количество
```

## 📱 Отображение категорий

### Получение названия категории для отображения
```python
def get_category_display_name(category: ExpenseCategory, user_lang: str) -> str:
    """Возвращает название категории на нужном языке"""
    
    if not category.is_translatable:
        # Категория не переводится - показываем оригинал из правильного поля
        if category.original_language == 'ru':
            name = category.name_ru
        elif category.original_language == 'en':
            name = category.name_en
        else:
            # Fallback на старое поле name для обратной совместимости
            name = category.name.replace(category.icon, '').strip()
        
        return f"{category.icon} {name}" if name else category.name
    
    # Категория переводимая - выбираем нужный язык с fallback
    if user_lang == 'ru':
        name = category.name_ru or category.name_en
    else:
        name = category.name_en or category.name_ru
    
    # Последний fallback на старое поле name
    if not name:
        name = category.name.replace(category.icon, '').strip()
    
    return f"{category.icon} {name}" if name else category.name
```

### Поиск категории по названию
```python
def normalize_text_for_search(text: str) -> Set[str]:
    """Нормализует текст для поиска: удаляет эмодзи, приводит к нижнему регистру, токенизирует"""
    import re
    
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
    """Ищет категорию по названию на любом языке с улучшенным алгоритмом"""
    
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
```

## 📅 План внедрения

### Неделя 1: Подготовка
- [ ] Создать миграции БД
- [ ] Написать скрипты миграции данных
- [ ] Подготовить AI промпты

### Неделя 2: Реализация
- [ ] Реализовать создание категорий с переводом
- [ ] Интегрировать AI для генерации ключевых слов
- [ ] Обновить логику отображения

### Неделя 3: Тестирование
- [ ] Протестировать на тестовой БД
- [ ] Проверить все сценарии использования
- [ ] Исправить найденные баги

### Неделя 4: Развертывание
- [ ] Создать бэкап продакшн БД
- [ ] Запустить миграцию на продакшне
- [ ] Мониторинг и поддержка

## ⚠️ Важные моменты

1. **Обратная совместимость** - поле `name` остается для старого кода
2. **Постепенная миграция** - можно мигрировать пользователей по частям
3. **Кеширование переводов** - для экономии API запросов к AI
4. **Fallback логика** - если перевод не удался, используем оригинал
5. **Логирование** - все операции с AI должны логироваться