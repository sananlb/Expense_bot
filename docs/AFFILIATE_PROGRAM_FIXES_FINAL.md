# ФИНАЛЬНЫЕ ИСПРАВЛЕНИЯ К ПЛАНУ МИГРАЦИИ

> **Дата:** 12.11.2025
> **Статус:** Критические несоответствия кода и плана
> **Цель:** Точные инструкции для реального кода

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ В ТЕКУЩЕМ ПЛАНЕ

### Проблема #1: total_spent не возвращается из get_referrer_stats()

**Файл:** `bot/services/affiliate.py:368-429`
**Проблема:** Функция возвращает только эти ключи:
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
    # ❌ НЕТ 'total_spent'!
}
```

**Последствие:** План использует `stats['total_spent']` → KeyError при рендере UI

**РЕШЕНИЕ:**

В `bot/services/affiliate.py:368-429` найти строки 402-405:
```python
reward_stats = referrals_qs.filter(reward_granted=True).aggregate(
    total_months=Sum('reward_months')
)
total_reward_months = reward_stats['total_months'] or 0
```

**ДОБАВИТЬ ПОСЛЕ:**
```python
# Агрегация total_spent из всех рефералов
payment_stats = referrals_qs.aggregate(
    total_spent=Sum('total_spent')
)
total_spent = payment_stats['total_spent'] or 0
```

**ИЗМЕНИТЬ return на строке 412-423:**
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
    'total_spent': total_spent,  # ✅ ДОБАВИТЬ ЭТУ СТРОКУ
}
```

**ТАКЖЕ ИЗМЕНИТЬ return при отсутствии ссылки (строки 384-394):**
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
    'total_spent': 0,  # ✅ ДОБАВИТЬ
}
```

**И в except Profile.DoesNotExist (строки 425-429):**
```python
except Profile.DoesNotExist:
    return {
        'has_link': False,
        'error': 'Profile not found',
        'total_spent': 0,  # ✅ ДОБАВИТЬ
    }
```

---

### Проблема #2: План предлагает изменить show_referral_menu, но текст формируется в get_referral_info_text

**Файл:** `bot/routers/referral.py:61-98`
**Проблема:** План говорит "переписать show_referral_menu", но этот handler только вызывает get_referral_info_text() и использует результат. Текст формируется в get_referral_info_text().

**Текущая структура:**
```python
# show_referral_menu (строки 101-138)
text, has_code, share_text, share_url = await get_referral_info_text(profile, bot_username, lang)
await callback.message.edit_text(text=text, ...)

# get_referral_info_text (строки 61-98) - ЗДЕСЬ ФОРМИРУЕТСЯ ТЕКСТ
if lang == 'en':
    text = (
        "🔗 <b>Share with friends</b>\n\n"
        "Click the 'Share' button below to invite friends!\n\n"
        "🎁 <b>Bonus</b>\n"
        "When a friend buys their first subscription, we'll extend yours for the same period (one time)."
    )
else:
    text = (
        "🔗 <b>Поделитесь с друзьями</b>\n\n"
        "Нажмите кнопку «Поделиться» ниже, чтобы пригласить друзей!\n\n"
        "🎁 <b>Бонус</b>\n"
        "Когда друг купит первую подписку, мы продлим вашу на такой же срок (один раз)."
    )

return text, True, share_message, affiliate_link.telegram_link
```

**РЕШЕНИЕ:**

НЕ трогать show_referral_menu вообще! Изменить только get_referral_info_text():

**В `bot/routers/referral.py:61-98` ПЕРЕД return (строка 98):**

```python
# ДОБАВИТЬ блок о Telegram Program ПЕРЕД return:
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

# Существующий return остается без изменений:
return text, True, share_message, affiliate_link.telegram_link
```

---

### Проблема #3: show_referral_rewards - план ссылается на несуществующие переменные

**Файл:** `bot/routers/referral.py:194-267`
**Проблема:** План предлагает использовать `rewarded_referrals` и `rewarded_months` в show_referral_rewards, но эти переменные не в scope. Функция только получает `rewards = await get_reward_history(...)` и итерирует.

**Текущая структура:**
```python
@router.callback_query(F.data == "referral_rewards")
async def show_referral_rewards(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_language(user_id)

    rewards = await get_reward_history(user_id, limit=10)  # ← Единственные данные!

    if lang == 'en':
        text = "📅 <b>Bonus history</b>\n\n"
        if not rewards:
            text += "No referral activity yet.\n\n"
            text += "💡 <i>Share your link — the first paid plan of a friend will extend your subscription.</i>"
        else:
            for reward in rewards:  # ← Итерация по rewards
                if reward['reward_granted']:
                    # ... форматирование каждого reward
```

**get_reward_history возвращает (bot/services/affiliate.py:472-494):**
```python
[
    {
        'referred_user_id': int,
        'joined_at': datetime,
        'reward_granted': bool,
        'reward_months': int,
        'reward_granted_at': datetime or None,
    },
    ...
]
```

**РЕШЕНИЕ:**

НЕ добавлять новые переменные! Просто изменить тексты:

**В `bot/routers/referral.py:194-267`:**

**ЗАМЕНИТЬ текст заголовка и хинта:**

```python
if lang == 'en':
    text = "📅 <b>Referral History</b>\n\n"  # Было: Bonus history
    if not rewards:
        text += "No referral activity yet.\n\n"
        text += (
            "ℹ️ <i>Subscription extension bonus discontinued as of Nov 12, 2025.\n"
            "Connect to Telegram Stars Affiliate Program to earn from referrals.</i>"
        )
    else:
        # ✅ СОХРАНИТЬ СУЩЕСТВУЮЩУЮ ИТЕРАЦИЮ:
        for reward in rewards:
            if reward['reward_granted']:
                granted_at = reward['reward_granted_at'].strftime('%d.%m.%Y') if reward['reward_granted_at'] else '—'
                months_text = '1 month' if reward['reward_months'] == 1 else f"{reward['reward_months']} months"
                text += (
                    f"✅ {granted_at}\n"
                    f"   Bonus: {months_text}\n"
                    f"   Referred user: {reward['referred_user_id']}\n\n"
                )
            else:
                joined = reward['joined_at'].strftime('%d.%m.%Y') if reward.get('joined_at') else '—'
                text += (
                    f"⏳ {joined}\n"
                    "   Waiting for the first payment\n"
                    f"   Referred user: {reward['referred_user_id']}\n\n"
                )

        # ДОБАВИТЬ ПОСЛЕ ИТЕРАЦИИ:
        text += (
            "\nℹ️ <i>Subscription extension discontinued (Nov 12, 2025).\n"
            "Future rewards via Telegram Stars Program.</i>"
        )
else:
    text = "📅 <b>История рефералов</b>\n\n"  # Было: История бонусов
    if not rewards:
        text += "Пока нет данных.\n\n"
        text += (
            "ℹ️ <i>Бонус продления подписки отключен с 12.11.2025.\n"
            "Подключитесь к программе Telegram Stars для заработка на рефералах.</i>"
        )
    else:
        # ✅ СОХРАНИТЬ СУЩЕСТВУЮЩУЮ ИТЕРАЦИЮ:
        for reward in rewards:
            if reward['reward_granted']:
                granted_at = reward['reward_granted_at'].strftime('%d.%m.%Y') if reward['reward_granted_at'] else '—'
                months_text = '1 месяц' if reward['reward_months'] == 1 else f"{reward['reward_months']} месяцев"
                text += (
                    f"✅ {granted_at}\n"
                    f"   Бонус: {months_text}\n"
                    f"   Пользователь: {reward['referred_user_id']}\n\n"
                )
            else:
                joined = reward['joined_at'].strftime('%d.%m.%Y') if reward.get('joined_at') else '—'
                text += (
                    f"⏳ {joined}\n"
                    "   Ожидаем первую оплату\n"
                    f"   Пользователь: {reward['referred_user_id']}\n\n"
                )

        # ДОБАВИТЬ ПОСЛЕ ИТЕРАЦИИ:
        text += (
            "\nℹ️ <i>Продление подписки отключено (12.11.2025).\n"
            "Будущие вознаграждения через Telegram Stars Program.</i>"
        )
```

---

### Проблема #4: start.py - план не указывает точное место изменения

**Файл:** `bot/routers/start.py:300-348`
**Проблема:** План дает пример с переменными которых нет в реальном коде. Реальная структура:

```python
# Строки 301-321:
referral_message = ""
if is_new_user and referral_code and not utm_data:
    # ... обработка
    if affiliate_referral:
        if display_lang == 'en':
            referral_message = (
                "\n\n🤝 You joined via an affiliate link! "
                "Your friend will get a one-time subscription extension matching your first plan."
            )
        else:
            referral_message = (
                "\n\n🤝 Вы перешли по партнёрской ссылке! "
                "Ваш друг получит однократное продление подписки на срок вашей первой покупки."
            )
```

**РЕШЕНИЕ:**

**В `bot/routers/start.py:312-321` ЗАМЕНИТЬ блок referral_message на:**

```python
if display_lang == 'en':
    referral_message = (
        "\n\n🤝 You joined via an affiliate link!\n"
        "ℹ️ <i>Note: Subscription extension bonus discontinued (Nov 12, 2025).\n"
        "Your friend can earn Stars via Telegram Affiliate Program.</i>"
    )
else:
    referral_message = (
        "\n\n🤝 Вы перешли по партнёрской ссылке!\n"
        "ℹ️ <i>Примечание: Бонус продления подписки отключен (12.11.2025).\n"
        "Ваш друг может зарабатывать Stars через программу Telegram.</i>"
    )
```

---

### Проблема #5: Импорт не обновлен в subscription.py

**Файл:** `bot/routers/subscription.py:22`
**Проблема:** План говорит добавить `from bot.services.affiliate import update_affiliate_conversion_stats` в теле функции, но не упоминает что нужно удалить или изменить импорт на строке 22.

**Текущий импорт (строка 22):**
```python
from bot.services.affiliate import reward_referrer_subscription_extension
```

**РЕШЕНИЕ:**

**ЗАМЕНИТЬ строку 22 на:**
```python
from bot.services.affiliate import update_affiliate_conversion_stats
```

**Удалить старую функцию уже не нужно импортировать в теле функции!**

---

## ✅ ПРАВИЛЬНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ ИЗМЕНЕНИЙ

### Этап 1: Обновление bot/services/affiliate.py

1. **Добавить total_spent в get_referrer_stats()** (строки 402-423)
2. **Заглушка для reward_referrer_subscription_extension()** (строки 216-362)
3. **Новая функция update_affiliate_conversion_stats()** (после строки 362)

### Этап 2: Обновление bot/routers/subscription.py

1. **Изменить импорт** (строка 22): `update_affiliate_conversion_stats` вместо `reward_referrer_subscription_extension`
2. **Заменить блок вызова** (строки 956-1012)

### Этап 3: Обновление UI в bot/routers/referral.py

1. **Добавить Telegram Program блок** в get_referral_info_text() (перед строкой 98)
2. **Добавить кнопку Telegram Program** в get_referral_keyboard() (строки 26-58)
3. **Добавить handler show_telegram_program_info()** (после строки 139)
4. **Обновить тексты** в show_referral_rewards() (строки 194-267)

### Этап 4: Обновление приветствия в bot/routers/start.py

1. **Изменить referral_message** (строки 312-321)

---

### Проблема #6: Клавиатура - несуществующий код

**Файл:** `bot/routers/referral.py:26-58`
**Проблема:** План предлагал создать переменные `btn_*` и массив `keyboard = [...]`, но реальный код использует `InlineKeyboardBuilder`.

**Реальная структура:**
```python
def get_referral_keyboard(lang: str = 'ru', share_url: str = None, share_text: str = None):
    builder = InlineKeyboardBuilder()

    # Кнопка Share через builder.row()
    if share_url and share_text:
        builder.row(InlineKeyboardButton(...))

    # Остальные через builder.button()
    builder.button(text="📊 Статистика" if lang == 'ru' else "📊 Statistics", callback_data="referral_stats")
    builder.button(text="📅 История бонусов" if lang == 'ru' else "📅 Bonus history", callback_data="referral_rewards")
    builder.button(text=get_text('back', lang), callback_data="menu_subscription")
    builder.button(text=get_text('close', lang), callback_data="close")  # ← НЕ "delete_message"!

    builder.adjust(1)
    return builder.as_markup()
```

**РЕШЕНИЕ:**

**В `bot/routers/referral.py` ПОСЛЕ строки 38 (после кнопки Share) ДОБАВИТЬ:**
```python
    # НОВАЯ КНОПКА: Telegram Stars Program
    builder.button(
        text="📖 Telegram Stars Program",
        callback_data="referral_telegram_program"
    )
```

**НЕ делать:**
- ❌ НЕ создавать переменные `btn_telegram_program`, `btn_stats` и т.д.
- ❌ НЕ создавать массив `keyboard = [...]`
- ❌ НЕ использовать `callback_data="delete_message"` для Close (правильно: `"close"`)

---

## 📋 ЧЕКЛИСТ ВАЛИДАЦИИ

После всех изменений проверить:

- [ ] `get_referrer_stats()` возвращает `total_spent` во всех return блоках
- [ ] Импорт в `subscription.py:22` изменен на `update_affiliate_conversion_stats`
- [ ] Текст формируется в `get_referral_info_text()`, а НЕ в `show_referral_menu()`
- [ ] `show_referral_rewards()` использует только данные из `get_reward_history()`
- [ ] `start.py` изменяет блок со строками 312-321 с переменной `display_lang`
- [ ] Все callback используют `referral_stats` а не `referral_detailed_stats`
- [ ] F() expressions не логируются напрямую
- [ ] `get_referral_keyboard()` использует `builder.button()` а не массив
- [ ] Callback для Close кнопки: `"close"` а НЕ `"delete_message"`

---

**Дата:** 12.11.2025
**Статус:** ✅ Готово к применению
**Цель:** Точное соответствие реальному коду
