"""
Роутер для обработки inline queries (приглашения в семейный бюджет)
"""
from aiogram import Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from bot.services.profile import get_or_create_profile
from bot.services.household import HouseholdService
from asgiref.sync import sync_to_async
from bot.utils import get_text
from expenses.models import Household
import logging

logger = logging.getLogger(__name__)

router = Router(name='inline')


@sync_to_async
def get_profile_with_household(profile_id: int):
    """Загрузка профиля с household для async контекста"""
    from expenses.models import Profile
    return Profile.objects.select_related('household').get(id=profile_id)


@sync_to_async
def check_household_can_add_member(household_id: int) -> bool:
    """Проверка возможности добавления участника в async контексте"""
    try:
        household = Household.objects.get(id=household_id)
        return household.can_add_member()
    except Household.DoesNotExist:
        return False


@router.inline_query(F.query.startswith("household_invite"))
async def household_invite_inline(inline_query: InlineQuery):
    """
    Обработка inline запроса для отправки приглашения в семейный бюджет

    ВАЖНО: Проверяет все условия безопасности перед генерацией приглашения
    """
    user_id = inline_query.from_user.id

    try:
        # Получаем профиль пользователя
        profile = await get_or_create_profile(user_id)

        # Определяем язык пользователя
        lang = profile.language_code if profile and profile.language_code else 'ru'

        # Проверка 1: У пользователя должен быть household (используем household_id чтобы не делать запрос к БД)
        if not profile.household_id:
            await inline_query.answer(
                results=[],
                switch_pm_text=get_text('not_in_household', lang),
                switch_pm_parameter="household_budget",
                cache_time=1,
                is_personal=True
            )
            return

        # Загружаем профиль с household для дальнейших проверок
        profile = await get_profile_with_household(profile.id)
        household = profile.household

        # Проверка 2: Пользователь должен быть создателем
        if household.creator_id != profile.id:
            await inline_query.answer(
                results=[],
                switch_pm_text=get_text('only_creator_can_invite', lang),
                switch_pm_parameter="household_budget",
                cache_time=1,
                is_personal=True
            )
            return

        # Проверка 3: Должны быть свободные места
        can_add = await check_household_can_add_member(household.id)
        if not can_add:
            await inline_query.answer(
                results=[],
                switch_pm_text=get_text('household_full', lang),
                switch_pm_parameter="household_budget",
                cache_time=1,
                is_personal=True
            )
            return

        # Генерируем приглашение
        bot_info = await inline_query.bot.get_me()
        success, invite_link = await sync_to_async(HouseholdService.generate_invite_link)(profile, bot_info.username)

        if not success:
            logger.error(f"Failed to generate invite link for user {user_id}: {invite_link}")
            await inline_query.answer(
                results=[],
                switch_pm_text=get_text('error_generating_invite', lang),
                switch_pm_parameter="household_budget",
                cache_time=1,
                is_personal=True
            )
            return

        # Генерируем красивый текст приглашения (обернем в sync_to_async т.к. обращается к household)
        invite_text = await sync_to_async(HouseholdService.generate_invite_message_text)(profile, lang)

        # Создаем кнопку "Присоединиться"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text('join_household_button', lang),
                url=invite_link
            )]
        ])

        # Создаем результат inline query
        result = InlineQueryResultArticle(
            id="household_invite_1",
            title=get_text('inline_invite_title', lang),
            description=get_text('inline_invite_description', lang),
            input_message_content=InputTextMessageContent(
                message_text=invite_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard,
            thumb_url="https://img.icons8.com/color/96/000000/home.png"
        )

        await inline_query.answer(
            results=[result],
            cache_time=1,
            is_personal=True  # КРИТИЧНО: предотвращает кеширование приватных ссылок для других пользователей
        )

        logger.info(f"Inline invite generated for user {user_id}, household {household.id}")

    except Exception as e:
        logger.error(f"Error handling inline query: {e}", exc_info=True)

        # Попытка определить язык из языка Telegram
        lang = 'ru'
        if inline_query.from_user.language_code:
            lang = 'ru' if inline_query.from_user.language_code.startswith('ru') else 'en'

        await inline_query.answer(
            results=[],
            switch_pm_text=get_text('error_try_again', lang),
            switch_pm_parameter="household_budget",
            cache_time=1,
            is_personal=True
        )
