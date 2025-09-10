#!/usr/bin/env python
"""
Демонстрация функционала внесения операций задним числом
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.utils.expense_parser import parse_expense_message, extract_date_from_text
from datetime import date, datetime


def test_date_extraction():
    """Тест извлечения дат из текста"""
    print("=" * 60)
    print("ТЕСТ ИЗВЛЕЧЕНИЯ ДАТ ИЗ ТЕКСТА")
    print("=" * 60)
    
    test_cases = [
        ("Кофе 200 15.03.2024", date(2024, 3, 15), "Кофе 200"),
        ("25.12.2023 подарки 5000", date(2023, 12, 25), "подарки 5000"),
        ("Бензин 3000 01.01.24", date(2024, 1, 1), "Бензин 3000"),
        ("15.11 обед 500", date(datetime.now().year, 11, 15), "обед 500"),
        ("Продукты 1500", None, "Продукты 1500"),
    ]
    
    for text, expected_date, expected_text in test_cases:
        extracted_date, text_without_date = extract_date_from_text(text)
        
        success = extracted_date == expected_date and text_without_date.strip() == expected_text
        status = "OK" if success else "FAIL"
        
        print(f"\nТекст: '{text}'")
        print(f"  Ожидаемая дата: {expected_date}")
        print(f"  Извлеченная дата: {extracted_date}")
        print(f"  Текст без даты: '{text_without_date}'")
        print(f"  Статус: {status}")


def test_expense_parsing_with_dates():
    """Тест парсинга расходов с датами"""
    print("\n" + "=" * 60)
    print("ТЕСТ ПАРСИНГА РАСХОДОВ С ДАТАМИ")
    print("=" * 60)
    
    test_messages = [
        "Кофе 200 15.03.2024",
        "25.12.2023 подарки 5000",
        "Бензин 3000 01.01.24",
        "15.11 обед в ресторане 1500",
        "Продукты в магазине 2500 10.10.2024",
        "01.09 школьные принадлежности 3000",
    ]
    
    for message in test_messages:
        print(f"\nСообщение: '{message}'")
        
        # Парсим сообщение
        parsed = parse_expense_message(message)
        
        if parsed:
            print(f"  Сумма: {parsed.get('amount')}")
            print(f"  Описание: {parsed.get('description')}")
            print(f"  Категория: {parsed.get('category', 'не определена')}")
            print(f"  Дата: {parsed.get('expense_date', 'сегодня')}")
        else:
            print("  ERROR: Не удалось распарсить")


def demonstrate_usage():
    """Демонстрация использования"""
    print("\n" + "=" * 60)
    print("КАК ИСПОЛЬЗОВАТЬ ВНЕСЕНИЕ ЗАДНИМ ЧИСЛОМ")
    print("=" * 60)
    
    print("\nФОРМАТЫ ДАТА:")
    print("  • ДД.ММ.ГГГГ - полная дата (15.03.2024)")
    print("  • ДД.ММ.ГГ - короткий год (15.03.24)")
    print("  • ДД.ММ - без года (15.03) - будет использован текущий год")
    
    print("\nПРИМЕРЫ СООБЩЕНИЙ:")
    examples = [
        "Кофе 200 15.03.2024",
        "25.12.2023 подарки 5000",
        "Бензин АЗС 3000 01.01.24",
        "15.11 обед 500",
        "Продукты 1500 10.10.2024",
        "01.09 школа 3000",
    ]
    
    for example in examples:
        print(f"  • {example}")
    
    print("\nОСОБЕННОСТИ:")
    print("  • Дату можно указать в начале или конце сообщения")
    print("  • Для трат задним числом время устанавливается в 12:00")
    print("  • Для трат сегодня используется текущее время")
    print("  • Если год не указан, используется текущий год")
    
    print("\nОГРАНИЧЕНИЯ:")
    print("  • Максимум 100 операций в день")
    print("  • Нельзя вносить траты в будущем")
    print("  • Дата должна быть в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ или ДД.ММ")


def test_income_with_dates():
    """Тест парсинга доходов с датами"""
    print("\n" + "=" * 60)
    print("ТЕСТ ПАРСИНГА ДОХОДОВ С ДАТАМИ")
    print("=" * 60)
    
    from bot.utils.expense_parser import parse_income_message
    
    test_incomes = [
        "зарплата 100000 01.12.2024",
        "15.11 премия 50000",
        "фриланс 30000 20.12.2023",
        "возврат налогов 13000 10.10.2024",
    ]
    
    for message in test_incomes:
        print(f"\nСообщение: '{message}'")
        
        # Парсим как доход
        parsed = parse_income_message(message)
        
        if parsed:
            print(f"  Сумма: {parsed.get('amount')}")
            print(f"  Описание: {parsed.get('description')}")
            print(f"  Категория: {parsed.get('category', 'не определена')}")
            print(f"  Дата: {parsed.get('income_date', 'сегодня')}")
        else:
            print("  ERROR: Не удалось распарсить")


if __name__ == "__main__":
    print("\nДЕМОНСТРАЦИЯ ФУНКЦИОНАЛА ВНЕСЕНИЯ ОПЕРАЦИЙ ЗАДНИМ ЧИСЛОМ\n")
    
    # Запускаем тесты
    test_date_extraction()
    test_expense_parsing_with_dates()
    test_income_with_dates()
    demonstrate_usage()
    
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)