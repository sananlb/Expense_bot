"""
Обработчик кешбэков
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import date, datetime
from decimal import Decimal
from typing import List
import asyncio

from ..services.cashback import (
    get_user_cashbacks, add_cashback, update_cashback, 
    delete_cashback, get_cashback_by_id, format_cashback_note
)
from ..services.category import get_user_categories
from expenses.models import Cashback
from ..utils.message_utils import send_message_with_cleanup, delete_message_with_effect
from ..utils import get_text

router = Router(name="cashback")


async def restore_cashback_menu_if_needed(state: FSMContext, bot, chat_id: int):
    """Восстановить меню кешбека если оно было активно"""
    data = await state.get_data()
    if data.get('persistent_cashback_menu'):
        # Получаем сохраненный месяц
        month = data.get('cashback_menu_month')
        # Создаем фиктивное сообщение для вызова show_cashback_menu
        from aiogram.types import User, Chat
        fake_user = User(id=chat_id, is_bot=False, first_name="User")
        fake_chat = Chat(id=chat_id, type="private")
        fake_message = types.Message(
            message_id=0,
            date=datetime.now(),
            chat=fake_chat,
            from_user=fake_user,
            text=""
        )
        fake_message.bot = bot
        await show_cashback_menu(fake_message, state, month=month)


class CashbackForm(StatesGroup):
    """Состояния для добавления кешбэка"""
    waiting_for_category = State()
    waiting_for_bank = State()
    waiting_for_percent = State()  # Только процент вводится текстом
    
    # Состояния для редактирования
    choosing_cashback_to_edit = State()
    editing_bank = State()
    editing_percent = State()


@router.message(Command("cashback"))
async def cmd_cashback(message: types.Message, state: FSMContext, lang: str = 'ru'):
    """Команда /cashback - управление кешбэками"""
    await show_cashback_menu(message, state, lang)


async def show_cashback_menu(message: types.Message | types.CallbackQuery, state: FSMContext, lang: str = 'ru', month: int = None):
    """Показать меню кешбэков"""
    # Получаем user_id в зависимости от типа сообщения
    if isinstance(message, types.CallbackQuery):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
    current_date = date.today()
    target_month = month or current_date.month
    
    # Сохраняем информацию о том, что меню кешбека активно
    await state.update_data(
        persistent_cashback_menu=True,
        cashback_menu_month=target_month,
        cashback_menu_message_id=None  # Будет установлен после отправки
    )
    
    # Получаем кешбэки пользователя
    cashbacks = await get_user_cashbacks(user_id, target_month)
    
    # Получаем язык пользователя
    if state:
        state_data = await state.get_data()
        lang = state_data.get('lang', 'ru')
    else:
        lang = 'ru'
    
    # Названия месяцев
    month_names = {
        1: get_text('january', lang).capitalize(),
        2: get_text('february', lang).capitalize(),
        3: get_text('march', lang).capitalize(),
        4: get_text('april', lang).capitalize(),
        5: get_text('may', lang).capitalize(),
        6: get_text('june', lang).capitalize(),
        7: get_text('july', lang).capitalize(),
        8: get_text('august', lang).capitalize(),
        9: get_text('september', lang).capitalize(),
        10: get_text('october', lang).capitalize(),
        11: get_text('november', lang).capitalize(),
        12: get_text('december', lang).capitalize()
    }
    
    if not cashbacks:
        text = f"💳 {get_text('cashbacks', lang)} {month_names[target_month]}\n\n"
        text += f"{get_text('no_cashback_info', lang)}\n\n"
        text += get_text('add_cashback_hint', lang)
        
        # Если кешбеков нет, показываем только кнопки добавить и закрыть
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add")],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    else:
        text = format_cashback_note(cashbacks, target_month)
        
        # Если кешбеки есть, показываем все кнопки управления
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text('add_cashback', lang), callback_data="cashback_add"),
                InlineKeyboardButton(text="✏️ Редактировать", callback_data="cashback_edit")
            ],
            [
                InlineKeyboardButton(text=get_text('remove_cashback', lang), callback_data="cashback_remove"),
                InlineKeyboardButton(text=get_text('remove_all_cashback', lang), callback_data="cashback_remove_all")
            ],
            [InlineKeyboardButton(text=get_text('close', lang), callback_data="close_cashback_menu")]
        ])
    
    # Отправляем меню кешбека особым способом
    if isinstance(message, (types.Message, types.CallbackQuery)):
        bot = message.bot if hasattr(message, 'bot') else message.message.bot
        chat_id = message.chat.id if hasattr(message, 'chat') else message.message.chat.id
        
        # Удаляем старое меню кешбека если оно есть
        data = await state.get_data()
        old_cashback_menu_id = data.get('cashback_menu_message_id')
        if old_cashback_menu_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=old_cashback_menu_id)
            except:
                pass
        
        # Отправляем новое меню
        sent_message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Сохраняем ID меню кешбека в ОБА места для полной защиты
        await state.update_data(
            cashback_menu_message_id=sent_message.message_id,
            last_menu_message_id=sent_message.message_id,  # ВАЖНО: также сохраняем как last_menu для совместимости
            persistent_cashback_menu=True,
            cashback_menu_month=target_month
        )


@router.callback_query(lambda c: c.data == "cashback_menu")
async def callback_cashback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Показать меню кешбэков через callback"""
    # Проверяем подписку
    from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button
    
    has_subscription = await check_subscription(callback.from_user.id)
    if not has_subscription:
        await callback.message.edit_text(
            subscription_required_message() + "\n\n💳 Управление кешбэками доступно только с подпиской.",
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await show_cashback_menu(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "close_cashback_menu")
async def close_cashback_menu(callback: types.CallbackQuery, state: FSMContext):
    """Закрыть меню кешбека"""
    await callback.message.delete()
    # Очищаем флаг постоянного меню кешбека и оба ID
    await state.update_data(
        cashback_menu_message_id=None,
        last_menu_message_id=None,  # Также очищаем last_menu_message_id
        persistent_cashback_menu=False
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "cashback_add")
async def add_cashback_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало добавления кешбэка"""
    user_id = callback.from_user.id
    
    # Получаем язык из состояния
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    
    categories = await get_user_categories(user_id)
    
    if not categories:
        await callback.answer("Сначала создайте категории расходов", show_alert=True)
        return
    
    # Показываем список категорий
    keyboard_buttons = []
    
    # Добавляем опцию "Все категории"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="🌐 Все категории", 
            callback_data="cashback_cat_all"
        )
    ])
    
    # Группируем категории по 2 в строке
    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(
            text=f"{categories[i].icon} {categories[i].name}", 
            callback_data=f"cashback_cat_{categories[i].id}"
        )]
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(
                text=f"{categories[i + 1].icon} {categories[i + 1].name}", 
                callback_data=f"cashback_cat_{categories[i + 1].id}"
            ))
        keyboard_buttons.append(row)
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_menu")])
    
    text = f"{get_text('adding_cashback', lang)}\n\n{get_text('choose_category', lang)}"
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    except Exception:
        await send_message_with_cleanup(callback, state, 
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    await state.set_state(CashbackForm.waiting_for_category)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cashback_cat_"), CashbackForm.waiting_for_category)
async def process_cashback_category(callback: types.CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Обработка выбора категории"""
    if callback.data == "cashback_cat_all":
        # Если выбраны все категории, сохраняем None
        await state.update_data(category_id=None)
    else:
        category_id = int(callback.data.split("_")[-1])
        await state.update_data(category_id=category_id)
    
    # Показываем список банков для выбора
    banks = [
        "Т-Банк", "Альфа", "ВТБ", "Сбер", 
        "Райффайзен", "Яндекс", "Озон"
    ]
    
    keyboard_buttons = []
    for i in range(0, len(banks), 2):
        row = [InlineKeyboardButton(text=banks[i], callback_data=f"cashback_bank_{banks[i]}")]
        if i + 1 < len(banks):
            row.append(InlineKeyboardButton(text=banks[i + 1], callback_data=f"cashback_bank_{banks[i + 1]}"))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_add")])
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")])
    
    await callback.message.edit_text(
        "🏦 Выберите банк или введите название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(CashbackForm.waiting_for_bank)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cashback_bank_"), CashbackForm.waiting_for_bank)
async def process_cashback_bank(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора банка"""
    bank = callback.data.replace("cashback_bank_", "")
    
    await state.update_data(bank_name=bank)
    
    # Запрашиваем процент и описание
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_add")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    await callback.message.edit_text(
        f"💳 <b>Банк:</b> {bank}\n\n"
        "💰 Введите описание (необязательно) и процент кешбэка:\n\n"
        "<b>Примеры:</b>\n"
        "• 5\n"
        "• Все покупки 3.5\n"
        "• Только онлайн 10%\n"
        "• В супермаркетах 7",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(CashbackForm.waiting_for_percent)
    await callback.answer()


@router.message(CashbackForm.waiting_for_bank)
async def process_bank_text(message: types.Message, state: FSMContext):
    """Обработка ввода названия банка текстом"""
    bank_name = message.text.strip()
    
    if len(bank_name) > 100:
        await message.answer("❌ Название банка слишком длинное. Максимум 100 символов.")
        return
    
    await state.update_data(bank_name=bank_name)
    
    # Запрашиваем процент и описание
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_add")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    await message.answer(
        f"💳 <b>Банк:</b> {bank_name}\n\n"
        "💰 Введите описание (необязательно) и процент кешбэка:\n\n"
        "<b>Примеры:</b>\n"
        "• 5\n"
        "• Все покупки 3.5\n"
        "• Только онлайн 10%\n"
        "• В супермаркетах 7",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(CashbackForm.waiting_for_percent)


@router.message(CashbackForm.waiting_for_percent)
async def process_percent_text(message: types.Message, state: FSMContext):
    """Обработка ввода описания и процента кешбэка"""
    import re
    
    text = message.text.strip()
    
    # Паттерн для извлечения процента - ищем число в любом месте строки
    # Если только число - это процент без описания
    # Если есть текст и число - текст это описание, число это процент
    
    # Сначала проверяем, это только число (процент)?
    only_percent_pattern = r'^(\d+(?:[.,]\d+)?)\s*%?$'
    match = re.match(only_percent_pattern, text)
    
    if match:
        # Только процент, без описания
        percent_str = match.group(1).replace(',', '.')
        description = ''
    else:
        # Ищем число в конце строки (описание + процент)
        percent_at_end = r'^(.*?)\s+(\d+(?:[.,]\d+)?)\s*%?$'
        match = re.match(percent_at_end, text)
        
        if match:
            description = match.group(1).strip()
            percent_str = match.group(2).replace(',', '.')
        else:
            await message.answer(
                "❌ Некорректный формат.\n\n"
                "Введите описание и процент.\n"
                "Например: Все покупки 5"
            )
            return
    
    try:
        percent = float(percent_str)
    except ValueError:
        await message.answer("❌ Некорректный процент. Попробуйте еще раз.")
        return
    
    # Проверяем разумность процента
    if percent > 100:
        await message.answer("❌ Процент не может быть больше 100%")
        return
    
    if percent <= 0:
        await message.answer("❌ Процент должен быть больше 0")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = message.from_user.id
    current_month = date.today().month
    bank_name = data.get('bank_name', '')
    
    # Сразу сохраняем кешбэк с описанием
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data.get('category_id'),
            bank_name=bank_name,
            cashback_percent=percent,
            month=current_month,
            limit_amount=None,  # Без лимита
            description=description  # Используем введенное описание
        )
        
        await state.clear()
        
        # Сразу показываем меню кешбэков без подтверждения
        await show_cashback_menu(message, state)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {str(e)}")
        await state.clear()


# Обработчики редактирования кешбека

@router.callback_query(lambda c: c.data == "cashback_edit")
async def edit_cashback_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список кешбеков для редактирования"""
    user_id = callback.from_user.id
    current_month = date.today().month
    
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if not cashbacks:
        await callback.answer("У вас нет кешбэков для редактирования", show_alert=True)
        return
    
    keyboard_buttons = []
    for cb in cashbacks:
        if cb.category:
            text = f"{cb.category.name} - {cb.bank_name} {cb.cashback_percent}%"
        else:
            text = f"🌐 Все категории - {cb.bank_name} {cb.cashback_percent}%"
        
        # Добавляем описание, если есть
        if cb.description:
            text += f" ({cb.description})"
            
        keyboard_buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"edit_cb_{cb.id}")
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_menu")])
    
    await callback.message.edit_text(
        "✏️ Выберите кешбэк для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    
    await state.set_state(CashbackForm.choosing_cashback_to_edit)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_cb_"), CashbackForm.choosing_cashback_to_edit)
async def edit_cashback_selected(callback: types.CallbackQuery, state: FSMContext):
    """Кешбэк выбран для редактирования - показываем выбор банка"""
    cashback_id = int(callback.data.split("_")[-1])
    
    # Получаем информацию о кешбэке
    cashback = await get_cashback_by_id(callback.from_user.id, cashback_id)
    
    if not cashback:
        await callback.answer("Кешбэк не найден", show_alert=True)
        return
    
    # Сохраняем данные кешбэка в состоянии
    await state.update_data(
        editing_cashback_id=cashback_id,
        current_bank=cashback.bank_name,
        current_percent=cashback.cashback_percent,
        current_description=cashback.description or '',
        current_category_id=cashback.category_id
    )
    
    # Показываем список банков с кнопкой "Пропустить"
    banks = [
        "Т-Банк", "Альфа", "ВТБ", "Сбер", 
        "Райффайзен", "Яндекс", "Озон"
    ]
    
    keyboard_buttons = []
    for i in range(0, len(banks), 2):
        row = [InlineKeyboardButton(text=banks[i], callback_data=f"edit_bank_{banks[i]}")]
        if i + 1 < len(banks):
            row.append(InlineKeyboardButton(text=banks[i + 1], callback_data=f"edit_bank_{banks[i + 1]}"))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_edit_bank")])
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cashback_edit")])
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")])
    
    text = f"💳 <b>Редактирование кешбэка</b>\n\n"
    text += f"Текущий банк: {cashback.bank_name}\n\n"
    text += "Выберите новый банк или введите название:"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
        parse_mode="HTML"
    )
    
    await state.set_state(CashbackForm.editing_bank)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("edit_bank_"), CashbackForm.editing_bank)
async def process_edit_bank(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора нового банка"""
    bank = callback.data.replace("edit_bank_", "")
    
    await state.update_data(new_bank=bank)
    await show_edit_percent_prompt(callback, state)
    await callback.answer()


@router.callback_query(lambda c: c.data == "skip_edit_bank", CashbackForm.editing_bank)
async def skip_edit_bank(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить изменение банка"""
    data = await state.get_data()
    await state.update_data(new_bank=data['current_bank'])  # Оставляем текущий банк
    await show_edit_percent_prompt(callback, state)
    await callback.answer()


@router.message(CashbackForm.editing_bank)
async def process_edit_bank_text(message: types.Message, state: FSMContext):
    """Обработка ввода названия банка текстом при редактировании"""
    bank_name = message.text.strip()
    
    if len(bank_name) > 100:
        await message.answer("❌ Название банка слишком длинное. Максимум 100 символов.")
        return
    
    await state.update_data(new_bank=bank_name)
    await show_edit_percent_prompt(message, state)


async def show_edit_percent_prompt(message_or_callback, state: FSMContext):
    """Показать запрос на ввод описания и процента при редактировании"""
    data = await state.get_data()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"edit_cb_{data['editing_cashback_id']}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    text = f"💳 <b>Редактирование кешбэка</b>\n\n"
    text += f"Банк: {data.get('new_bank', data['current_bank'])}\n"
    text += f"Текущий процент: {data['current_percent']}%\n"
    if data['current_description']:
        text += f"Текущее описание: {data['current_description']}\n"
    text += "\n💰 Введите новое описание (необязательно) и процент:\n\n"
    text += "<b>Примеры:</b>\n"
    text += "• 5\n"
    text += "• Все покупки 3.5\n"
    text += "• Только онлайн 10%"
    
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.set_state(CashbackForm.editing_percent)


@router.message(CashbackForm.editing_percent)
async def process_edit_percent(message: types.Message, state: FSMContext):
    """Обработка ввода нового описания и процента"""
    import re
    
    text = message.text.strip()
    
    # Используем тот же парсинг, что и при добавлении
    only_percent_pattern = r'^(\d+(?:[.,]\d+)?)\s*%?$'
    match = re.match(only_percent_pattern, text)
    
    if match:
        # Только процент, без описания
        percent_str = match.group(1).replace(',', '.')
        description = ''
    else:
        # Ищем число в конце строки (описание + процент)
        percent_at_end = r'^(.*?)\s+(\d+(?:[.,]\d+)?)\s*%?$'
        match = re.match(percent_at_end, text)
        
        if match:
            description = match.group(1).strip()
            percent_str = match.group(2).replace(',', '.')
        else:
            await message.answer(
                "❌ Некорректный формат.\n\n"
                "Введите описание и процент.\n"
                "Например: Все покупки 5"
            )
            return
    
    try:
        percent = float(percent_str)
    except ValueError:
        await message.answer("❌ Некорректный процент. Попробуйте еще раз.")
        return
    
    # Проверяем разумность процента
    if percent > 100:
        await message.answer("❌ Процент не может быть больше 100%")
        return
    
    if percent <= 0:
        await message.answer("❌ Процент должен быть больше 0")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Обновляем кешбэк
    try:
        cashback = await update_cashback(
            user_id=user_id,
            cashback_id=data['editing_cashback_id'],
            bank_name=data.get('new_bank', data['current_bank']),
            cashback_percent=percent,
            description=description
        )
        
        await state.clear()
        
        # Сразу показываем меню кешбэков без подтверждения
        await show_cashback_menu(message, state)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {str(e)}")
        await state.clear()


# Удален старый обработчик waiting_for_bank_and_percent

# Старые функции больше не используются после упрощения процесса
# Закомментированы старые функции, которые больше не нужны после упрощения процесса добавления кешбека.
# Теперь банк и процент вводятся одним сообщением.

'''

async def ask_for_description(message: types.Message, state: FSMContext):
    # Запрос описания кешбэка
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    text = "📝 Введите описание кешбэка\n\n"
    text += "Например: только в Пятёрочке, только онлайн, кроме алкоголя\n\n"
    text += "Или нажмите 'Пропустить' если описание не требуется"
    
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def ask_for_percent(message: types.Message | types.CallbackQuery, state: FSMContext):
    """Запрос процента кешбэка"""
    # Кнопки с популярными процентами
    keyboard_buttons = []
    percents = ["1%", "2%", "3%", "5%", "7%", "10%", "15%"]
    
    # Две кнопки в ряд
    for i in range(0, len(percents), 2):
        row = []
        for j in range(2):
            if i + j < len(percents):
                row.append(InlineKeyboardButton(
                    text=percents[i + j], 
                    callback_data=f"cashback_percent_{percents[i + j].replace('%', '')}"
                ))
        keyboard_buttons.append(row)
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    text = "💰 Укажите процент кешбэка:\n\n" \
           "Выберите из списка или введите свой:"
    
    # Проверяем тип сообщения и используем соответствующий метод
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )
    else:
        # Для обычного сообщения используем send_message_with_cleanup
        from ..utils.message_utils import send_message_with_cleanup
        await send_message_with_cleanup(
            message, state, text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        )


@router.callback_query(lambda c: c.data.startswith("cashback_percent_"), CashbackForm.waiting_for_percent)
async def process_cashback_percent_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора процента кнопкой и сохранение кешбэка"""
    percent = callback.data.split("_")[-1]
    await state.update_data(cashback_percent=float(percent))
    
    # Сохраняем кешбэк без лимита и месяца (по умолчанию с текущего момента)
    data = await state.get_data()
    user_id = callback.from_user.id
    current_month = date.today().month
    
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=float(percent),
            month=current_month,
            limit_amount=None,  # Без лимита
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


async def ask_for_limit(message: types.Message, state: FSMContext):
    """Запрос лимита кешбэка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без лимита", callback_data="cashback_no_limit")],
        [InlineKeyboardButton(text="1000 ₽", callback_data="cashback_limit_1000")],
        [InlineKeyboardButton(text="2000 ₽", callback_data="cashback_limit_2000")],
        [InlineKeyboardButton(text="3000 ₽", callback_data="cashback_limit_3000")],
        [InlineKeyboardButton(text="5000 ₽", callback_data="cashback_limit_5000")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")]
    ])
    
    await message.edit_text(
        "💸 Есть ли лимит кешбэка в месяц?\n\n"
        "Выберите из списка или введите свою сумму:",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("cashback_limit_") or c.data == "cashback_no_limit", CashbackForm.waiting_for_limit)
async def process_cashback_limit_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора лимита кнопкой"""
    if callback.data == "cashback_no_limit":
        limit = None
    else:
        limit = float(callback.data.split("_")[-1])
    
    await state.update_data(limit_amount=limit)
    
    # Спрашиваем про месяц
    await ask_for_month(callback.message, state)
    await state.set_state(CashbackForm.waiting_for_month)
    await callback.answer()


async def ask_for_month(message: types.Message, state: FSMContext):
    """Запрос месяца для кешбэка"""
    current_month = date.today().month
    
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    keyboard_buttons = []
    # Показываем текущий и следующие 3 месяца
    for i in range(4):
        month = ((current_month - 1 + i) % 12) + 1
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=month_names[month], 
                callback_data=f"cashback_month_{month}"
            )
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await message.edit_text(
        "📅 На какой месяц действует кешбэк?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


@router.callback_query(lambda c: c.data.startswith("cashback_month_"), CashbackForm.waiting_for_month)
async def process_cashback_month(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора месяца и сохранение кешбэка"""
    month = int(callback.data.split("_")[-1])
    data = await state.get_data()
    
    user_id = callback.from_user.id
    
    # Сохраняем кешбэк
    try:
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=data['cashback_percent'],
            month=month,
            limit_amount=data.get('limit_amount'),
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
        await state.clear()


@router.callback_query(lambda c: c.data == "cashback_remove")
async def remove_cashback_list(callback: types.CallbackQuery, state: FSMContext):
    """Показать список кешбэков для удаления"""
    user_id = callback.from_user.id
    current_month = date.today().month
    
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if not cashbacks:
        await callback.answer("У вас нет кешбэков для удаления", show_alert=True)
        return
    
    keyboard_buttons = []
    for cb in cashbacks:
        if cb.category:
            text = f"{cb.category.name} - {cb.bank_name} {cb.cashback_percent}%"
        else:
            text = f"🌐 Все категории - {cb.bank_name} {cb.cashback_percent}%"
        keyboard_buttons.append([
            InlineKeyboardButton(text=text, callback_data=f"remove_cb_{cb.id}")
        ])
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "➖ Выберите кешбэк для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    # Обновляем ID сообщения в состоянии
    await state.update_data(last_menu_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("remove_cb_"))
async def confirm_remove_cashback(callback: types.CallbackQuery):
    """Подтверждение удаления кешбэка"""
    cashback_id = int(callback.data.split("_")[-1])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_remove_cb_{cashback_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот кешбэк?",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("confirm_remove_cb_"))
async def remove_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление кешбэка подтверждено"""
    cashback_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    
    success = await delete_cashback(user_id, cashback_id)
    
    if success:
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    else:
        await callback.answer("❌ Не удалось удалить кешбэк", show_alert=True)


@router.callback_query(lambda c: c.data == "cashback_other_month")
async def select_other_month(callback: types.CallbackQuery):
    """Выбор другого месяца для просмотра кешбэков"""
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    keyboard_buttons = []
    # Показываем все 12 месяцев
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            if i + j < 12:
                month = i + j + 1
                row.append(InlineKeyboardButton(
                    text=month_names[month][:3],  # Сокращенное название
                    callback_data=f"view_cb_month_{month}"
                ))
        keyboard_buttons.append(row)
    
    # Убрали кнопку "Назад" по требованию пользователя
    
    await callback.message.edit_text(
        "📅 Выберите месяц:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("view_cb_month_"))
async def view_cashback_month(callback: types.CallbackQuery, state: FSMContext):
    """Просмотр кешбэков за выбранный месяц"""
    month = int(callback.data.split("_")[-1])
    await show_cashback_menu(callback, state, month=month)
    await callback.answer()


@router.callback_query(lambda c: c.data == "cashback_remove_all")
async def confirm_remove_all_cashback(callback: types.CallbackQuery):
    """Подтверждение удаления всех кешбэков"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cashback_menu"),
            InlineKeyboardButton(text="✅ Да, удалить все", callback_data="confirm_remove_all")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить ВСЕ кешбэки?\n\n"
        "Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "confirm_remove_all")
async def remove_all_cashback_confirmed(callback: types.CallbackQuery, state: FSMContext):
    """Удаление всех кешбэков подтверждено"""
    user_id = callback.from_user.id
    current_month = date.today().month
    
    # Получаем все кешбэки пользователя
    cashbacks = await get_user_cashbacks(user_id, current_month)
    
    if cashbacks:
        # Удаляем все кешбэки
        deleted_count = 0
        for cashback in cashbacks:
            success = await delete_cashback(user_id, cashback.id)
            if success:
                deleted_count += 1
        
        # Сразу показываем меню кешбэков
        await show_cashback_menu(callback, state)
    else:
        await callback.answer("Нет кешбэков для удаления", show_alert=True)
    
    await callback.answer()


# Обработчики ввода текста для форм
# Старый обработчик для банка удален - теперь банк и процент вводятся вместе


@router.callback_query(lambda c: c.data == "skip_description", CashbackForm.waiting_for_description)
async def skip_description(callback: types.CallbackQuery, state: FSMContext):
    """Пропустить ввод описания"""
    await state.update_data(description='')
    await ask_for_percent(callback.message, state)
    await state.set_state(CashbackForm.waiting_for_percent)
    await callback.answer()


@router.message(CashbackForm.waiting_for_description)
async def process_description_text(message: types.Message, state: FSMContext):
    """Обработка ввода описания"""
    description = message.text.strip()
    
    if len(description) > 200:
        await send_message_with_cleanup(message, state, "❌ Описание слишком длинное. Максимум 200 символов.")
        return
    
    await state.update_data(description=description)
    await ask_for_percent(message, state)
    await state.set_state(CashbackForm.waiting_for_percent)


@router.message(CashbackForm.waiting_for_percent)
async def process_percent_text(message: types.Message, state: FSMContext):
    """Обработка ввода процента и сохранение кешбэка"""
    try:
        # Убираем символ % если есть
        percent_text = message.text.strip().replace('%', '').replace(',', '.')
        percent = float(percent_text)
        
        if percent <= 0 or percent > 100:
            await send_message_with_cleanup(message, state, "❌ Процент должен быть от 0 до 100")
            return
        
        # Сохраняем кешбэк без лимита и месяца
        data = await state.get_data()
        user_id = message.from_user.id
        current_month = date.today().month
        
        cashback = await add_cashback(
            user_id=user_id,
            category_id=data['category_id'],
            bank_name=data['bank_name'],
            cashback_percent=percent,
            month=current_month,
            limit_amount=None,
            description=data.get('description', '')
        )
        
        await state.clear()
        # Сразу показываем меню кешбэков
        await show_cashback_menu(message, state)
        
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Введите корректный процент (например: 5 или 5.5)")


@router.message(CashbackForm.waiting_for_limit)
async def process_limit_text(message: types.Message, state: FSMContext):
    """Обработка ввода лимита"""
    try:
        limit_text = message.text.strip().replace(' ', '').replace(',', '.')
        limit = float(limit_text)
        
        if limit <= 0:
            await send_message_with_cleanup(message, state, "❌ Лимит должен быть больше 0")
            return
        
        await state.update_data(limit_amount=limit)
        await ask_for_month(message, state)
        await state.set_state(CashbackForm.waiting_for_month)
        
    except ValueError:
        await send_message_with_cleanup(message, state, "❌ Введите корректную сумму (например: 1000 или 1000.50)")
'''  # Конец закомментированного кода