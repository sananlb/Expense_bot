#!/usr/bin/env python
"""
Тест для проверки, что сообщения о доходах не исчезают
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

def check_keep_message_param():
    """Проверка параметра keep_message в обработчиках доходов"""
    print("=" * 50)
    print("ПРОВЕРКА ПАРАМЕТРА keep_message")
    print("=" * 50)
    
    # Читаем файл expense.py
    with open('bot/routers/expense.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем все места где отправляется сообщение о доходе
    income_sends = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if 'format_income_added_message' in line:
            # Ищем ближайший вызов send_message_with_cleanup
            for j in range(i, min(i + 30, len(lines))):
                if 'send_message_with_cleanup' in lines[j]:
                    # Проверяем наличие keep_message в следующих строках
                    has_keep_message = False
                    for k in range(j, min(j + 10, len(lines))):
                        if 'keep_message=True' in lines[k]:
                            has_keep_message = True
                            break
                    
                    income_sends.append({
                        'line': i + 1,
                        'has_keep_message': has_keep_message
                    })
                    break
    
    # Выводим результаты
    print(f"\nНайдено {len(income_sends)} мест отправки сообщений о доходах:")
    for send in income_sends:
        status = "OK" if send['has_keep_message'] else "ERROR"
        print(f"  Строка {send['line']}: {status} keep_message={'True' if send['has_keep_message'] else 'False'}")
    
    # Проверяем расходы для сравнения
    expense_sends = []
    for i, line in enumerate(lines):
        if 'format_expense_added_message' in line:
            # Ищем ближайший вызов send_message_with_cleanup
            for j in range(i, min(i + 30, len(lines))):
                if 'send_message_with_cleanup' in lines[j]:
                    # Проверяем наличие keep_message в следующих строках
                    has_keep_message = False
                    for k in range(j, min(j + 10, len(lines))):
                        if 'keep_message=True' in lines[k]:
                            has_keep_message = True
                            break
                    
                    expense_sends.append({
                        'line': i + 1,
                        'has_keep_message': has_keep_message
                    })
                    break
    
    print(f"\nДля сравнения - расходы ({len(expense_sends)} мест):")
    for send in expense_sends:
        status = "OK" if send['has_keep_message'] else "ERROR"
        print(f"  Строка {send['line']}: {status} keep_message={'True' if send['has_keep_message'] else 'False'}")
    
    # Итог
    all_income_ok = all(send['has_keep_message'] for send in income_sends)
    all_expense_ok = all(send['has_keep_message'] for send in expense_sends)
    
    print("\n" + "=" * 50)
    if all_income_ok and all_expense_ok:
        print("OK - ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("Сообщения о доходах и расходах НЕ будут исчезать")
    else:
        print("WARNING - ЕСТЬ ПРОБЛЕМЫ!")
        if not all_income_ok:
            print("ERROR - Некоторые сообщения о доходах могут исчезать")
        if not all_expense_ok:
            print("ERROR - Некоторые сообщения о расходах могут исчезать")
    print("=" * 50)

if __name__ == "__main__":
    print("\nТЕСТИРОВАНИЕ СОХРАНЕНИЯ СООБЩЕНИЙ О ДОХОДАХ\n")
    check_keep_message_param()
    print("\nТестирование завершено!")