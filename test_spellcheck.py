#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестирование проверки правописания
"""
from bot.utils.expense_categorizer import correct_typos, categorize_expense
from bot.utils.expense_parser_improved import parse_expense_message

def test_spellcheck():
    """Тестируем исправление опечаток"""
    
    test_cases = [
        # (текст с опечатками, ожидаемое исправление)
        ("вада и кофе", "вода и кофе"),
        ("кофэ и чибурек", "кофе и чебурек"),
        ("малоко и хлеп", "молоко и хлеб"),
        ("токси до дома", "такси до дома"),
        ("аптека ликарства", "аптека лекарства"),
        ("интирнет и телифон", "интернет и телефон"),
        ("пица и кофе", "пицца и кофе"),
        ("прадукты в магазине", "продукты в магазине"),  # тест spell checker
        ("бинзин на заправке", "бензин на заправке"),
        ("калбаса и сыр", "колбаса и сыр"),
    ]
    
    print("=" * 70)
    print("ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЯ ОПЕЧАТОК")
    print("=" * 70)
    
    for original, expected in test_cases:
        corrected = correct_typos(original)
        print(f"\nОригинал: {original}")
        print(f"Исправлено: {corrected}")
        print(f"Ожидалось: {expected}")
        if corrected == expected:
            print("OK - Правильно")
        else:
            print("FAIL - Неправильно")
    
    print("\n" + "=" * 70)
    print("ТЕСТИРОВАНИЕ КАТЕГОРИЗАЦИИ С ОПЕЧАТКАМИ")
    print("=" * 70)
    
    expense_tests = [
        ("вада кофэ и чибурек 350", "кафе"),
        ("прадукты в магазине 1500", "продукты"),
        ("токси до дома 500", "транспорт"),
        ("ликарства в оптеке 800", "здоровье"),
        ("бинзин на заправке 3000", "транспорт"),
        ("интирнет за месяц 900", "связь"),
        ("калбаса хлеп малоко 600", "продукты"),
    ]
    
    for text, expected_category in expense_tests:
        result = parse_expense_message(text)
        if result:
            print(f"\nВвод: {text}")
            print(f"Описание: {result.description}")
            print(f"Категория: {result.category}")
            print(f"Ожидалось: {expected_category}")
            if result.category == expected_category:
                print("OK - Правильная категория")
            else:
                print("FAIL - Неправильная категория")
        else:
            print(f"\nВвод: {text}")
            print("FAIL - Не удалось распознать")

if __name__ == "__main__":
    test_spellcheck()