"""
Top-5 aggregation and rendering service
"""
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple

from asgiref.sync import sync_to_async
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from expenses.models import Expense, Income, Profile, ExpenseCategory, IncomeCategory, Cashback, Top5Snapshot, Top5Pin
from bot.utils import get_currency_symbol, format_amount
from bot.utils.category_helpers import get_category_display_name, get_category_emoji


def _norm_title(title: str) -> str:
    return (title or '').strip().lower()


def _norm_amount(amount: Decimal, currency: str) -> Decimal:
    # Округление до точности валюты (по умолчанию 2 знака; для некоторых валют 0)
    zero_decimals = {'RUB', 'JPY', 'KRW', 'CLP', 'ISK', 'TWD', 'HUF', 'COP', 'IDR', 'VND'}
    quant = Decimal('1') if currency.upper() in zero_decimals else Decimal('0.01')
    return (Decimal(amount).quantize(quant, rounding=ROUND_HALF_UP))


def _make_id(title_norm: str, category_id: int, amount_norm: Decimal, currency: str, op_type: str) -> str:
    s = f"{title_norm}|{category_id}|{amount_norm}|{currency.upper()}|{op_type}"
    h = hashlib.sha1(s.encode('utf-8')).hexdigest()  # 40 hex chars
    return h[:16]  # compact id


@sync_to_async
def calculate_top5_sync(profile: Profile, window_start: date, window_end: date) -> Tuple[List[Dict], str]:
    """Собрать топ-5 за окно по правилам. Возвращает (items, hash).

    Каждый item содержит:
      id, title_display, title_norm, category_id, category_kind (expense|income), amount, amount_norm,
      currency, op_type (expense|income), count, last_at
    """
    # Собираем расходы
    expense_qs = Expense.objects.filter(
        profile=profile,
        expense_date__gte=window_start,
        expense_date__lte=window_end,
    ).select_related('category')

    # Собираем доходы
    income_qs = Income.objects.filter(
        profile=profile,
        income_date__gte=window_start,
        income_date__lte=window_end,
    ).select_related('category')

    groups: Dict[Tuple, Dict] = {}

    # Группировка расходов
    for e in expense_qs:
        title_norm = _norm_title(e.description)
        amount_norm = _norm_amount(e.amount, e.currency or 'RUB')
        key = (title_norm, e.category_id or 0, str(amount_norm), (e.currency or 'RUB').upper(), 'expense')
        g = groups.setdefault(key, {
            'title_norm': title_norm,
            'title_display': e.description or '',
            'category_id': e.category_id or 0,
            'category_kind': 'expense',
            'amount': Decimal(e.amount),
            'amount_norm': amount_norm,
            'currency': (e.currency or 'RUB').upper(),
            'op_type': 'expense',
            'count': 0,
            'last_at': None,
        })
        g['count'] += 1
        # Берём самое свежее название
        last_dt = datetime.combine(e.expense_date, e.expense_time)
        if not g['last_at'] or last_dt > g['last_at']:
            g['last_at'] = last_dt
            g['title_display'] = e.description or ''

    # Группировка доходов
    for inc in income_qs:
        title_norm = _norm_title(inc.description)
        amount_norm = _norm_amount(inc.amount, inc.currency or 'RUB')
        key = (title_norm, inc.category_id or 0, str(amount_norm), (inc.currency or 'RUB').upper(), 'income')
        g = groups.setdefault(key, {
            'title_norm': title_norm,
            'title_display': inc.description or '',
            'category_id': inc.category_id or 0,
            'category_kind': 'income',
            'amount': Decimal(inc.amount),
            'amount_norm': amount_norm,
            'currency': (inc.currency or 'RUB').upper(),
            'op_type': 'income',
            'count': 0,
            'last_at': None,
        })
        g['count'] += 1
        last_dt = datetime.combine(inc.income_date, inc.income_time)
        if not g['last_at'] or last_dt > g['last_at']:
            g['last_at'] = last_dt
            g['title_display'] = inc.description or ''

    # Оставляем только группы с count >= 2
    candidates = [v for v in groups.values() if v['count'] >= 2]

    # Делим на расходы/доходы с сортировкой
    def sort_key(it):
        return (-it['count'], -(it['last_at'].timestamp() if it['last_at'] else 0), it['title_norm'])

    expenses_sorted = sorted([g for g in candidates if g['op_type'] == 'expense'], key=sort_key)
    incomes_sorted = sorted([g for g in candidates if g['op_type'] == 'income'], key=sort_key)

    # Слияние: сначала расходы, затем доходы, максимум 5
    final: List[Dict] = []
    for lst in (expenses_sorted, incomes_sorted):
        for g in lst:
            if len(final) < 5:
                g_copy = dict(g)
                g_copy['id'] = _make_id(g['title_norm'], g['category_id'], g['amount_norm'], g['currency'], g['op_type'])
                final.append(g_copy)

    # Разрешаем коллизии категорий: найдём множества с одинаковыми (title_norm, amount_norm, currency, op_type)
    key_counts: Dict[Tuple, int] = {}
    for it in final:
        kk = (it['title_norm'], str(it['amount_norm']), it['currency'], it['op_type'])
        key_counts[kk] = key_counts.get(kk, 0) + 1
    for it in final:
        kk = (it['title_norm'], str(it['amount_norm']), it['currency'], it['op_type'])
        it['needs_category_hint'] = key_counts[kk] > 1

    # Подготовка к сериализации для JSONField
    serialized: List[Dict] = []
    for it in final:
        serialized.append({
            'id': it['id'],
            'title_display': it.get('title_display') or '',
            'title_norm': it.get('title_norm') or '',
            'category_id': int(it.get('category_id') or 0),
            'category_kind': it.get('category_kind') or 'expense',
            'amount': float(it.get('amount_norm') or 0),  # используем нормализованную сумму
            'amount_norm': float(it.get('amount_norm') or 0),
            'currency': (it.get('currency') or 'RUB').upper(),
            'op_type': it.get('op_type') or 'expense',
            'count': int(it.get('count') or 0),
            'last_at': (it.get('last_at').isoformat() if it.get('last_at') else None),
            'needs_category_hint': bool(it.get('needs_category_hint', False)),
        })

    # Хэш состава (включая порядок)
    def serial(it: Dict) -> str:
        return f"{it['id']}|{it['count']}"
    digest = hashlib.sha1('|'.join(serial(i) for i in serialized).encode('utf-8')).hexdigest()

    return serialized, digest


@sync_to_async
def save_snapshot(profile: Profile, window_start: date, window_end: date, items: List[Dict], digest: str) -> Top5Snapshot:
    obj, _ = Top5Snapshot.objects.update_or_create(
        profile=profile,
        defaults={
            'window_start': window_start,
            'window_end': window_end,
            'items': items,
            'hash': digest,
        }
    )
    return obj


def build_top5_keyboard(items: List[Dict], lang: str = 'ru') -> InlineKeyboardMarkup:
    rows = []
    # Предварительно соберём подсказки категорий
    for it in items:
        title = it.get('title_display') or ''
        if len(title) > 30:
            title = title[:27] + '…'
        amt_str = format_amount(float(it['amount_norm']), currency=it['currency'], lang=lang)
        if it['op_type'] == 'income':
            # Добавляем + только к сумме
            if ' ' in amt_str:
                parts = amt_str.split(' ', 1)
                amt_vis = f"+{parts[0]} {parts[1]}"
            else:
                amt_vis = f"+{amt_str}"
        else:
            amt_vis = amt_str

        # Между названием и суммой с тире
        btn_text = f"{title} — {amt_vis}"
        if it.get('needs_category_hint'):
            # Добавляем эмодзи категории, если есть; иначе краткое имя в скобках
            cat_emoji = None
            try:
                if it['category_kind'] == 'expense' and it['category_id']:
                    cat = ExpenseCategory.objects.filter(id=it['category_id']).first()
                elif it['category_kind'] == 'income' and it['category_id']:
                    cat = IncomeCategory.objects.filter(id=it['category_id']).first()
                else:
                    cat = None
                cat_emoji = get_category_emoji(cat) if cat else None
                if cat_emoji:
                    btn_text += f" {cat_emoji}"
                elif cat:
                    btn_text += f" ({get_category_display_name(cat)})"
            except Exception:
                pass

        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"t5:{it['id']}")])

    # Добавляем кнопку Назад и Закрыть
    from bot.utils import get_text
    rows.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data='expenses_today')])
    rows.append([InlineKeyboardButton(text=get_text('close', lang), callback_data='close')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@sync_to_async
def get_current_cashback_amount(profile: Profile, category_id: int, amount: Decimal, when: date) -> Decimal:
    """Рассчитать актуальный кешбэк по категории на дату.
    Возвращает сумму кешбэка (amount * percent, с учётом лимита).
    """
    try:
        month = when.month
        qs = Cashback.objects.filter(profile=profile, month=month, category_id=category_id)
        if not qs.exists():
            return Decimal('0')
        cb = max(qs, key=lambda x: x.cashback_percent)
        val = (Decimal(amount) * cb.cashback_percent) / Decimal('100')
        if cb.limit_amount:
            return min(val, cb.limit_amount)
        return val
    except Exception:
        return Decimal('0')


@sync_to_async
def get_profiles_with_activity(window_start: date, window_end: date) -> List[Profile]:
    from django.db.models import Q
    expense_profiles = Expense.objects.filter(
        expense_date__gte=window_start, expense_date__lte=window_end
    ).values_list('profile_id', flat=True).distinct()
    income_profiles = Income.objects.filter(
        income_date__gte=window_start, income_date__lte=window_end
    ).values_list('profile_id', flat=True).distinct()
    ids = set(list(expense_profiles) + list(income_profiles))
    return list(Profile.objects.filter(id__in=ids))
