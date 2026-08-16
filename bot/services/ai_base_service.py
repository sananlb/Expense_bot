"""
Базовый класс для AI сервисов
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class AIBaseService(ABC):
    """Базовый класс для всех AI сервисов"""
    
    @abstractmethod
    async def categorize_expense(
        self, 
        text: str, 
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Категоризация расхода
        
        Args:
            text: Описание расхода
            amount: Сумма
            currency: Валюта
            categories: Список доступных категорий пользователя
            user_context: Дополнительный контекст (недавние категории и т.д.)
            
        Returns:
            Dict с результатом или None
        """
        pass
    
    @abstractmethod
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Чат с AI ассистентом
        
        Args:
            message: Сообщение пользователя
            context: История сообщений [{role: 'user'|'assistant', content: str}]
            user_context: Дополнительный контекст пользователя
            
        Returns:
            Ответ ассистента
        """
        pass
    
    def get_expense_categorization_prompt(
        self,
        text: str,
        amount: Optional[float],
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Создает универсальный языконезависимый промпт для категоризации записи.
        Работает с категориями на разных языках, с emoji и без.

        Используется и для расходов, и для доходов: тип операции берется из
        user_context['operation_type'] ('expense' по умолчанию, 'income' для доходов).
        Для дефолтных категорий в список подставляются смысловые описания границ
        категории из definitions-модулей; кастомные категории идут без описания.
        """
        from bot.utils.emoji_utils import EMOJI_PREFIX_RE

        is_income = bool(user_context) and user_context.get('operation_type') == 'income'
        record_type = 'income' if is_income else 'expense'

        if is_income:
            from bot.utils.income_category_definitions import get_income_category_description as get_description
        else:
            from bot.utils.expense_category_definitions import get_expense_category_description as get_description

        # Убираем эмодзи из категорий (включая композитные с ZWJ) и добавляем
        # смысловое описание, если категория дефолтная
        category_lines = []
        for cat in categories:
            clean_name = EMOJI_PREFIX_RE.sub('', cat).strip()
            description = get_description(cat)
            if description:
                category_lines.append(f"- {clean_name}: {description}")
            else:
                category_lines.append(f"- {clean_name}")
        categories_list = '\n'.join(category_lines)

        amount_info = f"\nAmount: {amount} {currency}" if amount is not None else ""

        context_info = ""
        if user_context:
            if 'recent_categories' in user_context:
                # Также убираем эмодзи из недавних категорий
                recent_clean = [EMOJI_PREFIX_RE.sub('', cat).strip() for cat in user_context['recent_categories'][:3]]
                context_info += f"\nRecently used categories: {', '.join(recent_clean)}"

        groceries_rule = (
            "\n   - CRITICAL: \"продукт\", \"продукты\", \"product\" or \"products\" without additional "
            "medical/pharmaceutical context → ALWAYS means groceries/food"
        ) if not is_income else ""

        return f"""You are the categorization module of a personal finance tracking bot. Users log their expenses and incomes as short free-form messages, and each record must be assigned to one of the user's categories. Your task is to categorize the {record_type} record below.

{record_type.capitalize()} information:
Description: "{text}"{amount_info}
{context_info}

User's available categories (name: what it covers):
{categories_list}

IMPORTANT INSTRUCTIONS:
1. Choose ONLY from the list above - return the exact category name WITHOUT any emoji
2. Categories may be in different languages (English, Russian, Spanish, etc.) - match semantically, not by language (e.g. "кофе" and "coffee" mean the same)
3. Return ONLY the text part of the category name, NO emojis
4. Match by the MEANING of the record; where a category has a description after the colon, treat that description as the source of truth for what the category covers{groceries_rule}
5. User-created custom categories (without a description) are equally valid - judge them by their name
6. If no category fits exactly, choose the most semantically similar one; fall back to the generic "other" category only when nothing else is close, and reflect the uncertainty in the confidence value

Return JSON:
{{
    "category": "exact category name from the list WITHOUT emoji",
    "confidence": number from 0 to 1,
    "reasoning": "brief explanation of the choice"
}}"""
    
    def get_chat_prompt(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Создает промпт для чата с пользователем
        """
        # Формируем историю сообщений
        history = ""
        if context:
            for msg in context[-10:]:  # Берем последние 10 сообщений
                role = "Пользователь" if msg['role'] == 'user' else "Ассистент"
                history += f"\n{role}: {msg['content']}"
        
        # Информация о пользователе
        user_info = ""
        if user_context:
            if 'recent_expenses' in user_context:
                recent = user_context['recent_expenses'][:3]
                user_info += f"\nНедавние траты пользователя: {', '.join(recent)}"
            if 'total_today' in user_context:
                from bot.utils.formatters import format_currency
                currency = user_context.get('currency') or 'RUB'
                user_info += f"\nПотрачено сегодня: {format_currency(user_context['total_today'], currency)}"
        
        return f"""Ты - умный помощник в боте для учета личных расходов и доходов. 
Твоя задача - помогать пользователю с учетом финансов, отвечать на вопросы и давать советы.

История диалога:{history}
{user_info}

Сообщение пользователя: {message}

Ответ помощника:"""
