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
        Создает промпт для категоризации расхода
        """
        context_info = ""
        if user_context:
            if 'recent_categories' in user_context:
                context_info += f"\nЧасто используемые категории: {', '.join(user_context['recent_categories'][:3])}"
        
        categories_list = '\n'.join([f"- {cat}" for cat in categories])
        
        return f"""Ты помощник в боте для учета личных расходов. Твоя задача - определить категорию траты.

Информация о трате:
Описание: "{text}"
Сумма: {amount} {currency}
{context_info}

Доступные категории пользователя:
{categories_list}

ВАЖНО:
1. Выбери ТОЛЬКО из списка выше
2. Учитывай контекст личных расходов
3. Если не уверен, выбери наиболее подходящую общую категорию

Верни JSON:
{{
    "category": "выбранная категория из списка",
    "confidence": число от 0 до 1,
    "reasoning": "краткое объяснение выбора"
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
        
        return f"""Ты - умный помощник в боте для учета личных расходов. 
Твоя задача - помогать пользователю с учетом трат, отвечать на вопросы о расходах и давать советы по управлению финансами.

ВАЖНЫЕ ПРАВИЛА:
1. Будь дружелюбным и полезным
2. Отвечай кратко и по существу
3. Помогай анализировать траты
4. Если пользователь хочет записать трату - скажи, что нужно просто отправить сообщение вида "Продукты 500"
5. Если пользователь спрашивает о тратах за конкретную дату или период - скажи, что можно написать "покажи траты за [дата/период]" или "дневник трат за [дата/период]"
6. НЕ используй форматирование Markdown, пиши простым текстом

История диалога:{history}
{user_info}

Сообщение пользователя: {message}

Ответ помощника:"""