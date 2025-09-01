#!/usr/bin/env python3
"""
Анализ системы переводов категорий в боте
"""

# DEFAULT_CATEGORIES из models.py
DEFAULT_CATEGORIES = [
    ('Продукты', '🛒'),
    ('Кафе и рестораны', '🍽️'),
    ('АЗС', '⛽'),
    ('Транспорт', '🚕'),
    ('Автомобиль', '🚗'),
    ('Жилье', '🏠'),
    ('Аптеки', '💊'),
    ('Медицина', '🏥'),
    ('Красота', '💄'),
    ('Спорт и фитнес', '🏃'),
    ('Одежда и обувь', '👔'),
    ('Развлечения', '🎭'),
    ('Образование', '📚'),
    ('Подарки', '🎁'),
    ('Путешествия', '✈️'),
    ('Родственники', '👪'),
    ('Коммунальные услуги и подписки', '📱'),
    ('Прочие расходы', '💰')
]

# Словарь переводов из language.py
TRANSLATIONS = {
    # Русский -> Английский
    'Супермаркеты': 'Supermarkets',
    'Продукты': 'Products',
    'Другие продукты': 'Other Products',
    'Рестораны и кафе': 'Restaurants and Cafes',
    'Кафе и рестораны': 'Restaurants and Cafes',
    'АЗС': 'Gas Stations',
    'Такси': 'Taxi',
    'Общественный транспорт': 'Public Transport',
    'Автомобиль': 'Car',
    'Транспорт': 'Transport',
    'Жилье': 'Housing',
    'Аптеки': 'Pharmacies',
    'Медицина': 'Medicine',
    'Спорт': 'Sports',
    'Спорт и фитнес': 'Sports and Fitness',
    'Спортивные товары': 'Sports Goods',
    'Одежда и обувь': 'Clothes and Shoes',
    'Цветы': 'Flowers',
    'Развлечения': 'Entertainment',
    'Образование': 'Education',
    'Подарки': 'Gifts',
    'Путешествия': 'Travel',
    'Связь и интернет': 'Communication and Internet',
    'Коммунальные услуги и подписки': 'Utilities and Subscriptions',
    'Прочие расходы': 'Other Expenses',
    'Благотворительность': 'Charity',
    'Родственники': 'Relatives',
    'Красотища': 'Beauty',
    'Красота': 'Beauty',
    'Улулу': 'Ululu',
    # Английский -> Русский (обратные)
    'Supermarkets': 'Супермаркеты',
    'Products': 'Продукты',
    'Other Products': 'Другие продукты',
    'Restaurants and Cafes': 'Рестораны и кафе',
    'Gas Stations': 'АЗС',
    'Taxi': 'Такси',
    'Public Transport': 'Общественный транспорт',
    'Car': 'Автомобиль',
    'Transport': 'Транспорт',
    'Housing': 'Жилье',
    'Pharmacies': 'Аптеки',
    'Medicine': 'Медицина',
    'Sports': 'Спорт',
    'Sports and Fitness': 'Спорт и фитнес',
    'Sports Goods': 'Спортивные товары',
    'Clothes and Shoes': 'Одежда и обувь',
    'Flowers': 'Цветы',
    'Entertainment': 'Развлечения',
    'Education': 'Образование',
    'Gifts': 'Подарки',
    'Travel': 'Путешествия',
    'Communication and Internet': 'Связь и интернет',
    'Utilities and Subscriptions': 'Коммунальные услуги и подписки',
    'Other Expenses': 'Прочие расходы',
    'Charity': 'Благотворительность',
    'Relatives': 'Родственники',
    'Beauty': 'Красота',
    'Ululu': 'Улулу'
}

def analyze_category_translations():
    """Анализ покрытия переводов категорий"""
    print("=== АНАЛИЗ СИСТЕМЫ ПЕРЕВОДОВ КАТЕГОРИЙ ===\n")
    
    # 1. Проверяем покрытие DEFAULT_CATEGORIES
    print("1. Проверка покрытия стандартных категорий:")
    print("-" * 50)
    
    missing_translations_ru_en = []
    for category_name, emoji in DEFAULT_CATEGORIES:
        if category_name not in TRANSLATIONS:
            missing_translations_ru_en.append(category_name)
            print(f"❌ ОТСУТСТВУЕТ перевод RU->EN: {category_name}")
        else:
            en_translation = TRANSLATIONS[category_name]
            print(f"✅ {category_name} -> {en_translation}")
    
    print(f"\nОтсутствующих переводов RU->EN: {len(missing_translations_ru_en)}")
    
    # 2. Проверяем обратную симметричность
    print("\n2. Проверка обратной симметричности переводов:")
    print("-" * 50)
    
    asymmetric_translations = []
    for ru_category, en_category in TRANSLATIONS.items():
        # Пропускаем английские ключи (они уже обратные переводы)
        if any(char in ru_category for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            # Проверяем, есть ли обратный перевод
            if en_category not in TRANSLATIONS:
                asymmetric_translations.append((ru_category, en_category))
                print(f"❌ НЕТ ОБРАТНОГО ПЕРЕВОДА: {ru_category} -> {en_category} (нет {en_category} -> ?)")
            else:
                reverse_translation = TRANSLATIONS[en_category]
                if reverse_translation != ru_category:
                    asymmetric_translations.append((ru_category, en_category, reverse_translation))
                    print(f"⚠️  НЕСИММЕТРИЧНЫЙ ПЕРЕВОД: {ru_category} -> {en_category} -> {reverse_translation}")
                else:
                    print(f"✅ СИММЕТРИЧНЫЙ: {ru_category} <-> {en_category}")
    
    print(f"\nНесимметричных переводов: {len(asymmetric_translations)}")
    
    # 3. Ищем категории, которые есть в переводах, но нет в DEFAULT_CATEGORIES
    print("\n3. Дополнительные категории в словаре переводов:")
    print("-" * 50)
    
    default_category_names = {name for name, emoji in DEFAULT_CATEGORIES}
    extra_categories = []
    
    for category in TRANSLATIONS.keys():
        # Проверяем только русские категории
        if any(char in category for char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            if category not in default_category_names:
                extra_categories.append(category)
                print(f"➕ Дополнительная категория: {category} -> {TRANSLATIONS[category]}")
    
    if not extra_categories:
        print("Нет дополнительных категорий")
    
    # 4. Проверяем английские категории для создания по умолчанию
    print("\n4. Английские категории для создания по умолчанию:")
    print("-" * 50)
    
    english_default_categories = []
    for category_name, emoji in DEFAULT_CATEGORIES:
        if category_name in TRANSLATIONS:
            en_name = TRANSLATIONS[category_name]
            english_default_categories.append((en_name, emoji))
            print(f"📝 {en_name} ({emoji})")
        else:
            print(f"❌ Нет перевода для: {category_name}")
    
    # 5. Итоговая сводка
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СВОДКА:")
    print("=" * 60)
    print(f"Всего стандартных категорий: {len(DEFAULT_CATEGORIES)}")
    print(f"Переведенных категорий: {len(DEFAULT_CATEGORIES) - len(missing_translations_ru_en)}")
    print(f"Отсутствующих переводов RU->EN: {len(missing_translations_ru_en)}")
    print(f"Несимметричных переводов: {len(asymmetric_translations)}")
    print(f"Дополнительных категорий в словаре: {len(extra_categories)}")
    
    if missing_translations_ru_en:
        print(f"\n❌ ПРОБЛЕМЫ с переводами:")
        for category in missing_translations_ru_en:
            print(f"  - Отсутствует перевод: {category}")
    
    if asymmetric_translations:
        print(f"\n⚠️  АСИММЕТРИЧНЫЕ переводы:")
        for item in asymmetric_translations:
            if len(item) == 2:
                print(f"  - {item[0]} -> {item[1]} (нет обратного)")
            else:
                print(f"  - {item[0]} -> {item[1]} -> {item[2]} (неверный обратный)")
    
    return {
        'missing_translations': missing_translations_ru_en,
        'asymmetric_translations': asymmetric_translations,
        'extra_categories': extra_categories,
        'english_default_categories': english_default_categories
    }

if __name__ == "__main__":
    results = analyze_category_translations()