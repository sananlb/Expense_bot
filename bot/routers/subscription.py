"""
Роутер для управления подписками через Telegram Stars
"""
from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import logging

from expenses.models import Profile, Subscription, PromoCode, PromoCodeUsage, ReferralBonus
from bot.utils.message_utils import send_message_with_cleanup

logger = logging.getLogger(__name__)

router = Router(name='subscription')


class PromoCodeStates(StatesGroup):
    """Состояния для промокода"""
    waiting_for_promo = State()


# Цены подписок в Telegram Stars
SUBSCRIPTION_PRICES = {
    'month': {
        'stars': 100,
        'months': 1,
        'title': 'Подписка на месяц',
        'description': 'Полный доступ ко всем функциям на 1 месяц'
    },
    'six_months': {
        'stars': 500,
        'months': 6,
        'title': 'Подписка на 6 месяцев',
        'description': 'Полный доступ ко всем функциям на 6 месяцев'
    }
}


def get_subscription_keyboard():
    """Клавиатура выбора подписки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="⭐ На месяц - 100 звёзд",
        callback_data="subscription_buy_month"
    )
    builder.button(
        text="⭐ На 6 месяцев - 500 звёзд",
        callback_data="subscription_buy_six_months"
    )
    builder.button(
        text="🎟️ У меня есть промокод",
        callback_data="subscription_promo"
    )
    builder.button(
        text="❌ Закрыть",
        callback_data="close"
    )
    
    builder.adjust(1)
    return builder.as_markup()


async def get_subscription_info_text(profile: Profile) -> str:
    """Получить текст с информацией о подписке"""
    # Проверяем активную подписку
    active_subscription = await profile.subscriptions.filter(
        is_active=True,
        end_date__gt=timezone.now()
    ).order_by('-end_date').afirst()
    
    if active_subscription:
        days_left = (active_subscription.end_date - timezone.now()).days
        subscription_type = active_subscription.get_type_display()
        
        # Добавляем информацию о пробном периоде
        if active_subscription.type == 'trial':
            emoji = "🎁"
            subscription_type = "Пробный период"
        else:
            emoji = "✅"
            
        return (
            f"{emoji} <b>У вас есть активная подписка</b>\n\n"
            f"Тип: {subscription_type}\n"
            f"Действует до: {active_subscription.end_date.strftime('%d.%m.%Y')}\n"
            f"Осталось дней: {days_left}\n\n"
            f"Вы можете продлить подписку заранее."
        )
    else:
        return (
            "❌ <b>У вас нет активной подписки</b>\n\n"
            "С подпиской вы получаете:\n"
            "• Голосовой ввод расходов\n"
            "• Редактирование категорий\n"
            "• Управление кешбэками\n"
            "• Экспорт отчетов в PDF\n"
            "• Неограниченное количество трат\n\n"
            "Выберите подходящий план:"
        )


@router.callback_query(F.data == "menu_subscription")
async def show_subscription_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню подписки"""
    # Получаем сохраненные ID сообщений
    data = await state.get_data()
    invoice_msg_id = data.get('invoice_msg_id')
    subscription_back_msg_id = data.get('subscription_back_msg_id')
    
    # Удаляем сообщение с инвойсом, если оно есть
    if invoice_msg_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.from_user.id,
                message_id=invoice_msg_id
            )
        except:
            pass
    
    # Удаляем сообщение с кнопкой "Назад"
    if subscription_back_msg_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.from_user.id,
                message_id=subscription_back_msg_id
            )
        except:
            pass
    
    # Очищаем сохраненные ID
    await state.update_data(invoice_msg_id=None, subscription_back_msg_id=None)
    
    profile = await Profile.objects.aget(telegram_id=callback.from_user.id)
    
    text = await get_subscription_info_text(profile)
    
    # Отправляем новое сообщение с меню подписки
    await send_message_with_cleanup(
        callback.message, 
        state, 
        text, 
        reply_markup=get_subscription_keyboard(), 
        parse_mode="HTML"
    )
    
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
    
    sub_info = SUBSCRIPTION_PRICES[sub_type]
    
    # Отвечаем на callback чтобы убрать индикатор загрузки
    await callback.answer()
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Создаем инвойс для оплаты
    invoice_msg = await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=sub_info['title'],
        description=sub_info['description'],
        payload=f"subscription_{sub_type}_{callback.from_user.id}",
        currency="XTR",  # Telegram Stars
        prices=[
            LabeledPrice(
                label=sub_info['title'],
                amount=sub_info['stars']
            )
        ],
        start_parameter=f"sub_{sub_type}",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )
    
    # Отправляем отдельное сообщение с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️", callback_data="menu_subscription")
    
    back_msg = await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="Назад в меню подписки",
        reply_markup=builder.as_markup()
    )
    
    # Сохраняем ID обоих сообщений для удаления после оплаты или при новой команде
    await state.update_data(
        invoice_msg_id=invoice_msg.message_id,
        subscription_back_msg_id=back_msg.message_id
    )
    
    await callback.answer()




@router.message(Command("subscription"))
async def cmd_subscription(message: Message, state: FSMContext):
    """Команда для просмотра подписки"""
    profile = await Profile.objects.aget(telegram_id=message.from_user.id)
    
    text = await get_subscription_info_text(profile)
    
    await send_message_with_cleanup(
        message, 
        state,
        text,
        reply_markup=get_subscription_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscription_promo")
async def ask_promocode(callback: CallbackQuery, state: FSMContext):
    """Запрос промокода"""
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
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
    promo_code = message.text.strip().upper()
    user_id = message.from_user.id
    
    try:
        # Получаем профиль пользователя
        profile = await Profile.objects.aget(telegram_id=user_id)
        
        # Ищем промокод
        try:
            promocode = await PromoCode.objects.aget(code=promo_code)
        except PromoCode.DoesNotExist:
            await message.answer(
                "❌ <b>Промокод не найден</b>\n\n"
                "Проверьте правильность ввода и попробуйте снова.",
                parse_mode="HTML"
            )
            await state.clear()
            # Показываем меню подписки
            text = await get_subscription_info_text(profile)
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
            text = await get_subscription_info_text(profile)
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
            text = await get_subscription_info_text(profile)
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
                f"✅ <b>Промокод активирован!</b>\n\n"
                f"Вы получили {days_to_add} дней подписки.\n"
                f"Подписка действует до: {subscription.end_date.strftime('%d.%m.%Y')}",
                parse_mode="HTML"
            )
            
        else:
            # Промокод на скидку - показываем кнопки оплаты со скидкой
            await state.update_data(active_promocode=promocode.id)
            
            discount_text = promocode.get_discount_display()
            
            # Создаем клавиатуру с ценами со скидкой
            builder = InlineKeyboardBuilder()
            
            # Рассчитываем цены со скидкой
            month_price = SUBSCRIPTION_PRICES['month']['stars']
            six_months_price = SUBSCRIPTION_PRICES['six_months']['stars']
            
            month_discounted = int(promocode.apply_discount(month_price))
            six_months_discounted = int(promocode.apply_discount(six_months_price))
            
            builder.button(
                text=f"⭐ На месяц - {month_discounted} звёзд {discount_text}",
                callback_data="subscription_buy_month_promo"
            )
            builder.button(
                text=f"⭐ На 6 месяцев - {six_months_discounted} звёзд {discount_text}",
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
    except:
        pass
    
    # Создаем инвойс для оплаты со скидкой
    invoice_msg = await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{sub_info['title']} (со скидкой)",
        description=f"{sub_info['description']}\n\n💸 Промокод: {promocode.code} {promocode.get_discount_display()}\n✨ Цена со скидкой: {discounted_price} звёзд (вместо {original_price})",
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
    
    # Отправляем отдельное сообщение с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️", callback_data="menu_subscription")
    
    back_msg = await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="Назад в меню подписки",
        reply_markup=builder.as_markup()
    )
    
    # Сохраняем ID обоих сообщений для удаления после оплаты или при новой команде
    await state.update_data(
        invoice_msg_id=invoice_msg.message_id,
        subscription_back_msg_id=back_msg.message_id
    )
    
    await callback.answer()


# Обновляем обработчик pre_checkout для поддержки промокодов
@router.pre_checkout_query()
async def process_pre_checkout_updated(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение оплаты перед списанием Stars"""
    # Проверяем payload
    payload_parts = pre_checkout_query.invoice_payload.split("_")
    
    if len(payload_parts) < 4 or payload_parts[0] != "subscription":
        await pre_checkout_query.answer(
            ok=False,
            error_message="Ошибка в данных платежа"
        )
        return
    
    # Все проверки пройдены, подтверждаем оплату
    await pre_checkout_query.answer(ok=True)


# Обновляем обработчик успешной оплаты
@router.message(F.successful_payment)
async def process_successful_payment_updated(message: Message, state: FSMContext):
    """Обработка успешной оплаты"""
    # Получаем сохраненные ID сообщений перед очисткой состояния
    data = await state.get_data()
    invoice_msg_id = data.get('invoice_msg_id')
    subscription_back_msg_id = data.get('subscription_back_msg_id')
    
    # Удаляем сообщение с кнопкой "Назад", если оно есть
    if subscription_back_msg_id:
        try:
            await message.bot.delete_message(
                chat_id=message.from_user.id,
                message_id=subscription_back_msg_id
            )
        except:
            pass
    
    # Очищаем состояние после оплаты
    await state.clear()
    
    payment = message.successful_payment
    payload_parts = payment.invoice_payload.split("_")
    
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
    start_date = timezone.now()
    
    # Если есть активная подписка, продлеваем от её окончания
    active_sub = await profile.subscriptions.filter(
        is_active=True,
        end_date__gt=timezone.now()
    ).order_by('-end_date').afirst()
    
    if active_sub:
        start_date = active_sub.end_date
    
    # Продлеваем по месяцам
    end_date = start_date + relativedelta(months=sub_info['months'])
    
    # Создаем новую подписку
    subscription = await Subscription.objects.acreate(
        profile=profile,
        type=sub_type,
        payment_method='stars',
        amount=payment.total_amount,  # Фактически оплаченная сумма
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )
    
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
        except:
            discount_text = ""
    else:
        discount_text = ""
    
    # Проверяем реферальную программу
    # Если это первая платная подписка и есть реферер, начисляем бонус
    if profile.referrer and sub_type in ['month', 'six_months']:
        # Проверяем, была ли уже платная подписка
        previous_paid_subs = await profile.subscriptions.filter(
            type__in=['month', 'six_months'],
            id__lt=subscription.id  # Все подписки до текущей
        ).acount()
        
        if previous_paid_subs == 0:
            # Это первая платная подписка - начисляем бонус рефереру
            referrer = profile.referrer
            
            # Создаем запись о бонусе
            bonus = await ReferralBonus.objects.acreate(
                referrer=referrer,
                referred=profile,
                bonus_days=30,
                subscription=subscription,
                is_activated=False
            )
            
            # Проверяем активную подписку реферера
            referrer_active_sub = await referrer.subscriptions.filter(
                is_active=True,
                end_date__gt=timezone.now()
            ).order_by('-end_date').afirst()
            
            if referrer_active_sub:
                # Продлеваем существующую подписку
                referrer_active_sub.end_date = referrer_active_sub.end_date + timedelta(days=30)
                await referrer_active_sub.asave()
            else:
                # Создаем новую подписку на 30 дней
                bonus_start = timezone.now()
                bonus_end = bonus_start + timedelta(days=30)
                
                await Subscription.objects.acreate(
                    profile=referrer,
                    type='month',
                    payment_method='stars',
                    amount=0,  # Бесплатно за реферала
                    start_date=bonus_start,
                    end_date=bonus_end,
                    is_active=True
                )
            
            # Активируем бонус
            bonus.is_activated = True
            bonus.activated_at = timezone.now()
            await bonus.asave()
            
            # Уведомляем реферера
            try:
                await message.bot.send_message(
                    referrer.telegram_id,
                    "🎉 <b>Поздравляем!</b>\n\n"
                    "Ваш друг оформил подписку по вашей реферальной ссылке!\n"
                    "Вы получили <b>30 дней</b> бесплатной подписки.\n\n"
                    "Спасибо за то, что рекомендуете нас!",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify referrer {referrer.telegram_id}: {e}")
    
    # Отправляем подтверждение
    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"Подписка: {sub_info['title']}\n"
        f"Действует до: {end_date.strftime('%d.%m.%Y')}{discount_text}\n\n"
        f"Спасибо за поддержку проекта! 🙏",
        parse_mode="HTML"
    )
    
    # Показываем кнопку закрыть
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Закрыть", callback_data="close")
    
    await message.answer(
        "Что дальше?",
        reply_markup=builder.as_markup()
    )