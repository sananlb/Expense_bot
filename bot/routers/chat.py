"""
Обработчик чата для естественного ввода расходов
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any

from ..services.expense import get_today_summary, get_month_summary
from ..utils.message_utils import send_message_with_cleanup
from ..services.ai_selector import get_service
from ..services.subscription import check_subscription, is_trial_active, subscription_required_message, get_subscription_button
from ..decorators import require_subscription, rate_limit
from ..routers.reports import show_expenses_summary
from expenses.models import Profile
from dateutil import parser
from calendar import monthrange
import re

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


async def process_chat_message(message: types.Message, state: FSMContext, text: str, use_ai: bool = True):
    """Обработать сообщение как чат"""
    user_id = message.from_user.id
    
    # Сначала проверяем, не запрос ли это дневника трат
    diary_result = await check_and_process_diary_request(message, state, text)
    if diary_result:
        return  # Запрос дневника обработан
    
    # Проверяем подписку для AI чата (включая пробный период)
    has_subscription_or_trial = await check_subscription(user_id, include_trial=True)
    has_paid_subscription = await check_subscription(user_id, include_trial=False)
    is_trial = await is_trial_active(user_id)
    
    # Получаем или создаем сессию
    session_id = await ChatContextManager.get_or_create_session(user_id, state)
    
    # Добавляем сообщение пользователя в контекст
    await ChatContextManager.add_message(state, 'user', text)
    
    # Если есть подписка (включая пробный период) и включен AI - используем AI для ответа
    if has_subscription_or_trial and use_ai:
        try:
            # Получаем контекст
            context = await ChatContextManager.get_context(state)
            
            # Получаем дополнительную информацию о пользователе
            today_summary = await get_today_summary(user_id)
            user_context = {
                'total_today': today_summary.get('total', 0) if today_summary else 0
            }
            
            # Получаем AI сервис и генерируем ответ
            ai_service = get_service('chat')
            response = await ai_service.chat(text, context, user_context)
            
            # Если пользователь на пробном периоде, напоминаем о подписке
            if is_trial and not has_paid_subscription:
                response += "\n\n🎁 Вы используете пробный период. Оформите подписку для продолжения /subscription"
            
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            # Fallback на простые ответы
            response = await get_simple_response(text, user_id)
    else:
        # Простые ответы без AI для пользователей без подписки
        response = await get_simple_response(text, user_id)
        
        # Если нет подписки и пробного периода, предлагаем оформить
        if not has_subscription_or_trial and use_ai:
            response += "\n\n💡 Для доступа к AI-ассистенту оформите подписку /subscription"
    
    # Добавляем ответ в контекст
    await ChatContextManager.add_message(state, 'assistant', response)
    
    await send_message_with_cleanup(message, state, response)


async def get_simple_response(text: str, user_id: int) -> str:
    """Получить простой ответ без использования AI"""
    text_lower = text.lower()
    
    # Обработка запросов отчетов
    if 'трат' in text_lower or 'расход' in text_lower or 'потратил' in text_lower:
        if 'сегодня' in text_lower:
            # Показать траты за сегодня
            summary = await get_today_summary(user_id)
            if not summary or summary['total'] == 0:
                return "Сегодня трат пока нет."
            else:
                # Проверяем, спрашивают ли о категориях
                if 'категори' in text_lower:
                    response = f"Сегодня траты были в следующих категориях:\n\n"
                    for cat in summary['categories']:
                        response += f"{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽\n"
                    response += f"\nОбщая сумма: {summary['total']:,.0f} ₽"
                else:
                    response = f"Траты за сегодня: {summary['total']:,.0f} ₽\n\n"
                    for cat in summary['categories']:
                        response += f"{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽\n"
                return response
        
        elif 'вчера' in text_lower:
            # Показать траты за вчера
            return "Функция просмотра трат за вчера будет добавлена в следующей версии."
        
        elif 'месяц' in text_lower:
            # Показать траты за месяц
            today = datetime.now().date()
            summary = await get_month_summary(user_id, today.month, today.year)
            if not summary or summary['total'] == 0:
                return "В этом месяце трат пока нет."
            else:
                response = f"Траты за текущий месяц: {summary['total']:,.0f} ₽\n\n"
                for cat in summary['categories'][:5]:
                    response += f"{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽\n"
                return response
        else:
            return "Я могу показать траты за сегодня или за текущий месяц. Просто спросите!"
    
    else:
        # Общий ответ
        return ("Я помогу вам учитывать расходы. Просто отправьте мне сообщение с тратой, "
               "например 'Кофе 200' или спросите о ваших тратах.")


async def check_and_process_diary_request(message: types.Message, state: FSMContext, text: str) -> bool:
    """Проверить и обработать запрос дневника трат"""
    text_lower = text.lower()
    
    # Ключевые слова для дневника трат
    diary_keywords = ['дневник', 'траты за', 'расходы за', 'покажи траты', 'показать траты', 
                      'потратил за', 'сколько потратил']
    
    # Проверяем наличие ключевых слов
    is_diary_request = any(keyword in text_lower for keyword in diary_keywords)
    
    if not is_diary_request:
        return False
    
    # Пытаемся распознать даты в тексте
    dates = await parse_dates_from_text(text)
    
    if dates:
        # Если даты найдены - показываем дневник за указанный период
        start_date, end_date = dates
        lang = 'ru'  # TODO: получить язык пользователя
        
        await show_expenses_summary(
            message=message,
            start_date=start_date,
            end_date=end_date,
            lang=lang
        )
        return True
    
    # Если даты не распознаны, но есть ключевые слова - используем простые периоды
    if 'вчера' in text_lower:
        yesterday = datetime.now().date() - timedelta(days=1)
        await show_expenses_summary(message, yesterday, yesterday, 'ru')
        return True
    elif 'неделю' in text_lower or 'недели' in text_lower:
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        await show_expenses_summary(message, week_start, today, 'ru')
        return True
    elif 'месяц' in text_lower and ('прошлый' in text_lower or 'прошлого' in text_lower):
        today = datetime.now().date()
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        
        start_date = datetime(prev_year, prev_month, 1).date()
        _, last_day = monthrange(prev_year, prev_month)
        end_date = datetime(prev_year, prev_month, last_day).date()
        
        await show_expenses_summary(message, start_date, end_date, 'ru')
        return True
    
    return False


async def parse_dates_from_text(text: str) -> Optional[tuple[datetime.date, datetime.date]]:
    """Распознать даты в тексте"""
    text_lower = text.lower()
    today = datetime.now().date()
    
    # Паттерны для месяцев
    months = {
        'январь': 1, 'января': 1,
        'февраль': 2, 'февраля': 2,
        'март': 3, 'марта': 3,
        'апрель': 4, 'апреля': 4,
        'май': 5, 'мая': 5,
        'июнь': 6, 'июня': 6,
        'июль': 7, 'июля': 7,
        'август': 8, 'августа': 8,
        'сентябрь': 9, 'сентября': 9,
        'октябрь': 10, 'октября': 10,
        'ноябрь': 11, 'ноября': 11,
        'декабрь': 12, 'декабря': 12
    }
    
    # Проверяем конкретные даты (например, "15 марта", "15.03", "15/03")
    date_pattern = r'(\d{1,2})\s*(?:число|числа)?\s*([а-я]+)|(?:(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?)|(?:(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?)'
    matches = re.findall(date_pattern, text_lower)
    
    if matches:
        for match in matches:
            try:
                if match[0] and match[1]:  # "15 марта"
                    day = int(match[0])
                    month_name = match[1]
                    if month_name in months:
                        month = months[month_name]
                        year = today.year
                        # Если дата в будущем, берем прошлый год
                        test_date = datetime(year, month, day).date()
                        if test_date > today:
                            year -= 1
                        parsed_date = datetime(year, month, day).date()
                        return (parsed_date, parsed_date)
                        
                elif match[2] and match[3]:  # "15.03" или "15.03.2024"
                    day = int(match[2])
                    month = int(match[3])
                    year = int(match[4]) if match[4] else today.year
                    if year < 100:  # Двузначный год
                        year += 2000
                    parsed_date = datetime(year, month, day).date()
                    if parsed_date <= today:
                        return (parsed_date, parsed_date)
                        
            except (ValueError, KeyError):
                continue
    
    # Проверяем диапазоны дат
    range_pattern = r'с\s*(\d{1,2}\.\d{1,2})\s*по\s*(\d{1,2}\.\d{1,2})'
    range_match = re.search(range_pattern, text_lower)
    if range_match:
        try:
            start_str = range_match.group(1)
            end_str = range_match.group(2)
            
            # Добавляем текущий год если не указан
            if len(start_str.split('.')) == 2:
                start_str += f'.{today.year}'
            if len(end_str.split('.')) == 2:
                end_str += f'.{today.year}'
                
            start_date = parser.parse(start_str, dayfirst=True).date()
            end_date = parser.parse(end_str, dayfirst=True).date()
            
            if start_date <= today and end_date <= today:
                return (start_date, end_date)
        except:
            pass
    
    # Проверяем названия месяцев для периода за весь месяц
    for month_name, month_num in months.items():
        if month_name in text_lower:
            year = today.year
            # Если месяц в будущем, берем прошлый год
            if month_num > today.month:
                year -= 1
            
            start_date = datetime(year, month_num, 1).date()
            _, last_day = monthrange(year, month_num)
            end_date = datetime(year, month_num, last_day).date()
            
            return (start_date, end_date)
    
    return None


# Обработчик текстовых сообщений - только чат
# Expense handler имеет более высокий приоритет и обработает расходы
@router.message(F.text & ~F.text.startswith('/'))
@rate_limit(max_calls=20, period=60)  # 20 сообщений в минуту для чата
async def handle_chat_message(message: types.Message, state: FSMContext):
    """Обработка текстовых сообщений как чат"""
    text = message.text.strip()
    
    # Если сообщение дошло до этого обработчика, значит expense handler
    # не смог его распознать как трату, поэтому обрабатываем как чат
    await process_chat_message(message, state, text)