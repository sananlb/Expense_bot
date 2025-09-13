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
from .key_rotation_mixin import GoogleKeyRotationMixin
from django.conf import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Проверяем наличие ключей при инициализации
if hasattr(settings, 'GOOGLE_API_KEYS') and settings.GOOGLE_API_KEYS:
    logger.info(f"[GoogleAI] Found {len(settings.GOOGLE_API_KEYS)} API keys for rotation")
else:
    logger.warning("[GoogleAI] No GOOGLE_API_KEYS found in settings")


class GoogleAIService(AIBaseService, GoogleKeyRotationMixin):
    """Сервис для работы с Google AI (Gemini) - упрощенная стабильная версия"""
    
    def __init__(self):
        """Инициализация сервиса"""
        api_keys = self.get_api_keys()
        if not api_keys:
            raise ValueError("GOOGLE_API_KEYS not found in settings")
        
        logger.info(f"[GoogleAI] Service initialized with {len(api_keys)} keys for rotation")
    
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
            
            model_name = get_model('categorization', 'google')
            
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return None
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for categorization")
            
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
            
            # Таймаут для ускорения категоризации: при превышении – fallback на OpenAI категоризацию
            import asyncio as _asyncio
            timeout_seconds = int(os.getenv('GOOGLE_CATEGORIZATION_TIMEOUT', os.getenv('GOOGLE_CHAT_TIMEOUT', '15')))
            try:
                response = await _asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    ),
                    timeout=timeout_seconds
                )
            except _asyncio.TimeoutError:
                logger.warning(f"[GoogleAI] categorize_expense timeout after {timeout_seconds}s, falling back to OpenAI categorization")
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    return await openai_service.categorize_expense(text, amount, currency, categories, user_context)
                except Exception as e:
                    logger.error(f"[GoogleAI] OpenAI categorization fallback failed after timeout: {e}")
                    return None
            
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
                result = {
                    'category': categories[0] if categories else 'Прочее',
                    'confidence': 0.3
                }
                # Помечаем ключ как рабочий
                self.mark_key_success(key_index)
                return result
            
            # Помечаем ключ как рабочий если дошли до сюда без исключений
            self.mark_key_success(key_index)
            return None
            
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
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
                    from .function_call_utils import normalize_function_call
                    func_name, params = normalize_function_call(message, func_name, params, user_id)

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
                            
                            try:
                                import json as _json
                                _prev = _json.dumps(result, ensure_ascii=True)
                            except Exception:
                                _prev = str(result).encode('ascii','ignore').decode('ascii')
                            if len(_prev) > 300:
                                _prev = _prev[:300] + '...'
                            logger.info(f"[GoogleAI] Function {func_name} returned: {_prev}")

                        except Exception as e:
                            logger.error(f"[GoogleAI] Error calling function {func_name}: {e}", exc_info=True)
                            result = {
                                'success': False,
                                'message': f'Ошибка при выполнении функции: {str(e)}'
                            }
                        
                        if result.get('success'):
                            # Используем универсальный форматтер
                            try:
                                from bot.services.response_formatter import format_function_result
                                return format_function_result(func_name, result)
                            except Exception as _fmt_err:
                                logger.error(f"[GoogleAI] Error formatting result for {func_name}: {_fmt_err}")
                                import json as _json
                                try:
                                    return _json.dumps(result, ensure_ascii=False)[:1000]
                                except Exception:
                                    return str(result)[:1000]

                    elif func_name == 'get_max_expense_day':
                        # Нормализация period/month/year -> period_days
                        import calendar as _cal
                        period_days = params.get('period_days')
                        if not period_days:
                            period = str(params.get('period', '')).lower()
                            month = params.get('month')
                            year = params.get('year')
                            try:
                                if period == 'week':
                                    period_days = 7
                                elif period == 'year':
                                    period_days = 365
                                elif period == 'month':
                                    if month and year:
                                        period_days = _cal.monthrange(int(year), int(month))[1]
                                    else:
                                        period_days = 31
                            except Exception:
                                period_days = None
                        new_params = {'user_id': user_id}
                        if period_days:
                            try:
                                new_params['period_days'] = int(period_days)
                            except Exception:
                                pass
                        params = new_params
                    elif func_name == 'get_daily_totals':

                                daily = result.get('daily_totals', {})
                                # Итоги могут приходить как в корне, так и в result['statistics']
                                stats = result.get('statistics', {}) if isinstance(result.get('statistics'), dict) else {}
                                total = result.get('total', stats.get('total', 0))
                                average = result.get('average', stats.get('average', 0))

                                response_text = f"Траты по дням (всего: {total:,.0f} ₽, среднее: {average:,.0f} ₽/день)\n\n"

                                # Показываем последние 30 дней
                                dates = sorted(daily.keys(), reverse=True)[:30]
                                for date in dates:
                                    entry = daily.get(date)
                                    # daily может быть как {date: number}, так и {date: {amount, count}}
                                    if isinstance(entry, dict):
                                        amount_val = entry.get('amount', 0) or 0
                                    else:
                                        amount_val = entry or 0
                                    try:
                                        amount_float = float(amount_val)
                                    except (TypeError, ValueError):
                                        amount_float = 0.0
                                    if amount_float > 0:
                                        response_text += f"• {date}: {amount_float:,.0f} ₽\n"

                                if len(daily) > 30:
                                    response_text += f"\n... данные за {len(daily)} дней"

                                return response_text
                            
                            elif func_name == 'search_expenses':
                                results = result.get('results', [])
                                count = result.get('count', len(results))
                                query = result.get('query', '')
                                
                                return format_expenses_from_dict_list(
                                    results,
                                    title=f"🔍 Результаты поиска по запросу '{query}'",
                                    subtitle=f"Найдено: {count} трат",
                                    max_expenses=100
                                )
                            
                            elif func_name == 'get_expenses_by_amount_range':
                                expenses = result.get('expenses', [])
                                total = result.get('total', 0)
                                count = result.get('count', len(expenses))
                                min_amt = result.get('min_amount', 0)
                                max_amt = result.get('max_amount', 0)
                                
                                # Формируем подзаголовок
                                subtitle = f"Найдено: {count} трат на сумму {total:,.0f} ₽"
                                
                                # Добавляем сообщение о лимите, если оно есть
                                limit_message = result.get('limit_message', '')
                                if limit_message:
                                    subtitle += f"\n\n{limit_message}"
                                
                                return format_expenses_from_dict_list(
                                    expenses,
                                    title=f"💰 Траты от {min_amt:,.0f} до {max_amt:,.0f} ₽",
                                    subtitle=subtitle,
                                    max_expenses=100
                                )
                            
                            # Обработка функций доходов
                            elif func_name == 'get_incomes_list':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                incomes_data = result.get('incomes', [])
                                total = result.get('total', 0)
                                count = result.get('count', len(incomes_data))
                                start_date = result.get('start_date', '')
                                end_date = result.get('end_date', '')
                                
                                # Определяем описание периода
                                try:
                                    from datetime import datetime
                                    start = datetime.fromisoformat(start_date)
                                    end = datetime.fromisoformat(end_date)
                                    
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
                                
                                subtitle = f"Всего: {count} доходов на сумму {total:,.0f} ₽"
                                limit_message = result.get('limit_message', '')
                                if limit_message:
                                    subtitle += f"\n\n{limit_message}"
                                
                                return format_incomes_from_dict_list(
                                    incomes_data,
                                    title=f"💰 Доходы {period_desc}",
                                    subtitle=subtitle,
                                    max_incomes=100
                                )
                            
                            elif func_name == 'get_recent_incomes':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                incomes_data = result.get('incomes', [])
                                count = result.get('count', 0)
                                
                                return format_incomes_from_dict_list(
                                    incomes_data,
                                    title="💰 Последние доходы",
                                    subtitle=f"Показано последних доходов: {count}",
                                    max_incomes=100
                                )
                            
                            elif func_name == 'get_max_income_day':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                date_str = result.get('date', '')
                                total = result.get('total', 0)
                                count = result.get('count', 0)
                                details = result.get('details', [])
                                
                                # Преобразуем детали в формат для форматтера
                                incomes_data = []
                                for detail in details:
                                    incomes_data.append({
                                        'date': date_str,
                                        'amount': detail.get('amount', 0),
                                        'description': detail.get('description', 'Доход'),
                                        'category': detail.get('category', 'Без категории')
                                    })
                                
                                return format_incomes_from_dict_list(
                                    incomes_data,
                                    title=f"💰 День с максимальным доходом",
                                    subtitle=f"Дата: {date_str}\nВсего доходов: {count}\nОбщая сумма: {total:,.0f} ₽",
                                    max_incomes=100
                                )
                            
                            elif func_name == 'get_daily_income_totals':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                daily_totals = result.get('daily_totals', [])
                                grand_total = result.get('grand_total', 0)
                                period_days = result.get('period_days', 30)
                                days_with_income = result.get('days_with_income', 0)
                                
                                # Преобразуем в формат для форматтера
                                incomes_data = []
                                for day in daily_totals:
                                    incomes_data.append({
                                        'date': day.get('date'),
                                        'amount': day.get('total', 0),
                                        'description': f"Доходы за день ({day.get('count', 0)} шт.)",
                                        'category': 'Итог дня'
                                    })
                                
                                return format_incomes_from_dict_list(
                                    incomes_data,
                                    title=f"💰 Доходы по дням за {period_days} дней",
                                    subtitle=f"Всего: {grand_total:,.0f} ₽\nДней с доходами: {days_with_income}",
                                    max_incomes=100
                                )
                            
                            elif func_name == 'search_incomes':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                incomes = result.get('incomes', [])
                                query = result.get('query', '')
                                count = result.get('count', 0)
                                
                                return format_incomes_from_dict_list(
                                    incomes,
                                    title=f"🔍 Поиск доходов: '{query}'",
                                    subtitle=f"Найдено: {count} записей",
                                    max_incomes=100
                                )
                            
                            elif func_name == 'get_incomes_by_amount_range':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                incomes = result.get('incomes', [])
                                min_amount = result.get('min_amount')
                                max_amount = result.get('max_amount')
                                count = result.get('count', 0)
                                
                                # Формируем заголовок с диапазоном
                                if min_amount and max_amount:
                                    range_str = f"от {min_amount:,.0f} до {max_amount:,.0f} ₽"
                                elif min_amount:
                                    range_str = f"более {min_amount:,.0f} ₽"
                                elif max_amount:
                                    range_str = f"до {max_amount:,.0f} ₽"
                                else:
                                    range_str = "все суммы"
                                
                                return format_incomes_from_dict_list(
                                    incomes,
                                    title=f"💰 Доходы в диапазоне {range_str}",
                                    subtitle=f"Найдено: {count} записей",
                                    max_incomes=100
                                )
                            
                            elif func_name == 'compare_income_periods':
                                from bot.utils.income_formatter import format_incomes_from_dict_list
                                period1 = result.get('period1', {})
                                period2 = result.get('period2', {})
                                difference = result.get('difference', 0)
                                percent_change = result.get('percent_change', 0)
                                trend = result.get('trend', '')
                                
                                # Формируем читаемый ответ
                                response = f"📊 <b>Сравнение доходов</b>\n\n"
                                response += f"<b>{period1.get('name', 'Период 1')}:</b>\n"
                                response += f"  • Сумма: {period1.get('total', 0):,.0f} ₽\n"
                                response += f"  • Период: {period1.get('start', '')} - {period1.get('end', '')}\n\n"
                                response += f"<b>{period2.get('name', 'Период 2')}:</b>\n"
                                response += f"  • Сумма: {period2.get('total', 0):,.0f} ₽\n"
                                response += f"  • Период: {period2.get('start', '')} - {period2.get('end', '')}\n\n"
                                
                                if difference != 0:
                                    emoji = '📈' if difference > 0 else '📉'
                                    response += f"{emoji} <b>Изменение:</b> {difference:+,.0f} ₽ ({percent_change:+.1f}%)\n"
                                    response += f"Тренд: {trend}"
                                else:
                                    response += "💎 Доходы не изменились"
                                
                                return response
                            
                            elif func_name == 'get_income_trend':
                                trends = result.get('trends', [])
                                group_by = result.get('group_by', 'month')
                                
                                response = f"📈 <b>Динамика доходов по {group_by}</b>\n\n"
                                
                                for trend in trends:
                                    period = trend.get('period', '')
                                    total = trend.get('total', 0)
                                    count = trend.get('count', 0)
                                    
                                    response += f"<b>{period}:</b>\n"
                                    response += f"  • Сумма: {total:,.0f} ₽\n"
                                    response += f"  • Количество: {count}\n\n"
                                
                                return response
                            
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
                            final_response = await self._call_ai_simple(result_prompt, user_context=user_context)
                            return final_response
                        else:
                            # Ошибка выполнения функции
                            return f"Ошибка: {result.get('message', 'Неизвестная ошибка')}"
                    else:
                        logger.error(f"Function {func_name} not found")
                        return f"Извините, не могу выполнить запрос. Функция {func_name} не найдена."
            
            # Если функция не нужна, возвращаем обычный ответ
            # Помечаем ключ как рабочий перед возвратом успешного результата
            if 'key_index' in locals():
                self.mark_key_success(key_index)
            return response
            
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI Chat] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI Chat] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
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
            try:
                _msg_preview = (message or '')[:100]
                _msg_preview = _msg_preview.encode('ascii','ignore').decode('ascii')
            except Exception:
                _msg_preview = ''
            logger.info(f"[GoogleAI] _call_ai_with_functions started for message: {_msg_preview}")
            
            from datetime import datetime
            today = datetime.now()
            
            from bot.services.prompt_builder import build_function_call_prompt
            # Here we receive already-enhanced message; use the parameter
            prompt = build_function_call_prompt(message, context)

            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return "Извините, сервис временно недоступен."
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat with functions")
            
            model_name = get_model('chat', 'google')
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction="You are a finance tracking assistant for both expenses and income. Analyze the user's question and determine if a function call is needed."
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
            
            # Ограничиваем время форматирования, при таймауте пробуем OpenAI
            import asyncio as _asyncio
            timeout_seconds = int(os.getenv('GOOGLE_CHAT_FORMAT_TIMEOUT', os.getenv('GOOGLE_CHAT_TIMEOUT', '15')))
            try:
                response = await _asyncio.wait_for(
                    model.generate_content_async(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    ),
                    timeout=timeout_seconds
                )
            except _asyncio.TimeoutError:
                logger.warning(f"[GoogleAI] _call_ai_simple timeout after {timeout_seconds}s, falling back to OpenAI formatter")
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    # Используем OpenAI как простой чат для форматирования текста промпта
                    return await openai_service.chat(prompt, [], None)
                except Exception as e:
                    logger.error(f"[GoogleAI] OpenAI formatter fallback failed after timeout: {e}")
                    return "Извините, сервис временно недоступен. Попробуйте еще раз."
            
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
                # Помечаем ключ как рабочий перед возвратом успешного результата
                self.mark_key_success(key_index)
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error in _call_ai_with_functions with {key_name}: {e}")
                else:
                    logger.error(f"[GoogleAI] Error in _call_ai_with_functions with key {key_index}: {e}")
            else:
                logger.error(f"[GoogleAI] Error in _call_ai_with_functions: {e}")
            return "Извините, произошла ошибка."
    
    async def _call_ai_simple(self, prompt: str, user_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Простой вызов AI для форматирования ответа
        """
        try:
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return "Извините, сервис временно недоступен."
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat with functions")
            
            model_name = get_model('chat', 'google')
            model = genai.GenerativeModel(
                model_name=model_name,
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
                            
                            if expenses_data:
                                # Используем универсальный форматтер
                                from bot.utils.expense_formatter import format_expenses_from_dict_list
                                
                                result_text = format_expenses_from_dict_list(
                                    expenses_data,
                                    title="📋 Список трат",
                                    subtitle=f"Найдено: {count} трат на сумму {total:,.0f} ₽",
                                    max_expenses=100
                                )
                                
                                logger.info(f"[GoogleAI] Fallback formatting successful, returning {len(result_text)} chars")
                                return result_text
                            else:
                                return "Траты за указанный период не найдены."
                except Exception as fallback_error:
                    logger.error(f"[GoogleAI] Fallback formatting failed: {fallback_error}")
                # Попытаемся отдать форматирование OpenAI с учётом контекста пользователя
                try:
                    from .openai_service import OpenAIService
                    openai_service = OpenAIService()
                    return await openai_service.chat(prompt, [], user_context)
                except Exception:
                    return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI] Error in _call_ai_simple with {key_name}: {e}")
                else:
                    logger.error(f"[GoogleAI] Error in _call_ai_simple with key {key_index}: {e}")
            else:
                logger.error(f"[GoogleAI] Error in _call_ai_simple: {e}")
            # Попытаемся отдать форматирование OpenAI с учётом контекста пользователя
            try:
                from .openai_service import OpenAIService
                openai_service = OpenAIService()
                return await openai_service.chat(prompt, [], user_context)
            except Exception:
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
            
            # Получаем следующий ключ для ротации
            key_result = self.get_next_key()
            if not key_result:
                logger.error("[GoogleAI] No API keys available")
                return "Извините, сервис временно недоступен."
            
            api_key, key_index = key_result
            key_name = self.get_key_name(key_index)
            
            # Конфигурируем с новым ключом
            genai.configure(api_key=api_key)
            logger.debug(f"[GoogleAI] Using {key_name} for chat with functions")
            
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
                # Помечаем ключ как рабочий перед возвратом успешного результата
                self.mark_key_success(key_index)
                return response.text.strip()
            else:
                logger.warning(f"[GoogleAI] Empty response from API - response={response}, parts={response.parts if response else None}")
                return "Извините, не удалось получить ответ от AI."
                
        except Exception as e:
            # Помечаем ключ как нерабочий и логируем с его именем
            if 'key_index' in locals():
                self.mark_key_failure(key_index, e)
                if 'key_name' in locals():
                    logger.error(f"[GoogleAI Chat] Error with {key_name}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    logger.error(f"[GoogleAI Chat] Error with key {key_index}: {type(e).__name__}: {str(e)[:200]}")
            else:
                logger.error(f"[GoogleAI Chat] Error: {type(e).__name__}: {str(e)[:200]}")
            return "Извините, произошла ошибка при обработке вашего сообщения."
