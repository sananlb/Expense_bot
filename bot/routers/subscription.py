"""
Роутер для управления подписками через Telegram Stars
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramNotFound
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import logging

from expenses.models import Profile, Subscription, PromoCode, PromoCodeUsage
from bot.constants import get_offer_url_for
from django.core.exceptions import ObjectDoesNotExist
from bot.utils.message_utils import send_message_with_cleanup
from bot.utils import get_text
from bot.services.affiliate import reward_referrer_subscription_extension

logger = logging.getLogger(__name__)

router = Router(name='subscription')


class PromoCodeStates(StatesGroup):
    """Состояния для промокода"""
    waiting_for_promo = State()


# Цены подписок в Telegram Stars
SUBSCRIPTION_PRICES = {
    'month': {
        'stars': 150,
        'months': 1,
        'title': '💎 Premium на 1 месяц',
        'description': '''🎯 Естественные вопросы к статистике
🎤 Голосовой ввод трат
💵 Учёт доходов
📊 PDF отчёты и графики
🏷️ Редактирование категорий
💳 Отслеживание кэшбэка
🏠 Семейный доступ''',
        'emoji_title': '💎 Premium • 1 месяц',
        'features': [
            '🎯 Естественные вопросы к статистике',
            '🎤 Голосовой ввод трат',
            '💵 Учёт доходов',
            '📊 PDF отчёты и графики',
            '🏷️ Редактирование категорий',
            '💳 Отслеживание кэшбэка',
            '🏠 Семейный доступ'
        ]
    },
    'six_months': {
        'stars': 600,
        'months': 6,
        'title': '💎 Premium на 6 месяцев',
        'description': '''✨ Все функции Premium + Экономия 300 звёзд!
🎯 AI-аналитика
🎤 Голосовой ввод
💵 Учёт доходов
📊 PDF отчёты
🏷️ Редактирование категорий
💳 Отслеживание кэшбэка
🏠 Семейный доступ
🚀 Приоритетная поддержка''',
        'emoji_title': '💎 Premium • 6 месяцев',
        'features': [
            '🎯 Все функции Premium',
            '💰 Экономия 300 звёзд',
            '🚀 Приоритетная поддержка',
            '🎁 Ранний доступ к новинкам',
            '💵 Учёт доходов',
            '🏷️ Редактирование категорий',
            '💳 Отслеживание кэшбэка',
            '🏠 Семейный доступ'
        ]
    }
}


def get_subscription_keyboard(is_beta_tester: bool = False, lang: str = 'ru'):
    """Клавиатура выбора подписки"""
    builder = InlineKeyboardBuilder()
    
    # Для бета-тестеров показываем только кнопку закрыть
    if not is_beta_tester:
        builder.button(
            text=get_text('month_stars', lang),
            callback_data="subscription_buy_month"
        )
        builder.button(
            text=get_text('six_months_stars', lang),
            callback_data="subscription_buy_six_months"
        )
        builder.button(
            text=get_text('have_promocode', lang),
            callback_data="subscription_promo"
        )
        # Добавляем кнопку для шаринга бота
        builder.button(
            text="🔗 Поделиться ботом" if lang == 'ru' else "🔗 Share the bot",
            callback_data="menu_referral"
        )
    
    builder.button(
        text=get_text('close', lang),
        callback_data="close"
    )
    
    builder.adjust(1)
    return builder.as_markup()


async def get_subscription_info_text(profile: Profile, lang: str = 'ru') -> str:
    """Получить текст с информацией о подписке"""
    
    # Проверяем, является ли пользователь бета-тестером
    if profile.is_beta_tester:
        return (
            f"{get_text('beta_tester_status', lang)}\n\n"
            f"{get_text('beta_access_text', lang)}"
        )
    
    # Проверяем активную подписку
    active_subscription = await profile.subscriptions.filter(
        is_active=True,
        end_date__gt=timezone.now()
    ).order_by('-end_date').afirst()
    
    if active_subscription:
        # Вычисляем оставшиеся дни (только полные дни)
        days_left = (active_subscription.end_date - timezone.now()).days
        subscription_type = active_subscription.get_type_display()
        
        # Добавляем информацию о пробном периоде
        if active_subscription.type == 'trial':
            emoji = "🎁"
            subscription_type = get_text('trial_period', lang) if lang == 'ru' else "Trial period"
        else:
            emoji = "✅"
            # Переводим тип подписки в зависимости от языка
            if lang == 'en':
                type_translations = {
                    'month': 'Monthly subscription',
                    'six_months': 'Six-month subscription'
                }
                subscription_type = type_translations.get(active_subscription.type, active_subscription.get_type_display())
            else:
                subscription_type = active_subscription.get_type_display()
            
        return (
            f"{emoji} <b>{get_text('active_subscription_text', lang)}</b>\n\n"
            f"{get_text('valid_until', lang)}: {active_subscription.end_date.strftime('%d.%m.%Y')}\n"
            f"{get_text('days_left', lang)}: {days_left}\n\n"
            f"{get_text('can_extend_early', lang)}"
        )
    else:
        return (
            f"<b>{get_text('no_active_subscription', lang)}</b>\n\n"
            f"{get_text('subscription_benefits', lang)}"
        )


@router.callback_query(F.data == "menu_subscription")
async def show_subscription_menu(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    """Показать меню подписки"""
    # Получаем сохраненные ID сообщений
    data = await state.get_data()
    invoice_msg_id = data.get('invoice_msg_id')

    # Удаляем сообщение с инвойсом, если оно есть
    if invoice_msg_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.from_user.id,
                message_id=invoice_msg_id
            )
        except (TelegramBadRequest, TelegramNotFound):
            pass  # Сообщение уже удалено или не найдено

    # Очищаем сохраненный ID
    await state.update_data(invoice_msg_id=None)

    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)

    text = await get_subscription_info_text(profile, lang)

    # Отправляем новое сообщение с меню подписки
    await send_message_with_cleanup(
        callback.message,
        state,
        text,
        reply_markup=get_subscription_keyboard(is_beta_tester=profile.is_beta_tester, lang=lang),
        parse_mode="HTML"
    )

    await callback.answer()


async def send_stars_invoice(callback: CallbackQuery, state: FSMContext, sub_type: str):
    """Создать и отправить инвойс в Telegram Stars для указанного типа подписки"""
    sub_info = SUBSCRIPTION_PRICES[sub_type]

    # Определяем язык пользователя
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        lang = profile.language_code or 'ru'
    except Exception:
        lang = 'ru'

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass

    # Отправляем инвойс с оригинальным описанием
    if lang.startswith('en'):
        title = '💎 Premium for 1 month' if sub_type == 'month' else '💎 Premium for 6 months'
        description = (
            "🎯 Natural questions to statistics\n"
            "🎤 Voice expense input\n"
            "💵 Income tracking\n"
            "📊 PDF reports and analytics\n"
            "🏷️ Category customization\n"
            "💳 Cashback tracking\n"
            "🏠 Family access"
            if sub_type == 'month' else
            "✨ All Premium features + Save 300 stars!\n"
            "🎯 AI analytics\n"
            "🎤 Voice input\n"
            "💵 Income tracking\n"
            "📊 PDF reports\n"
            "🏷️ Category customization\n"
            "💳 Cashback tracking\n"
            "🏠 Family access\n"
            "🚀 Priority support"
        )
        price_label = "Pay"
    else:
        title = sub_info['title']
        description = sub_info['description']
        price_label = "Оплата"

    invoice_msg = await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=title,
        description=description,
        payload=f"subscription_{sub_type}_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=price_label, amount=sub_info['stars'])],
        start_parameter=f"sub_{sub_type}",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

    # Сохраняем ID сообщения с инвойсом для удаления
    await state.update_data(invoice_msg_id=invoice_msg.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("subscription_buy_"))
async def process_subscription_purchase(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки подписки"""
    # Извлекаем тип подписки из callback_data
    # subscription_buy_month -> month
    # subscription_buy_six_months -> six_months
    callback_parts = callback.data.split("subscription_buy_")[1]
    
    if callback_parts == "month":
        sub_type = "month"
    elif callback_parts == "six_months":
        sub_type = "six_months"
    else:
        await callback.answer("Неверный тип подписки", show_alert=True)
        return
    
    # Проверяем принятие оферты
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        lang = profile.language_code or 'ru'
    except Exception:
        lang = 'ru'

    if not profile.accepted_offer:
        short = get_text('short_offer_for_acceptance', lang)
        offer_url = get_offer_url_for(lang)
        text = (
            f"<b>📄 Публичная оферта</b>\n\n"
            f"{short}\n\n"
            f"Полный текст: <a href=\"{offer_url}\">по ссылке</a>"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text=get_text('btn_decline_offer', lang), callback_data='offer_decline')
        kb.button(text=get_text('btn_accept_offer', lang), callback_data=f'offer_accept_{sub_type}')
        kb.adjust(2)
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode='HTML')
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode='HTML')
        await callback.answer()
        return

    # Если оферта уже принята, сразу отправляем инвойс
    await send_stars_invoice(callback, state, sub_type)


@router.callback_query(F.data.startswith("offer_accept_"))
async def offer_accept(callback: CallbackQuery, state: FSMContext):
    """Принятие оферты и продолжение оплаты"""
    sub_type = callback.data.split("offer_accept_")[-1]
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        if not profile.accepted_offer:
            profile.accepted_offer = True
            await profile.asave()
    except Exception as e:
        logger.error(f"offer_accept save error: {e}")
    await send_stars_invoice(callback, state, sub_type)


@router.callback_query(F.data == 'offer_decline')
async def offer_decline(callback: CallbackQuery, state: FSMContext, lang: str = 'ru'):
    try:
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
        lang = profile.language_code or 'ru'
    except Exception:
        pass
    await callback.message.edit_text(get_text('offer_decline_message', lang))
    await callback.answer()




@router.message(Command("subscription"))
async def cmd_subscription(message: Message, state: FSMContext, lang: str = 'ru'):
    """Команда для просмотра подписки"""
    profile = await Profile.objects.aget(telegram_id=message.from_user.id)
    
    text = await get_subscription_info_text(profile, lang)
    
    await send_message_with_cleanup(
        message, 
        state,
        text,
        reply_markup=get_subscription_keyboard(is_beta_tester=profile.is_beta_tester, lang=lang),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscription_promo")
async def ask_promocode(callback: CallbackQuery, state: FSMContext):
    """Запрос промокода"""
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass  # Сообщение уже удалено или не найдено
    
    # Кнопка отмены
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="menu_subscription")
    
    await callback.message.answer(
        "🎟️ <b>Введите промокод</b>\n\n"
        "Отправьте промокод для активации специального предложения:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    await state.set_state(PromoCodeStates.waiting_for_promo)
    await callback.answer()


@router.message(PromoCodeStates.waiting_for_promo)
async def process_promocode(message: Message, state: FSMContext):
    """Обработка введенного промокода"""
    raw_code = (message.text or '').strip()
    user_id = message.from_user.id
    
    try:
        # Получаем профиль пользователя
        profile = await Profile.objects.aget(telegram_id=user_id)
        
        # Ищем промокод
        try:
            promocode = await PromoCode.objects.filter(code__iexact=raw_code).afirst()
            if not promocode:
                raise PromoCode.DoesNotExist
        except PromoCode.DoesNotExist:
            await message.answer(
                "❌ <b>Промокод не найден</b>\n\n"
                "Проверьте правильность ввода и попробуйте снова.",
                parse_mode="HTML"
            )
            await state.clear()
            # Показываем меню подписки
            text = await get_subscription_info_text(profile, lang)
            await send_message_with_cleanup(
                message, 
                state,
                text,
                reply_markup=get_subscription_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Проверяем валидность промокода
        if not promocode.is_valid():
            await message.answer(
                "❌ <b>Промокод недействителен</b>\n\n"
                "Возможно, истек срок действия или достигнут лимит использований.",
                parse_mode="HTML"
            )
            await state.clear()
            # Показываем меню подписки
            text = await get_subscription_info_text(profile, lang)
            await send_message_with_cleanup(
                message, 
                state,
                text,
                reply_markup=get_subscription_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Проверяем, использовал ли пользователь этот промокод
        usage_exists = await PromoCodeUsage.objects.filter(
            promocode=promocode,
            profile=profile
        ).aexists()
        
        if usage_exists:
            await message.answer(
                "❌ <b>Вы уже использовали этот промокод</b>\n\n"
                "Каждый промокод можно использовать только один раз.",
                parse_mode="HTML"
            )
            await state.clear()
            # Показываем меню подписки
            text = await get_subscription_info_text(profile, lang)
            await send_message_with_cleanup(
                message, 
                state,
                text,
                reply_markup=get_subscription_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Применяем промокод
        if promocode.discount_type == 'days':
            # Промокод на дополнительные дни
            days_to_add = int(promocode.discount_value)
            
            # Проверяем текущую подписку
            active_sub = await profile.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).order_by('-end_date').afirst()
            
            if active_sub:
                # Продлеваем существующую подписку
                active_sub.end_date = active_sub.end_date + timedelta(days=days_to_add)
                await active_sub.asave()
                subscription = active_sub
            else:
                # Создаем новую подписку
                start_date = timezone.now()
                end_date = start_date + timedelta(days=days_to_add)
                
                subscription = await Subscription.objects.acreate(
                    profile=profile,
                    type='month',  # По умолчанию месячная
                    payment_method='stars',
                    amount=0,  # Бесплатно по промокоду
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
            
            # Записываем использование промокода
            await PromoCodeUsage.objects.acreate(
                promocode=promocode,
                profile=profile,
                subscription=subscription
            )
            
            # Увеличиваем счетчик использований
            promocode.used_count += 1
            await promocode.asave()
            
            await message.answer(
                f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ <b>Промокод активирован!</b>\n\n"
                f"📦 <b>Получено:</b> {days_to_add} дней подписки\n"
                f"📅 <b>Действует до:</b> {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 <b>Преимущества вашей подписки:</b>\n"
                f"• 🎯 Естественные вопросы к статистике\n"
                f"• 🎤 Голосовой ввод трат\n"
                f"• 🏠 Семейный бюджет\n"
                f"• 📊 PDF, Excel и CSV отчёты с графиками\n"
                f"• 📂 Свои категории расходов\n"
                f"• 💳 Кешбэк-трекер\n"
                f"• ⚡ Приоритетная поддержка\n\n"
                f"<i>Спасибо за поддержку проекта!</i> 💙",
                parse_mode="HTML"
            )
            
        else:
            # Промокод на скидку - проверяем не дает ли он 100% скидку
            # Проверяем применимость промокода к типам подписок
            applicable_to = getattr(promocode, 'applicable_subscription_types', 'all')

            month_price = SUBSCRIPTION_PRICES['month']['stars']
            six_months_price = SUBSCRIPTION_PRICES['six_months']['stars']

            # Применяем скидку с учетом ограничений по типу подписки
            if applicable_to == 'month':
                # Промокод только для месячной подписки
                month_discounted = int(promocode.apply_discount(month_price))
                six_months_discounted = six_months_price  # Без скидки
            elif applicable_to == 'six_months':
                # Промокод только для 6-месячной подписки
                month_discounted = month_price  # Без скидки
                six_months_discounted = int(promocode.apply_discount(six_months_price))
            else:
                # Промокод для всех подписок (applicable_to == 'all')
                month_discounted = int(promocode.apply_discount(month_price))
                six_months_discounted = int(promocode.apply_discount(six_months_price))

            # Проверяем есть ли 100% скидка на какую-либо подписку
            has_free_subscription = False
            if applicable_to == 'month' and month_discounted == 0:
                # 100% скидка на месячную подписку
                has_free_subscription = True
                days_to_add = 30
                sub_type = 'month'
                period_text = 'месяц'
            elif applicable_to == 'six_months' and six_months_discounted == 0:
                # 100% скидка на 6-месячную подписку
                has_free_subscription = True
                days_to_add = 180
                sub_type = 'six_months'
                period_text = '6 месяцев'
            elif applicable_to == 'all' and (month_discounted == 0 or six_months_discounted == 0):
                # 100% скидка на все подписки - даем месячную по умолчанию
                has_free_subscription = True
                days_to_add = 30
                sub_type = 'month'
                period_text = 'месяц'

            if has_free_subscription:

                # Проверяем текущую подписку
                active_sub = await profile.subscriptions.filter(
                    is_active=True,
                    end_date__gt=timezone.now()
                ).order_by('-end_date').afirst()

                if active_sub:
                    # Продлеваем существующую подписку на месяц
                    active_sub.end_date = active_sub.end_date + timedelta(days=days_to_add)
                    await active_sub.asave()
                    subscription = active_sub
                else:
                    # Создаем новую подписку соответствующего типа
                    start_date = timezone.now()
                    end_date = start_date + timedelta(days=days_to_add)

                    subscription = await Subscription.objects.acreate(
                        profile=profile,
                        type=sub_type,  # Тип подписки из промокода
                        payment_method='promo',  # Промокод
                        amount=0,  # Бесплатно по промокоду
                        start_date=start_date,
                        end_date=end_date,
                        is_active=True
                    )

                # Записываем использование промокода
                await PromoCodeUsage.objects.acreate(
                    promocode=promocode,
                    profile=profile,
                    subscription=subscription
                )

                # Увеличиваем счетчик использований
                promocode.used_count += 1
                await promocode.asave()

                # Очищаем состояние
                await state.clear()

                await message.answer(
                    f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✨ <b>Промокод активирован!</b>\n\n"
                    f"📦 <b>Подписка:</b> На <b>{period_text} БЕСПЛАТНО!</b>\n"
                    f"📅 <b>Действует до:</b> {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💎 <b>Преимущества вашей подписки:</b>\n"
                    f"• 🎯 Естественные вопросы к статистике\n"
                    f"• 🎤 Голосовой ввод трат\n"
                    f"• 🏠 Семейный бюджет\n"
                    f"• 📊 PDF, Excel и CSV отчёты с графиками\n"
                    f"• 📂 Свои категории расходов\n"
                    f"• 💳 Кешбэк-трекер\n"
                    f"• ⚡ Приоритетная поддержка\n\n"
                    f"<i>Спасибо за поддержку проекта!</i> 💙",
                    parse_mode="HTML"
                )
                return  # Завершаем обработку

            else:
                # Обычный промокод со скидкой (не 100%)
                await state.update_data(active_promocode=promocode.id)

                discount_text = promocode.get_discount_display()

                # Создаем клавиатуру с ценами со скидкой
                builder = InlineKeyboardBuilder()

                # Проверяем были ли цены изначально 0 (бесплатные)
                month_was_free = month_discounted == 0
                six_months_was_free = six_months_discounted == 0

                # Убеждаемся что цены не меньше 1 звезды (минимум для Telegram)
                month_discounted = max(1, month_discounted)
                six_months_discounted = max(1, six_months_discounted)

                # Формируем текст кнопок с учетом бесплатности и применимости
                if applicable_to in ['month', 'all']:
                    if month_was_free:
                        month_text = "⭐ На месяц - бесплатно!"
                    elif month_discounted < month_price:
                        month_text = f"⭐ На месяц - {month_discounted} звёзд {discount_text}"
                    else:
                        month_text = f"⭐ На месяц - {month_discounted} звёзд"

                    builder.button(
                        text=month_text,
                        callback_data="subscription_buy_month_promo"
                    )

                if applicable_to in ['six_months', 'all']:
                    if six_months_was_free:
                        six_months_text = "⭐ На 6 месяцев - бесплатно!"
                    elif six_months_discounted < six_months_price:
                        six_months_text = f"⭐ На 6 месяцев - {six_months_discounted} звёзд {discount_text}"
                    else:
                        six_months_text = f"⭐ На 6 месяцев - {six_months_discounted} звёзд"

                    builder.button(
                        text=six_months_text,
                        callback_data="subscription_buy_six_months_promo"
                    )
                builder.button(
                    text="❌ Отмена",
                    callback_data="menu_subscription"
                )

                builder.adjust(1)

                await message.answer(
                    f"✅ <b>Промокод принят!</b>\n\n"
                    f"Промокод: {promocode.code}\n"
                    f"Скидка: {discount_text}\n\n"
                    f"Выберите подписку для покупки со скидкой:",
                    reply_markup=builder.as_markup(),
                    parse_mode="HTML"
                )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing promocode: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке промокода. Попробуйте позже.",
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data.startswith("subscription_buy_") & F.data.endswith("_promo"))
async def process_subscription_purchase_with_promo(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки подписки с промокодом"""
    data = await state.get_data()
    promocode_id = data.get('active_promocode')
    
    if not promocode_id:
        await callback.answer("Промокод не найден", show_alert=True)
        return
    
    # Получаем промокод
    promocode = await PromoCode.objects.aget(id=promocode_id)
    
    # Определяем тип подписки
    if "_month_" in callback.data:
        sub_type = "month"
    else:
        sub_type = "six_months"
    
    sub_info = SUBSCRIPTION_PRICES[sub_type]
    
    # Применяем скидку
    original_price = sub_info['stars']
    discounted_price = int(promocode.apply_discount(original_price))

    # Отвечаем на callback чтобы убрать индикатор загрузки
    await callback.answer()

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramNotFound):
        pass  # Сообщение уже удалено или не найдено

    # Проверяем случай с нулевой ценой (бесплатный промокод)
    if discounted_price == 0:
        # Не можем создать инвойс на 0 звезд - обработаем как бесплатную подписку
        profile = await Profile.objects.aget(telegram_id=callback.from_user.id)

        # Определяем количество дней на основе типа подписки
        days_to_add = 30 if sub_type == "month" else 180

        # Проверяем текущую подписку
        active_sub = await profile.subscriptions.filter(
            is_active=True,
            end_date__gt=timezone.now()
        ).order_by('-end_date').afirst()

        if active_sub:
            # Продлеваем существующую подписку
            active_sub.end_date = active_sub.end_date + timedelta(days=days_to_add)
            await active_sub.asave()
            subscription = active_sub
        else:
            # Создаем новую подписку
            start_date = timezone.now()
            end_date = start_date + timedelta(days=days_to_add)

            subscription = await Subscription.objects.acreate(
                profile=profile,
                type=sub_type,
                payment_method='promo',  # Промокод
                amount=0,  # Бесплатно по промокоду
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )

        # Записываем использование промокода
        await PromoCodeUsage.objects.acreate(
            promocode=promocode,
            profile=profile,
            subscription=subscription
        )

        # Увеличиваем счетчик использований
        promocode.used_count += 1
        await promocode.asave()

        # Очищаем состояние
        await state.clear()

        period_text = "месяц" if sub_type == "month" else "6 месяцев"
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=(
                f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✨ <b>Промокод активирован!</b>\n\n"
                f"📦 <b>Подписка:</b> На {period_text} (бесплатно)\n"
                f"📅 <b>Действует до:</b> {subscription.end_date.strftime('%d.%m.%Y')}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 <b>Преимущества вашей подписки:</b>\n"
                f"• 🎯 Естественные вопросы к статистике\n"
                f"• 🎤 Голосовой ввод трат\n"
                f"• 🏠 Семейный бюджет\n"
                f"• 📊 PDF, Excel и CSV отчёты с графиками\n"
                f"• 📂 Свои категории расходов\n"
                f"• 💳 Кешбэк-трекер\n"
                f"• ⚡ Приоритетная поддержка\n\n"
                f"<i>Спасибо за поддержку проекта!</i> 💙"
            ),
            parse_mode="HTML"
        )
        return

    # Обычный случай - создаем инвойс для оплаты со скидкой
    # Убеждаемся что цена не меньше 1 звезды
    discounted_price = max(1, discounted_price)

    # Описание для инвойса со скидкой
    invoice_description = f"🎁 Промокод {promocode.code} ({promocode.get_discount_display()}) • Цена: {discounted_price}⭐ вместо {original_price}⭐ • " + sub_info['description']

    invoice_msg = await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{sub_info['title']} (со скидкой)",
        description=invoice_description,
        payload=f"subscription_{sub_type}_{callback.from_user.id}_promo_{promocode.id}",
        currency="XTR",  # Telegram Stars
        prices=[
            LabeledPrice(
                label=f"{sub_info['title']} {promocode.get_discount_display()}",
                amount=discounted_price
            )
        ],
        start_parameter=f"sub_{sub_type}_promo",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

    # Сохраняем ID сообщения с инвойсом для удаления после оплаты или при новой команде
    await state.update_data(invoice_msg_id=invoice_msg.message_id)

    await callback.answer()


# Обновляем обработчик pre_checkout для поддержки промокодов
@router.pre_checkout_query()
async def process_pre_checkout_updated(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение оплаты перед списанием Stars"""
    # Проверяем payload
    payload = pre_checkout_query.invoice_payload
    payload_parts = payload.split("_")
    
    # Логируем для отладки
    logger.info(f"Pre-checkout query received. Payload: {payload}")
    logger.info(f"Payload parts: {payload_parts}, count: {len(payload_parts)}")
    
    # Проверяем, что payload начинается с "subscription" и имеет минимум 3 части
    # Формат: subscription_TYPE_USER_ID или subscription_TYPE_USER_ID_promo_PROMO_ID
    if len(payload_parts) < 3 or payload_parts[0] != "subscription":
        logger.error(f"Invalid payload format: {payload}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="Ошибка в данных платежа"
        )
        return
    
    # Все проверки пройдены, подтверждаем оплату
    logger.info(f"Payment pre-checkout approved for payload: {payload}")
    await pre_checkout_query.answer(ok=True)


# Обновляем обработчик успешной оплаты
@router.message(F.successful_payment)
async def process_successful_payment_updated(message: Message, state: FSMContext):
    """Обработка успешной оплаты"""
    # Логируем успешную оплату
    logger.info(f"Successful payment from user {message.from_user.id}")

    # Очищаем состояние после оплаты
    await state.clear()
    
    payment = message.successful_payment
    payload = payment.invoice_payload
    payload_parts = payload.split("_")

    # Логируем payload и сумму для отладки
    logger.info(f"Payment payload: {payload}")
    logger.info(f"Payload parts: {payload_parts}")
    logger.info(f"Payment total_amount: {payment.total_amount}")
    logger.info(f"Payment currency: {payment.currency}")
    logger.info(f"Payment telegram_payment_charge_id: {payment.telegram_payment_charge_id}")
    
    # Проверяем тип подписки
    if payload_parts[2] == "months":
        sub_type = f"{payload_parts[1]}_{payload_parts[2]}"
        user_id = int(payload_parts[3])
        promocode_id = int(payload_parts[5]) if len(payload_parts) > 5 and payload_parts[4] == "promo" else None
    else:
        sub_type = payload_parts[1]
        user_id = int(payload_parts[2])
        promocode_id = int(payload_parts[4]) if len(payload_parts) > 4 and payload_parts[3] == "promo" else None
    
    # Получаем профиль
    profile = await Profile.objects.aget(telegram_id=user_id)
    
    # Создаем подписку
    sub_info = SUBSCRIPTION_PRICES[sub_type]
    
    now_ts = timezone.now()

    # Снимаем флаг активности с истекших подписок (чтобы чистить историю)
    expired = await profile.subscriptions.filter(
        is_active=True,
        end_date__lte=now_ts
    ).aupdate(is_active=False)

    if expired:
        logger.info(f"Marked {expired} expired subscriptions inactive for user {user_id}")

    # Рассчитываем период новой подписки
    latest_subscription = await profile.subscriptions.filter(
        end_date__gt=now_ts
    ).order_by('-end_date').afirst()

    if latest_subscription:
        base_start = max(latest_subscription.end_date, now_ts)
        logger.info(
            f"Extending subscription for user {user_id}: latest_end={latest_subscription.end_date}, new_start={base_start}"
        )
    else:
        base_start = now_ts
        logger.info(f"Creating fresh subscription for user {user_id}: start={base_start}")

    start_date = base_start
    end_date = start_date + relativedelta(months=sub_info['months'])

    # Определяем правильную сумму в Stars
    # Если валюта XTR (Telegram Stars), то total_amount уже в Stars
    # Иначе используем цену из конфига
    if payment.currency == "XTR":
        stars_amount = payment.total_amount
    else:
        # Fallback на цену из конфигурации
        stars_amount = sub_info['stars']

    logger.info(f"Creating subscription with amount: {stars_amount} Stars")

    # Создаем запись подписки с корректным методом оплаты
    subscription = await Subscription.objects.acreate(
        profile=profile,
        type=sub_type,
        payment_method='stars',  # ВАЖНО: всегда 'stars' для платных подписок
        amount=stars_amount,  # Используем правильную сумму в Stars
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )

    # Обновляем статистику платежей в профиле пользователя
    profile.total_payments_count = (profile.total_payments_count or 0) + 1
    profile.total_stars_paid = (profile.total_stars_paid or 0) + stars_amount
    await profile.asave(update_fields=['total_payments_count', 'total_stars_paid'])

    logger.info(f"Created subscription #{subscription.id} for user {user_id}: {start_date} → {end_date}")
    
    # Бонус за приглашение
    try:
        reward_result = await reward_referrer_subscription_extension(subscription)

        if reward_result and reward_result.get('status') == 'reward_granted':
            referrer_tid = reward_result['referrer_id']
            reward_months = reward_result['reward_months']
            reward_end = reward_result['reward_end'].strftime('%d.%m.%Y')
            months_text_ru = '1 месяц' if reward_months == 1 else f'{reward_months} месяцев'
            months_text_en = '1 month' if reward_months == 1 else f'{reward_months} months'

            try:
                referrer_profile = await Profile.objects.aget(telegram_id=referrer_tid)
                referrer_lang = referrer_profile.language_code or 'ru'
            except Profile.DoesNotExist:
                referrer_profile = None
                referrer_lang = 'ru'

            if referrer_lang == 'en':
                referrer_message = (
                    "🎉 <b>Referral bonus!</b>\n\n"
                    "Your invited friend purchased a subscription.\n"
                    f"We extended your access for {months_text_en}.\n"
                    f"New expiry date: <b>{reward_end}</b>\n\n"
                    "Thank you for sharing the bot!"
                )
            else:
                referrer_message = (
                    "🎉 <b>Реферальный бонус!</b>\n\n"
                    "Ваш приглашённый пользователь оплатил подписку.\n"
                    f"Мы продлили вашу подписку на {months_text_ru}.\n"
                    f"Новая дата окончания: <b>{reward_end}</b>\n\n"
                    "Спасибо, что делитесь ботом!"
                )

            try:
                await message.bot.send_message(
                    chat_id=referrer_tid,
                    text=referrer_message,
                    parse_mode='HTML'
                )
                logger.info(
                    "Notified referrer %s about subscription extension reward",
                    referrer_tid
                )
            except Exception as send_error:
                if "bot was blocked" in str(send_error).lower() or "chat not found" in str(send_error).lower():
                    logger.info("Referrer %s unavailable for reward notification", referrer_tid)
                else:
                    logger.warning(
                        "Could not notify referrer %s: %s",
                        referrer_tid,
                        send_error
                    )
    except Exception as e:
        logger.error(f"Error processing referral reward: {e}")
        # Не прерываем основной процесс из-за ошибки в реферальной системе
    
    # Если был использован промокод, записываем это
    if promocode_id:
        try:
            promocode = await PromoCode.objects.aget(id=promocode_id)
            
            # Записываем использование
            await PromoCodeUsage.objects.acreate(
                promocode=promocode,
                profile=profile,
                subscription=subscription
            )
            
            # Увеличиваем счетчик
            promocode.used_count += 1
            await promocode.asave()
            
            discount_text = f"\nИспользован промокод: {promocode.code} {promocode.get_discount_display()}"
        except (ObjectDoesNotExist, AttributeError) as e:
            logger.warning(f"Error applying promocode {promocode_id}: {e}")
            discount_text = ""
    else:
        discount_text = ""
    
    # Старая система с бонусными днями ПОЛНОСТЬЮ УДАЛЕНА
    # Используется только новая система Telegram Stars (обработана выше)
    
    # Отправляем подтверждение с улучшенным оформлением
    await message.answer(
        f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> 🎉\n"
        f"{'━' * 25}\n\n"
        f"✨ <b>Оплата прошла успешно!</b>\n\n"
        f"📦 <b>Подписка:</b> {sub_info['title']}\n"
        f"📅 <b>Действует до:</b> {end_date.strftime('%d.%m.%Y')}{discount_text}\n\n"
        f"{'━' * 25}\n"
        f"💎 <b>Преимущества вашей подписки:</b>\n"
        f"• 🎯 Естественные вопросы к статистике\n"
        f"• 🎤 Голосовой ввод трат\n"
        f"• 🏠 Семейный бюджет\n"
        f"• 📄 PDF-отчёты с графиками\n"
        f"• 📂 Свои категории расходов\n"
        f"• 💳 Кешбэк-трекер\n"
        f"• ⚡ Приоритетная поддержка\n\n"
        f"<i>Спасибо за поддержку проекта!</i> 💙",
        parse_mode="HTML"
    )


# Удален обработчик show_affiliate - теперь используется menu_referral
