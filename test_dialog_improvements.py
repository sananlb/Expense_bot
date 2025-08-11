#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование улучшений системы диалогов
"""

import sys
import os
import io

# Исправляем проблемы с кодировкой в Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.expense_intent import is_show_expenses_request, is_expense_record_request
from bot.utils.text_classifier import classify_message

def test_show_requests():
    """Тестируем определение запросов показа трат"""
    print("\n=== Тестирование запросов показа трат ===\n")
    
    test_cases = [
        # Должны определяться как запросы показа
        ("покажи траты", True),
        ("показать трату вчера", True),
        ("покажи трату за вчера", True),
        ("траты вчера", True),
        ("траты сегодня", True),
        ("расходы за неделю", True),
        ("сколько потратил вчера", True),
        ("что я купил сегодня", True),
        ("мои траты за месяц", True),
        ("покажи расходы за прошлый месяц", True),
        ("отчет за неделю", True),
        ("статистика трат", True),
        ("траты за январь", True),
        ("всего потрачено", True),
        ("итого за год", True),
        
        # НЕ должны определяться как запросы показа
        ("кофе 200", False),
        ("купил молоко", False),
        ("заплатил за интернет 500", False),
        ("продукты", False),
        ("бензин 2000", False),
    ]
    
    for text, expected_show in test_cases:
        is_show, confidence = is_show_expenses_request(text)
        classifier_type, classifier_conf = classify_message(text)
        
        status = "✅" if is_show == expected_show else "❌"
        print(f"{status} '{text}':")
        print(f"   - expense_intent: show={is_show}, conf={confidence:.2f}")
        print(f"   - classifier: type={classifier_type}, conf={classifier_conf:.2f}")
        print(f"   - Ожидалось: show={expected_show}")
        
        if is_show != expected_show:
            print(f"   ⚠️  ОШИБКА: Неправильное определение!")
        print()


def test_expense_records():
    """Тестируем определение записей трат"""
    print("\n=== Тестирование записей трат ===\n")
    
    test_cases = [
        # Должны определяться как записи трат
        ("кофе 200", True),
        ("купил молоко 150", True),
        ("заплатил за интернет 500", True),
        ("продукты 1500", True),
        ("бензин 95 2000р", True),
        ("обед", True),
        ("такси 350", True),
        
        # НЕ должны определяться как записи трат
        ("покажи траты", False),
        ("траты вчера", False),
        ("сколько потратил", False),
        ("мои расходы", False),
        ("отчет за месяц", False),
    ]
    
    for text, expected_record in test_cases:
        is_record, confidence = is_expense_record_request(text)
        classifier_type, classifier_conf = classify_message(text)
        
        status = "✅" if is_record == expected_record else "❌"
        print(f"{status} '{text}':")
        print(f"   - expense_intent: record={is_record}, conf={confidence:.2f}")
        print(f"   - classifier: type={classifier_type}, conf={classifier_conf:.2f}")
        print(f"   - Ожидалось: record={expected_record}")
        
        if is_record != expected_record:
            print(f"   ⚠️  ОШИБКА: Неправильное определение!")
        print()


def test_edge_cases():
    """Тестируем сложные случаи"""
    print("\n=== Тестирование сложных случаев ===\n")
    
    test_cases = [
        ("показать трату вчера", "chat", "Запрос показа с опечаткой"),
        ("покажи мне траты", "chat", "Запрос показа с 'мне'"),
        ("вчера", "chat", "Только временной маркер"),
        ("сегодня", "chat", "Только временной маркер"),
        ("прошлая неделя", "chat", "Временной период"),
        ("траты", "chat", "Только слово 'траты'"),
        ("200", "record", "Только число"),
        ("вчера купил кофе", "record", "Глагол покупки с временем"),
        ("потратил вчера 500", "record", "Глагол траты с суммой"),
    ]
    
    for text, expected_type, description in test_cases:
        is_show, show_conf = is_show_expenses_request(text)
        is_record, record_conf = is_expense_record_request(text)
        classifier_type, classifier_conf = classify_message(text)
        
        print(f"'{text}' ({description}):")
        print(f"   - is_show: {is_show} (conf: {show_conf:.2f})")
        print(f"   - is_record: {is_record} (conf: {record_conf:.2f})")
        print(f"   - classifier: {classifier_type} (conf: {classifier_conf:.2f})")
        print(f"   - Ожидается: {expected_type}")
        
        if classifier_type != expected_type:
            print(f"   ⚠️  Возможная проблема!")
        print()


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ УЛУЧШЕНИЙ СИСТЕМЫ ДИАЛОГОВ")
    print("="*60)
    
    test_show_requests()
    test_expense_records()
    test_edge_cases()
    
    print("\n" + "="*60)
    print("Тестирование завершено!")
    print("="*60)


if __name__ == "__main__":
    main()