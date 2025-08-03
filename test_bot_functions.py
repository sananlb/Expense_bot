"""
Скрипт для тестирования функций бота
"""
import os
import sys
import django
import asyncio
from datetime import date, datetime
from decimal import Decimal
import codecs

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

# Импорты после настройки Django
from bot.utils.expense_parser import parse_expense_message
from bot.services.user import get_or_create_user, create_default_categories
from bot.services.category import get_or_create_category, get_user_categories
from bot.services.expense import add_expense, get_today_summary, get_month_summary
from expenses.models import Profile, ExpenseCategory, Expense


async def test_parser():
    """Тест парсера расходов"""
    print("\n=== ТЕСТ ПАРСЕРА ===")
    test_messages = [
        "Кофе 200",
        "Такси домой 450 руб",
        "Потратил на продукты 1500",
        "Дизель 4095 АЗС",
        "Обед в кафе 650 рублей",
        "Купил подарок жене 3000",
        "Интернет 800",
        "Проездной на метро 2800"
    ]
    
    for msg in test_messages:
        result = await parse_expense_message(msg, use_ai=False)
        if result:
            print(f"✅ '{msg}' -> Сумма: {result['amount']}₽, Категория: {result['category']}, Описание: {result['description']}")
        else:
            print(f"❌ '{msg}' -> Не распознано")


async def test_user_creation():
    """Тест создания пользователя"""
    print("\n=== ТЕСТ СОЗДАНИЯ ПОЛЬЗОВАТЕЛЯ ===")
    
    # Создаем тестового пользователя
    user = await get_or_create_user(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    
    print(f"✅ Пользователь создан: {user.first_name} {user.last_name} (@{user.username})")
    
    # Создаем базовые категории
    await create_default_categories(user.telegram_id)
    print("✅ Базовые категории созданы")
    
    return user


async def test_categories(user_id: int):
    """Тест работы с категориями"""
    print("\n=== ТЕСТ КАТЕГОРИЙ ===")
    
    # Получаем категории пользователя
    categories = await get_user_categories(user_id)
    print(f"✅ Найдено категорий: {len(categories)}")
    
    for cat in categories[:5]:  # Показываем первые 5
        print(f"   {cat.icon} {cat.name}")
    
    # Создаем новую категорию
    new_cat = await get_or_create_category(user_id, "Бензин")
    print(f"✅ Создана/найдена категория: {new_cat.icon} {new_cat.name}")
    
    return categories


async def test_expenses(user_id: int):
    """Тест добавления расходов"""
    print("\n=== ТЕСТ РАСХОДОВ ===")
    
    # Добавляем несколько расходов
    test_expenses = [
        ("Кофе утром", 200, "Кафе"),  # Используем с заглавной буквы
        ("Обед в столовой", 350, "Кафе и рестораны"),  # Точное имя
        ("Проезд на метро", 60, "Транспорт"),
        ("Продукты в магазине", 1200, "Продукты"),
        ("Бензин", 2000, "Транспорт")
    ]
    
    for desc, amount, cat_name in test_expenses:
        category = await get_or_create_category(user_id, cat_name)
        expense = await add_expense(
            user_id=user_id,
            category_id=category.id,
            amount=amount,
            description=desc
        )
        print(f"✅ Добавлен расход: {expense.description} - {expense.amount}₽ ({category.name})")
    
    # Получаем сводку за сегодня
    today_summary = await get_today_summary(user_id)
    print(f"\n📊 Сводка за сегодня:")
    print(f"   Всего потрачено: {today_summary['total']}₽")
    print(f"   Количество трат: {today_summary['count']}")
    
    if today_summary['categories']:
        print("   По категориям:")
        for cat in today_summary['categories']:
            percent = (cat['amount'] / today_summary['total']) * 100
            print(f"   {cat['icon']} {cat['name']}: {cat['amount']}₽ ({percent:.1f}%)")


async def main():
    """Основная функция тестирования"""
    print("🚀 НАЧАЛО ТЕСТИРОВАНИЯ EXPENSEBOT")
    print("=" * 50)
    
    try:
        # Тест парсера
        await test_parser()
        
        # Тест создания пользователя
        user = await test_user_creation()
        
        # Тест категорий
        await test_categories(user.telegram_id)
        
        # Тест расходов
        await test_expenses(user.telegram_id)
        
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())