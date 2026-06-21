"""
Групповой роутер явного ввода трат/доходов в группе.

В группах/супергруппах бот реагирует ТОЛЬКО на bang-ввод или direct mention:
    «!кофе 200»        → трата в личный бюджет отправителя;
    «@НашБот кофе 200» → та же трата;
    «!зарплата +50000» → доход (маркеры +/плюс/п/plus/p распознаёт detect_income_intent).

Этот роутер подключается ПЕРВЫМ в create_dispatcher() (до start_router), и его хендлер
забирает групповые bang/mention-сообщения. Slash-сообщения дропает GroupChatGuardMiddleware,
поэтому личные command-роутеры в группе не срабатывают и не раскрывают личные меню/данные.

GROUP-SAFE путь: мы НЕ вызываем handle_text_expense напрямую, т.к. у неё вредные в группе
fallback'и (ожидание суммы через FSM waiting_for_amount_clarification и AI-чат
process_chat_message). Вместо этого делаем тонкий stateless путь: определить доход/расход
(detect_income_intent), распарсить (parse_expense_message / parse_income_message) и сохранить
через те же сервисы (add_expense_with_conversion / create_income_with_conversion). На
неполный/нераспознанный ввод — одна короткая локализованная подсказка и СТОП.
"""
import logging
from typing import Optional

from aiogram import Bot, F, Router, types
from aiogram.types import (
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.utils import get_text, get_user_language
from bot.utils.group_input import extract_leading_bot_mention_payload
from bot.utils.logging_safe import log_safe_id, summarize_text

logger = logging.getLogger(__name__)

router = Router(name="group")

GROUP_CHAT_TYPES = {"group", "supergroup"}

# Статусы участия бота, которые считаем «бот в группе» (для приветствия)
_BOT_PRESENT_STATUSES = {"member", "administrator"}


@router.message(F.chat.type.in_(GROUP_CHAT_TYPES) & F.text.startswith("@"))
@router.message(F.chat.type.in_(GROUP_CHAT_TYPES) & F.text.startswith("!"))
async def handle_group_explicit_entry(message: types.Message, lang: str = "ru") -> None:
    """Точка входа для явных групповых bang/mention-сообщений."""
    user = message.from_user
    if user is None:
        return
    user_id = user.id

    bot: Bot = message.bot
    try:
        # Bot.me() кэширует результат (сеть — только при первом вызове), безопасно на hot path.
        me = await bot.me()
        bot_username = me.username
    except Exception:  # noqa: BLE001 - получение username не критично для парсинга
        bot_username = None

    raw_text = message.text or ""
    if raw_text.startswith("@"):
        text = extract_leading_bot_mention_payload(raw_text, bot_username)
        if text is None:
            return
        # «@НашБот !кофе 200» и «@НашБот кофе 200» эквивалентны.
        if text.startswith("!"):
            text = text[1:].strip()
    elif raw_text.startswith("!"):
        text = raw_text[1:].strip()
    else:
        # Защита при прямом вызове: slash/обычный текст не поддерживается этим роутером.
        return

    if not text:
        # Пустой ввод вроде «!» или «@bot» — короткая подсказка.
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    # Профиль/политика проверяются PrivacyCheckMiddleware (group-aware deeplink) ДО хендлера,
    # поэтому здесь профиль уже принял политику. Тем не менее парсинг/сохранение делаем
    # защищённо.
    from bot.utils.expense_parser import detect_income_intent

    if detect_income_intent(text):
        await _handle_group_income(message, user_id, text, lang)
    else:
        await _handle_group_expense(message, user_id, text, lang)


async def _handle_group_expense(
    message: types.Message, user_id: int, text: str, lang: str
) -> None:
    """Group-safe сохранение траты в личный бюджет отправителя (stateless)."""
    from bot.services.category import get_or_create_category
    from bot.services.expense import add_expense_with_conversion
    from bot.utils.expense_parser import parse_expense_message
    from bot.utils.expense_messages import format_expense_added_message
    from expenses.models import Profile

    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        profile = None

    parsed = await parse_expense_message(text, user_id=user_id, profile=profile, use_ai=True)
    if not parsed or not parsed.get("amount"):
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    category = await get_or_create_category(user_id, parsed["category"])

    currency = parsed.get("currency")
    if not currency:
        currency = (profile.currency if profile else None) or "RUB"

    try:
        expense = await add_expense_with_conversion(
            user_id=user_id,
            category_id=category.id,
            amount=parsed["amount"],
            description=parsed["description"],
            input_currency=currency,
            expense_date=parsed.get("expense_date"),
            ai_categorized=parsed.get("ai_enhanced", False),
            ai_confidence=parsed.get("confidence"),
        )
    except ValueError as e:
        await message.reply(f"❌ {str(e)}", parse_mode="HTML")
        return

    if expense is None:
        logger.error(
            "[Group] Failed to create expense for %s: add_expense returned None",
            log_safe_id(user_id, "user"),
        )
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    message_text = await format_expense_added_message(
        expense=expense,
        category=category,
        cashback_text="",
        confidence_text="",
        reused_from_last=parsed.get("reused_from_last", False),
        lang=lang,
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=get_text("edit_button", lang),
            callback_data=f"edit_expense_{expense.id}",
        )
    ]])
    await message.reply(message_text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(
        "[Group] Expense %s created for %s: %s",
        expense.id,
        log_safe_id(user_id, "user"),
        summarize_text(text),
    )


async def _handle_group_income(
    message: types.Message, user_id: int, text: str, lang: str
) -> None:
    """Group-safe сохранение дохода. Доход — премиум: то же правило подписки, что и в личке."""
    from django.db import DatabaseError
    from django.db.models import Q

    from bot.services.income import create_income_with_conversion
    from bot.services.subscription import check_subscription
    from bot.utils.expense_parser import parse_income_message
    from bot.utils.expense_messages import format_income_added_message
    from bot.utils.income_category_definitions import (
        get_income_category_display_name as get_income_category_display_for_key,
        normalize_income_category_key,
        strip_leading_emoji,
    )
    from expenses.models import IncomeCategory, Profile

    has_subscription = await check_subscription(user_id)
    if not has_subscription:
        # В группе не спамим карточкой подписки с кнопками — короткая подсказка про премиум
        # с deeplink в личку (отдельный текст, чтобы не путать принявшего политику юзера).
        await message.reply(
            get_text("group_income_premium", lang).format(
                bot_username=(await _safe_bot_username(message.bot)) or ""
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    try:
        profile = await Profile.objects.aget(telegram_id=user_id)
    except Profile.DoesNotExist:
        # Не создаём профиль молча в группе: PrivacyCheck уже должен был отсечь незарегистрированных.
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    default_currency = profile.currency or "RUB"

    parsed_income = await parse_income_message(
        text, user_id=user_id, profile=profile, use_ai=True
    )
    if not parsed_income or not parsed_income.get("amount"):
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    # Подбор категории дохода (логика как в handle_text_expense).
    category = None
    category_key = parsed_income.get("category_key") or normalize_income_category_key(
        parsed_income.get("category")
    )
    candidate_names = set()
    if parsed_income.get("category"):
        candidate_names.add(parsed_income["category"])
        candidate_names.add(strip_leading_emoji(parsed_income["category"]))
    if category_key:
        for lang_code_candidate in ("ru", "en"):
            display_name = get_income_category_display_for_key(category_key, lang_code_candidate)
            candidate_names.add(display_name)
            candidate_names.add(strip_leading_emoji(display_name))
    candidate_names = {name for name in candidate_names if name}

    if candidate_names:
        query = Q()
        for name in candidate_names:
            query |= Q(name__iexact=name) | Q(name_ru__iexact=name) | Q(name_en__iexact=name)
        try:
            category = await IncomeCategory.objects.filter(
                profile=profile, is_active=True
            ).filter(query).afirst()
        except (DatabaseError, AttributeError) as e:
            logger.debug("[Group] Error matching income category: %s", e)
            category = None

    if not category:
        try:
            default_names = [
                get_income_category_display_for_key("other", "ru"),
                get_income_category_display_for_key("other", "en"),
                "💰 Прочие доходы",
            ]
            category = await IncomeCategory.objects.filter(
                profile=profile, is_active=True
            ).filter(name__in=default_names).afirst()
        except (DatabaseError, AttributeError) as e:
            logger.debug("[Group] Error finding default income category: %s", e)
            category = None

    try:
        income = await create_income_with_conversion(
            user_id=user_id,
            amount=parsed_income["amount"],
            category_id=category.id if category else None,
            description=parsed_income.get("description", get_text("income", lang)),
            income_date=parsed_income.get("income_date"),
            ai_categorized=parsed_income.get("ai_enhanced", False),
            ai_confidence=parsed_income.get("confidence", 0.5),
            input_currency=parsed_income.get("currency", default_currency),
        )
    except ValueError as e:
        await message.reply(f"❌ {str(e)}", parse_mode="HTML")
        return

    if income is None:
        logger.error(
            "[Group] Failed to create income for %s: create_income returned None",
            log_safe_id(user_id, "user"),
        )
        await message.reply(get_text("group_format_hint", lang), parse_mode="HTML")
        return

    text_msg = await format_income_added_message(
        income=income,
        category=category,
        similar_income=parsed_income.get("similar_income", False),
        lang=lang,
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=get_text("edit_button", lang),
            callback_data=f"edit_income_{income.id}",
        )
    ]])
    await message.reply(text_msg, reply_markup=keyboard, parse_mode="HTML")
    logger.info(
        "[Group] Income %s created for %s: %s",
        income.id,
        log_safe_id(user_id, "user"),
        summarize_text(text),
    )


def _lang_from_telegram_code(language_code: Optional[str]) -> str:
    """Маппит Telegram language_code в поддерживаемый язык: 'ru' если начинается с 'ru', иначе 'en'."""
    if language_code and language_code.lower().startswith("ru"):
        return "ru"
    return "en"


async def _safe_bot_username(bot: Bot) -> Optional[str]:
    try:
        me = await bot.get_me()
        return me.username
    except Exception:  # noqa: BLE001
        return None


@router.my_chat_member(F.chat.type.in_(GROUP_CHAT_TYPES))
async def on_added_to_group(event: ChatMemberUpdated) -> None:
    """Приветствие-инструкция при добавлении бота в группу (одно короткое сообщение)."""
    old_status = event.old_chat_member.status if event.old_chat_member else None
    new_status = event.new_chat_member.status if event.new_chat_member else None

    # Реагируем только на переход «не в группе» → «в группе».
    if new_status not in _BOT_PRESENT_STATUSES:
        return
    if old_status in _BOT_PRESENT_STATUSES:
        # Уже был участником (например, повышение до админа) — не приветствуем повторно.
        return

    # Язык приветствия — по тому, кто добавил бота (его профиль/Telegram-язык).
    # get_user_language() для пользователя без профиля молча возвращает 'ru' (не бросает),
    # поэтому сперва проверяем наличие профиля: нет профиля → берём язык из Telegram-кода
    # actor'а; есть профиль → его сохранённый язык.
    actor = event.from_user
    lang = "ru"
    if actor is not None:
        from expenses.models import Profile

        has_profile = await Profile.objects.filter(telegram_id=actor.id).aexists()
        if has_profile:
            try:
                lang = await get_user_language(actor.id)
            except Exception:  # noqa: BLE001
                lang = _lang_from_telegram_code(actor.language_code)
        else:
            lang = _lang_from_telegram_code(actor.language_code)

    try:
        bot_username = (await _safe_bot_username(event.bot)) or "bot"
        await event.bot.send_message(
            chat_id=event.chat.id,
            text=get_text("group_welcome", lang).format(bot_username=bot_username),
            parse_mode="HTML",
        )
    except Exception as e:  # noqa: BLE001 - не падаем, если нет прав писать
        logger.warning(
            "[Group] Failed to send welcome to chat %s: %s",
            log_safe_id(event.chat.id, "chat"),
            e,
        )
