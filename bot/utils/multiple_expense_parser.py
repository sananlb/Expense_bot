"""
Batch expense parser.

This module only splits one user message into several single-expense messages.
Each resulting item is parsed by the existing single expense parser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bot.utils.expense_parser import AMOUNT_MULTIPLIERS, detect_currency


MAX_MULTIPLE_EXPENSES_PER_MESSAGE = 10

_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[A-Za-zА-Яа-яЁё]+|[$€£¥₽₸₣₹₺]")
_CURRENCY_SYMBOLS = {"$", "€", "£", "¥", "₽", "₸", "₣", "₹", "₺"}


@dataclass(frozen=True)
class _Token:
    value: str
    start: int
    end: int
    kind: str


def _token_kind(value: str) -> str:
    if re.fullmatch(r"\d+(?:[.,]\d+)?", value):
        return "number"
    if value in _CURRENCY_SYMBOLS:
        return "currency"
    return "word"


def _tokenize(text: str) -> list[_Token]:
    return [
        _Token(
            value=match.group(0),
            start=match.start(),
            end=match.end(),
            kind=_token_kind(match.group(0)),
        )
        for match in _TOKEN_RE.finditer(text)
    ]


def _is_multiplier_token(token: _Token) -> bool:
    return token.kind == "word" and token.value.lower() in AMOUNT_MULTIPLIERS


def _is_currency_token(token: _Token) -> bool:
    if token.kind == "currency":
        return True
    if token.kind != "word":
        return False
    return detect_currency(f"1 {token.value}", user_currency="XXX") != "XXX"


def _split_by_explicit_separators(text: str) -> list[str] | None:
    """Split by separators typed or transcribed explicitly."""
    parts: list[str] = []
    start = 0
    found_separator = False

    for index, char in enumerate(text):
        is_separator = char in "\n;,"

        if not is_separator:
            continue

        found_separator = True
        part = text[start:index].strip(" \t\r\n,;")
        if part:
            parts.append(part)
        start = index + 1

    if not found_separator:
        return None

    tail = text[start:].strip(" \t\r\n,;")
    if tail:
        parts.append(tail)

    return parts if len(parts) >= 2 else None


def _has_later_number(tokens: list[_Token], start_index: int) -> bool:
    return any(token.kind == "number" for token in tokens[start_index:])


def _segment_has_word(tokens: list[_Token], start_index: int, end_index: int) -> bool:
    return any(token.kind == "word" for token in tokens[start_index:end_index])


def _consume_amount_suffix(tokens: list[_Token], number_index: int) -> int:
    """Return the token index after optional multiplier/currency suffixes."""
    index = number_index + 1
    while index < len(tokens) and (
        _is_multiplier_token(tokens[index]) or _is_currency_token(tokens[index])
    ):
        index += 1
    return index


def _split_voice_without_separators(text: str) -> list[str] | None:
    """Split voice text like 'coffee 120 bread 50' into item strings."""
    tokens = _tokenize(text)
    if sum(1 for token in tokens if token.kind == "number") < 2:
        return None

    splits: list[tuple[int, int]] = []
    segment_start_token = 0
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token.kind != "number":
            index += 1
            continue

        amount_end_index = _consume_amount_suffix(tokens, index)
        if amount_end_index >= len(tokens):
            break

        next_token = tokens[amount_end_index]
        has_description_before_amount = _segment_has_word(tokens, segment_start_token, index)

        if (
            has_description_before_amount
            and next_token.kind == "word"
            and not _is_currency_token(next_token)
            and not _is_multiplier_token(next_token)
            and _has_later_number(tokens, amount_end_index + 1)
        ):
            previous_token = tokens[amount_end_index - 1]
            splits.append((previous_token.end, next_token.start))
            segment_start_token = amount_end_index
            index = amount_end_index
            continue

        index += 1

    if not splits:
        return None

    parts: list[str] = []
    start_char = 0
    for end_char, next_start_char in splits:
        part = text[start_char:end_char].strip()
        if part:
            parts.append(part)
        start_char = next_start_char

    tail = text[start_char:].strip()
    if tail:
        parts.append(tail)

    return parts if len(parts) >= 2 else None


def _limited_parts_or_none(parts: list[str]) -> list[str] | None:
    if len(parts) < 2 or len(parts) > MAX_MULTIPLE_EXPENSES_PER_MESSAGE:
        return None

    return parts


def split_multiple_expense_texts(
    text: str,
    input_source: str = "text",
) -> list[str] | None:
    """Split a message into multiple single-expense texts when it is a batch."""
    if not text or not text.strip():
        return None

    normalized_text = text.strip()

    explicit_parts = _split_by_explicit_separators(normalized_text)
    if explicit_parts:
        return _limited_parts_or_none(explicit_parts)

    if input_source != "voice":
        return None

    voice_parts = _split_voice_without_separators(normalized_text)
    if not voice_parts:
        return None

    return _limited_parts_or_none(voice_parts)
