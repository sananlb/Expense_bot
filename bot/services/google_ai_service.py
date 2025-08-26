"""
Google AI Service - основной сервис для работы с Google Gemini
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from .ai_base_service import AIBaseService
from .ai_selector import get_model

# Настройка логирования
logger = logging.getLogger(__name__)

# Загружаем API ключ
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("[GoogleAI] API key configured")
else:
    logger.error("[GoogleAI] GOOGLE_API_KEY not found in environment")


class GoogleAIService(AIBaseService):
    """Сервис для работы с Google AI (Gemini) - упрощенная стабильная версия"""
    
    def __init__(self):
        """Инициализация сервиса"""
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        
        self.api_key = GOOGLE_API_KEY
        logger.info("[GoogleAI] Service initialized (fixed version)")
    
    async def categorize_expense(
        self,
        text: str,
        amount: float,
        currency: str,
        categories: List[str],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Категоризация расхода с помощью Google AI
        
        Args:
            text: Текст описания расхода
            amount: Сумма расхода
            currency: Валюта
            categories: Список доступных категорий
            user_context: Дополнительный контекст пользователя
            
        Returns:
            Словарь с категорией и уверенностью или None при ошибке
        """
        try:
            prompt = self.get_expense_categorization_prompt(text, amount, currency, categories, user_context)
            
            model_name = 'gemini-2.5-flash'  # Используем фиксированную модель
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="You are an expense categorization assistant. Always respond with a valid category name from the provided list."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=1500,
                top_p=0.8
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            if response and response.parts:
                text_response = response.text.strip()
                
                # Парсим ответ
                import json
                try:
                    # Пробуем распарсить как JSON
                    if text_response.startswith('{'):
                        result = json.loads(text_response)
                        return {
                            'category': result.get('category', categories[0] if categories else 'Прочее'),
                            'confidence': float(result.get('confidence', 0.5))
                        }
                except:
                    pass
                
                # Если не JSON, ищем категорию в тексте
                text_lower = text_response.lower()
                for category in categories:
                    if category.lower() in text_lower:
                        return {
                            'category': category,
                            'confidence': 0.7
                        }
                
                # Если ничего не нашли, возвращаем первую категорию
                return {
                    'category': categories[0] if categories else 'Прочее',
                    'confidence': 0.3
                }
            
            return None
            
        except Exception as e:
            logger.error(f"[GoogleAI] Error: {type(e).__name__}: {str(e)[:200]}")
            return None
    
    async def chat_with_functions(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None,
        user_id: int = None
    ) -> str:
        """
        Чат с Google AI и поддержкой функций
        """
        try:
            # Добавляем контекст предыдущих сообщений для связанных вопросов
            enhanced_message = message
            if context and len(context) > 0:
                # Проверяем, является ли вопрос уточняющим
                clarifying_keywords = ['дата', 'когда', 'день', 'какой день', 'в какой', 'число']
                if any(keyword in message.lower() for keyword in clarifying_keywords):
                    # Добавляем контекст последних сообщений
                    recent_context = context[-2:] if len(context) >= 2 else context
                    context_str = ' '.join([f"{msg.get('role', '')}: {msg.get('content', '')}" for msg in recent_context])
                    enhanced_message = f"Контекст диалога: {context_str}\nТекущий вопрос: {message}"
            
            # Первый вызов AI для определения нужной функции
            response = await self._call_ai_with_functions(enhanced_message, context, user_context, user_id)
            
            logger.info(f"[GoogleAI] chat_with_functions - AI response type: {type(response)}, length: {len(response) if response else 0}")
            logger.info(f"[GoogleAI] chat_with_functions - AI response preview: {response[:200] if response else 'None'}")
            
            # Проверяем, нужно ли вызвать функцию
            if response and response.startswith("FUNCTION_CALL:"):
                # Извлекаем вызов функции
                function_call = response.replace("FUNCTION_CALL:", "").strip()
                logger.info(f"[GoogleAI] Function requested: {function_call}")
                
                # Выполняем функцию
                from .expense_functions import ExpenseFunctions
                functions = ExpenseFunctions()
                
                # Парсим вызов функции
                import re
                match = re.match(r'(\w+)\((.*)\)', function_call)
                if match:
                    func_name = match.group(1)
                    params_str = match.group(2)
                    
                    # Парсим параметры
                    params = {'user_id': user_id}
                    if params_str:
                        # Простой парсинг параметров
                        for param in params_str.split(','):
                            if '=' in param:
                                key, value = param.split('=', 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                                # Преобразуем типы
                                if value.isdigit():
                                    value = int(value)
                                elif value.replace('.', '').isdigit():
                                    value = float(value)
                                params[key] = value
                    
                    # Вызываем функцию
                    if hasattr(functions, func_name):
                        try:
                            logger.info(f"[GoogleAI] Calling function {func_name} with params: {params}")
                            
                            # Создаем синхронную функцию для выполнения в потоке
                            def run_sync_function():
                                import django
                                django.setup()
                                
                                # Импортируем функции после setup
                                from bot.services.expense_functions import ExpenseFunctions
                                funcs = ExpenseFunctions()
                                
                                # Получаем метод без декоратора (прямой вызов)
                                method = getattr(funcs, func_name)
                                # Если метод обернут в sync_to_async, получаем оригинальную функцию
                                if hasattr(method, '__wrapped__'):
                                    method = method.__wrapped__
                                
                                # Вызываем синхронную версию
                                return method(**params)
                            
                            # Выполняем в потоке
                            import asyncio
                            result = await asyncio.to_thread(run_sync_function)
                            logger.info(f"[GoogleAI] Function {func_name} returned: {result}")
                        except Exception as e:
                            logger.error(f"[GoogleAI] Error calling function {func_name}: {e}", exc_info=True)
                            result = {
                                'success': False,
                                'message': f'Ошибка при выполнении функции: {str(e)}'
                            }
                        
                        # Определяем функции с большим объемом данных
                        large_data_functions = {
                            'get_expenses_list',
                            'get_max_expense_day', 
                            'get_category_statistics',
                            'get_daily_totals',
                            'search_expenses',
                            'get_expenses_by_amount_range'
                        }
                        
                        # Для функций с большим объемом данных форматируем локально
                        if result.get('success') and func_name in large_data_functions:
                            # Форматируем результат в зависимости от функции
                            if func_name == 'get_expenses_list':
                                expenses_data = result.get('expenses', [])
                                total = result.get('total', 0)
                                count = result.get('count', len(expenses_data))
                                start_date = result.get('start_date', '')
                                end_date = result.get('end_date', '')
                                
                                if expenses_data:
                                    # Преобразуем данные в объекты-заглушки для форматтера
                                    from datetime import datetime
                                    from types import SimpleNamespace
                                    
                                    expense_objects = []
                                    for exp in expenses_data[:100]:  # Увеличиваем лимит до 100 записей
                                        expense_obj = SimpleNamespace()
                                        expense_obj.expense_date = datetime.fromisoformat(exp.get('date', '2024-01-01')).date()
                                        
                                        # Парсим время если есть
                                        time_str = exp.get('time', '')
                                        if time_str:
                                            try:
                                                expense_obj.expense_time = datetime.strptime(time_str, '%H:%M').time()
                                            except:
                                                expense_obj.expense_time = None
                                        else:
                                            expense_obj.expense_time = None
                                        
                                        expense_obj.created_at = datetime.now()
                                        expense_obj.description = exp.get('description', 'Без описания')
                                        expense_obj.amount = exp.get('amount', 0)
                                        expense_obj.currency = 'RUB'
                                        
                                        expense_objects.append(expense_obj)
                                    
                                    # Форматируем с помощью стандартного форматтера
                                    from bot.utils.expense_formatter import format_expenses_diary_style
                                    
                                    # Определяем описание периода
                                    try:
                                        start = datetime.fromisoformat(start_date)
                                        end = datetime.fromisoformat(end_date)
                                        
                                        # Если это один месяц
                                        if start.month == end.month and start.year == end.year:
                                            months_ru = {
                                                1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
                                                5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
                                                9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
                                            }
                                            period_desc = f"за {months_ru[start.month]} {start.year}"
                                        else:
                                            period_desc = f"с {start_date} по {end_date}"
                                    except:
                                        period_desc = f"с {start_date} по {end_date}"
                                    
                                    response_text = format_expenses_diary_style(
                                        expense_objects, 
                                        max_expenses=100,
                                        show_warning=(count > 100)
                                    )
                                    
                                    # Заменяем заголовок на более подходящий
                                    response_text = response_text.replace(
                                        "📋 <b>Дневник трат</b>",
                                        f"📋 <b>Траты {period_desc}</b>\n<i>Всего: {count} трат на сумму {total:,.0f} ₽</i>"
                                    )
                                    
                                    # Убираем HTML теги для чистого текста
                                    import re
                                    response_text = re.sub(r'<[^>]+>', '', response_text)
                                    
                                    return response_text
                                else:
                                    return "Траты за указанный период не найдены."
                            
                            elif func_name == 'get_max_expense_day':
                                date = result.get('date', '')
                                total = result.get('total', 0)
                                count = result.get('count', 0)
                                details = result.get('details', [])
                                
                                response_text = f"День с максимальными тратами: {date}\n"
                                response_text += f"Всего: {total:,.0f} ₽ ({count} трат)\n\n"
                                
                                if details:
                                    response_text += "Детали:\n"
                                    for exp in details[:50]:  # Увеличиваем до 50 записей
                                        time = exp.get('time', '')
                                        desc = exp.get('description', '')
                                        amount = exp.get('amount', 0)
                                        category = exp.get('category', '')
                                        response_text += f"• {time}: {desc} - {amount:,.0f} ₽ [{category}]\n"
                                    
                                    if len(details) > 50:
                                        response_text += f"\n... и еще {len(details) - 50} трат"
                                
                                return response_text
                            
                            elif func_name == 'get_category_statistics':
                                categories = result.get('categories', [])
                                total = result.get('total', 0)
                                
                                response_text = f"Статистика по категориям (всего: {total:,.0f} ₽)\n\n"
                                
                                for cat in categories[:20]:  # Увеличиваем до топ-20 категорий
                                    name = cat.get('name', '')
                                    cat_total = cat.get('total', 0)
                                    count = cat.get('count', 0)
                                    percent = cat.get('percentage', 0)
                                    response_text += f"• {name}: {cat_total:,.0f} ₽ ({count} шт., {percent:.1f}%)\n"
                                
                                if len(categories) > 20:
                                    response_text += f"\n... и еще {len(categories) - 20} категорий"
                                
                                return response_text
                            
                            elif func_name == 'get_daily_totals':
                                daily = result.get('daily_totals', {})
                                total = result.get('total', 0)
                                average = result.get('average', 0)
                                
                                response_text = f"Траты по дням (всего: {total:,.0f} ₽, среднее: {average:,.0f} ₽/день)\n\n"
                                
                                # Показываем последние 30 дней
                                dates = sorted(daily.keys(), reverse=True)[:30]
                                for date in dates:
                                    amount = daily[date]
                                    if amount > 0:
                                        response_text += f"• {date}: {amount:,.0f} ₽\n"
                                
                                if len(daily) > 30:
                                    response_text += f"\n... данные за {len(daily)} дней"
                                
                                return response_text
                            
                            elif func_name == 'search_expenses':
                                results = result.get('results', [])
                                count = result.get('count', len(results))
                                query = result.get('query', '')
                                
                                response_text = f"Найдено {count} трат по запросу '{query}':\n\n"
                                
                                for exp in results:
                                    date = exp.get('date', '')
                                    desc = exp.get('description', '')
                                    amount = exp.get('amount', 0)
                                    response_text += f"• {date}: {desc} - {amount:,.0f} ₽\n"
                                
                                return response_text
                            
                            elif func_name == 'get_expenses_by_amount_range':
                                expenses = result.get('expenses', [])
                                total = result.get('total', 0)
                                count = result.get('count', len(expenses))
                                min_amt = result.get('min_amount', 0)
                                max_amt = result.get('max_amount', 0)
                                
                                response_text = f"Траты от {min_amt:,.0f} до {max_amt:,.0f} ₽\n"
                                response_text += f"Найдено: {count} трат на сумму {total:,.0f} ₽\n\n"
                                
                                for exp in expenses[:50]:  # Увеличиваем до 50
                                    date = exp.get('date', '')
                                    desc = exp.get('description', '')
                                    amount = exp.get('amount', 0)
                                    response_text += f"• {date}: {desc} - {amount:,.0f} ₽\n"
                                
                                if count > 50:
                                    response_text += f"\n... и еще {count - 50} трат"
                                
                                return response_text
                            
                            else:
                                # Для других больших функций возвращаем JSON (fallback)
                                return f"Результат:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
                        
                        # Для функций с малым объемом данных используем второй вызов AI
                        elif result.get('success'):
                            # Формируем промпт для AI
                            result_prompt = f"""Вопрос: {message}

Данные: {json.dumps(result, ensure_ascii=False, indent=2)}

ВАЖНО: Дай полный ответ с максимумом деталей из данных:
- ВСЕГДА указывай точную дату (число, месяц, год) если есть
- ВСЕГДА указывай сумму и валюту
- Включи описание траты если есть
- Укажи день недели если есть
- Укажи категорию если есть
Отвечай естественно, но с полной информацией."""
                            
                            # Второй вызов AI для форматирования ответа
                            final_response = await self._call_ai_simple(result_prompt)
                            return final_response
                        else:
                            # Ошибка выполнения функции
                            return f"Ошибка: {result.get('message', 'Неизвестная ошибка')}"
                    else:
                        logger.error(f"Function {func_name} not found")
                        return f"Извините, не могу выполнить запрос. Функция {func_name} не найдена."
            
            # Если функция не нужна, возвращаем обычный ответ
            return response
            
        except Exception as e:
            logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."
    
    async def _call_ai_with_functions(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None,
        user_id: int = None
    ) -> str:
        """
        Вызов AI с инструкциями о функциях
        """
        try:
            logger.info(f"[GoogleAI] _call_ai_with_functions started for message: {message[:100]}")
            
            from datetime import datetime
            today = datetime.now()
            
            prompt = f"""Ты - помощник по учету расходов. У тебя есть доступ к функциям для анализа трат.
Сегодня: {today.strftime('%Y-%m-%d')} ({today.strftime('%B %Y')})

ДОСТУПНЫЕ ФУНКЦИИ:
1. get_max_expense_day() - для вопросов "В какой день я больше всего потратил?"
2. get_period_total(period='today'|'yesterday'|'week'|'month'|'year') - для "Сколько я потратил сегодня/вчера/на этой неделе?"
3. get_max_single_expense() - для "Какая моя самая большая трата?"
4. get_category_statistics() - для "На что я трачу больше всего?"
5. get_average_expenses() - для "Сколько я трачу в среднем?"
6. get_recent_expenses(limit=10) - для "Покажи последние траты"
7. search_expenses(query='текст') - для "Когда я покупал..."
8. get_weekday_statistics() - для "В какие дни недели я трачу больше?"
9. predict_month_expense() - для "Сколько я потрачу в этом месяце?"
10. check_budget_status(budget_amount=50000) - для "Уложусь ли я в бюджет?"
11. compare_periods() - для "Я стал тратить больше или меньше?"
12. get_expense_trend() - для "Покажи динамику трат"
13. get_expenses_by_amount_range(min_amount=1000) - для "Покажи траты больше 1000"
14. get_category_total(category='продукты', period='month') - для "Сколько я трачу на продукты?"
15. get_expenses_list(start_date='2025-08-01', end_date='2025-08-31') - для "Покажи траты за период/с даты по дату"
16. get_daily_totals(days=30) - для "Покажи траты по дням/суммы по дням за последний месяц"

ВАЖНО: Если вопрос требует анализа данных, ответь ТОЛЬКО в формате:
FUNCTION_CALL: имя_функции(параметр1=значение1, параметр2=значение2)

Если вопрос не требует анализа данных (приветствие, общий вопрос), отвечай обычным текстом.

Вопрос пользователя: {message}"""

            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="You are an expense tracking assistant. Analyze the user's question and determine if a function call is needed."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=5000,  # Увеличено для обработки больших списков трат
                top_p=0.9
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            logger.info(f"[GoogleAI] Calling generate_content_async with prompt length: {len(prompt)}")
            logger.info(f"[GoogleAI] Generation config: max_output_tokens={generation_config.max_output_tokens}")
            
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info(f"[GoogleAI] generate_content_async completed")
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                
                # Логируем текст ответа
                if hasattr(response, 'text'):
                    try:
                        response_text = response.text
                        logger.info(f"[GoogleAI] Response text length: {len(response_text) if response_text else 0}")
                        logger.info(f"[GoogleAI] Response text preview: {response_text[:500] if response_text else 'No text'}")
                        
                        # Проверяем наличие FUNCTION_CALL
                        if response_text and 'FUNCTION_CALL:' in response_text:
                            logger.info(f"[GoogleAI] FUNCTION_CALL detected in response")
                        elif response_text:
                            logger.warning(f"[GoogleAI] No FUNCTION_CALL found, AI returned plain text")
                    except Exception as e:
                        logger.error(f"[GoogleAI] Error accessing response text: {e}")
                
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            logger.error(f"[GoogleAI] Error in _call_ai_with_functions: {e}")
            return "Извините, произошла ошибка."
    
    async def _call_ai_simple(self, prompt: str) -> str:
        """
        Простой вызов AI для форматирования ответа
        """
        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="Answer in Russian with complete information. Always include dates, amounts, descriptions when available. Be natural but informative."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=5000,  # Увеличено для полных ответов с большим количеством трат
                top_p=0.9
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                
                # Попробуем извлечь данные из промпта для форматирования локально
                try:
                    if "Данные:" in prompt and "expenses" in prompt:
                        logger.info("[GoogleAI] Attempting local fallback formatting")
                        # Извлекаем JSON из промпта
                        json_start = prompt.find("Данные:") + len("Данные:")
                        json_end = prompt.find("\n\nВАЖНО:")
                        if json_end == -1:
                            json_end = len(prompt)
                        
                        json_str = prompt[json_start:json_end].strip()
                        data = json.loads(json_str)
                        
                        if 'expenses' in data:
                            expenses_data = data['expenses']
                            total = data.get('total', 0)
                            count = data.get('count', len(expenses_data))
                            remaining = data.get('remaining_count', 0)
                            
                            if expenses_data:
                                # Используем форматирование в стиле дневника
                                from datetime import datetime
                                from types import SimpleNamespace
                                from bot.utils.expense_formatter import format_expenses_diary_style
                                import re
                                
                                expense_objects = []
                                for exp in expenses_data[:100]:
                                    expense_obj = SimpleNamespace()
                                    expense_obj.expense_date = datetime.fromisoformat(exp.get('date', '2024-01-01')).date()
                                    
                                    time_str = exp.get('time', '')
                                    if time_str:
                                        try:
                                            expense_obj.expense_time = datetime.strptime(time_str, '%H:%M').time()
                                        except:
                                            expense_obj.expense_time = None
                                    else:
                                        expense_obj.expense_time = None
                                    
                                    expense_obj.created_at = datetime.now()
                                    expense_obj.description = exp.get('description', 'Без описания')
                                    expense_obj.amount = exp.get('amount', 0)
                                    expense_obj.currency = 'RUB'
                                    
                                    expense_objects.append(expense_obj)
                                
                                result_text = format_expenses_diary_style(
                                    expense_objects,
                                    max_expenses=100,
                                    show_warning=(remaining > 0)
                                )
                                
                                # Убираем HTML теги для чистого текста
                                result_text = re.sub(r'<[^>]+>', '', result_text)
                                
                                logger.info(f"[GoogleAI] Fallback formatting successful, returning {len(result_text)} chars")
                                return result_text
                            else:
                                return "Траты за указанный период не найдены."
                except Exception as fallback_error:
                    logger.error(f"[GoogleAI] Fallback formatting failed: {fallback_error}")
                
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            logger.error(f"[GoogleAI] Error in _call_ai_simple: {e}")
            return "Извините, произошла ошибка."
    
    async def chat(
        self,
        message: str,
        context: List[Dict[str, str]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Обычный чат с Google AI (для обратной совместимости)
        """
        try:
            # Если есть user_context с user_id, используем функции
            if user_context and 'user_id' in user_context:
                return await self.chat_with_functions(
                    message=message,
                    context=context,
                    user_context=user_context,
                    user_id=user_context['user_id']
                )
            
            # Иначе обычный чат
            prompt = self.get_chat_prompt(message, context, user_context)
            
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction="You are an expense tracking bot. Answer naturally and concisely in the user's language."
            )
            
            generation_config = genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=5000,  # Увеличено для полных ответов с большим количеством трат
                top_p=0.9
            )
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Детальное логирование для диагностики
            logger.info(f"[GoogleAI] Response received: response={response is not None}")
            if response:
                logger.info(f"[GoogleAI] Response details: parts={response.parts is not None and len(response.parts) if response.parts else 0}")
                logger.info(f"[GoogleAI] Response candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
                if hasattr(response, 'prompt_feedback'):
                    logger.info(f"[GoogleAI] Prompt feedback: {response.prompt_feedback}")
                if response.parts and len(response.parts) > 0:
                    logger.info(f"[GoogleAI] First part text preview: {str(response.parts[0])[:100]}")
            
            if response and response.parts:
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."