"""
Обработчик чата для естественного ввода расходов
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any

from ..services.expense import get_today_summary
from ..utils.message_utils import send_message_with_cleanup
from ..services.ai_selector import get_service
from ..services.subscription import check_subscription, subscription_required_message, get_subscription_button
from ..decorators import require_subscription, rate_limit
from ..routers.reports import show_expenses_summary
from expenses.models import Profile
from dateutil import parser
from calendar import monthrange
import re
from bot.utils.category_helpers import get_category_display_name

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
            # Преобразуем строку обратно в datetime если нужно
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            inactive_minutes = (now - last_activity).total_seconds() / 60
            if inactive_minutes > ChatContextManager.CONTEXT_RESET_MINUTES:
                need_reset = True
        
        if need_reset:
            session_id = f"chat_{user_id}_{int(now.timestamp())}"
            await state.update_data(
                chat_session_id=session_id,
                chat_last_activity=now.isoformat(),
                chat_messages=[]
            )
        else:
            await state.update_data(chat_last_activity=now.isoformat())
        
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


async def process_chat_message(message: types.Message, state: FSMContext, text: str, use_ai: bool = True, skip_typing: bool = False):
    """Обработать сообщение как чат
    
    Args:
        message: Сообщение Telegram
        state: Состояние FSM
        text: Текст для обработки
        use_ai: Использовать ли AI для обработки
        skip_typing: Пропустить ли индикатор печатания (если уже запущен извне)
    """
    user_id = message.from_user.id
    
    # Основная логика обработки
    # УБРАНО: Больше не проверяем запросы дневника трат
    # Все сообщения идут через AI
    
    # Проверяем подписку для AI чата (включая пробный период)
    has_subscription = await check_subscription(user_id, include_trial=True)
    
    # Получаем или создаем сессию
    session_id = await ChatContextManager.get_or_create_session(user_id, state)
    
    # Добавляем сообщение пользователя в контекст
    await ChatContextManager.add_message(state, 'user', text)
    
    # Функция для выполнения основной логики
    async def _process():
        # Если есть подписка (включая пробный период) и включен AI - используем AI для ответа
        if has_subscription and use_ai:
            try:
                # Получаем контекст
                context = await ChatContextManager.get_context(state)
                
                # Получаем дополнительную информацию о пользователе
                from expenses.models import Expense
                from datetime import timedelta
                
                today = datetime.now().date()
                today_summary = await get_today_summary(user_id)
                
                # Получаем последние расходы для контекста
                recent_expenses = []
                try:
                    from asgiref.sync import sync_to_async
                    
                    @sync_to_async
                    def get_recent_expenses_sync():
                        return list(
                            Expense.objects.filter(
                                profile__telegram_id=user_id,
                                expense_date__gte=today - timedelta(days=30)
                            ).select_related('category').order_by('-expense_date', '-id')[:20]
                        )
                    
                    expenses = await get_recent_expenses_sync()
                    
                    for exp in expenses:
                        # Используем язык пользователя для отображения категории
                        # Получаем профиль пользователя
                        try:
                            from expenses.models import Profile
                            profile = await sync_to_async(Profile.objects.get)(telegram_id=user_id)
                            lang = getattr(profile, 'language_code', 'ru') if profile else 'ru'
                        except:
                            lang = 'ru'
                            
                        category_name = get_category_display_name(exp.category, lang) if exp.category else 'Без категории'
                        recent_expenses.append({
                            'date': exp.expense_date.isoformat(),
                            'amount': float(exp.amount),
                            'category': category_name,
                            'description': exp.description or ''
                        })
                except Exception as e:
                    logger.error(f"Error getting recent expenses: {e}")
                
                user_context = {
                    'total_today': today_summary.get('total', 0) if today_summary else 0,
                    'expenses_data': recent_expenses,
                    'user_id': user_id  # Добавляем user_id для function calling
                }
                
                # Получаем AI сервис и генерируем ответ
                ai_service = get_service('chat')
                logger.info(f"[Chat] Got AI service: {type(ai_service).__name__}")
                logger.info(f"[Chat] Calling AI with user_id={user_id}, message={text[:50]}...")
                
                response = await ai_service.chat(text, context, user_context)
                # Безопасное логирование в Windows-консолях (ASCII-only превью)
                try:
                    preview = (response or '')[:100]
                    safe_preview = preview.encode('ascii', 'ignore').decode('ascii')
                except Exception:
                    safe_preview = 'None'
                logger.info(f"[Chat] AI response received: {safe_preview}...")
                
            except Exception as e:
                logger.error(f"AI chat error with primary service: {e}")
                # Fallback на OpenAI
                try:
                    logger.info("Trying fallback to OpenAI service...")
                    from ..services.openai_service import OpenAIService
                    openai_service = OpenAIService()
                    response = await openai_service.chat(text, context, user_context)
                    logger.info("OpenAI fallback successful")
                except Exception as fallback_error:
                    logger.error(f"OpenAI fallback also failed: {fallback_error}")
                    # Крайний случай - простые ответы
                    response = "AI сервис временно недоступен. Попробуйте позже."
        else:
            # Простые ответы без AI для пользователей без подписки
            response = await get_simple_response(text, user_id)
        
        # Если нет подписки и пробного периода, предлагаем оформить
        if not has_subscription and use_ai:
            response += "\n\n💡 Для доступа к AI-ассистенту оформите подписку /subscription"
        
        return response
    
    # Выполняем обработку с индикатором печатания или без него
    if skip_typing:
        # Если индикатор уже запущен извне, просто выполняем логику
        response = await _process()
    else:
        # Запускаем индикацию "печатает..."
        from ..utils.typing_action import TypingAction
        async with TypingAction(message):
            response = await _process()
    
    # Добавляем ответ в контекст
    await ChatContextManager.add_message(state, 'assistant', response)
    
    # Конвертируем Markdown в HTML для правильного отображения
    import re
    # Заменяем **text** на <b>text</b>
    response_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', response)
    # Заменяем *text* на <i>text</i> (только одинарные звездочки)
    response_html = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', response_html)
    
    await send_message_with_cleanup(message, state, response_html, parse_mode="HTML")


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
            from datetime import date
            from ..services.expense import get_expenses_summary
            today = date.today()
            start_date = today.replace(day=1)
            
            summary = await get_expenses_summary(
                user_id=user_id,
                start_date=start_date,
                end_date=today
            )
            
            if not summary or summary.get('total', 0) == 0:
                return "В этом месяце трат пока нет."
            else:
                response = f"Траты за текущий месяц: {summary['total']:,.0f} ₽\n\n"
                for cat in summary.get('by_category', [])[:5]:
                    response += f"{cat.get('icon', '')} {cat['name']}: {cat['total']:,.0f} ₽\n"
                
                # Добавим информацию о доходах если есть
                if summary.get('income_total', 0) > 0:
                    response += f"\nДоходы: {summary['income_total']:,.0f} ₽"
                    
                return response
        else:
            return "Я могу показать траты за сегодня или за текущий месяц. Просто спросите!"
    
    else:
        # Общий ответ
        return ("Я помогу вам учитывать расходы. Просто отправьте мне сообщение с тратой, "
               "например 'Кофе 200' или спросите о ваших тратах.")


# ФУНКЦИЯ ОТКЛЮЧЕНА - весь чат идет через AI
# async def check_and_process_diary_request(message: types.Message, state: FSMContext, text: str) -> bool:
#     """Проверить и обработать запрос дневника трат"""
#     # Эта функция больше не используется - все запросы обрабатываются через AI
#     return False


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
    # Не запускаем свой typing indicator, так как process_chat_message сам управляет им
    await process_chat_message(message, state, text, skip_typing=False)
