"""
Обработчик чата для естественного ввода расходов
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
from typing import Optional

from ..utils.expense_parser import parse_expense_message
from ..services.expense import add_expense, get_today_summary, get_month_summary
from ..services.category import get_or_create_category
from ..services.profile import get_or_create_profile
from ..utils.message_utils import send_message_with_cleanup
from expenses.models import Profile

logger = logging.getLogger(__name__)

router = Router(name="chat")


class ChatStates(StatesGroup):
    """Состояния для чата"""
    active_chat = State()


class ChatContextManager:
    """Менеджер контекста чата"""
    MAX_CONTEXT_MESSAGES = 20
    MAX_TOKENS_ESTIMATE = 3000
    CONTEXT_RESET_MINUTES = 1440  # 24 часа
    
    @staticmethod
    async def get_or_create_session(user_id: int, state: FSMContext) -> str:
        """Получить или создать сессию чата"""
        data = await state.get_data()
        session_id = data.get('chat_session_id')
        last_activity = data.get('chat_last_activity')
        
        now = datetime.now()
        need_reset = False
        
        if not session_id:
            need_reset = True
        elif last_activity:
            inactive_minutes = (now - last_activity).total_seconds() / 60
            if inactive_minutes > ChatContextManager.CONTEXT_RESET_MINUTES:
                need_reset = True
        
        if need_reset:
            session_id = f"chat_{user_id}_{int(now.timestamp())}"
            await state.update_data(
                chat_session_id=session_id,
                chat_last_activity=now,
                chat_messages=[]
            )
        else:
            await state.update_data(chat_last_activity=now)
        
        return session_id
    
    @staticmethod
    async def add_message(state: FSMContext, role: str, content: str):
        """Добавить сообщение в контекст"""
        data = await state.get_data()
        messages = data.get('chat_messages', [])
        
        messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # Ограничиваем количество сообщений
        if len(messages) > ChatContextManager.MAX_CONTEXT_MESSAGES:
            messages = messages[-ChatContextManager.MAX_CONTEXT_MESSAGES:]
        
        await state.update_data(chat_messages=messages)
    
    @staticmethod
    async def get_context(state: FSMContext) -> list:
        """Получить контекст чата"""
        data = await state.get_data()
        return data.get('chat_messages', [])


def classify_by_heuristics(text: str, lang: str = 'ru') -> str:
    """Классифицировать сообщение по эвристикам"""
    text_lower = text.lower().strip()
    
    # Вопросы всегда чат
    if text.strip().endswith('?'):
        return 'chat'
    
    # Слова-стартеры чата
    chat_start_words = {
        'ru': {'что', 'как', 'почему', 'зачем', 'когда', 'где', 'сколько', 'покажи', 'показать', 'выведи', 'вывести'},
        'en': {'what', 'how', 'why', 'when', 'where', 'can', 'should', 'show', 'display'}
    }
    
    first_word = text_lower.split()[0] if text_lower.split() else ""
    if first_word in chat_start_words.get(lang, set()):
        return 'chat'
    
    # Фразы для отчетов
    report_phrases = {
        'ru': ['траты за', 'расходы за', 'потратил за', 'сколько потратил', 'покажи траты', 'отчет за'],
        'en': ['expenses for', 'spent in', 'show expenses', 'report for']
    }
    
    for phrase in report_phrases.get(lang, []):
        if phrase in text_lower:
            return 'report'
    
    # По умолчанию пытаемся распознать как расход
    return 'expense'


async def process_chat_message(message: types.Message, state: FSMContext, text: str):
    """Обработать сообщение как чат"""
    # Добавляем сообщение пользователя в контекст
    await ChatContextManager.add_message(state, 'user', text)
    
    # Анализируем запрос
    text_lower = text.lower()
    user_id = message.from_user.id
    
    # Обработка запросов отчетов
    if 'трат' in text_lower or 'расход' in text_lower or 'потратил' in text_lower:
        if 'сегодня' in text_lower:
            # Показать траты за сегодня
            summary = await get_today_summary(user_id)
            if not summary or summary['total'] == 0:
                response = "Сегодня трат пока нет."
            else:
                response = f"Траты за сегодня: {summary['total']:,.0f} ₽\n\n"
                for cat in summary['categories']:
                    response += f"{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽\n"
        
        elif 'вчера' in text_lower:
            # Показать траты за вчера
            yesterday = datetime.now().date() - timedelta(days=1)
            response = "Функция просмотра трат за вчера будет добавлена в следующей версии."
        
        elif 'месяц' in text_lower:
            # Показать траты за месяц
            today = datetime.now().date()
            summary = await get_month_summary(user_id, today.month, today.year)
            if not summary or summary['total'] == 0:
                response = "В этом месяце трат пока нет."
            else:
                response = f"Траты за текущий месяц: {summary['total']:,.0f} ₽\n\n"
                for cat in summary['categories'][:5]:
                    response += f"{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽\n"
        else:
            response = "Я могу показать траты за сегодня или за текущий месяц. Просто спросите!"
    
    else:
        # Общий ответ
        response = ("Я помогу вам учитывать расходы. Просто отправьте мне сообщение с тратой, "
                   "например 'Кофе 200' или спросите о ваших тратах.")
    
    # Добавляем ответ в контекст
    await ChatContextManager.add_message(state, 'assistant', response)
    
    await send_message_with_cleanup(message, state, response)


# Обработчик текстовых сообщений с приоритетом ниже, чем у expense handler
@router.message(F.text & ~F.text.startswith('/'))
async def handle_chat_or_expense(message: types.Message, state: FSMContext):
    """Обработка текстовых сообщений - чат или расход"""
    text = message.text.strip()
    
    # Получаем профиль пользователя
    user_id = message.from_user.id
    profile = await get_or_create_profile(
        telegram_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code
    )
    
    lang = profile.language_code or 'ru'
    
    # Классифицируем сообщение
    message_type = classify_by_heuristics(text, lang)
    
    if message_type == 'chat' or message_type == 'report':
        # Обрабатываем как чат
        await process_chat_message(message, state, text)
    else:
        # Пытаемся распознать как расход
        parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
        
        if parsed:
            # Это расход - передаем обработку expense handler
            # Важно: expense handler должен иметь более высокий приоритет
            return  # Пропускаем обработку, пусть обработает expense handler
        else:
            # Не удалось распознать как расход - обрабатываем как чат
            await process_chat_message(message, state, text)