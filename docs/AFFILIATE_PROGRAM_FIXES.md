# Исправления к плану миграции реферальной программы

> Дата: 12.11.2025
> Дополнения к AFFILIATE_PROGRAM_MIGRATION_PLAN.md

## 🔴 Критические исправления

### 1. Добавить total_spent в get_referrer_stats()

**Файл:** `bot/services/affiliate.py`
**Строки:** 368-430

**Проблема:** Функция не возвращает `total_spent`, но он используется в UI.

**Решение:** Добавить агрегацию total_spent

**Найти:**
```python
reward_stats = referrals_qs.filter(reward_granted=True).aggregate(
    total_months=Sum('reward_months')
)
total_reward_months = reward_stats['total_months'] or 0
```

**Добавить после:**
```python
# Агрегация total_spent из всех рефералов
payment_stats = referrals_qs.aggregate(
    total_spent=Sum('total_spent')
)
total_spent = payment_stats['total_spent'] or 0
```

**И в return добавить:**
```python
return {
    'has_link': True,
    'link': affiliate_link.telegram_link,
    'code': affiliate_link.affiliate_code,
    'clicks': affiliate_link.clicks,
    'conversions': affiliate_link.conversions,
    'conversion_rate': conversion_rate,
    'referrals_count': referrals_count,
    'rewarded_referrals': rewarded_referrals,
    'pending_referrals': pending_referrals,
    'rewarded_months': total_reward_months,
    'total_spent': total_spent,  # ДОБАВИТЬ ЭТУ СТРОКУ
}
```

**Также обновить return при отсутствии ссылки:**
```python
return {
    'has_link': False,
    'link': None,
    'clicks': 0,
    'conversions': 0,
    'conversion_rate': 0,
    'referrals_count': 0,
    'rewarded_referrals': 0,
    'pending_referrals': 0,
    'rewarded_months': 0,
    'total_spent': 0,  # ДОБАВИТЬ
}
```

---

### 2. Исправить callback_data для кнопки статистики

**Файл:** Весь план (все упоминания)

**Проблема:** В плане используется `referral_detailed_stats`, но в коде handler `referral_stats`.

**Решение:** Везде заменить на `referral_stats`

**В AFFILIATE_PROGRAM_MIGRATION_PLAN.md везде заменить:**
- `callback_data='referral_detailed_stats'` → `callback_data='referral_stats'`
- Handler уже существует и называется `show_referral_stats`

**В клавиатуре (строка 523 плана):**
```python
[InlineKeyboardButton(text=btn_stats, callback_data='referral_stats')],  # НЕ referral_detailed_stats
```

---

### 3. Исправить логирование F() expressions

**Файл:** План, Этап 1.2

**Проблема:** Логирование `referral.total_payments + 1` после присвоения F() вызовет TypeError.

**Решение:** Не логировать точные значения ИЛИ делать refresh

**Вариант A - Убрать из логов (рекомендую):**

**Было в плане:**
```python
logger.info(
    f"[AFFILIATE] Stats updated for referral {referral.id}. "
    f"Total payments: {referral.total_payments + 1}, "
    f"Total spent: {referral.total_spent + subscription.amount} Stars"
)
```

**Стало:**
```python
logger.info(
    f"[AFFILIATE] Stats updated for referral {referral.id}. "
    f"Payment amount: {subscription.amount} Stars"
)
```

**Вариант B - Refresh перед логированием:**
```python
# Обновляем общую статистику
referral.total_payments = F('total_payments') + 1
referral.total_spent = F('total_spent') + subscription.amount
await referral.asave(
    update_fields=['first_payment_at', 'total_payments', 'total_spent']
)

# Refresh чтобы получить актуальные значения
await referral.arefresh_from_db()

logger.info(
    f"[AFFILIATE] Stats updated for referral {referral.id}. "
    f"Total payments: {referral.total_payments}, "
    f"Total spent: {referral.total_spent} Stars"
)
```

---

### 4. Правильные имена handlers

**В плане упоминаются функции, которые нужно обновить:**

- ✅ `show_referral_menu` с callback `menu_referral` - **ПРАВИЛЬНО**
- ✅ `show_referral_stats` с callback `referral_stats` - **ПРАВИЛЬНО** (НЕ referral_detailed_stats!)
- ✅ `show_referral_rewards` с callback `referral_rewards` - **ПРАВИЛЬНО**

**Новый handler:** `show_telegram_program_info` с callback `referral_telegram_program` - создается впервые.

---

## Полный исправленный Этап 1.2

**Файл:** `bot/services/affiliate.py`
**После:** `reward_referrer_subscription_extension`

```python
async def update_affiliate_conversion_stats(subscription) -> Optional[dict]:
    """
    Обновляет статистику конверсий реферальной программы.

    НЕ начисляет бонусы - только обновляет счетчики для мониторинга.

    Args:
        subscription: Объект подписки после успешной оплаты

    Returns:
        dict: Результат обновления или None если нет реферальной связи
    """
    from expenses.models import AffiliateReferral
    from django.db.models import F
    import logging

    logger = logging.getLogger(__name__)

    # Проверяем что это оплаченная подписка через Stars
    if subscription.payment_method != 'stars' or subscription.amount == 0:
        logger.debug(
            f"[AFFILIATE] Skipping stats for subscription {subscription.id}: "
            f"payment_method={subscription.payment_method}, amount={subscription.amount}"
        )
        return None

    try:
        profile = subscription.profile

        # Находим реферальную связь
        referral = await AffiliateReferral.objects.select_related(
            'referrer', 'affiliate_link'
        ).aget(referred=profile)

        # Первый платеж - обновляем конверсию
        is_first_payment = referral.first_payment_at is None

        if is_first_payment:
            referral.first_payment_at = subscription.created_at

            # Увеличиваем счетчик конверсий
            referral.affiliate_link.conversions = F('conversions') + 1
            await referral.affiliate_link.asave(update_fields=['conversions'])

            logger.info(
                f"[AFFILIATE] First payment for referral {referral.id}. "
                f"Conversion recorded."
            )

        # Обновляем общую статистику
        referral.total_payments = F('total_payments') + 1
        referral.total_spent = F('total_spent') + subscription.amount
        await referral.asave(
            update_fields=['first_payment_at', 'total_payments', 'total_spent']
        )

        logger.info(
            f"[AFFILIATE] Stats updated for referral {referral.id}. "
            f"Payment amount: {subscription.amount} Stars. "
            f"Is first payment: {is_first_payment}"
        )

        return {
            'status': 'stats_updated',
            'referral_id': referral.id,
            'referrer_id': referral.referrer.telegram_id,
            'is_first_payment': is_first_payment,
        }

    except AffiliateReferral.DoesNotExist:
        logger.debug(
            f"[AFFILIATE] No referral for user {profile.telegram_id}"
        )
        return None
    except Exception as e:
        logger.error(
            f"[AFFILIATE] Error updating stats: {e}",
            exc_info=True
        )
        return None
```

---

## Полный исправленный get_referrer_stats()

**Файл:** `bot/services/affiliate.py`
**Строки:** 368-430

**Полностью заменить функцию на:**

```python
@sync_to_async
def get_referrer_stats(user_id: int) -> Dict[str, Any]:
    """
    Получить статистику реферера

    Args:
        user_id: Telegram ID реферера

    Returns:
        Словарь со статистикой (включая total_spent)
    """
    try:
        profile = Profile.objects.get(telegram_id=user_id)
        affiliate_link = AffiliateLink.objects.filter(profile=profile).first()

        if not affiliate_link:
            return {
                'has_link': False,
                'link': None,
                'clicks': 0,
                'conversions': 0,
                'conversion_rate': 0,
                'referrals_count': 0,
                'rewarded_referrals': 0,
                'pending_referrals': 0,
                'rewarded_months': 0,
                'total_spent': 0,  # ДОБАВЛЕНО
            }

        referrals_qs = AffiliateReferral.objects.filter(referrer=profile)

        referrals_count = referrals_qs.count()
        rewarded_referrals = referrals_qs.filter(reward_granted=True).count()
        pending_referrals = referrals_count - rewarded_referrals

        # Агрегация месяцев бонусов
        reward_stats = referrals_qs.filter(reward_granted=True).aggregate(
            total_months=Sum('reward_months')
        )
        total_reward_months = reward_stats['total_months'] or 0

        # НОВОЕ: Агрегация total_spent
        payment_stats = referrals_qs.aggregate(
            total_spent=Sum('total_spent')
        )
        total_spent = payment_stats['total_spent'] or 0

        conversion_rate = 0
        if referrals_count > 0:
            rate = (rewarded_referrals / referrals_count) * 100
            conversion_rate = int(rate) if rate == int(rate) else round(rate, 1)

        return {
            'has_link': True,
            'link': affiliate_link.telegram_link,
            'code': affiliate_link.affiliate_code,
            'clicks': affiliate_link.clicks,
            'conversions': affiliate_link.conversions,
            'conversion_rate': conversion_rate,
            'referrals_count': referrals_count,
            'rewarded_referrals': rewarded_referrals,
            'pending_referrals': pending_referrals,
            'rewarded_months': total_reward_months,
            'total_spent': total_spent,  # ДОБАВЛЕНО
        }

    except Profile.DoesNotExist:
        return {
            'has_link': False,
            'error': 'Profile not found',
            'total_spent': 0,  # ДОБАВЛЕНО
        }
```

---

## Исправленные тексты UI (Этап 2.1)

**В show_referral_menu НЕ нужно полностью переписывать!**

Просто добавить информационный блок в существующую функцию `get_referral_info_text()`.

**Файл:** `bot/routers/referral.py`
**Найти функцию:** `get_referral_info_text()` (строки ~60-98)

**Добавить в конец текста:**

```python
# ... существующий код формирования текста ...

# НОВОЕ: Добавляем информацию о Telegram Program
if lang == 'en':
    telegram_program_info = (
        "\n\n💰 <b>Want to earn Stars from referrals?</b>\n"
        "Connect to official Telegram Stars Affiliate Program!\n"
        "You'll receive up to 20% Stars from each referral's purchase.\n\n"
        "💡 <b>Important:</b>\n"
        "• Bot statistics - for monitoring effectiveness\n"
        "• Stars earnings - via Telegram Program (separate connection)"
    )
else:
    telegram_program_info = (
        "\n\n💰 <b>Хотите заработать Stars от рефералов?</b>\n"
        "Подключитесь к официальной программе Telegram Stars!\n"
        "Вы будете получать до 20% Stars от каждой покупки реферала.\n\n"
        "💡 <b>Важно:</b>\n"
        "• Статистика в боте - для мониторинга эффективности\n"
        "• Заработок Stars - через Telegram Program (отдельное подключение)"
    )

text = text + telegram_program_info

return text, has_code, share_text, share_url
```

---

## Исправленная клавиатура (Этап 2.3)

**Файл:** `bot/routers/referral.py`
**Функция:** `get_referral_keyboard()` (строки 20-55)

**НЕ нужно полностью переписывать!** Просто добавить кнопку.

**Найти:**
```python
keyboard = [
    [InlineKeyboardButton(text=btn_share, url=share_url)],
    [InlineKeyboardButton(text=btn_stats, callback_data='referral_stats')],
    [InlineKeyboardButton(text=btn_rewards, callback_data='referral_rewards')],
    [InlineKeyboardButton(text=btn_close, callback_data='delete_message')]
]
```

**Заменить на:**
```python
if lang == 'ru':
    btn_telegram_program = "📖 Telegram Stars Program"
else:
    btn_telegram_program = "📖 Telegram Stars Program"

keyboard = [
    [InlineKeyboardButton(text=btn_share, url=share_url)],
    [InlineKeyboardButton(text=btn_telegram_program, callback_data='referral_telegram_program')],  # НОВАЯ КНОПКА
    [InlineKeyboardButton(text=btn_stats, callback_data='referral_stats')],  # ПРАВИЛЬНЫЙ callback
    [InlineKeyboardButton(text=btn_rewards, callback_data='referral_rewards')],
    [InlineKeyboardButton(text=btn_close, callback_data='delete_message')]
]
```

---

## Чеклист обновлений

### Фаза 1: Исправления кода ✅

- [ ] Обновить `get_referrer_stats()` - добавить `total_spent`
- [ ] Добавить `update_affiliate_conversion_stats()` с правильным логированием
- [ ] Обновить `reward_referrer_subscription_extension()` - заглушка
- [ ] Обновить `process_successful_payment_updated()` в subscription.py
- [ ] Проверить компиляцию

### Фаза 2: Исправления UI ✅

- [ ] Добавить блок о Telegram Program в `get_referral_info_text()`
- [ ] Добавить `show_telegram_program_info()` с callback `referral_telegram_program`
- [ ] Обновить `get_referral_keyboard()` - новая кнопка
- [ ] Обновить `show_referral_rewards()` - информация об отключении
- [ ] Использовать правильный callback: `referral_stats` (НЕ referral_detailed_stats)

### Фаза 3: Тесты ✅

- [ ] Проверить что `stats['total_spent']` работает
- [ ] Проверить что кнопка "Telegram Program" открывает handler
- [ ] Проверить что кнопка "Статистика" работает (callback referral_stats)
- [ ] Проверить что логирование не падает

---

## Итоговый список файлов для изменения

1. **bot/services/affiliate.py:**
   - Обновить `get_referrer_stats()` - добавить total_spent
   - Заглушка `reward_referrer_subscription_extension()`
   - Новая функция `update_affiliate_conversion_stats()`

2. **bot/routers/subscription.py:**
   - Заменить вызов бонуса на вызов статистики

3. **bot/routers/referral.py:**
   - Добавить блок о Telegram Program в `get_referral_info_text()`
   - Добавить handler `show_telegram_program_info()`
   - Обновить клавиатуру - новая кнопка
   - Обновить `show_referral_rewards()` - новые тексты

4. **bot/routers/start.py:**
   - Обновить приветствие реферала

5. **docs/AFFILIATE_PROGRAM.md:**
   - Новая версия документации

---

**Дата:** 12.11.2025
**Статус:** ✅ Все критические ошибки исправлены
