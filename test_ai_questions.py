#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django
import asyncio
from datetime import datetime

# Установка Django настроек
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from bot.services.google_ai_service import GoogleAIService
from bot.services.expense_functions import ExpenseFunctions

# Тестовые вопросы по категориям
TEST_QUESTIONS = {
    "Вопросы по тратам за период": [
        "Сколько я потратил вчера?",
        "Сколько потратил в этом месяце?",
    ],
    "По категориям и товарам": [
        "Сколько я потратил на продукты в сентябре?",
        "Покупки в Пятёрочке за сентябрь",
    ],
    "Поисковые запросы": [
        "Когда я последний раз покупал молоко?",
        "Найди все покупки сникерса",
    ],
    "Аналитика и статистика": [
        "В какой день я больше всего потратил?",
        "Какая моя самая большая трата?",
    ],
    "Прогнозы и сравнения": [
        "Сколько я потрачу в этом месяце?",
        "Я стал тратить больше или меньше?",
    ],
    "Доходы": [
        "Сколько я заработал в этом месяце?",
        "В какой день было больше всего доходов?",
    ],
    "Комплексные запросы": [
        "Покажи финансовую сводку за месяц",
        "Все операции за сегодня",
    ],
    "Специфические вопросы": [
        "Покажи траты больше 1000 рублей",
        "Покажи самую маленькую покупку",
    ],
    "Вопросы с опечатками": [
        "скок потратил на прадукты?",
        "снкрс купил когда?",
    ],
    "Вопросы с естественными датами": [
        "Сколько потратил в прошлом месяце?",
        "Траты за позавчера",
    ],
}

async def test_question(ai_service, user_id, question, category):
    """Тестирует один вопрос"""
    print(f"\n{'='*60}")
    print(f"Категория: {category}")
    print(f"Вопрос: {question}")
    print("-"*60)

    try:
        # Получаем ответ от AI
        result = await ai_service.chat_with_functions(
            message=question,
            context=[],  # Пустой контекст для тестов
            user_context={'user_id': user_id},
            user_id=user_id
        )

        # result - это строка с форматированным ответом, не словарь
        if isinstance(result, str):
            print(f"[TEXT] Ответ AI: {result[:500]}...")
            return

        if result and isinstance(result, dict) and result.get('function_call'):
            func_name = result['function_call'].get('name', 'Unknown')
            params = result['function_call'].get('parameters', {})

            print(f"[OK] Функция: {func_name}")
            print(f"   Параметры:")
            for key, value in params.items():
                if key != 'user_id':  # Не показываем user_id для читаемости
                    print(f"     - {key}: {value}")

            # Пробуем выполнить функцию
            try:
                expense_func = ExpenseFunctions()
                if hasattr(expense_func, func_name):
                    func = getattr(expense_func, func_name)
                    func_result = await func(**params)

                    if func_result.get('success'):
                        # Показываем краткую статистику результата
                        if 'total' in func_result:
                            print(f"   Результат: Найдено сумма = {func_result['total']} руб.")
                        elif 'count' in func_result:
                            print(f"   Результат: Найдено записей = {func_result['count']}")
                        elif 'amount' in func_result:
                            print(f"   Результат: {func_result['amount']} руб.")
                        else:
                            print(f"   Результат: Успешно выполнено")
                    else:
                        print(f"   [!] Ошибка выполнения: {func_result.get('message', 'Unknown error')}")
                else:
                    print(f"   [!] Функция {func_name} не найдена в ExpenseFunctions")
            except Exception as e:
                print(f"   [ERROR] Ошибка при выполнении функции: {e}")

        elif result.get('text'):
            print(f"[TEXT] Текстовый ответ: {result['text'][:200]}...")
        else:
            print(f"[?] Неизвестный формат ответа: {result}")

    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")

async def main():
    # Инициализируем AI сервис
    ai_service = GoogleAIService()
    user_id = 881292737  # Тестовый пользователь

    print(f"\n{'='*60}")
    print(f"ТЕСТИРОВАНИЕ AI ФУНКЦИЙ")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"User ID: {user_id}")
    print(f"{'='*60}")

    # Тестируем все вопросы
    for category, questions in TEST_QUESTIONS.items():
        for question in questions:
            await test_question(ai_service, user_id, question, category)
            await asyncio.sleep(1)  # Небольшая пауза между запросами

    print(f"\n{'='*60}")
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())