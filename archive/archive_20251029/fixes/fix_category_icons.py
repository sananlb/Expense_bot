"""
Исправление эмодзи в категориях трат
"""
import os
import sys
import django

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import ExpenseCategory

# Словарь соответствий для исправления эмодзи
ICON_MAPPING = {
    'АЗС': '⛽',
    'Gas Station': '⛽', 
    'Такси': '🚕',
    'Taxi': '🚕',
    'Транспорт': '🚇',
    'Transport': '🚇',
    'Общественный транспорт': '🚌',
    'Public Transport': '🚌',
    'Автомобиль': '🚗',
    'Car': '🚗',
    'Жил': '🏠',
    'Housing': '🏠',
    'Аптек': '💊',
    'Pharmac': '💊',
    'Медицин': '🏥',
    'Medicine': '🏥',
    'Красот': '💄',
    'Beauty': '💄',
    'Спорт': '🏃',
    'Sport': '🏃',
    'Одежда': '👔',
    'Clothes': '👔',
    'Развлечен': '🎭',
    'Entertainment': '🎭',
    'Подарк': '🎁',
    'Gift': '🎁',
    'Путешеств': '✈️',
    'Travel': '✈️',
    'Родственник': '👪',
    'Relative': '👪',
    'Коммунал': '📱',
    'Связь': '📱',
    'Utilities': '📱',
    'Прочие': '📦',
    'Other': '📦',
    'Цветы': '🌹',
    'Flower': '🌹',
    'Образован': '📚',
    'Education': '📚',
    'Супермаркет': '🛒',
    'Supermarket': '🛒',
    'Продукт': '🛒',
    'Product': '🛒',
    'Groceries': '🛒',
    'Кафе': '☕',
    'Cafe': '☕',
    'Ресторан': '🍽️',
    'Restaurant': '🍽️',
}

def fix_icons():
    """Исправляет эмодзи у категорий"""
    fixed_count = 0
    categories = ExpenseCategory.objects.all()
    
    for cat in categories:
        # Пропускаем категории с нормальными эмодзи
        if cat.icon and cat.icon not in ('', '💰'):
            continue
            
        # Ищем подходящий эмодзи
        new_icon = None
        
        # Проверяем русское название
        if cat.name_ru:
            for keyword, icon in ICON_MAPPING.items():
                if keyword.lower() in cat.name_ru.lower():
                    new_icon = icon
                    break
        
        # Если не нашли, проверяем английское название
        if not new_icon and cat.name_en:
            for keyword, icon in ICON_MAPPING.items():
                if keyword.lower() in cat.name_en.lower():
                    new_icon = icon
                    break
        
        # Если нашли - обновляем
        if new_icon:
            old_icon = cat.icon
            # Обновляем только поле icon, чтобы избежать проблем с уникальностью
            ExpenseCategory.objects.filter(id=cat.id).update(icon=new_icon)
            fixed_count += 1
            print(f"✅ {cat.name_ru or cat.name_en}: '{old_icon}' → '{new_icon}'")
        else:
            print(f"⚠️ Не найден эмодзи для: {cat.name_ru or cat.name_en}")
    
    print(f"\n✅ Исправлено категорий: {fixed_count}")
    
    # Показываем итоговую статистику
    total = categories.count()
    with_icon = categories.exclude(icon='').exclude(icon='💰').count()
    without_icon = categories.filter(icon='').count()
    with_default = categories.filter(icon='💰').count()
    
    print(f"\n📊 Статистика:")
    print(f"  Всего категорий: {total}")
    print(f"  С правильными эмодзи: {with_icon}")
    print(f"  Без эмодзи: {without_icon}")
    print(f"  С дефолтным 💰: {with_default}")

if __name__ == "__main__":
    fix_icons()