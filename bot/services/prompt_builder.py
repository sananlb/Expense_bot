"""
Unified prompt builder for function-calling across AI providers.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict

def build_function_call_prompt(message: str, context: List[Dict[str,str]]|None=None, user_language: str = 'ru') -> str:
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
            ctx_text = f"Dialog context: {' | '.join(recent)}\n"

    # Language mapping
    lang_names = {
        'ru': 'Russian',
        'en': 'English',
        'es': 'Spanish',
        'de': 'German',
        'fr': 'French'
    }
    lang_instruction = f"**IMPORTANT: You MUST respond in {lang_names.get(user_language, 'Russian')} language.**"

    prompt = f"""You are a finance tracking assistant for both expenses and income. You have access to functions for financial analysis.
Today: {today.strftime('%Y-%m-%d')} ({today.strftime('%B %Y')})

{lang_instruction}


AVAILABLE EXPENSE FUNCTIONS:
1. get_max_expense_day(period='last_week'|'last_month'|'week'|'month') - for "What day did I spend the most last week?"
2. get_period_total(period='today'|'yesterday'|'day_before_yesterday'|'week'|'last_week'|'month'|'last_month'|'year'|'январь'|...|'декабрь'|'january'|...|'december'|'зима'|'весна'|'лето'|'осень'|'winter'|'spring'|'summer'|'fall') - for "How much did I spend today/yesterday/day before yesterday/last week/in August/in summer?"
3. get_max_single_expense(period='last_week'|'last_month'|'day_before_yesterday'|'week'|'month'|'январь'|'февраль'|...|'декабрь'|'january'|'august'|'зима'|'весна'|'лето'|'осень') - for "What's my biggest expense day before yesterday/last week/last month/in August/in summer?"
4. get_min_single_expense(period='last_week'|'last_month'|'week'|'month') - for "What's my smallest/cheapest expense last week/last month?"
5. get_category_statistics() - for "What do I spend the most on?"
6. get_average_expenses() - for "How much do I spend on average?"
7. get_recent_expenses(limit=10) - for "Show recent expenses"
8. search_expenses(query='text', period='last_week'|'last_month') - UNIVERSAL SEARCH in categories AND descriptions: "How much did I spend on groceries last week?", "Coffee expenses last month"
9. get_weekday_statistics() - for "What days of the week do I spend more?"
10. predict_month_expense() - for "How much will I spend this month?"
11. compare_periods() - for "Am I spending more or less?"
12. get_expense_trend() - for "Show expense trend"
13. get_expenses_by_amount_range(min_amount=1000) - for "Show expenses over 1000"
14. get_category_total(category='groceries', period='month'|'week'|'январь'|...|'декабрь'|'january'|...|'december'|'зима'|'лето'|'winter'|'summer') - for CATEGORIES: "How much did I spend on groceries this month/in August/in summer?"
15. get_expenses_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') - for "Show expenses for period/from date to date"
16. get_daily_totals(days=30) - for "Show daily expenses/totals for last month"

AVAILABLE INCOME FUNCTIONS:
18. get_max_income_day() - for "What day did I earn the most?"
19. get_income_period_total(period='today'|'yesterday'|'week'|'month'|'year') - for "How much did I earn today/yesterday/this week?"
20. get_max_single_income(period='last_week'|'last_month'|'week'|'month'|'январь'|'февраль'|...|'декабрь'|'january'|'august'|'зима'|'весна'|'лето'|'осень') - for "What's my biggest income last week/last month/in August/in summer?"
21. get_income_category_statistics() - for "Where does most income come from?"
22. get_average_incomes() - for "How much do I earn on average?"
23. get_recent_incomes(limit=10) - for "Show recent income"
24. search_incomes(query='text') - for "When did I receive..."
25. get_income_weekday_statistics() - for "What days of the week have more income?"
26. predict_month_income() - for "How much will I earn this month?"
27. check_income_target(target_amount=100000) - for "Will I reach my income goal?"
28. compare_income_periods() - for "Am I earning more or less?"
29. get_income_trend() - for "Show income trend"
30. get_incomes_by_amount_range(min_amount=10000) - for "Show income over 10000"
31. get_income_category_total(category='salary', period='month') - for "How much salary do I get?"
32. get_incomes_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') - for "Show income for period"
33. get_daily_income_totals(days=30) - for "Show daily income"

COMPLEX ANALYSIS FUNCTIONS:
34. get_all_operations(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD', limit=200) - for "All operations", "Show all transactions"
35. get_financial_summary(period='month') - for "Financial summary", "Balance", "Month results"

UNIVERSAL FUNCTION (USE IF NO SUITABLE FUNCTION ABOVE):
36. analytics_query(spec_json='<JSON query specification>') - for non-standard analytical queries

CRITICALLY IMPORTANT: search_expenses is a UNIVERSAL search function!
search_expenses searches BOTH in categories AND in expense descriptions simultaneously.

Examples of search_expenses usage:
- "How much did I spend on groceries in September?" → search_expenses(query='groceries', start_date='2025-09-01', end_date='2025-09-30')
- "How much did I spend on snickers in September?" → search_expenses(query='snickers', start_date='2025-09-01', end_date='2025-09-30')
- "Transport expenses in August" → search_expenses(query='transport', start_date='2025-08-01', end_date='2025-08-31')
- "Expenses at store X this month" → search_expenses(query='store name', start_date='2025-MM-01', end_date='2025-MM-31')
- "Supermarket purchases" → search_expenses(query='supermarket')

IMPORTANT: If the question requires data analysis, respond ONLY in format:
FUNCTION_CALL: function_name(parameter1=value1, parameter2=value2)

If the question doesn't require data analysis (greeting, general question), respond in plain text.

ADDITIONAL FUNCTION SELECTION RULES:
- If user asks about SPECIFIC DATE (single day), e.g. "How much did I spend on August 25?",
  THEN use get_expenses_list(start_date='YYYY-MM-DD', end_date='YYYY-MM-DD') with same start_date and end_date = this date (in ISO format, take year from context/current year).
- If asking about DATE RANGE, use get_expenses_list with specified dates.
- If asking about CATEGORIES for a month ("what categories did I spend most in August"), use get_category_statistics and set period_days for the month.
- Don't use get_daily_totals for single date - it's for summary across multiple days.

SPECIAL CASES:
- For searches with period "last week", "last month", "day before yesterday" use search_expenses with period:
  "how much did I spend on groceries last week" → search_expenses(query='groceries', period='last_week')
  "coffee expenses last month" → search_expenses(query='coffee', period='last_month')
  "expenses day before yesterday" → search_expenses(query='', period='day_before_yesterday')
- For questions "biggest expense last week" use:
  get_max_single_expense(period='last_week')
- For questions "biggest expense day before yesterday" use:
  get_max_single_expense(period='day_before_yesterday')
- For questions "biggest expense in August" use:
  get_max_single_expense(period='август') or get_max_single_expense(period='august')
- For questions "biggest expense in summer" use:
  get_max_single_expense(period='лето') or get_max_single_expense(period='summer')
- For questions "biggest income last month" use:
  get_max_single_income(period='last_month')
- Use get_category_statistics when statistics for ALL categories needed (not specific one)
- Use get_category_total only for current periods (this month, this week) without specifying dates

{ctx_text}User question: {message}"""
    return prompt
