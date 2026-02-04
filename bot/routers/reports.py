"""
Router for expense reports and analytics
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime, date, timedelta
from calendar import monthrange
import logging
import asyncio
import time
import os
from django.core.cache import cache
from aiogram import Bot

from bot.keyboards import expenses_summary_keyboard
from bot.utils import get_text, format_amount, get_month_name, get_currency_symbol
from bot.utils.category_helpers import get_category_display_name
from bot.services.expense import get_expenses_summary, get_expenses_by_period, get_last_expenses
from bot.utils.message_utils import send_message_with_cleanup
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

router = Router(name="reports")


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
    from calendar import monthrange

    today = date.today()
    start_date = today.replace(day=1)

    # Получаем последний день текущего месяца
    _, last_day = monthrange(today.year, today.month)
    end_date = date(today.year, today.month, last_day)

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
    await callback.answer()


@router.callback_query(F.data == "toggle_view_scope_expenses")
async def toggle_view_scope_expenses(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Переключить режим (личный/семейный) из экрана расходов и обновить сводку"""
    try:
        from asgiref.sync import sync_to_async
        from expenses.models import Profile, UserSettings
        
        @sync_to_async
        def toggle(uid):
            profile = Profile.objects.get(telegram_id=uid)
            if not profile.household_id:
                return False
            settings = profile.settings if hasattr(profile, 'settings') else UserSettings.objects.create(profile=profile)
            current = getattr(settings, 'view_scope', 'personal')
            settings.view_scope = 'household' if current == 'personal' else 'personal'
            settings.save()
            return True
        
        ok = await toggle(callback.from_user.id)
        if not ok:
            await callback.answer('Нет семейного бюджета' if lang == 'ru' else 'No household', show_alert=True)
            return
        
        data = await state.get_data()
        from datetime import date as date_type, date
        start_date = data.get('report_start_date')
        end_date = data.get('report_end_date')
        if isinstance(start_date, str):
            start_date = date_type.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date_type.fromisoformat(end_date)
        if not start_date or not end_date:
            today = date.today()
            start_date = today
            end_date = today
        
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
        await callback.answer()
    except Exception as e:
        logger.error(f"Error toggling scope from expenses: {e}")
        await callback.answer(get_text('error_occurred', lang))




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
        
        # Определяем режим отображения (личный/семья)
        from bot.services.profile import get_or_create_profile, get_user_settings
        from asgiref.sync import sync_to_async
        
        # Создаем синхронную функцию для получения настроек
        def get_household_mode(uid):
            from expenses.models import Profile, UserSettings
            try:
                profile = Profile.objects.get(telegram_id=uid)
                settings = profile.settings if hasattr(profile, 'settings') else UserSettings.objects.create(profile=profile)

                # Если нет семьи, всегда личный режим
                if not profile.household:
                    return False

                # Проверяем, есть ли другие члены семьи
                has_other_members = Profile.objects.filter(
                    household=profile.household
                ).exclude(telegram_id=uid).exists()

                # Если нет других членов семьи, автоматически переключаем на личный режим
                if not has_other_members:
                    if settings.view_scope == 'household':
                        settings.view_scope = 'personal'
                        settings.save()
                    return False

                return getattr(settings, 'view_scope', 'personal') == 'household'
            except Profile.DoesNotExist:
                return False
        
        household_mode = await sync_to_async(get_household_mode)(user_id)

        # Определяем, есть ли у пользователя семья с другими активными членами (для показа переключателя)
        @sync_to_async
        def has_household(uid):
            from expenses.models import Profile
            try:
                profile = Profile.objects.filter(telegram_id=uid, household__isnull=False).first()
                if not profile or not profile.household:
                    return False
                # Проверяем, есть ли другие активные члены семьи (кроме текущего пользователя)
                return Profile.objects.filter(
                    household=profile.household
                ).exclude(telegram_id=uid).exists()
            except Exception:
                return False
        
        has_subscription = await check_subscription(user_id)

        if not has_subscription:
            household_mode = False

        user_has_household = await has_household(user_id) if has_subscription else False

        summary = await get_expenses_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            household_mode=household_mode
        )
        
        logger.info(f"Summary result: total={summary.get('total', 0)}, count={summary.get('count', 0)}, categories={len(summary.get('by_category', []))}")

        # Определяем период для правильного заголовка и клавиатуры
        today = date.today()
        is_today = start_date == end_date == today
        is_current_month = (start_date.day == 1 and
                           start_date.month == today.month and
                           start_date.year == today.year and
                           end_date >= today)

        if is_today:
            period = 'today'
        elif is_current_month or (start_date.day == 1 and end_date.month == start_date.month):
            period = 'month'
        else:
            period = 'custom'

        logger.info(f"Period determination: start_date={start_date}, end_date={end_date}, today={today}, is_today={is_today}, period={period}")

        # Формируем текст периода
        if start_date == end_date:
            if start_date == today:
                period_text = ""
            else:
                period_text = start_date.strftime('%d.%m.%Y')
        else:
            month_name = get_month_name(start_date.month, lang)
            if start_date.month == end_date.month and start_date.year == end_date.year:
                period_text = f"{month_name} {start_date.year}"
            else:
                period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"

        # Выбираем правильный ключ для заголовка в зависимости от периода
        if period == 'today':
            summary_key = 'summary'
        else:
            summary_key = 'summary_monthly'

        # Добавляем индикатор семейного бюджета
        if household_mode:
            # Получаем название домохозяйства через sync_to_async
            def get_household_name(uid):
                from expenses.models import Profile
                try:
                    profile = Profile.objects.get(telegram_id=uid)
                    if profile.household:
                        return profile.household.name or "Семейный бюджет"
                except Profile.DoesNotExist:
                    pass
                return "Семейный бюджет"

            household_name = await sync_to_async(get_household_name)(user_id)
            text = f"🏠 <b>{household_name}</b>\n"
            if period_text:
                text += f"📊 <b>{get_text(summary_key, lang)} {period_text}</b>\n\n"
            else:
                text += f"📊 <b>{get_text(summary_key, lang)}</b>\n\n"
        else:
            if period_text:
                text = f"📊 <b>{get_text(summary_key, lang)} {period_text}</b>\n\n"
            else:
                text = f"📊 <b>{get_text(summary_key, lang)}</b>\n\n"
        
        # Проверяем есть ли операции вообще
        has_expenses = summary['total'] > 0
        has_incomes = summary.get('income_total', 0) > 0

        if not has_expenses and not has_incomes:
            text += get_text('no_expenses_period', lang)
            # Даже если нет трат, продолжаем показывать интерфейс

        if has_expenses or has_incomes:
            # Показываем только те строки, где есть данные
            expense_amount = format_amount(summary['total'], summary['currency'], lang)
            income_amount = format_amount(summary.get('income_total', 0), summary['currency'], lang)
            balance = summary.get('balance', -summary['total'])  # Если нет доходов, баланс = -расходы
            
            # Показываем расходы если они есть
            if has_expenses:
                text += f"💸 {get_text('expenses_label', lang)}: {expense_amount}\n"

            # Показываем доходы если они есть
            if has_incomes:
                text += f"💰 {get_text('income_label', lang)}: {income_amount}\n"

            # Показываем баланс только если есть и доходы и расходы
            if has_expenses and has_incomes:
                # Форматируем баланс с + или - в зависимости от знака
                if balance >= 0:
                    balance_text = f"+{format_amount(balance, summary['currency'], lang)}"
                else:
                    balance_text = format_amount(balance, summary['currency'], lang)
                text += f"⚖️ {get_text('balance_label', lang)}: {balance_text}\n"
            
            text += "\n"
            
            # По категориям расходов (если есть)
            if summary['by_category'] and has_expenses:
                text += f"📊 <b>{get_text('expenses_by_category', lang)}:</b>\n"
                total_categories = len(summary['by_category'])
                
                # Логика отображения: если 22 или меньше - показываем все, если 23+ показываем 20 + остальные
                if total_categories <= 22:
                    # Показываем все категории
                    for cat in summary['by_category']:
                        # Название уже содержит эмодзи из get_category_display_name
                        category_display = cat.get('name', get_text('no_category', lang))

                        # Формируем строку с суммами по валютам
                        amounts = cat.get('amounts', {})
                        amounts_str = " / ".join([format_amount(amt, cur, lang) for cur, amt in amounts.items()])
                        text += f"  {category_display}: {amounts_str}\n"
                else:
                    # Показываем первые 20 категорий
                    for cat in summary['by_category'][:20]:
                        # Название уже содержит эмодзи из get_category_display_name
                        category_display = cat.get('name', get_text('no_category', lang))

                        # Формируем строку с суммами по валютам
                        amounts = cat.get('amounts', {})
                        amounts_str = " / ".join([format_amount(amt, cur, lang) for cur, amt in amounts.items()])
                        text += f"  {category_display}: {amounts_str}\n"

                    # Добавляем "остальные траты" - собираем суммы по валютам
                    remaining_count = total_categories - 20
                    from decimal import Decimal
                    remaining_by_currency = {}
                    for cat in summary['by_category'][20:]:
                        for cur, amt in cat.get('amounts', {}).items():
                            if cur not in remaining_by_currency:
                                remaining_by_currency[cur] = Decimal('0')
                            remaining_by_currency[cur] += amt

                    remaining_str = " / ".join([format_amount(amt, cur, lang) for cur, amt in remaining_by_currency.items()])
                    if lang == 'ru':
                        text += f"  📦 <i>Остальные траты ({remaining_count} {'категория' if remaining_count == 1 else 'категории' if remaining_count < 5 else 'категорий'}): {remaining_str}</i>\n"
                    else:
                        text += f"  📦 <i>Other expenses ({remaining_count} {'category' if remaining_count == 1 else 'categories'}): {remaining_str}</i>\n"
                
                text += "\n"
            
            # Потенциальный кешбэк между категориями расходов и доходов
            if summary['potential_cashback'] > 0:
                text += f"💳 {get_text('potential_cashback', lang)}: {format_amount(summary['potential_cashback'], summary['currency'], lang)}\n\n"
            
            # По категориям доходов (если есть)
            if summary.get('by_income_category') and has_incomes:
                text += f"💵 <b>{get_text('income_by_category', lang)}:</b>\n"
                income_categories = summary.get('by_income_category', [])
                total_income_categories = len(income_categories)
                
                # Логика отображения: если 22 или меньше - показываем все, если 23+ показываем 20 + остальные
                if total_income_categories <= 22:
                    # Показываем все категории доходов
                    for cat in income_categories:
                        # Имя уже переведено в expense.py через get_display_name()
                        category_display = cat['name']
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                else:
                    # Показываем первые 20 категорий доходов
                    for cat in income_categories[:20]:
                        # Имя уже переведено в expense.py через get_display_name()
                        category_display = cat['name']
                        text += f"  {category_display}: {format_amount(cat['total'], summary['currency'], lang)}\n"
                    
                    # Добавляем "остальные доходы"
                    remaining_count = total_income_categories - 20
                    remaining_sum = sum(cat['total'] for cat in income_categories[20:])
                    if lang == 'ru':
                        text += f"  💰 <i>Остальные доходы ({remaining_count} {'категория' if remaining_count == 1 else 'категории' if remaining_count < 5 else 'категорий'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"
                    else:
                        text += f"  💰 <i>Other income ({remaining_count} {'category' if remaining_count == 1 else 'categories'}): {format_amount(remaining_sum, summary['currency'], lang)}</i>\n"

                text += "\n"

        # Добавляем подсказку о показе отчета за другой период
        text += get_text('show_report_another_period', lang)

        # Определяем показывать ли кнопку PDF
        if period == 'today':
            show_pdf = False
        else:
            show_pdf = True

        show_pdf = show_pdf and has_subscription
        
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
                    current_year=start_date.year if start_date.day == 1 else None,
                    show_scope_toggle=user_has_household,
                    current_scope=('household' if household_mode else 'personal')
                )
            )
        else:
            await send_message_with_cleanup(
                message, state, text,
                reply_markup=expenses_summary_keyboard(
                    lang, period, show_pdf,
                    current_month=start_date.month if start_date.day == 1 else None,
                    current_year=start_date.year if start_date.day == 1 else None,
                    show_scope_toggle=user_has_household,
                    current_scope=('household' if household_mode else 'personal')
                )
            )
            
    except Exception as e:
        logger.error(f"Error showing expenses summary: {e}")
        error_text = get_text('error_occurred', lang)
        if edit and original_message:
            await original_message.edit_text(error_text)
        else:
            await message.answer(error_text)


@router.callback_query(F.data.in_(["show_diary", "toggle_view_scope_diary"]))
async def callback_show_diary(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать дневник трат (последние 3 дня, максимум 30 записей)"""
    try:
        from datetime import datetime, timedelta
        from expenses.models import Expense, Profile, UserSettings
        from asgiref.sync import sync_to_async
        import pytz

        user_id = callback.from_user.id

        # Если это переключение режима, сначала переключаем
        if callback.data == "toggle_view_scope_diary":
            from django.db import transaction

            @sync_to_async
            def toggle_scope_atomic():
                """Атомарное переключение view_scope с блокировкой"""
                with transaction.atomic():
                    # Блокируем профиль для предотвращения race condition
                    profile = Profile.objects.select_for_update().get(telegram_id=user_id)
                    if not profile.household_id:
                        return False

                    # Получаем или создаем настройки с блокировкой
                    settings, _ = UserSettings.objects.select_for_update().get_or_create(profile=profile)
                    current = getattr(settings, 'view_scope', 'personal')
                    settings.view_scope = 'household' if current == 'personal' else 'personal'
                    settings.save()
                    return True

            ok = await toggle_scope_atomic()
            if not ok:
                await callback.answer('Нет семейного бюджета' if lang == 'ru' else 'No household', show_alert=True)
                return

        # Получаем профиль пользователя с часовым поясом
        @sync_to_async
        def get_user_profile():
            try:
                return Profile.objects.get(telegram_id=user_id)
            except Profile.DoesNotExist:
                return None

        profile = await get_user_profile()
        default_currency = (profile.currency or 'RUB') if profile else 'RUB'
        user_tz = pytz.timezone(profile.timezone if profile else 'UTC')
        
        # Определяем "сегодня" с учетом часового пояса пользователя
        now_user_tz = datetime.now(user_tz)
        end_date = now_user_tz.date()
        # Убираем ограничение по дням - показываем все операции (лимитируется только количеством)
        start_date = None

        # Получаем все траты и доходы, но не более 30 операций в сумме
        @sync_to_async
        def get_recent_operations():
            from expenses.models import Income
            from bot.services.profile import get_user_settings as gus
            # Получаем глобальный режим (sync доступ к wrapped функции)
            settings = gus.__wrapped__(user_id)
            household_mode = bool(profile and profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'
            
            # Получаем расходы
            if household_mode:
                expenses_qs = Expense.objects.filter(
                    profile__household=profile.household,
                    expense_date__lte=end_date
                )
            else:
                expenses_qs = Expense.objects.filter(
                    profile__telegram_id=user_id,
                    expense_date__lte=end_date
                )
            expenses = list(expenses_qs.select_related('category').order_by('-expense_date', '-expense_time')[:30])
            
            # Получаем доходы
            if household_mode:
                incomes_qs = Income.objects.filter(
                    profile__household=profile.household,
                    income_date__lte=end_date
                )
            else:
                incomes_qs = Income.objects.filter(
                    profile__telegram_id=user_id,
                    income_date__lte=end_date
                )
            incomes = list(incomes_qs.select_related('category').order_by('-income_date', '-income_time')[:30])
            
            # Объединяем и сортируем по дате (от новых к старым)
            operations = []
            for exp in expenses:
                currency = exp.currency or exp.profile.currency or default_currency
                operations.append({
                    'type': 'expense',
                    'date': exp.expense_date,
                    'time': exp.expense_time or exp.created_at.time(),
                    'amount': exp.amount,
                    'currency': currency,
                    'category': get_category_display_name(exp.category, lang) if exp.category else get_text('no_category', lang),
                    'description': exp.description,
                    'object': exp
                })
            
            for inc in incomes:
                currency = inc.currency or inc.profile.currency or default_currency
                operations.append({
                    'type': 'income',
                    'date': inc.income_date,
                    'time': inc.income_time or inc.created_at.time(),
                    'amount': inc.amount,
                    'currency': currency,
                    'category': get_category_display_name(inc.category, lang) if inc.category else get_text('other_income', lang),
                    'description': inc.description,
                    'object': inc
                })
            
            # Сортируем все операции вместе и берем первые 30
            operations.sort(key=lambda x: (x['date'], x['time']), reverse=True)
            return operations[:30]
        
        operations = await get_recent_operations()

        # Получаем текущий режим для заголовка
        @sync_to_async
        def get_scope_for_title():
            from bot.services.profile import get_user_settings as gus
            settings = gus.__wrapped__(user_id)
            return getattr(settings, 'view_scope', 'personal')

        current_scope = await get_scope_for_title()
        household_mode = bool(profile and profile.household) and current_scope == 'household'

        # Формируем заголовок с указанием режима
        diary_title = get_text('diary', lang)
        if household_mode:
            title_suffix = " (семейный)" if lang == 'ru' else " (household)"
        else:
            title_suffix = ""

        if not operations:
            text = f"📋 <b>{diary_title}{title_suffix}</b>\n\n<i>{get_text('no_operations', lang)}</i>"
        else:
            text = f"📋 <b>{diary_title}{title_suffix}</b>\n\n"
            
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
                
                description = operation['description'] or get_text('no_description', lang)
                if len(description) > 30:
                    description = description[:27] + "..."
                
                currency = operation['currency'] or default_currency
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
                        from bot.services.profile import get_user_settings as gus
                        # Определяем режим просмотра (так же как в get_recent_operations)
                        settings = gus.__wrapped__(user_id)
                        household_mode = bool(profile and profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

                        # Используем соответствующий фильтр в зависимости от режима
                        if household_mode:
                            expense_count = Expense.objects.filter(
                                profile__household=profile.household,
                                expense_date=first_day_date
                            ).count()
                            income_count = Income.objects.filter(
                                profile__household=profile.household,
                                income_date=first_day_date
                            ).count()
                        else:
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
                    date_str = get_text('today', lang)
                else:
                    month_keys = {
                        1: 'month_january', 2: 'month_february', 3: 'month_march', 4: 'month_april',
                        5: 'month_may', 6: 'month_june', 7: 'month_july', 8: 'month_august',
                        9: 'month_september', 10: 'month_october', 11: 'month_november', 12: 'month_december'
                    }
                    day = day_data['date'].day
                    month_key = month_keys.get(day_data['date'].month, 'month_january')
                    month_name = get_text(month_key, lang)
                    if lang == 'en':
                        date_str = f"{month_name} {day}"
                    else:
                        date_str = f"{day} {month_name}"
                
                text += f"\n<b>📅 {date_str}</b>\n"
                
                # Если день неполный (в начале списка), показываем индикатор
                if not day_data['is_complete'] and i == 0:
                    text += "  ...\n  ...\n"
                
                # Выводим операции дня
                for expense in day_data['expenses']:
                    amount_str = f"{expense['amount']:,.0f}".replace(',', ' ')
                    currency_symbol = get_currency_symbol(expense['currency'])
                    amount_str += f' {currency_symbol}'
                    
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
                        text += f"  💸 <b>{get_text('expenses_label', lang)}:</b> "
                        expenses_list = []
                        for currency, total in day_data['totals'].items():
                            if total.get('expenses', 0) > 0:
                                exp_str = f"{total['expenses']:,.0f}".replace(',', ' ')
                                curr_symbol = get_currency_symbol(currency)
                                expenses_list.append(f"{exp_str} {curr_symbol}")
                        text += ", ".join(expenses_list) + "\n"
                    
                    if has_incomes:
                        text += f"  💰 <b>{get_text('income_label', lang)}:</b> "
                        incomes_list = []
                        for currency, total in day_data['totals'].items():
                            if total.get('incomes', 0) > 0:
                                inc_str = f"{total['incomes']:,.0f}".replace(',', ' ')
                                curr_symbol = get_currency_symbol(currency)
                                incomes_list.append(f"+{inc_str} {curr_symbol}")
                        text += ", ".join(incomes_list) + "\n"
        
        # Добавляем вопрос в конце
        text += f"\n<i>💡 {get_text('show_other_days', lang)}</i>"

        # Получаем текущий режим просмотра
        @sync_to_async
        def get_current_scope():
            from bot.services.profile import get_user_settings as gus
            settings = gus.__wrapped__(user_id)
            has_household = bool(profile and profile.household)
            current_scope = getattr(settings, 'view_scope', 'personal')
            return has_household, current_scope

        has_household, current_scope = await get_current_scope()

        # Проверяем подписку для семейного бюджета
        from bot.services.subscription import check_subscription
        has_subscription = await check_subscription(user_id)

        # Формируем клавиатуру
        keyboard_buttons = []

        # Кнопка переключения режима - только если есть семья И активная подписка
        if has_household and has_subscription:
            scope_btn_text = (
                get_text('household_budget_button', lang)
                if current_scope == 'household'
                else get_text('my_budget_button', lang)
            )
            keyboard_buttons.append([InlineKeyboardButton(text=scope_btn_text, callback_data="toggle_view_scope_diary")])

        # Кнопка ТОП 5
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('top5_button', lang), callback_data="top5_menu")])

        # Кнопки Назад и Закрыть
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('back_button', lang), callback_data="expenses_today")])
        keyboard_buttons.append([InlineKeyboardButton(text=get_text('close', lang), callback_data="close")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing expense diary: {e}")
        await callback.answer("Произошла ошибка при загрузке дневника", show_alert=True)


@router.callback_query(F.data == "export_month_csv")
async def callback_export_month_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Экспорт операций за месяц в CSV (Premium функция)"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async

        user_id = callback.from_user.id

        # Проверка Premium подписки
        if not await check_subscription(user_id):
            await callback.answer()
            await callback.message.answer(
                get_text('export_premium_required', lang),
                reply_markup=get_subscription_button(),
                parse_mode="HTML"
            )
            return

        # Показываем уведомление о генерации
        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # Получаем месяц и год из state (из отчета)
        data = await state.get_data()
        start_date_str = data.get('report_start_date')
        end_date_str = data.get('report_end_date')

        if not start_date_str or not end_date_str:
            await callback.message.answer(
                get_text('export_error', lang),
                parse_mode="HTML"
            )
            return

        # Конвертируем строки в date
        from datetime import date as date_type
        start_date = date_type.fromisoformat(start_date_str)
        end_date = date_type.fromisoformat(end_date_str)

        # Используем year и month из start_date
        year = start_date.year
        month = start_date.month

        # Получаем данные пользователя и операции
        @sync_to_async
        def get_user_data():
            profile = Profile.objects.get(telegram_id=user_id)

            # Определяем режим просмотра (личный или семейный)
            settings = get_user_settings.__wrapped__(user_id)
            household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

            # Формируем фильтр для операций
            if household_mode:
                expenses = list(
                    Expense.objects.filter(
                        profile__household=profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__household=profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )
            else:
                expenses = list(
                    Expense.objects.filter(
                        profile__telegram_id=user_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__telegram_id=user_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )

            return expenses, incomes, household_mode

        expenses, incomes, household_mode = await get_user_data()

        # Проверка на пустоту
        if not expenses and not incomes:
            await callback.message.answer(
                get_text('export_empty', lang),
                parse_mode="HTML"
            )
            return

        # Генерация CSV с timeout защитой
        @sync_to_async
        def generate_csv_file():
            return ExportService.generate_csv(expenses, incomes, year, month, lang, user_id, household_mode)

        try:
            csv_bytes = await asyncio.wait_for(
                generate_csv_file(),
                timeout=10.0  # 10 секунд максимум для CSV
            )
        except asyncio.TimeoutError:
            logger.error(f"CSV generation timeout for user {user_id}, {year}/{month}")
            await callback.message.answer(
                "❌ Превышено время ожидания при генерации отчета. Попробуйте позже." if lang == 'ru'
                else "❌ Report generation timeout. Please try again later.",
                parse_mode="HTML"
            )
            return

        # Формируем имя файла с названием месяца
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"coins_{month_name}_{year}.csv"
        document = BufferedInputFile(csv_bytes, filename=filename)

        # Формируем caption с рекламным текстом
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"✨ Сгенерировано в Coins ✨\n"
            f"✨ @showmecoinbot ✨"
        )

        # Отправляем файл
        await callback.message.answer_document(
            document,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "export_month_excel")
async def callback_export_month_excel(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Экспорт операций за месяц в XLSX с графиками (Premium функция)"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async

        user_id = callback.from_user.id

        # Проверка Premium подписки
        if not await check_subscription(user_id):
            await callback.answer()
            await callback.message.answer(
                get_text('export_premium_required', lang),
                reply_markup=get_subscription_button(),
                parse_mode="HTML"
            )
            return

        # Показываем уведомление о генерации
        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # Получаем месяц и год из state (из отчета)
        data = await state.get_data()
        start_date_str = data.get('report_start_date')
        end_date_str = data.get('report_end_date')

        if not start_date_str or not end_date_str:
            await callback.message.answer(
                get_text('export_error', lang),
                parse_mode="HTML"
            )
            return

        # Конвертируем строки в date
        from datetime import date as date_type
        start_date = date_type.fromisoformat(start_date_str)
        end_date = date_type.fromisoformat(end_date_str)

        # Используем year и month из start_date
        year = start_date.year
        month = start_date.month

        # Получаем данные пользователя и операции
        @sync_to_async
        def get_user_data():
            profile = Profile.objects.get(telegram_id=user_id)

            # Определяем режим просмотра (личный или семейный)
            settings = get_user_settings.__wrapped__(user_id)
            household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

            # Формируем фильтр для операций
            if household_mode:
                expenses = list(
                    Expense.objects.filter(
                        profile__household=profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__household=profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )
            else:
                expenses = list(
                    Expense.objects.filter(
                        profile__telegram_id=user_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__telegram_id=user_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )

            return expenses, incomes, household_mode

        expenses, incomes, household_mode = await get_user_data()

        # Проверка на пустоту
        if not expenses and not incomes:
            await callback.message.answer(
                get_text('export_empty', lang),
                parse_mode="HTML"
            )
            return

        # Генерация XLSX с timeout защитой
        @sync_to_async
        def generate_xlsx_file():
            return ExportService.generate_xlsx_with_charts(expenses, incomes, year, month, user_id, lang, household_mode)

        try:
            xlsx_buffer = await asyncio.wait_for(
                generate_xlsx_file(),
                timeout=30.0  # 30 секунд для XLSX (графики требуют больше времени)
            )
        except asyncio.TimeoutError:
            logger.error(f"XLSX generation timeout for user {user_id}, {year}/{month}")
            await callback.message.answer(
                "❌ Превышено время ожидания при генерации отчета. Попробуйте позже." if lang == 'ru'
                else "❌ Report generation timeout. Please try again later.",
                parse_mode="HTML"
            )
            return

        # Формируем имя файла с названием месяца
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"coins_{month_name}_{year}.xlsx"
        document = BufferedInputFile(xlsx_buffer.read(), filename=filename)

        # Формируем caption с рекламным текстом
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"✨ Сгенерировано в Coins ✨\n"
            f"✨ @showmecoinbot ✨"
        )

        # Отправляем файл
        await callback.message.answer_document(
            document,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error exporting XLSX: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("monthly_report_csv_"))
async def callback_monthly_report_csv(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация CSV отчета из ежемесячного уведомления"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async

        user_id = callback.from_user.id

        # Парсим callback_data (формат: monthly_report_csv_2025_10)
        parts = callback.data.split('_')
        year = int(parts[3])
        month = int(parts[4])

        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # Запрашиваем данные по year/month
        @sync_to_async
        def get_user_data():
            profile = Profile.objects.get(telegram_id=user_id)
            settings = get_user_settings.__wrapped__(user_id)
            household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

            if household_mode:
                expenses = list(
                    Expense.objects.filter(
                        profile__household=profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__household=profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )
            else:
                expenses = list(
                    Expense.objects.filter(
                        profile__telegram_id=user_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__telegram_id=user_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )

            return expenses, incomes, household_mode

        expenses, incomes, household_mode = await get_user_data()

        # Проверка на пустоту
        if not expenses and not incomes:
            await callback.message.answer(
                get_text('export_empty', lang),
                parse_mode="HTML"
            )
            return

        # Генерация CSV с timeout защитой
        @sync_to_async
        def generate_csv_file():
            return ExportService.generate_csv(expenses, incomes, year, month, lang, user_id, household_mode)

        try:
            csv_bytes = await asyncio.wait_for(
                generate_csv_file(),
                timeout=10.0  # 10 секунд максимум для CSV
            )
        except asyncio.TimeoutError:
            logger.error(f"CSV generation timeout for user {user_id}, {year}/{month}")
            await callback.message.answer(
                "❌ Превышено время ожидания при генерации отчета. Попробуйте позже." if lang == 'ru'
                else "❌ Report generation timeout. Please try again later.",
                parse_mode="HTML"
            )
            return

        # Формируем имя файла
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"coins_{month_name}_{year}.csv"
        document = BufferedInputFile(csv_bytes, filename=filename)

        # Добавляем рекламный текст в caption
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"✨ Сгенерировано в Coins ✨\n"
            f"✨ @showmecoinbot ✨"
        )

        # Отправляем файл
        await callback.message.answer_document(
            document,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating monthly CSV report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("monthly_report_xlsx_"))
async def callback_monthly_report_xlsx(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Генерация XLSX отчета из ежемесячного уведомления"""
    try:
        from expenses.models import Expense, Income, Profile
        from bot.services.export_service import ExportService
        from bot.services.profile import get_user_settings
        from asgiref.sync import sync_to_async

        user_id = callback.from_user.id

        # Парсим callback_data (формат: monthly_report_xlsx_2025_10)
        parts = callback.data.split('_')
        year = int(parts[3])
        month = int(parts[4])

        await callback.answer(get_text('export_generating', lang), show_alert=False)

        # Запрашиваем данные по year/month
        @sync_to_async
        def get_user_data():
            profile = Profile.objects.get(telegram_id=user_id)
            settings = get_user_settings.__wrapped__(user_id)
            household_mode = bool(profile.household) and getattr(settings, 'view_scope', 'personal') == 'household'

            if household_mode:
                expenses = list(
                    Expense.objects.filter(
                        profile__household=profile.household,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__household=profile.household,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )
            else:
                expenses = list(
                    Expense.objects.filter(
                        profile__telegram_id=user_id,
                        expense_date__year=year,
                        expense_date__month=month
                    ).select_related('category').order_by('-expense_date', '-expense_time')
                )
                incomes = list(
                    Income.objects.filter(
                        profile__telegram_id=user_id,
                        income_date__year=year,
                        income_date__month=month
                    ).select_related('category').order_by('-income_date', '-income_time')
                )

            return expenses, incomes, household_mode

        expenses, incomes, household_mode = await get_user_data()

        # Проверка на пустоту
        if not expenses and not incomes:
            await callback.message.answer(
                get_text('export_empty', lang),
                parse_mode="HTML"
            )
            return

        # Генерация XLSX с timeout защитой
        @sync_to_async
        def generate_xlsx_file():
            return ExportService.generate_xlsx_with_charts(expenses, incomes, year, month, user_id, lang, household_mode)

        try:
            xlsx_buffer = await asyncio.wait_for(
                generate_xlsx_file(),
                timeout=30.0  # 30 секунд для XLSX (графики требуют больше времени)
            )
        except asyncio.TimeoutError:
            logger.error(f"XLSX generation timeout for user {user_id}, {year}/{month}")
            await callback.message.answer(
                "❌ Превышено время ожидания при генерации отчета. Попробуйте позже." if lang == 'ru'
                else "❌ Report generation timeout. Please try again later.",
                parse_mode="HTML"
            )
            return

        # Формируем имя файла
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"coins_{month_name}_{year}.xlsx"
        document = BufferedInputFile(xlsx_buffer.read(), filename=filename)

        # Добавляем рекламный текст в caption
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"✨ Сгенерировано в Coins ✨\n"
            f"✨ @showmecoinbot ✨"
        )

        # Отправляем файл
        await callback.message.answer_document(
            document,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating monthly XLSX report: {e}", exc_info=True)
        await callback.message.answer(
            get_text('export_error', lang),
            parse_mode="HTML"
        )


async def _generate_and_send_pdf_from_monthly_notification(
    user_id: int,
    chat_id: int,
    year: int,
    month: int,
    lang: str,
    lock_key: str,
    progress_msg_id: int = None
):
    """
    Фоновая генерация и отправка PDF отчета из ежемесячного уведомления.
    Не блокирует handler, выполняется асинхронно.

    Args:
        user_id: ID пользователя
        chat_id: ID чата для отправки
        year: Год отчета
        month: Месяц отчета
        lang: Язык пользователя
        lock_key: Ключ lock в Redis для снятия после завершения
        progress_msg_id: ID сообщения "Генерирую отчет..." для удаления
    """
    start_time = time.time()
    bot = None

    try:
        # Логируем начало генерации
        logger.info(f"[PDF_START] user={user_id}, period={year}/{month}, source=reports.py")

        # Создаем экземпляр бота для фоновой отправки
        bot = Bot(token=os.getenv('BOT_TOKEN'))

        # Генерируем PDF
        from bot.services.pdf_report import PDFReportService
        pdf_service = PDFReportService()
        pdf_bytes = await pdf_service.generate_monthly_report(
            user_id=user_id,
            year=year,
            month=month,
            lang=lang
        )

        duration = time.time() - start_time

        if not pdf_bytes:
            # Нет данных для отчета
            logger.warning(f"[PDF_NO_DATA] user={user_id}, period={year}/{month}, duration={duration:.2f}s")
            # Редактируем progress message
            if progress_msg_id:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg_id,
                    text=get_text('no_data_for_report', lang),
                    parse_mode='HTML'
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=get_text('no_data_for_report', lang),
                    parse_mode='HTML'
                )
            return

        # Логируем успешную генерацию
        logger.info(
            f"[PDF_SUCCESS] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, size={len(pdf_bytes)}"
        )

        # Алерт если генерация заняла > 30 секунд
        if duration > 30:
            from bot.services.admin_notifier import send_admin_alert
            await send_admin_alert(
                f"⚠️ Slow PDF generation\n"
                f"User: {user_id}\n"
                f"Period: {year}/{month}\n"
                f"Duration: {duration:.2f}s\n"
                f"Size: {len(pdf_bytes)} bytes\n"
                f"Source: reports.py",
                disable_notification=True
            )

        # Формируем имя файла
        month_names_ru = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                         'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
        month_names_en = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December']
        month_name = month_names_ru[month - 1] if lang == 'ru' else month_names_en[month - 1]

        filename = f"Report_Coins_{month_name}_{year}.pdf"
        pdf_file = BufferedInputFile(pdf_bytes, filename=filename)

        # Caption
        caption = (
            f"{get_text('export_success', lang).format(month=f'{month_name} {year}')}\n\n"
            f"✨ Сгенерировано в Coins ✨\n"
            f"✨ @showmecoinbot ✨"
        )

        # Отправляем PDF
        await bot.send_document(
            chat_id=chat_id,
            document=pdf_file,
            caption=caption,
            parse_mode='HTML'
        )

        # Удаляем сообщение о прогрессе
        if progress_msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=progress_msg_id)
            except Exception as e:
                logger.debug(f"Could not delete progress message: {e}")

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(f"[PDF_TIMEOUT] user={user_id}, period={year}/{month}, duration={duration:.2f}s")

        # Уведомляем пользователя
        if bot:
            try:
                # Редактируем progress message
                if progress_msg_id:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress_msg_id,
                        text=get_text('export_error', lang),
                        parse_mode='HTML'
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=get_text('export_error', lang),
                        parse_mode='HTML'
                    )
            except Exception:
                pass

        # Критический алерт админу
        from bot.services.admin_notifier import send_admin_alert
        await send_admin_alert(
            f"🔴 PDF Timeout\n"
            f"User: {user_id}\n"
            f"Period: {year}/{month}\n"
            f"Duration: {duration:.2f}s\n"
            f"Source: reports.py"
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"[PDF_ERROR] user={user_id}, period={year}/{month}, "
            f"duration={duration:.2f}s, error={str(e)}"
        )

        # Уведомляем пользователя
        if bot:
            try:
                # Редактируем progress message
                if progress_msg_id:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress_msg_id,
                        text=get_text('export_error', lang),
                        parse_mode='HTML'
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=get_text('export_error', lang),
                        parse_mode='HTML'
                    )
            except Exception:
                pass

    finally:
        # Всегда снимаем lock
        cache.delete(lock_key)
        logger.info(f"Released PDF lock for user {user_id}, {year}/{month}")

        # Закрываем сессию бота
        if bot:
            await bot.session.close()


@router.callback_query(F.data.startswith("monthly_report_pdf_"))
async def callback_monthly_report_pdf(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """
    Генерация PDF отчета из ежемесячного уведомления.
    Handler завершается немедленно, PDF генерируется в фоне.
    """
    user_id = callback.from_user.id

    # Парсим callback_data (формат: monthly_report_pdf_2025_10)
    parts = callback.data.split('_')
    year = int(parts[3])
    month = int(parts[4])

    # Создаем ключ lock для предотвращения дубликатов
    lock_key = f"pdf_generation:{user_id}:{year}:{month}"

    # Проверяем существующий lock
    if cache.get(lock_key):
        await callback.answer(
            "⏳ PDF уже генерируется для этого периода. Пожалуйста, подождите..."
            if lang == 'ru' else
            "⏳ PDF is already being generated for this period. Please wait...",
            show_alert=True
        )
        return

    # Устанавливаем lock на 10 минут (с запасом)
    cache.set(lock_key, True, timeout=600)

    try:
        # КРИТИЧНО: Отвечаем на callback СРАЗУ!
        # (важно: callback_query можно ответить только один раз)
        await callback.answer()

        # ВАЖНО: НЕ трогаем оригинальное сообщение с инсайтом!
        # Отправляем НОВОЕ сообщение о генерации
        progress_msg = await callback.message.answer(
            "⏳ " + (
                "Generating report..."
                if lang == 'en' else
                "Генерирую отчет..."
            ) + "\n\n" + (
                "This may take up to a minute. I'll send the PDF when it's ready."
                if lang == 'en' else
                "Это может занять до минуты. Я пришлю PDF когда он будет готов."
            )
        )

        # Запускаем фоновую задачу (НЕ блокирует handler!)
        asyncio.create_task(
            _generate_and_send_pdf_from_monthly_notification(
                user_id=user_id,
                chat_id=callback.message.chat.id,
                year=year,
                month=month,
                lang=lang,
                lock_key=lock_key,
                progress_msg_id=progress_msg.message_id
            )
        )

        # Handler завершается НЕМЕДЛЕННО - другие запросы пользователя обрабатываются!

    except Exception as e:
        # Снимаем lock при ошибке
        cache.delete(lock_key)
        logger.error(f"Error creating PDF background task: {e}")
        raise


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
        state=state,
        edit=True,
        original_message=callback.message,
        callback=callback
    )
    await callback.answer()
