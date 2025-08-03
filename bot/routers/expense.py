"""
Обработчик расходов - главная функция бота
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import date
import asyncio

from ..services.expense import get_today_summary
from ..services.cashback import calculate_potential_cashback
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect

router = Router(name="expense")


class ExpenseForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()


@router.message(Command("expenses"))
async def cmd_expenses(message: types.Message, state: FSMContext):
    """Команда /expenses - показать траты за сегодня"""
    user_id = message.from_user.id
    today = date.today()
    
    # Получаем сводку за сегодня
    summary = await get_today_summary(user_id)
    
    if not summary or summary['total'] == 0:
        currency_symbol = '₽' if summary.get('currency', 'RUB') == 'RUB' else summary.get('currency', 'RUB')
        text = f"""📊 Сводка за сегодня, {today.strftime('%d %B')}

💰 Всего: 0 {currency_symbol}

Сегодня трат пока нет."""
    else:
        # Форматируем текст с учетом валют
        currency = summary.get('currency', 'RUB')
        currency_symbol = '₽' if currency == 'RUB' else currency
        
        text = f"""📊 Сводка за сегодня, {today.strftime('%d %B')}

💰 Всего: {summary['total']:,.0f} {currency_symbol}"""
        
        # Если есть расходы в других валютах, показываем их
        if not summary.get('single_currency', True):
            text += "\n\n💱 Другие валюты:"
            for curr, amount in summary.get('currency_totals', {}).items():
                if curr != currency and amount > 0:
                    curr_symbol = '₽' if curr == 'RUB' else curr
                    text += f"\n{amount:,.2f} {curr_symbol}"
        
        text += "\n\n📊 По категориям:"
        
        # Добавляем категории
        for cat in summary['categories']:
            if summary['total'] > 0:
                percent = (cat['amount'] / summary['total']) * 100
                text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} {currency_symbol} ({percent:.1f}%)"
            else:
                text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} {currency_symbol}"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, today, today)
        text += f"\n\n💳 Потенциальный кешбэк: {cashback:,.0f} ₽"
    
    # Кнопки навигации
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Показать с начала месяца", callback_data="expenses_month")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close")]
    ])
    
    await send_message_with_cleanup(message, state, text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "expenses_month")
async def show_month_expenses(callback: types.CallbackQuery):
    """Показать траты за текущий месяц"""
    user_id = callback.from_user.id
    today = date.today()
    start_date = today.replace(day=1)
    
    # Импортируем здесь чтобы избежать циклических импортов
    from ..services.expense import get_month_summary
    
    # Получаем сводку за месяц
    summary = await get_month_summary(user_id, today.month, today.year)
    
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    if not summary or summary['total'] == 0:
        text = f"""📊 Сводка за {month_names[today.month]} {today.year}

💰 Всего потрачено: 0 ₽

В этом месяце трат пока нет."""
    else:
        # Форматируем текст согласно ТЗ
        text = f"""📊 Сводка за {month_names[today.month]} {today.year}

💰 Всего потрачено: {summary['total']:,.0f} ₽

📊 По категориям:"""
        
        # Добавляем топ-5 категорий
        for i, cat in enumerate(summary['categories'][:5]):
            percent = (cat['amount'] / summary['total']) * 100
            text += f"\n{cat['icon']} {cat['name']}: {cat['amount']:,.0f} ₽ ({percent:.1f}%)"
        
        # Добавляем потенциальный кешбэк
        cashback = await calculate_potential_cashback(user_id, start_date, today)
        text += f"\n\n💳 Потенциальный кешбэк: {cashback:,.0f} ₽"
    
    # Кнопки навигации с PDF отчетом
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Сформировать PDF отчет", callback_data="generate_pdf")],
        [
            InlineKeyboardButton(text="◀️", callback_data="expenses_today"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# Обработчик текстовых сообщений
@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_expense(message: types.Message, state: FSMContext):
    """Обработка текстовых сообщений с расходами"""
    from ..utils.expense_parser import parse_expense_message
    from ..services.expense import add_expense
    from ..services.category import get_or_create_category
    
    user_id = message.from_user.id
    text = message.text
    
    # Парсим сообщение с AI поддержкой
    from expenses.models import Profile
    try:
        profile = await Profile.objects.select_related('user').aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    
    if not parsed:
        # Не удалось распознать расход
        await send_message_with_cleanup(message, state,
            "❌ Не удалось распознать расход.\n\n"
            "Попробуйте написать в формате:\n"
            "• Кофе 200\n"
            "• Такси домой 450 руб\n"
            "• Потратил на продукты 1500"
        )
        return
    
    # Проверяем/создаем категорию
    category = await get_or_create_category(user_id, parsed['category'])
    
    # Сохраняем в оригинальной валюте
    amount = parsed['amount']
    currency = parsed.get('currency', 'RUB')
    
    # Добавляем расход в оригинальной валюте
    expense = await add_expense(
        user_id=user_id,
        category_id=category.id,
        amount=amount,
        description=parsed['description'],
        currency=currency
    )
    
    # Формируем ответ
    confidence_text = ""
    if parsed.get('ai_enhanced') and parsed.get('confidence'):
        confidence_text = f"\n🤖 AI уверенность: {parsed['confidence']*100:.0f}%"
    
    # Форматируем сообщение с учетом валюты
    if currency == 'RUB':
        amount_text = f"{expense.amount:,.0f} ₽"
    else:
        amount_text = f"{expense.amount:,.2f} {currency}"
    
    await send_message_with_cleanup(message, state,
        f"✅ Расход добавлен!\n\n"
        f"💰 Сумма: {amount_text}\n"
        f"📁 Категория: {category.icon} {category.name}\n"
        f"📝 Описание: {expense.description}"
        f"{confidence_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Расходы", callback_data="expenses_today"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_expense_{expense.id}")
            ],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_expense_{expense.id}")]
        ])
    )


# Обработчик голосовых сообщений
@router.message(F.voice)
async def handle_voice_expense(message: types.Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    from bot.services.voice_processing import process_voice_expense
    from expenses.models import Profile
    
    # Получаем бота из контекста
    bot = message.bot
    
    # Определяем язык пользователя
    user_id = message.from_user.id
    user_language = 'ru'  # По умолчанию русский
    
    try:
        profile = await Profile.objects.select_related('user').aget(telegram_id=user_id)
        # Если в профиле есть настройка языка, используем её
        if hasattr(profile, 'language'):
            user_language = profile.language
    except Profile.DoesNotExist:
        pass
    
    # Распознаем голосовое сообщение
    text = await process_voice_expense(message, bot, user_language)
    
    if not text:
        return
    
    # Дальше обрабатываем как обычное текстовое сообщение
    # Получаем профиль пользователя
    try:
        profile = await Profile.objects.select_related('user').aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None
    
    # Парсим расход с AI поддержкой
    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    
    if not parsed:
        await send_message_with_cleanup(message, state,
            "❌ Не удалось распознать расход из голосового сообщения.\n\n"
            "Попробуйте сказать четче, например:\n"
            "• \"Кофе двести рублей\"\n"
            "• \"Такси домой четыреста пятьдесят\"\n"
            "• \"Потратил на продукты тысяча пятьсот\""
        )
        return
    
    # Проверяем/создаем категорию
    category = await get_or_create_category(user_id, parsed['category'])
    
    # Сохраняем в оригинальной валюте
    amount = parsed['amount']
    currency = parsed.get('currency', 'RUB')
    
    # Добавляем расход в оригинальной валюте
    expense = await add_expense(
        user_id=user_id,
        category_id=category.id,
        amount=amount,
        description=parsed['description'],
        currency=currency
    )
    
    # Формируем ответ
    confidence_text = ""
    if parsed.get('ai_enhanced') and parsed.get('confidence'):
        confidence_text = f"\n🤖 AI уверенность: {parsed['confidence']*100:.0f}%"
    
    # Форматируем сообщение с учетом валюты
    if currency == 'RUB':
        amount_text = f"{expense.amount:,.0f} ₽"
    else:
        amount_text = f"{expense.amount:,.2f} {currency}"
    
    await send_message_with_cleanup(message, state,
        f"✅ Расход из голосового сообщения добавлен!\n\n"
        f"💰 Сумма: {amount_text}\n"
        f"📁 Категория: {category.icon} {category.name}\n"
        f"📝 Описание: {expense.description}"
        f"{confidence_text}\n"
        f"🎤 Распознано: \"{text}\"",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Расходы", callback_data="expenses_today"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_expense_{expense.id}")
            ],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_expense_{expense.id}")]
        ])
    )


# Обработчик фото (чеков)
@router.message(F.photo)
async def handle_photo_expense(message: types.Message, state: FSMContext):
    """Обработка фото чеков"""
    await send_message_with_cleanup(message, state, "📸 Обработка чеков будет добавлена в следующей версии.")


# Обработчик редактирования расхода
@router.callback_query(lambda c: c.data.startswith("edit_expense_"))
async def edit_expense(callback: types.CallbackQuery):
    """Редактирование расхода"""
    expense_id = int(callback.data.split("_")[-1])
    # TODO: Реализовать редактирование
    await callback.answer("Редактирование будет добавлено в следующей версии", show_alert=True)


# Обработчик удаления расхода
@router.callback_query(lambda c: c.data.startswith("delete_expense_"))
async def delete_expense(callback: types.CallbackQuery):
    """Удаление расхода"""
    expense_id = int(callback.data.split("_")[-1])
    from ..services.expense import delete_expense as delete_expense_service
    
    user_id = callback.from_user.id
    
    # Удаляем расход
    success = await delete_expense_service(user_id, expense_id)
    
    if success:
        await callback.message.edit_text("✅ Расход удален!")
    else:
        await callback.answer("❌ Не удалось удалить расход", show_alert=True)