"""
Router for expense reports and analytics
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, date, timedelta
from calendar import monthrange
import logging

from bot.keyboards import expenses_summary_keyboard, month_selection_keyboard, back_close_keyboard
from bot.utils import get_text, format_amount, get_month_name
from bot.utils.category_helpers import get_category_display_name
from bot.services.expense import get_expenses_summary, get_expenses_by_period, get_last_expenses
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

router = Router(name="reports")


@router.message(Command("summary"))
async def cmd_summary(message: Message, lang: str = 'ru'):
    """Команда /summary - показать сводку за месяц"""
    today = date.today()
    start_date = today.replace(day=1)
    end_date = today
    
    await show_expenses_summary(message, start_date, end_date, lang)


@router.callback_query(F.data == "expenses_today")
async def callback_expenses_today(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать расходы за сегодня"""
    today = date.today()
    
    await show_expenses_summary(
        callback.message,
        today,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    await callback.answer()


@router.callback_query(F.data == "show_month_start")
async def callback_show_month_start(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать расходы с начала месяца"""
    today = date.today()
    start_date = today.replace(day=1)
    
    await show_expenses_summary(
        callback.message,
        start_date,
        today,
        lang,
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    await callback.answer()




async def show_expenses_summary(
    message: Message,
    start_date: date,
    end_date: date,
    lang: str,
    state: FSMContext = None,
    edit: bool = False,
    original_message: Message = None,
    callback: CallbackQuery = None
):
    """Показать сводку расходов за период"""
    try:
        # Получаем данные - при edit берем user_id из callback
        if callback:
            user_id = callback.from_user.id
        elif not edit:
            user_id = message.from_user.id
        else:
            # Fallback - не должно происходить
            logger.error("No callback provided for edit mode!")
            user_id = message.chat.id
        
        logger.info(f"Getting expenses summary for user {user_id}, period: {start_date} to {end_date}")
        
        summary = await get_expenses_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(f"Summary result: total={summary.get('total', 0)}, count={summary.get('count', 0)}, categories={len(summary.get('by_category', []))}")
        
        # Формируем текст
        if start_date == end_date:
            if start_date == date.today():
                period_text = get_text('today', lang)
            else:
                period_text = start_date.strftime('%d.%m.%Y')
        else:
            month_name = get_month_name(start_date.month, lang)
            if start_date.month == end_date.month and start_date.year == end_date.year:
                period_text = f"{month_name} {start_date.year}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        
        text = f"📊 <b>{get_text('summary', lang)} {period_text}</b>\n\n"
        
        # Проверяем есть ли операции вообще
        has_expenses = summary['total'] > 0
        has_incomes = summary.get('income_total', 0) > 0
        
        if not has_expenses and not has_incomes:
            text += get_text('no_expenses_period', lang)
        else:
            # Показываем только те строки, где есть данные
            expense_amount = format_amount(summary['total'], summary['currency'], lang)
            income_amount = format_amount(summary.get('income_total', 0), summary['currency'], lang)
            balance = summary.get('balance', -summary['total'])  # Если нет доходов, баланс = -расходы
            
            # Показываем расходы если они есть
            if has_expenses:
                text += f"💸 Расходы: {expense_amount}\n"
            
            # Показываем доходы если они есть  
            if has_incomes:
                text += f"💰 Доходы: {income_amount}\n"
            
            # Показываем баланс только если есть и доходы и расходы
            if has_expenses and has_incomes:
                # Форматируем баланс с + или - в зависимости от знака
                if balance >= 0:
                    balance_text = f"+{format_amount(balance, summary['currency'], lang)}"
                else:
                    balance_text = format_amount(balance, summary['currency'], lang)
                text += f"⚖️ Баланс: {balance_text}\n"
            
            text += "\n"
            
            # По категориям расходов (если есть)
            if summary['by_category'] and has_expenses:
                text += f"📊 <b>Расходы по категориям:</b>\n"
                total_categories = len(summary['by_category'])
                
                # Логика отображения: если 22 или меньше - показываем все, если 23+ показываем 20 + остальные
                if total_categories <= 22:
                    # Показываем все категории
                    for cat in summary['by_category']:
                        # Категория в словаре содержит только имя, поэтому создаем псевдо-объект
                        from types import SimpleNamespace
                        cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                        category_display = get_category_display_name(cat_obj, lang)
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                else:
                    # Показываем первые 20 категорий
                    for cat in summary['by_category'][:20]:
                        # Категория в словаре содержит только имя, поэтому создаем псевдо-объект
                        from types import SimpleNamespace
                        cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                        category_display = get_category_display_name(cat_obj, lang)
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                    
                    # Добавляем "остальные траты"
                    remaining_count = total_categories - 20
                    remaining_sum = sum(cat['total'] for cat in summary['by_category'][20:])
                    if lang == 'ru':
                        text += f"  📦 <i>Остальные траты ({remaining_count} {'категория' if remaining_count == 1 else 'категории' if remaining_count < 5 else 'категорий'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"
                    else:
                        text += f"  📦 <i>Other expenses ({remaining_count} {'category' if remaining_count == 1 else 'categories'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"
                
                text += "\n"
            
            # Потенциальный кешбэк между категориями расходов и доходов
            if summary['potential_cashback'] > 0:
                text += f"💳 {get_text('potential_cashback', lang)}: {format_amount(summary['potential_cashback'], summary['currency'], lang)}\n\n"
            
            # По категориям доходов (если есть)
            if summary.get('by_income_category') and has_incomes:
                text += f"💵 <b>Доходы по категориям:</b>\n"
                income_categories = summary.get('by_income_category', [])
                total_income_categories = len(income_categories)
                
                # Логика отображения: если 22 или меньше - показываем все, если 23+ показываем 20 + остальные
                if total_income_categories <= 22:
                    # Показываем все категории доходов
                    for cat in income_categories:
                        # Категория в словаре содержит только имя, поэтому создаем псевдо-объект
                        from types import SimpleNamespace
                        cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                        category_display = get_category_display_name(cat_obj, lang)
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                else:
                    # Показываем первые 20 категорий доходов
                    for cat in income_categories[:20]:
                        # Категория в словаре содержит только имя, поэтому создаем псевдо-объект
                        from types import SimpleNamespace
                        cat_obj = SimpleNamespace(icon=cat.get('icon'), name=cat['name'])
                        category_display = get_category_display_name(cat_obj, lang)
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                    
                    # Добавляем "остальные доходы"
                    remaining_count = total_income_categories - 20
                    remaining_sum = sum(cat['total'] for cat in income_categories[20:])
                    if lang == 'ru':
                        text += f"  💰 <i>Остальные доходы ({remaining_count} {'категория' if remaining_count == 1 else 'категории' if remaining_count < 5 else 'категорий'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"
                    else:
                        text += f"  💰 <i>Other income ({remaining_count} {'category' if remaining_count == 1 else 'categories'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"
                
                text += "\n"
        
        # Добавляем подсказку внизу курсивом
        text += "\n\n<i>Показать отчет за другой период?</i>"
        
        # Определяем период для клавиатуры
        today = date.today()
        is_today = start_date == end_date == today
        is_current_month = (start_date.day == 1 and 
                           start_date.month == today.month and 
                           start_date.year == today.year and
                           end_date >= today)
        
        if is_today:
            period = 'today'
            show_pdf = False
        elif is_current_month or (start_date.day == 1 and end_date.month == start_date.month):
            period = 'month'
            show_pdf = True
        else:
            period = 'custom'
            show_pdf = True
        
        # Логирование для отладки
        logger.info(f"Period determination: start_date={start_date}, end_date={end_date}, today={today}, is_today={is_today}, period={period}")
        
        # Сохраняем даты в состоянии для генерации PDF
        if state:
            await state.update_data(
                report_start_date=start_date.isoformat(),
                report_end_date=end_date.isoformat(),
                current_month=start_date.month if start_date.day == 1 else None,
                current_year=start_date.year if start_date.day == 1 else None
            )
        
        # Отправляем или редактируем сообщение
        if edit and original_message:
            await original_message.edit_text(
                text,
                reply_markup=expenses_summary_keyboard(
                    lang, period, show_pdf,
                    current_month=start_date.month if start_date.day == 1 else None,
                    current_year=start_date.year if start_date.day == 1 else None
                )
            )
        else:
            await send_message_with_cleanup(
                message, state, text,
                reply_markup=expenses_summary_keyboard(
                    lang, period, show_pdf,
                    current_month=start_date.month if start_date.day == 1 else None,
                    current_year=start_date.year if start_date.day == 1 else None
                )
            )
            
    except Exception as e:
        logger.error(f"Error showing expenses summary: {e}")
        error_text = get_text('error_occurred', lang)
        if edit and original_message:
            await original_message.edit_text(error_text)
        else:
            await message.answer(error_text)


@router.message(Command("report"))
async def cmd_report(message: Message, lang: str = 'ru'):
    """Команда /report - выбор периода для отчета"""
    keyboard = month_selection_keyboard(lang)
    
    await send_message_with_cleanup(
        message, state,
        get_text('choose_month', lang),
        reply_markup=keyboard
    )


@router.callback_query(F.data == "show_diary")
async def callback_show_diary(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать дневник трат (последние 3 дня, максимум 30 записей)"""
    try:
        from datetime import datetime, timedelta
        from expenses.models import Expense, Profile
        from asgiref.sync import sync_to_async
        import pytz
        
        user_id = callback.from_user.id
        
        # Получаем профиль пользователя с часовым поясом
        @sync_to_async
        def get_user_profile():
            try:
                return Profile.objects.get(telegram_id=user_id)
            except Profile.DoesNotExist:
                return None
        
        profile = await get_user_profile()
        user_tz = pytz.timezone(profile.timezone if profile else 'UTC')
        
        # Определяем "сегодня" с учетом часового пояса пользователя
        now_user_tz = datetime.now(user_tz)
        end_date = now_user_tz.date()
        start_date = end_date - timedelta(days=3)  # Расширяем до 3 дней
        
        # Получаем траты и доходы за последние 3 дня, но не более 30 операций в сумме
        @sync_to_async
        def get_recent_operations():
            from expenses.models import Income
            
            # Получаем расходы
            expenses = list(Expense.objects.filter(
                profile__telegram_id=user_id,
                expense_date__gte=start_date,
                expense_date__lte=end_date
            ).select_related('category').order_by('-expense_date', '-expense_time')[:30])
            
            # Получаем доходы
            incomes = list(Income.objects.filter(
                profile__telegram_id=user_id,
                income_date__gte=start_date,
                income_date__lte=end_date
            ).select_related('category').order_by('-income_date', '-income_time')[:30])
            
            # Объединяем и сортируем по дате (от новых к старым)
            operations = []
            for exp in expenses:
                operations.append({
                    'type': 'expense',
                    'date': exp.expense_date,
                    'time': exp.expense_time or exp.created_at.time(),
                    'amount': exp.amount,
                    'currency': exp.currency,
                    'category': get_category_display_name(exp.category, lang) if exp.category else ('Без категории' if lang == 'ru' else 'No Category'),
                    'description': exp.description,
                    'object': exp
                })
            
            for inc in incomes:
                operations.append({
                    'type': 'income',
                    'date': inc.income_date,
                    'time': inc.income_time or inc.created_at.time(),
                    'amount': inc.amount,
                    'currency': inc.currency,
                    'category': get_category_display_name(inc.category, lang) if inc.category else ('Прочие доходы' if lang == 'ru' else 'Other Income'),
                    'description': inc.description,
                    'object': inc
                })
            
            # Сортируем все операции вместе и берем первые 30
            operations.sort(key=lambda x: (x['date'], x['time']), reverse=True)
            return operations[:30]
        
        operations = await get_recent_operations()
        
        if not operations:
            text = "📋 <b>Дневник</b>\n\n<i>Операций не найдено</i>"
        else:
            text = "📋 <b>Дневник</b>\n\n"
            
            # Сортируем операции по дате (от старых к новым) для группировки по дням
            operations = sorted(operations, key=lambda x: (x['date'], x['time']))
            
            current_date = None
            first_day_date = None  # Инициализируем переменную
            day_total = {}  # Для подсчета сумм по валютам за день
            day_expenses = []  # Список операций текущего дня
            all_days_data = []  # Список для хранения данных по всем дням
            
            for operation in operations:
                # Если дата изменилась, сохраняем данные предыдущего дня
                if operation['date'] != current_date:
                    if current_date is not None and day_expenses:
                        # Сохраняем данные предыдущего дня
                        all_days_data.append({
                            'date': current_date,
                            'expenses': day_expenses,
                            'totals': day_total,
                            'is_complete': True  # По умолчанию день полный
                        })
                    
                    # Начинаем новый день
                    current_date = operation['date']
                    if first_day_date is None:
                        first_day_date = current_date
                    day_total = {}
                    day_expenses = []
                
                # Форматируем время, описание и сумму
                time_str = operation['time'].strftime('%H:%M') if operation['time'] else '00:00'
                
                description = operation['description'] or "Без описания"
                if len(description) > 30:
                    description = description[:27] + "..."
                
                currency = operation['currency'] or 'RUB'
                amount = float(operation['amount'])
                
                # Добавляем к сумме дня
                if currency not in day_total:
                    day_total[currency] = {'expenses': 0, 'incomes': 0}
                
                if operation['type'] == 'income':
                    day_total[currency]['incomes'] += amount
                else:
                    day_total[currency]['expenses'] += amount
                
                # Добавляем операцию в список дня
                day_expenses.append({
                    'type': operation['type'],
                    'time': time_str,
                    'description': description,
                    'amount': amount,
                    'currency': currency
                })
            
            # Добавляем последний день
            if current_date is not None and day_expenses:
                all_days_data.append({
                    'date': current_date,
                    'expenses': day_expenses,
                    'totals': day_total,
                    'is_complete': True
                })
            
            # Проверяем, все ли операции показаны (максимум 30)
            if len(operations) == 30 and first_day_date:
                # Если показано ровно 30 записей, возможно есть еще
                # Проверяем первый день
                if all_days_data and all_days_data[0]['date'] == first_day_date:
                    # Проверяем есть ли еще операции за первый день
                    @sync_to_async
                    def check_first_day_completeness():
                        from expenses.models import Income
                        expense_count = Expense.objects.filter(
                            profile__telegram_id=user_id,
                            expense_date=first_day_date
                        ).count()
                        income_count = Income.objects.filter(
                            profile__telegram_id=user_id,
                            income_date=first_day_date
                        ).count()
                        return expense_count + income_count
                    
                    first_day_total = await check_first_day_completeness()
                    first_day_shown = len(all_days_data[0]['expenses'])
                    
                    if first_day_total > first_day_shown:
                        all_days_data[0]['is_complete'] = False
            
            # Формируем текст вывода
            for i, day_data in enumerate(all_days_data):
                # Форматируем дату
                if day_data['date'] == end_date:
                    date_str = "Сегодня"
                else:
                    months_ru = {
                        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
                        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
                        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
                    }
                    day = day_data['date'].day
                    month_name = months_ru.get(day_data['date'].month, day_data['date'].strftime('%B'))
                    date_str = f"{day} {month_name}"
                
                text += f"\n<b>📅 {date_str}</b>\n"
                
                # Если день неполный (в начале списка), показываем индикатор
                if not day_data['is_complete'] and i == 0:
                    text += "  ...\n  ...\n"
                
                # Выводим операции дня
                for expense in day_data['expenses']:
                    amount_str = f"{expense['amount']:,.0f}".replace(',', ' ')
                    if expense['currency'] == 'RUB':
                        amount_str += ' ₽'
                    elif expense['currency'] == 'USD':
                        amount_str += ' $'
                    elif expense['currency'] == 'EUR':
                        amount_str += ' €'
                    else:
                        amount_str += f" {expense['currency']}"
                    
                    # Добавляем "+" для доходов и делаем название жирным
                    if expense.get('type') == 'income':
                        text += f"  {expense['time']} — <b>{expense['description']}</b> <b>+{amount_str}</b>\n"
                    else:
                        text += f"  {expense['time']} — {expense['description']} {amount_str}\n"
                
                # Добавляем итог дня
                if day_data['totals']:
                    # Подсчитываем итоги
                    has_expenses = any(total.get('expenses', 0) > 0 for total in day_data['totals'].values())
                    has_incomes = any(total.get('incomes', 0) > 0 for total in day_data['totals'].values())
                    
                    if has_expenses:
                        text += "  💸 <b>Расходы:</b> "
                        expenses_list = []
                        for currency, total in day_data['totals'].items():
                            if total.get('expenses', 0) > 0:
                                exp_str = f"{total['expenses']:,.0f}".replace(',', ' ')
                                currency_symbol = {'RUB': '₽', 'USD': '$', 'EUR': '€'}.get(currency, currency)
                                expenses_list.append(f"{exp_str} {currency_symbol}")
                        text += ", ".join(expenses_list) + "\n"
                    
                    if has_incomes:
                        text += "  💰 <b>Доходы:</b> "
                        incomes_list = []
                        for currency, total in day_data['totals'].items():
                            if total.get('incomes', 0) > 0:
                                inc_str = f"{total['incomes']:,.0f}".replace(',', ' ')
                                currency_symbol = {'RUB': '₽', 'USD': '$', 'EUR': '€'}.get(currency, currency)
                                incomes_list.append(f"+{inc_str} {currency_symbol}")
                        text += ", ".join(incomes_list) + "\n"
        
        # Добавляем вопрос в конце
        text += "\n<i>💡 Показать траты в другие дни?</i>"
        
        # Добавляем кнопку "Назад"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back_button', lang), callback_data="expenses_today")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing expense diary: {e}")
        await callback.answer("Произошла ошибка при загрузке дневника", show_alert=True)



@router.callback_query(F.data == "back_to_summary")
async def callback_back_to_summary(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Вернуться к последнему отчету"""
    data = await state.get_data()
    start_date = data.get('report_start_date')
    end_date = data.get('report_end_date')
    
    if start_date and end_date:
        # Преобразуем строки обратно в date объекты
        from datetime import date as date_type
        if isinstance(start_date, str):
            start_date = date_type.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date_type.fromisoformat(end_date)
            
        await show_expenses_summary(
            callback.message,
            start_date,
            end_date,
            lang,
            state=state,
            edit=True,
            original_message=callback.message,
            callback=callback
        )
    else:
        # Если нет сохраненных дат, показываем отчет за текущий месяц
        today = date.today()
        start_date = today.replace(day=1)
        await show_expenses_summary(
            callback.message,
            start_date,
            today,
            lang,
            state=state,
            edit=True,
            original_message=callback.message,
            callback=callback
        )
    await callback.answer()


@router.callback_query(F.data.startswith("month_"))
async def callback_select_month(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора месяца для отчета"""
    month = int(callback.data.split('_')[1])
    year = date.today().year
    
    # Если выбранный месяц больше текущего, берем прошлый год
    if month > date.today().month:
        year -= 1
        
    # Определяем даты
    start_date = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = date(year, month, last_day)
    
    # Показываем сводку
    await show_expenses_summary(
        callback.message,
        start_date,
        end_date,
        lang,
        edit=True,
        original_message=callback.message
    )
    await callback.answer()