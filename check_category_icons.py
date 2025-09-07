"""
Скрипт для проверки и исправления эмодзи в категориях трат
"""
import os
import sys
import django
import locale

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory, Profile

# Словарь дефолтных эмодзи для категорий
DEFAULT_ICONS = {
    # Русские названия
    'продукты': '🛒',
    'супермаркеты': '🛒',
    'транспорт': '🚇',
    'кафе': '☕',
    'кафе и рестораны': '🍽️',
    'рестораны': '🍽️',
    'здоровье': '💊',
    'аптека': '💊',
    'одежда': '👕',
    'одежда и обувь': '👔',
    'развлечения': '🎮',
    'дом': '🏠',
    'дом и жкх': '🏠',
    'жкх': '🏠',
    'связь': '📱',
    'связь и интернет': '📱',
    'интернет': '🌐',
    'образование': '📚',
    'автомобиль': '🚗',
    'азс': '⛽',
    'заправка': '⛽',
    'топливо': '⛽',
    'подарки': '🎁',
    'путешествия': '✈️',
    'спорт': '⚽',
    'красота': '💄',
    'такси': '🚕',
    'другое': '📦',
    'прочие расходы': '📦',
    'прочее': '📦',
    
    # Английские названия
    'groceries': '🛒',
    'supermarkets': '🛒',
    'transport': '🚇',
    'cafe': '☕',
    'cafes and restaurants': '🍽️',
    'restaurants': '🍽️',
    'health': '💊',
    'pharmacy': '💊',
    'clothes': '👕',
    'clothes and shoes': '👔',
    'entertainment': '🎮',
    'home': '🏠',
    'home and utilities': '🏠',
    'utilities': '🏠',
    'communication': '📱',
    'communication and internet': '📱',
    'internet': '🌐',
    'education': '📚',
    'car': '🚗',
    'gas station': '⛽',
    'fuel': '⛽',
    'gifts': '🎁',
    'travel': '✈️',
    'sports': '⚽',
    'beauty': '💄',
    'taxi': '🚕',
    'other': '📦',
    'other expenses': '📦',
}

def check_and_fix_icons():
    """Проверяет и исправляет эмодзи у категорий"""
    
    print("=" * 60)
    print("Проверка эмодзи в категориях трат")
    print("=" * 60)
    
    # Получаем все категории
    categories = ExpenseCategory.objects.all().select_related('profile')
    
    categories_without_icon = []
    categories_with_icon = []
    fixed_categories = []
    
    for cat in categories:
        if not cat.icon or cat.icon.strip() == '':
            categories_without_icon.append(cat)
            
            # Пытаемся найти подходящий эмодзи
            possible_icon = None
            
            # Проверяем русское название
            if cat.name_ru:
                name_lower = cat.name_ru.lower().strip()
                if name_lower in DEFAULT_ICONS:
                    possible_icon = DEFAULT_ICONS[name_lower]
            
            # Если не нашли, проверяем английское название
            if not possible_icon and cat.name_en:
                name_lower = cat.name_en.lower().strip()
                if name_lower in DEFAULT_ICONS:
                    possible_icon = DEFAULT_ICONS[name_lower]
            
            # Если не нашли точное совпадение, ищем частичное
            if not possible_icon:
                for key, icon in DEFAULT_ICONS.items():
                    if cat.name_ru and key in cat.name_ru.lower():
                        possible_icon = icon
                        break
                    elif cat.name_en and key in cat.name_en.lower():
                        possible_icon = icon
                        break
            
            # Если нашли подходящий эмодзи - обновляем
            if possible_icon:
                cat.icon = possible_icon
                cat.save()
                fixed_categories.append((cat, possible_icon))
                print(f"✅ Исправлена категория '{cat.name_ru or cat.name_en}' (user {cat.profile.telegram_id}): добавлен эмодзи {possible_icon}")
            else:
                print(f"❌ Категория без эмодзи: '{cat.name_ru or cat.name_en}' (user {cat.profile.telegram_id})")
        else:
            categories_with_icon.append(cat)
    
    print("\n" + "=" * 60)
    print(f"Всего категорий: {categories.count()}")
    print(f"С эмодзи: {len(categories_with_icon)}")
    print(f"Без эмодзи: {len(categories_without_icon)}")
    print(f"Исправлено: {len(fixed_categories)}")
    
    if categories_without_icon and not fixed_categories:
        print("\n⚠️ Остались категории без эмодзи, которые не удалось исправить автоматически")
    
    # Проверяем дубликаты эмодзи
    print("\n" + "=" * 60)
    print("Проверка дубликатов эмодзи по пользователям:")
    
    # Группируем по пользователям
    users_categories = {}
    for cat in categories:
        user_id = cat.profile.telegram_id
        if user_id not in users_categories:
            users_categories[user_id] = []
        users_categories[user_id].append(cat)
    
    for user_id, user_cats in users_categories.items():
        icon_counts = {}
        for cat in user_cats:
            if cat.icon:
                if cat.icon not in icon_counts:
                    icon_counts[cat.icon] = []
                icon_counts[cat.icon].append(cat.name_ru or cat.name_en)
        
        # Проверяем дубликаты
        duplicates = {icon: names for icon, names in icon_counts.items() if len(names) > 1}
        if duplicates:
            print(f"\nПользователь {user_id}:")
            for icon, names in duplicates.items():
                print(f"  {icon} используется для: {', '.join(names)}")

if __name__ == "__main__":
    check_and_fix_icons()