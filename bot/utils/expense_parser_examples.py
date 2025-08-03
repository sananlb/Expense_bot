"""
Примеры использования улучшенного парсера расходов
"""
import asyncio
from expense_parser_improved import (
    parse_expense_message, 
    parse_multiple_expenses,
    validate_expense_data,
    ExpenseParserAI,
    suggest_category
)

def test_basic_parsing():
    """Тестирование базового парсинга"""
    test_cases = [
        # Простые случаи
        ("Кофе 200", "кафе", 200, "Кофе"),
        ("200 кофе", "кафе", 200, "кофе"),
        ("потратил на кофе 200", "кафе", 200, "на кофе"),
        
        # Сложные случаи
        ("Купил продукты в пятерочке за 1500 рублей", "продукты", 1500, "Купил продукты в пятерочке за рублей"),
        ("Заправил машину дизелем на 4095", "транспорт", 4095, "Заправил машину дизелем на"),
        ("Поехал на такси яндекс, заплатил 350", "транспорт", 350, "Поехал на такси яндекс, заплатил"),
        
        # Разные валюты
        ("Обед 25 долларов", "кафе", 25, "Обед долларов"),
        ("Билет в кино 15 евро", "развлечения", 15, "Билет в кино евро"),
        
        # Медицина и здоровье
        ("Купил лекарства в аптеке 36.6 за 850", "здоровье", 850, "Купил лекарства в аптеке 36.6 за"),
        ("Врач 2500", "здоровье", 2500, "Врач"),
        
        # Одежда
        ("Джинсы в зара 4999", "одежда", 4999, "Джинсы в зара"),
        
        # Коммунальные услуги
        ("Квартплата 15000", "дом", 15000, "Квартплата"),
        ("Оплатил свет 3200", "дом", 3200, "Оплатил свет"),
        
        # Связь
        ("Пополнил мтс на 500", "связь", 500, "Пополнил мтс на"),
        
        # Подарки
        ("Подарок на день рождения 2000", "подарки", 2000, "Подарок на день рождения"),
    ]
    
    print("=== Тестирование базового парсинга ===")
    for text, expected_category, expected_amount, expected_desc_part in test_cases:
        result = parse_expense_message(text)
        if result:
            success = (
                result.category == expected_category and 
                result.amount == expected_amount
            )
            status = "[OK]" if success else "[FAIL]"
            print(f"{status} '{text}' -> {result.amount} {result.currency}, {result.category}, '{result.description}' (conf: {result.confidence:.2f})")
            if not success:
                print(f"   Ожидалось: {expected_amount}, {expected_category}")
        else:
            print(f"[FAIL] '{text}' -> Не распознано")
    print()


def test_multiple_expenses():
    """Тестирование парсинга нескольких расходов"""
    test_cases = [
        "Кофе 200, такси 300",
        "Обед в кафе 800; кино 500",
        "Продукты 1500 + бензин 4000",
        "Завтрак 350\nОбед 650\nУжин 450",
    ]
    
    print("=== Тестирование множественных расходов ===")
    for text in test_cases:
        results = parse_multiple_expenses(text)
        print(f"'{text}' -> {len(results)} расходов:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.amount} {result.currency} - {result.description} ({result.category})")
    print()


def test_category_suggestion():
    """Тестирование предложения категорий"""
    test_cases = [
        "сходил в магазин",
        "поел в ресторане",
        "проезд в метро",
        "купил таблетки",
        "новая футболка",
        "оплата интернета",
        "что-то непонятное",
    ]
    
    print("=== Тестирование предложения категорий ===")
    for description in test_cases:
        category, confidence = suggest_category(description)
        print(f"'{description}' -> {category} (уверенность: {confidence:.2f})")
    print()


def test_validation():
    """Тестирование валидации данных"""
    from expense_parser_improved import ParsedExpense
    
    test_cases = [
        ParsedExpense(amount=200, description="Кофе", category="кафе"),  # Валидный
        ParsedExpense(amount=-100, description="Невозможно", category="кафе"),  # Отрицательная сумма
        ParsedExpense(amount=2000000, description="Очень дорого", category="кафе"),  # Слишком большая сумма
        ParsedExpense(amount=200, description="", category="кафе"),  # Пустое описание
        ParsedExpense(amount=200, description="Кофе", category="несуществующая"),  # Неизвестная категория
    ]
    
    print("=== Тестирование валидации ===")
    for i, expense in enumerate(test_cases, 1):
        errors = validate_expense_data(expense)
        status = "[OK]" if not errors else "[FAIL]"
        print(f"{status} Тест {i}: {expense.amount} - {expense.description} ({expense.category})")
        if errors:
            for error in errors:
                print(f"   Ошибка: {error}")
    print()


async def test_ai_parsing():
    """Тестирование AI-парсинга (требует API ключ OpenAI)"""
    # Примечание: для работы нужен API ключ OpenAI
    # Раскомментируйте следующие строки и добавьте ваш API ключ
    
    # ai_parser = ExpenseParserAI(api_key="your-openai-api-key")
    
    test_cases = [
        "Сегодня купил кофе за 200 рублей в старбаксе",
        "Потратил на бензин где-то 4 тысячи",
        "Сходил к врачу, обошлось в 2500",
        "Заказал пиццу домой, 800 рублей с доставкой",
    ]
    
    print("=== Тестирование AI-парсинга ===")
    print("Для работы требуется API ключ OpenAI")
    
    # Демонстрация без реального API вызова
    for text in test_cases:
        print(f"Текст: '{text}'")
        # result = await ai_parser.parse_expense_with_ai(text)
        print("  -> AI анализ недоступен (нужен API ключ)")
    print()


def demonstrate_advanced_features():
    """Демонстрация продвинутых возможностей"""
    print("=== Продвинутые возможности ===")
    
    # Сложные паттерны
    complex_texts = [
        "Сегодня утром зашел в пятерочку, купил продукты на неделю за 2300 рублей",
        "Вчера ездил к врачу на такси, потратил 400 на дорогу и 1500 на прием",
        "Заправился на лукойл, залил полный бак дизеля за 4850",
        "Купил жене подарок на 8 марта в золотом яблоке за 15000",
        "Оплатил коммуналку: свет 2300, вода 800, газ 1200",
    ]
    
    for text in complex_texts:
        print(f"\nТекст: '{text}'")
        result = parse_expense_message(text)
        if result:
            print(f"  Сумма: {result.amount} {result.currency}")
            print(f"  Описание: {result.description}")
            print(f"  Категория: {result.category}")
            print(f"  Уверенность: {result.confidence:.2f}")
            print(f"  AI обработка: {'Да' if result.ai_processed else 'Нет'}")
            
            # Валидация
            errors = validate_expense_data(result)
            if errors:
                print(f"  Ошибки: {', '.join(errors)}")
        else:
            print("  -> Не удалось распознать")


def main():
    """Запуск всех тестов"""
    print("Тестирование улучшенного парсера расходов\n")
    
    test_basic_parsing()
    test_multiple_expenses()
    test_category_suggestion()
    test_validation()
    demonstrate_advanced_features()
    
    print("Дополнительные возможности:")
    print("- AI-обработка с OpenAI API (требует ключ)")
    print("- Контекстуальный анализ пользовательских данных")
    print("- Поддержка множественных валют")
    print("- Расширяемая система категорий")
    print("- Нечеткое сопоставление ключевых слов")
    
    # Асинхронное тестирование AI
    # asyncio.run(test_ai_parsing())


if __name__ == "__main__":
    main()