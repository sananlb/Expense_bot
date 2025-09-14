"""
Utilities for unified function-calling parameter normalization and sanitization
used by both Google and OpenAI services.
"""
from __future__ import annotations

from typing import Dict, Tuple, Optional
import json
import re
import calendar
from datetime import datetime


ALLOWED_PARAMS: Dict[str, set] = {
    # Expenses
    'get_max_expense_day': {'user_id', 'period_days'},
    'get_period_total': {'user_id', 'period'},
    'get_max_single_expense': {'user_id', 'period_days'},
    'get_category_statistics': {'user_id', 'period_days', 'start_date', 'end_date'},
    'get_average_expenses': {'user_id', 'period_days'},
    'get_recent_expenses': {'user_id', 'limit'},
    'get_daily_totals': {'user_id', 'days'},
    'search_expenses': {'user_id', 'query', 'limit'},
    'get_weekday_statistics': {'user_id', 'period_days'},
    'predict_month_expense': {'user_id'},
    'check_budget_status': {'user_id', 'budget_amount'},
    'compare_periods': {'user_id', 'period1', 'period2'},
    'get_expense_trend': {'user_id', 'group_by', 'periods'},
    'get_expenses_by_amount_range': {'user_id', 'min_amount', 'max_amount', 'limit'},
    'get_category_total': {'user_id', 'category', 'period'},
    'get_expenses_list': {'user_id', 'start_date', 'end_date', 'limit'},

    # Incomes
    'get_max_income_day': {'user_id'},
    'get_income_period_total': {'user_id', 'period'},
    'get_max_single_income': {'user_id'},
    'get_income_category_statistics': {'user_id'},
    'get_average_incomes': {'user_id'},
    'get_recent_incomes': {'user_id', 'limit'},
    'search_incomes': {'user_id', 'query', 'limit'},
    'get_income_weekday_statistics': {'user_id'},
    'predict_month_income': {'user_id'},
    'check_income_target': {'user_id', 'target_amount'},
    'compare_income_periods': {'user_id'},
    'get_income_trend': {'user_id', 'days'},
    'get_incomes_by_amount_range': {'user_id', 'min_amount', 'max_amount', 'limit'},
    'get_income_category_total': {'user_id', 'category', 'period'},
    'get_incomes_list': {'user_id', 'start_date', 'end_date', 'limit'},
    'get_daily_income_totals': {'user_id', 'days'},

    # Unified / combined
    'get_all_operations': {'user_id', 'start_date', 'end_date', 'limit'},
    'get_financial_summary': {'user_id', 'period'},

    # Analytics fallback
    'analytics_query': {'user_id', 'spec_json'},
}


def sanitize_func_name(message: str, func_name: str) -> str:
    """Heuristically map non-ASCII or unknown function names to known ones."""
    if not func_name or any(ord(c) > 127 for c in func_name):
        low = (message or '').lower()
        if (('день' in low or 'дата' in low) and
            ('больше' in low or 'максим' in low) and
            ('потрат' in low or 'траты' in low)):
            return 'get_max_expense_day'
        if ('статистик' in low or 'категор' in low) and ('трат' in low or 'расход' in low):
            return 'get_category_statistics'
    return func_name


def _sanitize_keys(params: Dict, allowed: set) -> Dict:
    out: Dict[str, object] = {}
    for k, v in (params or {}).items():
        if not isinstance(k, str):
            continue
        if any(ord(c) > 127 for c in k):
            continue
        if not re.match(r'^[A-Za-z0-9_]+$', k):
            continue
        if k in allowed:
            out[k] = v
    return out


def _norm_datespan_to_days(ps: Dict) -> Optional[int]:
    try:
        sd = datetime.fromisoformat(str(ps['start_date']).strip("'\""))
        ed = datetime.fromisoformat(str(ps['end_date']).strip("'\""))
        return max(1, (ed.date() - sd.date()).days + 1)
    except Exception:
        return None


def _norm_period_to_days(ps: Dict) -> Optional[int]:
    period = str(ps.get('period', '')).lower()
    month = ps.get('month')
    year = ps.get('year')
    try:
        if period == 'week':
            return 7
        if period == 'year':
            return 365
        if period == 'month':
            if month and year:
                return calendar.monthrange(int(year), int(month))[1]
            return 31
    except Exception:
        return None
    return None


def normalize_function_call(
    message: str,
    func_name: str,
    params: Dict,
    user_id: Optional[int],
) -> Tuple[str, Dict]:
    func_name = sanitize_func_name(message, func_name)
    params = dict(params or {})
    params['user_id'] = user_id

    # Heuristic remap: user asks for MIN but model picked MAX
    low_msg = (message or '').lower()
    if func_name == 'get_max_single_expense' and any(s in low_msg for s in ['миним', 'маленьк', 'наименьш', 'дешев']):
        spec = {
            "entity": "expenses",
            "filters": {"date": {"period": "month"}},
            "sort": [{"by": "amount", "dir": "asc"}],
            "limit": 1,
            "projection": ["date", "amount", "category", "description", "currency"],
        }
        return 'analytics_query', {'user_id': user_id, 'spec_json': json.dumps(spec, ensure_ascii=False)}

    # Heuristic remap: minimum income
    if func_name == 'get_max_single_income' and any(s in low_msg for s in ['миним', 'маленьк', 'наименьш', 'дешев']):
        spec = {
            "entity": "incomes",
            "filters": {"date": {"period": "month"}},
            "sort": [{"by": "amount", "dir": "asc"}],
            "limit": 1,
            "projection": ["date", "amount", "category", "description", "currency"],
        }
        return 'analytics_query', {'user_id': user_id, 'spec_json': json.dumps(spec, ensure_ascii=False)}

    # Heuristic remap: minimum operation (mixed expenses+incomes)
    if any(s in low_msg for s in ['миним', 'маленьк', 'наименьш', 'дешев']) and 'операц' in low_msg and func_name in (
        'get_all_operations', 'get_financial_summary', 'get_max_single_expense', 'get_max_single_income'
    ):
        spec = {
            "entity": "operations",
            "filters": {"date": {"period": "month"}},
            "sort": [{"by": "amount", "dir": "asc"}],
            "limit": 1,
            "projection": ["date", "amount", "type", "category", "description", "currency"],
        }
        return 'analytics_query', {'user_id': user_id, 'spec_json': json.dumps(spec, ensure_ascii=False)}

    # Handle analytics_query specially - keep spec_json as is
    if func_name == 'analytics_query':
        return func_name, {
            'user_id': user_id,
            'spec_json': params.get('spec_json', '{}')
        }

    # Map deprecated function to supported one with explicit dates
    if func_name == 'get_category_total_by_dates':
        func_name = 'get_category_statistics'
        ps = {}
        if 'start_date' in params and 'end_date' in params:
            ps = {
                'user_id': user_id,
                'start_date': params.get('start_date'),
                'end_date': params.get('end_date'),
            }
        else:
            # Fallback to 31 days if parsing failed
            ps = {'user_id': user_id, 'period_days': 31}
        return func_name, ps

    if func_name == 'get_category_statistics':
        # Prefer explicit start/end dates when provided
        if 'start_date' in params and 'end_date' in params:
            params = _sanitize_keys(params, ALLOWED_PARAMS[func_name])
            params['user_id'] = user_id
        else:
            days = _norm_datespan_to_days(params)
            if days:
                params = {'user_id': user_id, 'period_days': days}
            else:
                params = _sanitize_keys(params, ALLOWED_PARAMS[func_name])

    elif func_name == 'get_max_expense_day':
        days = params.get('period_days')
        if not days:
            days = _norm_period_to_days(params)
        ps = {'user_id': user_id}
        if days:
            try:
                ps['period_days'] = int(days)
            except Exception:
                pass
        params = ps

    elif func_name == 'get_daily_totals':
        days = _norm_datespan_to_days(params)
        if days:
            params = {'user_id': user_id, 'days': days}
        else:
            params = _sanitize_keys(params, ALLOWED_PARAMS[func_name])

    elif func_name in ('get_expenses_list', 'get_incomes_list'):
        # Ensure single-date queries become start=end=same date in ISO
        ps = _sanitize_keys(params, ALLOWED_PARAMS[func_name])
        sd = ps.get('start_date')
        ed = ps.get('end_date')
        try:
            if sd and not ed:
                # If single date provided, mirror to end_date
                datetime.fromisoformat(str(sd).strip("'\""))
                ps['end_date'] = sd
        except Exception:
            pass
        ps['user_id'] = user_id
        params = ps

    else:
        allowed = ALLOWED_PARAMS.get(func_name, {'user_id'})
        params = _sanitize_keys(params, allowed)
        if 'user_id' not in params:
            params['user_id'] = user_id

    return func_name, params
