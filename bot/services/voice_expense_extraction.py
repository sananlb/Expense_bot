"""
Structured extraction for premium voice expense input.

Pipeline:
- OpenRouter audio-capable model -> JSON expense items
- fallback: Yandex STT -> DeepSeek text split -> same JSON schema
"""
from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from bot.constants import MAX_OPERATION_DESCRIPTION_LENGTH, MAX_TRANSACTION_AMOUNT
from bot.utils.expense_parser import AMOUNT_MULTIPLIERS, CURRENCY_PATTERNS, WORD_TO_NUMBER
from bot.utils.logging_safe import log_safe_id, summarize_text
from bot.utils.multiple_expense_parser import MAX_MULTIPLE_EXPENSES_PER_MESSAGE

from .ai_selector import AISelector, get_model, get_service
from .yandex_speech import YandexSpeechKit

logger = logging.getLogger(__name__)


VOICE_EXPENSE_JSON_SCHEMA_HINT = """
Return only valid JSON with this shape:
{
  "transcript": "what you heard/read",
  "items": [
    {
      "description": "item name, including quantity/unit/package",
      "amount": 123.45,
      "currency": "RUB",
      "confidence": 0.95
    }
  ]
}

Rules:
- description includes product quantity and units: "beer 1 liter", "cheese 300 g".
- amount is only a price explicitly said by the user. If no price was said, use null.
- currency is only an explicitly said currency. If no currency was said, use null.
- Do not infer, estimate, restore, or invent prices.
- Do not treat quantity/unit numbers as prices.
- Never split an item between quantity and its price.
- Use ISO 4217 currency codes only.
- Return no markdown and no explanation.
"""


VOICE_EXPENSE_AUDIO_PROMPT = """
Extract expense items from this voice message.
Keep the transcript in the same language as speech.

Important example:
"рыба сушеная 290 кальмар 250 жигулевское 1 литр 180 мороженое"
means:
- рыба сушеная, amount 290
- кальмар, amount 250
- жигулевское 1 литр, amount 180
- мороженое, amount null

""" + VOICE_EXPENSE_JSON_SCHEMA_HINT


TEXT_EXPENSE_SPLIT_PROMPT = """
Extract expense items from the user text.
The text may contain several expense items without commas.

Important example:
"рыба сушеная 290 кальмар 250 жигулевское 1 литр 180 мороженое"
means:
- рыба сушеная, amount 290
- кальмар, amount 250
- жигулевское 1 литр, amount 180
- мороженое, amount null

""" + VOICE_EXPENSE_JSON_SCHEMA_HINT


UNIT_WORDS = {
    "л",
    "л.",
    "литр",
    "литра",
    "литров",
    "ml",
    "мл",
    "миллилитр",
    "миллилитра",
    "миллилитров",
    "kg",
    "кг",
    "килограмм",
    "килограмма",
    "килограммов",
    "g",
    "г",
    "гр",
    "гр.",
    "грамм",
    "грамма",
    "граммов",
    "шт",
    "шт.",
    "штука",
    "штуки",
    "штук",
    "уп",
    "уп.",
    "упаковка",
    "упаковки",
    "упаковок",
    "пачка",
    "пачки",
    "пачек",
    "бутылка",
    "бутылки",
    "бутылок",
    "банка",
    "банки",
    "банок",
    "пакет",
    "пакета",
    "пакетов",
    "кусок",
    "куска",
    "кусков",
    "liter",
    "liters",
    "litre",
    "litres",
    "gram",
    "grams",
    "piece",
    "pieces",
    "pack",
    "packs",
    "bottle",
    "bottles",
    "can",
    "cans",
}


def parse_json_object(value: Any) -> Optional[Dict[str, Any]]:
    """Parse a JSON object from model output, tolerating fenced JSON."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.warning("[VoiceExpenseExtraction] Model output is not JSON: %s", summarize_text(text))
            return None
        try:
            loaded = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            logger.warning("[VoiceExpenseExtraction] JSON parse failed: %s", exc)
            return None

    if isinstance(loaded, list):
        return {"transcript": "", "items": loaded}
    if isinstance(loaded, dict):
        return loaded
    return None


def normalize_voice_expense_payload(
    payload: Any,
    *,
    fallback_transcript: Optional[str] = None,
    source: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Validate and normalize the minimal voice expense JSON schema.

    Amounts that are not represented in transcript as a non-unit number are
    treated as absent instead of being accepted blindly.
    """
    data = parse_json_object(payload)
    if not data:
        return None

    transcript = _clean_text(data.get("transcript") or fallback_transcript or "")
    if not transcript:
        logger.warning("[VoiceExpenseExtraction] Missing transcript in %s payload", source or "unknown")
        return None

    raw_items = data.get("items") or data.get("expenses")
    if not isinstance(raw_items, list):
        logger.warning("[VoiceExpenseExtraction] Missing items list in %s payload", source or "unknown")
        return None
    if not 1 <= len(raw_items) <= MAX_MULTIPLE_EXPENSES_PER_MESSAGE:
        logger.warning(
            "[VoiceExpenseExtraction] Invalid items count in %s payload: %s",
            source or "unknown",
            len(raw_items),
        )
        return None

    normalized_items: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            logger.warning("[VoiceExpenseExtraction] Item %s is not an object", index)
            return None

        description = _clean_text(raw_item.get("description") or raw_item.get("name") or "")
        if not description or len(description) > MAX_OPERATION_DESCRIPTION_LENGTH:
            logger.warning("[VoiceExpenseExtraction] Invalid description at item %s", index)
            return None

        amount = _coerce_amount(raw_item.get("amount"))
        if amount is not None and not _amount_is_represented_as_price(amount, transcript):
            logger.warning(
                "[VoiceExpenseExtraction] Amount demoted to null: amount=%s item=%s transcript=%s",
                amount,
                summarize_text(description),
                summarize_text(transcript),
            )
            amount = None

        normalized_items.append(
            {
                "description": description,
                "amount": float(amount) if amount is not None else None,
                "currency": _normalize_currency(raw_item.get("currency")),
                "confidence": _normalize_confidence(raw_item.get("confidence")),
            }
        )

    return {
        "transcript": transcript,
        "items": normalized_items,
    }


class VoiceExpenseExtractionService:
    """Coordinates the two allowed premium voice batch extraction paths."""

    MIN_AUDIO_BYTES = 3000

    @classmethod
    async def extract(
        cls,
        audio_bytes: bytes,
        *,
        user_language: str = "ru",
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if len(audio_bytes) < cls.MIN_AUDIO_BYTES:
            logger.warning(
                "[VoiceExpenseExtraction] %s | Audio too small: %s bytes",
                log_safe_id(user_id, "user"),
                len(audio_bytes),
            )
            return None

        primary = await cls._extract_openrouter_audio(audio_bytes, user_language=user_language, user_id=user_id)
        if primary:
            return primary

        logger.info(
            "[VoiceExpenseExtraction] %s | OpenRouter audio path failed, trying Yandex+DeepSeek",
            log_safe_id(user_id, "user"),
        )
        return await cls._extract_yandex_deepseek(audio_bytes, user_language=user_language, user_id=user_id)

    @classmethod
    async def _extract_openrouter_audio(
        cls,
        audio_bytes: bytes,
        *,
        user_language: str,
        user_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        try:
            service = get_service("voice")
            model = get_model("voice", "openrouter")
            raw_payload = await service.extract_voice_expenses(
                audio_bytes,
                model=model,
                user_context={"user_id": user_id, "language": user_language},
            )
        except Exception as exc:
            logger.error(
                "[VoiceExpenseExtraction] %s | OpenRouter audio extraction error: %s",
                log_safe_id(user_id, "user"),
                exc,
            )
            return None

        payload = normalize_voice_expense_payload(raw_payload, source="openrouter_audio")
        if not payload:
            logger.warning(
                "[VoiceExpenseExtraction] %s | Invalid OpenRouter audio payload: %s",
                log_safe_id(user_id, "user"),
                summarize_text(str(raw_payload)),
            )
            return None

        payload["pipeline"] = "openrouter_audio"
        logger.info(
            "[VoiceExpenseExtraction] %s | OpenRouter audio ok | items=%s transcript=%s",
            log_safe_id(user_id, "user"),
            len(payload["items"]),
            summarize_text(payload["transcript"]),
        )
        return payload

    @classmethod
    async def _extract_yandex_deepseek(
        cls,
        audio_bytes: bytes,
        *,
        user_language: str,
        user_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        transcript = await YandexSpeechKit.transcribe_primary(audio_bytes)
        if not transcript:
            logger.warning(
                "[VoiceExpenseExtraction] %s | Yandex fallback returned no transcript",
                log_safe_id(user_id, "user"),
            )
            return None

        try:
            service = AISelector("deepseek")
            model = get_model("default", "deepseek")
            raw_payload = await service.split_expense_text_to_items(
                transcript,
                model=model,
                user_context={"user_id": user_id, "language": user_language},
            )
        except Exception as exc:
            logger.error(
                "[VoiceExpenseExtraction] %s | DeepSeek text split error: %s",
                log_safe_id(user_id, "user"),
                exc,
            )
            return None

        payload = normalize_voice_expense_payload(
            raw_payload,
            fallback_transcript=transcript,
            source="yandex_deepseek",
        )
        if not payload:
            logger.warning(
                "[VoiceExpenseExtraction] %s | Invalid Yandex+DeepSeek payload: %s",
                log_safe_id(user_id, "user"),
                summarize_text(str(raw_payload)),
            )
            return None

        payload["pipeline"] = "yandex_deepseek"
        logger.info(
            "[VoiceExpenseExtraction] %s | Yandex+DeepSeek ok | items=%s transcript=%s",
            log_safe_id(user_id, "user"),
            len(payload["items"]),
            summarize_text(payload["transcript"]),
        )
        return payload


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip(" \t\r\n,;")


def _coerce_amount(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "нет", "unknown"}:
        return None

    try:
        if isinstance(value, str):
            match = re.search(r"\d+(?:[.,]\d+)?", value.replace(" ", ""))
            if not match:
                return None
            amount = Decimal(match.group(0).replace(",", "."))
        else:
            amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

    if amount <= 0 or amount > MAX_TRANSACTION_AMOUNT:
        return None
    return amount


def _normalize_currency(value: Any) -> Optional[str]:
    if value is None:
        return None
    currency = str(value).strip()
    if not currency or currency.lower() in {"null", "none", "нет", "unknown"}:
        return None

    code = currency.upper()
    if code in CURRENCY_PATTERNS:
        return code

    currency_lower = currency.lower()
    for candidate_code, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, currency_lower, flags=re.IGNORECASE):
                return candidate_code
    return None


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _amount_is_represented_as_price(amount: Decimal, transcript: str) -> bool:
    for value, next_token in _numeric_occurrences(transcript):
        if _decimal_equal(value, amount) and next_token not in UNIT_WORDS:
            return True
    return False


def _numeric_occurrences(text: str) -> List[tuple[Decimal, str]]:
    tokens = re.findall(r"\d+(?:[.,]\d+)?|[a-zA-Zа-яА-ЯёЁ.]+", text.lower())
    occurrences: List[tuple[Decimal, str]] = []
    index = 0

    while index < len(tokens):
        token = tokens[index].strip(".")
        digit_value = _decimal_from_digit_token(token)
        if digit_value is not None:
            occurrences.append((digit_value, _next_word(tokens, index + 1)))
            index += 1
            continue

        if token not in WORD_TO_NUMBER:
            index += 1
            continue

        start = index
        total = 0
        current = 0
        consumed = False
        while index < len(tokens):
            word = tokens[index].strip(".")
            if word in WORD_TO_NUMBER:
                consumed = True
                value = WORD_TO_NUMBER[word]
                if value == 100:
                    current = current * 100 if current else 100
                else:
                    current += value
                index += 1
                continue
            if word in AMOUNT_MULTIPLIERS:
                consumed = True
                multiplier = AMOUNT_MULTIPLIERS[word]
                total += (current or 1) * multiplier
                current = 0
                index += 1
                continue
            break

        if consumed:
            occurrences.append((Decimal(total + current), _next_word(tokens, index)))
            continue

        index = start + 1

    return occurrences


def _decimal_from_digit_token(token: str) -> Optional[Decimal]:
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        return None
    try:
        return Decimal(token.replace(",", "."))
    except InvalidOperation:
        return None


def _next_word(tokens: List[str], start: int) -> str:
    for token in tokens[start:]:
        word = token.strip(".")
        if re.fullmatch(r"[a-zA-Zа-яА-ЯёЁ]+", word):
            return word
    return ""


def _decimal_equal(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) < Decimal("0.01")
