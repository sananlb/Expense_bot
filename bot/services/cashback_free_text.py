"""
Свободный ввод кешбэка из текста:
- Пример: "добавь кешбек 5 процентов на категорию кафе и рестораны Промсвязьбанк"
- Требование: в тексте присутствуют слова "кешбек" и "категория" (допускается одна опечатка в каждом)
- Извлекаем: процент, категорию (сопоставляем с категориями пользователя), банк (оставшиеся слова; приоритет словам содержащим "банк")
"""
import re
from dataclasses import dataclass
from datetime import datetime
import calendar
from typing import Optional, Tuple, List, Set

from asgiref.sync import sync_to_async

from expenses.models import Profile, ExpenseCategory
from .cashback import add_cashback


def _levenshtein_distance(a: str, b: str) -> int:
    a = a.lower()
    b = b.lower()
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 1:
        return 2
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(
                dp[j] + 1,
                dp[j - 1] + 1,
                prev + cost,
            )
            prev = temp
    return dp[n]


def _normalize_letters(s: str) -> str:
    return (
        s.lower()
        .replace('ё', 'е')
        .replace('э', 'е')
        .replace('-', '')
    )


def _approx_contains(text: str, targets: List[str], prefix_ok: bool = False) -> bool:
    tokens = [ _normalize_letters(t) for t in re.findall(r"[\wа-яА-ЯёЁ\-]+", text.lower()) ]
    norm_targets = [_normalize_letters(t) for t in targets]
    for tok in tokens:
        for tgt in norm_targets:
            if _levenshtein_distance(tok, tgt) <= 1:
                return True
            if prefix_ok and tok.startswith(tgt[:max(3, len(tgt)-1)]):
                return True
    return False


def looks_like_cashback_free_text(text: str) -> bool:
    cashback_variants = ["кешбек", "кэшбек", "кэшбэк", "кешбэк", "cashback"]
    category_variants = ["категория"]
    return _approx_contains(text, cashback_variants, prefix_ok=False) and \
           _approx_contains(text, category_variants, prefix_ok=True)


_BANK_ALIASES = {
    # Т-Банк / Тинькофф (ребрендинг)
    "тинькофф": "Т-Банк",
    "т-банк": "Т-Банк",
    "тбанк": "Т-Банк",
    "tinkoff": "Т-Банк",
    # Сбер
    "сбер": "Сбер",
    "сбербанк": "Сбер",
    "sber": "Сбер",
    # Альфа
    "альфа": "Альфа-Банк",
    "альфабанк": "Альфа-Банк",
    "альфа-банк": "Альфа-Банк",
    "alfa": "Альфа-Банк",
    # ВТБ
    "втб": "ВТБ",
    "vtb": "ВТБ",
    # Райффайзен
    "райф": "Райффайзенбанк",
    "райффайзен": "Райффайзенбанк",
    "райффайзенбанк": "Райффайзенбанк",
    "raiffeisen": "Райффайзенбанк",
    # Газпромбанк
    "газпромбанк": "Газпромбанк",
    "gpbank": "Газпромбанк",
    # Промсвязьбанк
    "промсвязьбанк": "Промсвязьбанк",
    "psb": "Промсвязьбанк",
    # РоссельхозБанк
    "россельхозбанк": "Россельхозбанк",
    "рсхб": "Россельхозбанк",
    # Почта Банк
    "почтабанк": "Почта Банк",
    "почта банк": "Почта Банк",
    # Совкомбанк
    "совкомбанк": "Совкомбанк",
    # МТС Банк
    "мтсбанк": "МТС Банк",
    "мтс банк": "МТС Банк",
    # Открытие
    "открытие": "Открытие",
    # Ренессанс
    "ренессанс": "Ренессанс Банк",
    # Хоум Кредит
    "хоумкредит": "Хоум Кредит Банк",
    "хоум кредит": "Хоум Кредит Банк",
    # Росбанк
    "росбанк": "Росбанк",
    # Точка
    "точка": "Точка Банк",
    # УБРиР
    "убрир": "УБРиР",
    # ЮMoney/Яндекс и др.
    "яндекс": "Яндекс",
    "yandex": "Яндекс",
    # Озон
    "озон": "Озон",
}


def _normalize_bank_name(candidate: str) -> str:
    key = re.sub(r"[^\wа-яА-ЯёЁ]", "", candidate).lower()
    return _BANK_ALIASES.get(key, candidate.strip())


@dataclass
class ParsedCashback:
    percent: float
    category_name: str
    bank_name: str


def _extract_percent(text: str) -> Optional[float]:
    patterns = [
        r"(\d+[\.,]?\d*)\s*%",
        r"(\d+[\.,]?\d*)\s*процент\w*",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            val = m.group(1).replace(",", ".")
            try:
                return float(val)
            except ValueError:
                pass
    m = re.search(r"\b(\d+[\.,]?\d*)\b", text)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    return None


def _extract_category_and_bank(text: str) -> Tuple[Optional[str], Optional[str]]:
    # Проверяем специальный случай "все категории" / "всем категориям" и т.д.
    # Паттерн ищет: (все|всем|всех|всю) + (категори*)
    all_categories_pattern = r"\b(все|всем|всех|всю)\s+категор\w*"
    if re.search(all_categories_pattern, text, flags=re.IGNORECASE):
        # Это запрос на добавление кешбека ко ВСЕМ категориям
        # Извлекаем только банк (все что после "категори*")
        m = re.search(r"категор\w*\s+(.+)$", text, flags=re.IGNORECASE)
        if m:
            remainder = m.group(1).strip()
            remainder = re.sub(r"[\.,!]+$", "", remainder)
            # remainder может содержать только банк или банк с дополнительными словами
            # Возвращаем специальное значение "все" для категории
            return "все", remainder
        # Если не нашли что после категории, возвращаем ошибку
        return None, None

    m = re.search(r"категор\w*\s+(.+)$", text, flags=re.IGNORECASE)
    if not m:
        return None, None
    remainder = m.group(1).strip()
    remainder = re.sub(r"[\.,!]+$", "", remainder)
    tokens = re.findall(r"[\wа-яА-ЯёЁ\-]+", remainder)
    if not tokens:
        return None, None
    bank_tokens_idx = [i for i, t in enumerate(tokens) if "банк" in t.lower()]
    if bank_tokens_idx:
        start_bank = bank_tokens_idx[0]
        # По умолчанию категория — всё до вхождения "банк"
        category_tokens = tokens[:start_bank]
        bank_tokens: List[str] = []

        token_at = tokens[start_bank]
        token_at_l = token_at.lower()

        # Если встречаем паттерн "<Имя> банк" — включаем предыдущее слово в название банка
        # Пример: "Альфа банк" -> ["Альфа", "банк"]
        # Также корректно обработает слитные варианты типа "альфа-банк" или "тинькофф-банк".
        if token_at_l == "банк" and start_bank > 0:
            # Переназначаем категорию, исключив предыдущее слово — оно часть банка
            category_tokens = tokens[:start_bank - 1]
            bank_tokens.append(tokens[start_bank - 1])
            bank_tokens.append(tokens[start_bank])
        else:
            # Случай "альфа-банк", "тинькоффбанк" и т.п. — берём токен начиная с него
            bank_tokens.append(tokens[start_bank])

        # Добавляем последующие токены, пока не встретили числа или знак процента
        for t in tokens[start_bank + 1:]:
            if re.fullmatch(r"\d+[\.,]?\d*", t) or t == '%':
                break
            bank_tokens.append(t)

        category_name = " ".join(category_tokens).strip()
        bank_name = " ".join(bank_tokens).strip()
        return (category_name if category_name else None, bank_name if bank_name else None)
    if len(tokens) >= 2:
        category_candidate = " ".join(tokens[:-1]).strip()
        bank_candidate = _normalize_bank_name(tokens[-1])
        return (category_candidate if category_candidate else None, bank_candidate)
    return (remainder, None)


# Словарь синонимов для мультиязычной поддержки
_CATEGORY_SYNONYMS = {
    "подарки": ["gifts", "gift", "подарок"],
    "gifts": ["подарки", "подарок", "gift"],
    "рестораны": ["restaurants", "cafe", "кафе"],
    "restaurants": ["рестораны", "кафе", "cafe"],
    "супермаркеты": ["supermarkets", "products", "продукты"],
    "supermarkets": ["супермаркеты", "продукты", "products"],
    "одежда": ["clothes", "clothing", "обувь", "shoes"],
    "clothes": ["одежда", "обувь", "clothing", "shoes"],
    "развлечения": ["entertainment", "fun"],
    "entertainment": ["развлечения", "fun"],
    "путешествия": ["travel", "travels", "trip"],
    "travel": ["путешествия", "travels", "trip"],
    "такси": ["taxi", "cab"],
    "taxi": ["такси", "cab"],
    "аптеки": ["pharmacies", "pharmacy", "аптека"],
    "pharmacies": ["аптеки", "аптека", "pharmacy"],
    "спорт": ["sport", "sports", "fitness", "фитнес"],
    "sport": ["спорт", "sports", "fitness", "фитнес"],
}

@sync_to_async
def _resolve_category(profile: Profile, name: str) -> Optional[ExpenseCategory]:
    def tokenize(s: str) -> Set[str]:
        s = _normalize_letters(s)
        toks = re.findall(r"[\wа-яА-Я]+", s)
        stop = {"и", "в", "на", "по", "and", "or", "the"}
        return {t for t in toks if t and t not in stop}
    
    # Добавляем синонимы к целевым токенам
    def expand_with_synonyms(tokens: Set[str]) -> Set[str]:
        expanded = set(tokens)
        for token in tokens:
            if token in _CATEGORY_SYNONYMS:
                expanded.update(_CATEGORY_SYNONYMS[token])
        return expanded

    target_tokens = tokenize(name)
    if not target_tokens:
        return None
    
    # Расширяем целевые токены синонимами
    target_tokens = expand_with_synonyms(target_tokens)

    qs = profile.categories.all()
    
    # Логирование для отладки
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Searching for category '{name}' with tokens: {target_tokens}")
    
    for cat in qs:
        # Проверяем оба языковых поля категории
        for cat_name in [cat.name_ru, cat.name_en]:
            if not cat_name:
                continue
                
            cat_tokens = tokenize(cat_name)
            logger.debug(f"  Checking category field '{cat_name}' with tokens: {cat_tokens}")
            
            # Проверяем пересечение токенов (не обязательно полное включение)
            if target_tokens & cat_tokens:
                logger.debug(f"  -> Match found: {target_tokens & cat_tokens}")
                return cat

    # Проверяем точное совпадение нормализованных названий
    name_norm = _normalize_letters(name.strip())
    for cat in qs:
        # Проверяем оба языковых поля
        for cat_name in [cat.name_ru, cat.name_en]:
            if not cat_name:
                continue
            cleaned = _normalize_letters(re.sub(r"^[^\wа-яА-ЯёЁ]+", "", cat_name).strip())
            if cleaned == name_norm:
                logger.debug(f"  -> Exact match found: '{cat_name}'")
                return cat
    
    logger.debug(f"  -> No category found for '{name}'")
    return None


async def process_cashback_free_text(user_id: int, text: str):
    if not looks_like_cashback_free_text(text):
        return False, ""
    percent = _extract_percent(text)
    if percent is None or percent < 0 or percent > 99:
        return False, (
            "❌ Не удалось определить процент кешбэка.\n"
            "Укажите так: 'кешбек 5%', 'кешбек 5.5 процентов'."
        )
    cat_name, bank_name = _extract_category_and_bank(text)
    if not cat_name:
        return False, (
            "❌ Не удалось определить категорию.\n"
            "Формат: 'кешбек 5 процентов на категорию Кафе и рестораны <Банк>'."
        )
    try:
        profile = await sync_to_async(Profile.objects.get)(telegram_id=user_id)
    except Profile.DoesNotExist:
        return False, "❌ Профиль не найден. Отправьте /start."

    # Проверяем специальный случай "все категории"
    if cat_name.lower() == "все":
        # Извлекаем банк из bank_name (который содержит полный остаток текста)
        if not bank_name:
            return False, (
                "❌ Не удалось определить банк.\n"
                "Добавьте название банка, например: 'кешбек 5% на все категории Тинькофф'."
            )

        # Нормализуем название банка
        bank_name = _normalize_bank_name(bank_name)

        # Получаем все категории пользователя
        @sync_to_async
        def get_all_categories():
            return list(profile.categories.all())

        categories = await get_all_categories()
        if not categories:
            return False, (
                "❌ У вас пока нет категорий трат.\n"
                "Сначала создайте категории в разделе 'Категории'."
            )

        # Добавляем кешбек ко всем категориям
        now = datetime.now()
        month = now.month
        last_day = calendar.monthrange(now.year, now.month)[1]
        extended_next_month = (last_day - now.day) <= 1

        added_count = 0
        for category in categories:
            await add_cashback(
                user_id=user_id,
                category_id=category.id,
                bank_name=bank_name,
                cashback_percent=percent,
                month=month,
            )
            # Если создаем в последние 2 дня месяца — продлеваем на следующий
            if extended_next_month:
                next_month = 1 if month == 12 else month + 1
                await add_cashback(
                    user_id=user_id,
                    category_id=category.id,
                    bank_name=bank_name,
                    cashback_percent=percent,
                    month=next_month,
                )
            added_count += 1

        percent_str = ("{:.1f}".format(percent)).rstrip('0').rstrip('.')
        msg = (
            "✅ Кешбэк добавлен для всех категорий\n\n"
            f"Банк: {bank_name}\n"
            f"Категорий: {added_count}\n"
            f"Процент: {percent_str}%\n"
            f"Месяц: {month}"
        )
        if extended_next_month:
            msg += "\nТакже продлён на следующий месяц"
        return True, msg

    # Обычный случай - одна категория
    category = await _resolve_category(profile, cat_name)
    if not category:
        return False, (
            "❌ Категория не найдена среди ваших.\n"
            "Откройте раздел категорий и проверьте точное название."
        )
    if not bank_name:
        for alias, canon in _BANK_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text, flags=re.IGNORECASE):
                bank_name = canon
                break
    if not bank_name:
        return False, (
            "❌ Не удалось определить банк.\n"
            "Добавьте название банка в конце, например: '… категория Кафе и рестораны Тинькофф'."
        )
    bank_name = _normalize_bank_name(bank_name)
    now = datetime.now()
    month = now.month
    await add_cashback(
        user_id=user_id,
        category_id=category.id,
        bank_name=bank_name,
        cashback_percent=percent,
        month=month,
    )
    # Если кешбэк создан в последние 2 дня месяца — продлеваем на следующий месяц
    last_day = calendar.monthrange(now.year, now.month)[1]
    extended_next_month = False
    if (last_day - now.day) <= 1:
        next_month = 1 if month == 12 else month + 1
        await add_cashback(
            user_id=user_id,
            category_id=category.id,
            bank_name=bank_name,
            cashback_percent=percent,
            month=next_month,
        )
        extended_next_month = True
    percent_str = ("{:.1f}".format(percent)).rstrip('0').rstrip('.')
    # Получаем язык пользователя для правильного отображения категории
    from bot.utils.language import get_user_language
    user_lang = await get_user_language(user_id)
    category_display_name = category.get_display_name(user_lang)

    msg = (
        "✅ Кешбэк добавлен\n\n"
        f"Банк: {bank_name}\n"
        f"Категория: {category_display_name}\n"
        f"Процент: {percent_str}%\n"
        f"Месяц: {month}"
    )
    if extended_next_month:
        msg += "\nТакже продлён на следующий месяц"
    return True, msg
