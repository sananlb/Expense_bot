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
from ..services.ai_selector import get_service, get_fallback_chain, AISelector
from ..services.subscription import check_subscription, subscription_required_message, get_subscription_button
from ..decorators import require_subscription, rate_limit
from ..routers.reports import show_expenses_summary
from ..services.faq_service import find_faq_answer, get_faq_matcher
from expenses.models import Profile
from dateutil import parser
from calendar import monthrange
import re
from bot.utils.category_helpers import get_category_display_name
from ..utils.language import get_user_language, get_text

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


def is_greeting(text: str) -> bool:
    """Проверить, является ли сообщение приветствием"""
    text_lower = text.lower().strip()

    greetings = {
        # Русские приветствия
        'привет', 'приветик', 'здравствуй', 'здравствуйте', 'добрый день',
        'доброе утро', 'добрый вечер', 'хай', 'хэй', 'йо', 'салют',
        'здарова', 'здорово', 'прив', 'ку', 'хелло', 'хеллоу',
        # Английские приветствия
        'hi', 'hello', 'hey', 'good morning', 'good evening', 'good afternoon',
        'howdy', 'greetings', 'yo', 'sup', "what's up", 'whats up'
    }

    # Проверяем точное совпадение
    if text_lower in greetings:
        return True

    # Проверяем начало с приветствия
    for greeting in greetings:
        if text_lower.startswith(greeting + ' ') or text_lower.startswith(greeting + ',') or text_lower.startswith(greeting + '!'):
            return True

    return False


def get_greeting_response(lang: str = 'ru') -> str:
    """Получить ответ на приветствие с примерами вопросов"""
    if lang == 'en':
        return """👋 Hello! I'm your personal finance assistant.

<b>What I can do:</b>

💸 <b>Track expenses</b> — just send:
• "Coffee 200"
• "Taxi 450 to airport"

📊 <b>View reports</b> — ask me:
• "Show expenses for today"
• "How much did I spend in November?"
• "Show expenses for August 19"

🔍 <b>Search expenses</b>:
• "Find coffee expenses"
• "Show all groceries"

📈 <b>Analytics</b>:
• "Compare this month to last month"
• "What day did I spend the most?"

Try asking something!"""
    else:
        return """👋 Привет! Я твой помощник по учету финансов.

<b>Что я умею:</b>

💸 <b>Записывать траты</b> — просто отправь:
• "Кофе 200"
• "Такси 450"
Редактируй категорию — я запомню и в следующий раз подставлю правильно!

📊 <b>Показывать отчеты</b> — спроси меня:
• "Покажи траты за неделю"
• "Сколько потратил в ноябре?"
• "Покажи траты за 19 августа"

🔍 <b>Искать траты</b>:
• "Найди траты на кофе"
• "Покажи траты на продукты в ноябре"

📈 <b>Аналитика</b>:
• "Какая моя самая дорогая покупка в сентябре?"
• "В какой день я потратил больше всего?"

Попробуй спросить что-нибудь!"""


def classify_by_heuristics(text: str, lang: str = 'ru') -> str:
    """Классифицировать сообщение по эвристикам"""
    text_lower = text.lower().strip()

    # Приветствия обрабатываются отдельно
    if is_greeting(text):
        return 'greeting'

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
    lang = await get_user_language(user_id)

    # Проверяем приветствия - отвечаем мгновенно без AI
    if is_greeting(text):
        response = get_greeting_response(lang)
        await send_message_with_cleanup(message, state, response, parse_mode="HTML")
        return

    # FAQ (быстрый ответ без вызова AI)
    faq_answer, faq_confidence, faq_id = await find_faq_answer(text, lang)
    if faq_confidence >= get_faq_matcher().HIGH_CONFIDENCE_THRESHOLD:
        logger.info(f"[Chat] FAQ high confidence ({faq_id}) for user {user_id}")
        await send_message_with_cleanup(message, state, faq_answer, parse_mode="HTML")
        return
    if faq_confidence >= get_faq_matcher().MEDIUM_CONFIDENCE_THRESHOLD:
        logger.info(f"[Chat] FAQ medium confidence ({faq_id}) for user {user_id}")
        clarification = (
            "\n\n💡 Если это не то, что нужно — уточните вопрос."
            if lang == "ru"
            else "\n\n💡 If that is not what you need — please clarify."
        )
        await send_message_with_cleanup(message, state, faq_answer + clarification, parse_mode="HTML")
        return

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
                            cat_lang = getattr(profile, 'language_code', 'ru') if profile else 'ru'
                        except:
                            cat_lang = 'ru'

                        category_name = get_category_display_name(exp.category, cat_lang) if exp.category else get_text('no_category', cat_lang)
                        recent_expenses.append({
                            'date': exp.expense_date.isoformat(),
                            'amount': float(exp.amount),
                            'category': category_name,
                            'description': exp.description or ''
                        })
                except Exception as e:
                    logger.error(f"Error getting recent expenses: {e}")
                
                logger.info(f"[Chat] User language detected: {lang}")

                user_context = {
                    'total_today': today_summary.get('total', 0) if today_summary else 0,
                    'expenses_data': recent_expenses,
                    'user_id': user_id,  # Добавляем user_id для function calling
                    'language': lang,  # Добавляем язык пользователя для AI
                    'faq_context': get_faq_matcher().get_faq_context_for_ai(),
                }

                # Получаем AI сервис и генерируем ответ
                ai_service = get_service('chat')
                logger.info(f"[Chat] Got AI service: {type(ai_service).__name__}")
                logger.info(f"[Chat] Calling AI with user_id={user_id}, language={lang}, message={text[:50]}...")
                
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
                # Fallback chain из .env настроек
                fallback_chain = get_fallback_chain('chat')
                response = None

                for fallback_provider in fallback_chain:
                    try:
                        logger.info(f"Trying fallback to {fallback_provider} service...")
                        fallback_service = AISelector(fallback_provider)  # Returns actual service instance
                        response = await fallback_service.chat(text, context, user_context)
                        logger.info(f"{fallback_provider} fallback successful")
                        break
                    except Exception as fallback_error:
                        logger.error(f"{fallback_provider} fallback failed: {fallback_error}")
                        continue

                if not response:
                    # Крайний случай - все провайдеры недоступны
                    response = "AI сервис временно недоступен. Попробуйте позже."
        else:
            # Пользователи без подписки получают сообщение о необходимости оформить подписку
            response = "💬 AI-ассистент доступен только по подписке.\n\n💡 Оформите подписку /subscription чтобы получить доступ к умному помощнику, который ответит на ваши вопросы о финансах."

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
    user_id = message.from_user.id

    # Проверяем, является ли сообщение приветствием
    if is_greeting(text):
        lang = await get_user_language(user_id)
        response = get_greeting_response(lang)
        await send_message_with_cleanup(message, state, response, parse_mode="HTML")
        return

    # Если сообщение дошло до этого обработчика, значит expense handler
    # не смог его распознать как трату, поэтому обрабатываем как чат
    # Не запускаем свой typing indicator, так как process_chat_message сам управляет им
    await process_chat_message(message, state, text, skip_typing=False)
