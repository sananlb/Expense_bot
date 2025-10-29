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
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Создает универсальный языконезависимый промпт для категоризации расхода.
        Работает с категориями на разных языках, с emoji и без.
        """
        context_info = ""
        if user_context:
            if 'recent_categories' in user_context:
                context_info += f"\nRecently used categories: {', '.join(user_context['recent_categories'][:3])}"

        categories_list = '\n'.join([f"- {cat}" for cat in categories])

        return f"""You are an expense categorization assistant for a personal finance bot. Your task is to categorize the expense.

Expense information:
Description: "{text}"
Amount: {amount} {currency}
{context_info}

User's available categories:
{categories_list}

IMPORTANT INSTRUCTIONS:
1. Choose ONLY from the list above - return the exact category name including emoji if present
2. Categories may be in different languages (English, Russian, Spanish, etc.) - match semantically
3. Some categories have emoji (🍔, 🚗, 💰), some don't - both are valid
4. Match by meaning, not language:
   - "cookie" or "cookies" or "печенье" or "biscuit" → food/groceries category
   - "coffee" or "кофе" or "café" → cafe/restaurant category
   - "gas" or "бензин" or "diesel" → transport/fuel category
   - "carrot" or "carrots" or "vegetable" or "овощи" → groceries/produce category
   - "uber" or "taxi" or "такси" → transport category
5. If the exact match isn't found, choose the most semantically similar category
6. User-created custom categories (in any language) are equally valid as default ones

Return JSON:
{{
    "category": "exact category name from the list",
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
                user_info += f"\nПотрачено сегодня: {user_context['total_today']} ₽"
        
        return f"""Ты - умный помощник в боте для учета личных расходов и доходов. 
Твоя задача - помогать пользователю с учетом финансов, отвечать на вопросы и давать советы.

История диалога:{history}
{user_info}

Сообщение пользователя: {message}

Ответ помощника:"""