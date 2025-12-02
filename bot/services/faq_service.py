"""
Service for matching user questions to FAQ answers.
Uses exact match, fuzzy match, and keyword overlap.
"""
from __future__ import annotations

import logging
import re
from difflib import get_close_matches, SequenceMatcher
from typing import Optional, Tuple, List, Dict, Set

from bot.data.faq import FAQ_DATA, FAQEntry, get_faq_for_ai_context
from bot.routers.start import get_welcome_message

logger = logging.getLogger(__name__)

# Special marker for dynamic welcome message
WELCOME_MESSAGE_MARKER = "__WELCOME_MESSAGE__"


def _resolve_answer(answer: str, lang: str) -> str:
    """Resolve special markers in FAQ answers."""
    if answer == WELCOME_MESSAGE_MARKER:
        return get_welcome_message(lang)
    return answer


def _normalize_text(text: str) -> str:
    """Lowercase, replace ё, strip punctuation/extra spaces for stable matching."""
    text = text.lower().strip()
    text = text.replace("ё", "е")
    # Keep letters/numbers/spaces only
    text = re.sub(r"[^a-zа-я0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class FAQMatcher:
    """Matcher that returns FAQ answers with confidence."""

    HIGH_CONFIDENCE_THRESHOLD = 0.85  # Direct answer
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60  # Answer + ask to clarify
    FUZZY_CUTOFF = 0.72

    def __init__(self):
        self._build_index()

    def _build_index(self):
        """Pre-compute normalized indices for quick lookup."""
        self._questions_ru: Dict[str, FAQEntry] = {}
        self._questions_en: Dict[str, FAQEntry] = {}
        self._keywords: Dict[str, List[FAQEntry]] = {}

        for entry in FAQ_DATA:
            for q in entry.get("questions_ru", []):
                self._questions_ru[_normalize_text(q)] = entry
            for q in entry.get("questions_en", []):
                self._questions_en[_normalize_text(q)] = entry

            for kw in entry.get("keywords", []):
                key = _normalize_text(kw)
                if not key:
                    continue
                self._keywords.setdefault(key, []).append(entry)

    def _get_questions_index(self, lang: str) -> Dict[str, FAQEntry]:
        return self._questions_ru if lang == "ru" else self._questions_en

    def find_answer(self, text: str, lang: str = "ru") -> Tuple[Optional[str], float, Optional[str]]:
        """
        Find FAQ answer.

        Returns: (answer, confidence, faq_id)
        """
        text_norm = _normalize_text(text)
        if not text_norm:
            return None, 0.0, None

        questions_index = self._get_questions_index(lang)

        # 1) Exact match
        if text_norm in questions_index:
            entry = questions_index[text_norm]
            raw_answer = entry.get(f"answer_{lang}") or entry.get("answer_ru")
            answer = _resolve_answer(raw_answer, lang)
            logger.info(f"[FAQ] Exact match: '{text_norm}' -> {entry['id']}")
            return answer, 1.0, entry["id"]

        # 2) Fuzzy match
        all_questions = list(questions_index.keys())
        close = get_close_matches(text_norm, all_questions, n=1, cutoff=self.FUZZY_CUTOFF)
        if close:
            matched_q = close[0]
            entry = questions_index[matched_q]
            ratio = SequenceMatcher(None, text_norm, matched_q).ratio()
            raw_answer = entry.get(f"answer_{lang}") or entry.get("answer_ru")
            answer = _resolve_answer(raw_answer, lang)
            logger.info(f"[FAQ] Fuzzy match: '{text_norm}' -> '{matched_q}' (ratio={ratio:.2f})")
            return answer, ratio, entry["id"]

        # 3) Keyword overlap (need at least 2 common keywords)
        words = set(text_norm.split())
        best_entry: Optional[FAQEntry] = None
        best_count = 0

        for word in words:
            for entry in self._keywords.get(word, []):
                entry_kw: Set[str] = { _normalize_text(k) for k in entry.get("keywords", []) if _normalize_text(k) }
                count = len(words & entry_kw)
                if count > best_count:
                    best_count = count
                    best_entry = entry

        if best_entry and best_count >= 2:
            raw_answer = best_entry.get(f"answer_{lang}") or best_entry.get("answer_ru")
            answer = _resolve_answer(raw_answer, lang)
            confidence = min(0.7, 0.4 + best_count * 0.15)
            logger.info(f"[FAQ] Keyword match: '{text_norm}' -> {best_entry['id']} (kw={best_count})")
            return answer, confidence, best_entry["id"]

        logger.info(f"[FAQ] No match for: '{text_norm}'")
        return None, 0.0, None

    def get_faq_context_for_ai(self) -> str:
        return get_faq_for_ai_context()


_matcher: Optional[FAQMatcher] = None


def get_faq_matcher() -> FAQMatcher:
    global _matcher
    if _matcher is None:
        _matcher = FAQMatcher()
    return _matcher


async def find_faq_answer(text: str, lang: str = "ru") -> Tuple[Optional[str], float, Optional[str]]:
    matcher = get_faq_matcher()
    return matcher.find_answer(text, lang)
