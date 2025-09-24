"""
Unified prompt builder for function-calling across AI providers.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict

def build_function_call_prompt(message: str, context: List[Dict[str,str]]|None=None) -> str:
    today = datetime.now()
    # Optionally incorporate brief context if provided (last assistant/user turns)
    ctx_text = ""
    if context:
        recent = []
        for msg in context[-2:]:  # last 2 turns
            role = msg.get('role','user')
            content = msg.get('content','')
            recent.append(f"{role}: {content}")
        if recent:
            ctx_text = f"Контекст диалога: {' | '.join(recent)}\n"
    prompt = f"""Ты - помощник по учету расходов и доходов. У тебя есть доступ к функциям для анализа финансов.
Сегодня: {today.strftime('%Y-%m-%d')} ({today.strftime('%B %Y')})


ДОСТУПНЫЕ ФУНКЦИИ ДЛЯ РАСХОДОВ:
1. get_max_expense_day() - для вопросов "В какой день я больше всего потратил?"
2. get_period_total(period='today'|'yesterday'|'day_before_yesterday'|'week'|'last_week'|'month'|'last_month'|'year'|'январь'|...|'декабрь'|'зима'|'весна'|'лето'|'осень') - для "Сколько я потратил сегодня/вчера/позавчера/на прошлой неделе/в августе/летом?"
3. get_max_single_expense(period='last_week'|'last_month'|'day_before_yesterday'|'week'|'month'|'январь'|'февраль'|...|'декабрь'|'january'|'august'|'зима'|'весна'|'лето'|'осень') - для "Какая моя самая большая трата позавчера/на прошлой неделе/в прошлом месяце/в августе/летом?"
4. get_category_statistics() - для "На что я трачу больше всего?"
5. get_average_expenses() - для "Сколько я трачу в среднем?"
6. get_recent_expenses(limit=10) - для "Покажи последние траты"
7. search_expenses(query='текст', period='last_week'|'last_month') - УНИВЕРСАЛЬНЫЙ ПОИСК по категориям И описаниям: "Сколько потратил на продукты на прошлой неделе?", "Траты на кофе в прошлом месяце"
8. get_weekday_statistics() - для "В какие дни недели я трачу больше?"
9. predict_month_expense() - для "Сколько я потрачу в этом месяце?"
10. check_budget_status(budget_amount=50000) - для "Уложусь ли я в бюджет?"
11. compare_periods() - для "Я стал тратить больше или меньше?"
12. get_expense_trend() - для "Покажи динамику трат"
13. get_expenses_by_amount_range(min_amount=1000) - для "Покажи траты больше 1000"
14. get_category_total(category='продукты', period='month'|'week'|'январь'|...|'декабрь'|'зима'|'лето') - для КАТЕГОРИЙ: "Сколько я потратил на продукты в этом месяце/в августе/летом?"
15. get_expenses_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') - для "Покажи траты за период/с даты по дату"
16. get_daily_totals(days=30) - для "Покажи траты по дням/суммы по дням за последний месяц"

ДОСТУПНЫЕ ФУНКЦИИ ДЛЯ ДОХОДОВ:
17. get_max_income_day() - для "В какой день я больше всего заработал?"
18. get_income_period_total(period='today'|'yesterday'|'week'|'month'|'year') - для "Сколько я заработал сегодня/вчера/на этой неделе?"
19. get_max_single_income(period='last_week'|'last_month'|'week'|'month'|'январь'|'февраль'|...|'декабрь'|'january'|'august'|'зима'|'весна'|'лето'|'осень') - для "Какой мой самый большой доход на прошлой неделе/в прошлом месяце/в августе/летом?"
20. get_income_category_statistics() - для "Откуда больше всего доходов?"
21. get_average_incomes() - для "Сколько я зарабатываю в среднем?"
22. get_recent_incomes(limit=10) - для "Покажи последние доходы"
23. search_incomes(query='текст') - для "Когда я получал..."
24. get_income_weekday_statistics() - для "В какие дни недели больше доходов?"
25. predict_month_income() - для "Сколько я заработаю в этом месяце?"
26. check_income_target(target_amount=100000) - для "Достигну ли я цели по доходам?"
27. compare_income_periods() - для "Я стал зарабатывать больше или меньше?"
28. get_income_trend() - для "Покажи динамику доходов"
29. get_incomes_by_amount_range(min_amount=10000) - для "Покажи доходы больше 10000"
30. get_income_category_total(category='зарплата', period='month') - для "Сколько я получаю зарплаты?"
31. get_incomes_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') - для "Покажи доходы за период"
32. get_daily_income_totals(days=30) - для "Покажи доходы по дням"

ФУНКЦИИ ДЛЯ КОМПЛЕКСНОГО АНАЛИЗА:
33. get_all_operations(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD', limit=200) - для "Все операции", "Покажи все транзакции"
34. get_financial_summary(period='month') - для "Финансовая сводка", "Баланс", "Итоги месяца"

УНИВЕРСАЛЬНАЯ ФУНКЦИЯ (ИСПОЛЬЗУЙ ЕСЛИ НЕТ ПОДХОДЯЩЕЙ ВЫШЕ):
35. analytics_query(spec_json='<JSON-спецификация запроса>') - для нестандартных аналитических запросов

КРИТИЧЕСКИ ВАЖНО: search_expenses - УНИВЕРСАЛЬНАЯ функция поиска!
search_expenses ищет ОДНОВРЕМЕННО и в категориях, и в описаниях трат.

Примеры использования search_expenses:
- "Сколько потратил на продукты в сентябре?" → search_expenses(query='продукты', start_date='2025-09-01', end_date='2025-09-30')
- "Сколько потратил на сникерс в сентябре?" → search_expenses(query='сникерс', start_date='2025-09-01', end_date='2025-09-30')
- "Траты на транспорт в августе" → search_expenses(query='транспорт', start_date='2025-08-01', end_date='2025-08-31')
- "Траты в Пятёрочке за месяц" → search_expenses(query='пятёрочка', start_date='2025-MM-01', end_date='2025-MM-31')
- "Покупки в супермаркетах" → search_expenses(query='супермаркет')

ВАЖНО: Если вопрос требует анализа данных, ответь ТОЛЬКО в формате:
FUNCTION_CALL: имя_функции(параметр1=значение1, параметр2=значение2)

Если вопрос не требует анализа данных (приветствие, общий вопрос), отвечай обычным текстом.

ДОПОЛНИТЕЛЬНЫЕ ПРАВИЛА ВЫБОРА ФУНКЦИЙ:
- Если пользователь спрашивает про КОНКРЕТНУЮ ДАТУ (один день), например: "Сколько я потратил 25 августа?",
  ТО используй get_expenses_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') с одинаковыми start_date и end_date = эта дата (в формате ISO, год возьми из контекста/текущего года).
- Если спрашивают про ДИАПАЗОН ДАТ, используй get_expenses_list с указанными датами.
- Если спрашивают про КАТЕГОРИИ за месяц ("в каких категориях я больше всего тратил в августе"), используй get_category_statistics и задай period_days по месяцу.
- Не используй get_daily_totals для одиночной даты — он для сводки по нескольким дням.

СПЕЦИАЛЬНЫЕ СЛУЧАИ:
- Для поисков с периодом "прошлая неделя", "прошлый месяц", "позавчера" используй search_expenses с period:
  "сколько я потратил на продукты на прошлой неделе" → search_expenses(query='продукты', period='last_week')
  "траты на кофе в прошлом месяце" → search_expenses(query='кофе', period='last_month')
  "траты позавчера" → search_expenses(query='', period='day_before_yesterday')
- Для вопросов "самая большая трата на прошлой неделе" используй:
  get_max_single_expense(period='last_week')
- Для вопросов "самая большая трата позавчера" используй:
  get_max_single_expense(period='day_before_yesterday')
- Для вопросов "самая большая трата в августе" используй:
  get_max_single_expense(period='август') или get_max_single_expense(period='august')
- Для вопросов "самая большая трата летом" используй:
  get_max_single_expense(period='лето') или get_max_single_expense(period='summer')
- Для вопросов "самый большой доход в прошлом месяце" используй:
  get_max_single_income(period='last_month')
- get_category_statistics используй когда нужна статистика по ВСЕМ категориям (не конкретной)
- get_category_total используй только для текущих периодов (этот месяц, эта неделя) без указания дат

{ctx_text}Вопрос пользователя: {message}"""
    return prompt
