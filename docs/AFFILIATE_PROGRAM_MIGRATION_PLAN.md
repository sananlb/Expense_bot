# План миграции реферальной программы на Telegram Stars (MTProto API)

> Дата создания: 12.11.2025
> Дата обновления: 12.11.2025 (НОВАЯ ВЕРСИЯ - интеграция MTProto API)
> Статус: ✅ Фаза 1 завершена | 🚧 Фаза 2 в процессе
> Вариант: Полная интеграция с Telegram Stars Affiliate Program

---

## 📋 Содержание

1. [Обзор изменений](#обзор-изменений)
2. [Что уже сделано (Фаза 1)](#что-уже-сделано-фаза-1)
3. [Что нужно сделать (Фаза 2)](#что-нужно-сделать-фаза-2)
4. [Архитектура решения](#архитектура-решения)
5. [Детальный план реализации](#детальный-план-реализации)
6. [Чеклист выполнения](#чеклист-выполнения)
7. [Тестирование](#тестирование)
8. [Деплой](#деплой)

---

## Обзор изменений

### ✅ Фаза 1: Отключение старой системы бонусов (ЗАВЕРШЕНО)

**Что сделано:**
- ✅ Функция `reward_referrer_subscription_extension()` заменена на deprecated заглушку
- ✅ Добавлена `update_affiliate_conversion_stats()` для обновления статистики
- ✅ Удалены уведомления рефереру о продлении подписки
- ✅ Обновлены все тексты UI (убраны обещания продления)
- ✅ Добавлена информация о Telegram Stars Affiliate Program
- ✅ Исправлены критические баги (импорт InlineKeyboardMarkup, устаревшие тексты)

**Файлы изменены:**
- `bot/services/affiliate.py` (217-387 строки)
- `bot/routers/subscription.py` (17-22, 956-967 строки)
- `bot/routers/referral.py` (5, 67-407 строки)
- `bot/routers/start.py` (300-328 строки)

---

### 🚀 Фаза 2: Интеграция MTProto API для настоящих affiliate ссылок (НОВОЕ)

**Цель:** Автоматически создавать НАСТОЯЩИЕ affiliate ссылки Telegram, которые дают пользователям реальные Stars (до 20% от покупок).

**Проблема текущей реализации:**
- ❌ Наши ссылки `t.me/bot?start=ref_CODE` - только для внутренней статистики
- ❌ НЕ дают реальных Stars пользователям
- ❌ Пользователи должны вручную подключаться: Settings → My Stars → Earn Stars

**Решение:**
- ✅ Использовать **MTProto API** через библиотеку **pyrogram**
- ✅ Метод `payments.connectStarRefBot` для программного создания affiliate ссылок
- ✅ Пользователи получают настоящие ссылки автоматически при нажатии кнопки
- ✅ Stars приходят автоматически от Telegram

---

## Что уже сделано (Фаза 1)

### 1. bot/services/affiliate.py

**✅ Добавлено поле `total_spent`:**
```python
# get_referrer_stats() теперь агрегирует total_spent
payment_stats = referrals_qs.aggregate(total_spent=Sum('total_spent'))
total_spent = payment_stats['total_spent'] or 0

return {
    ...
    'total_spent': total_spent,  # Добавлено во все return пути
}
```

**✅ Функция награждения заменена на заглушку:**
```python
async def reward_referrer_subscription_extension(subscription):
    """
    DEPRECATED с 12.11.2025: Система продления подписки за рефералов отключена.
    """
    logger.info(f"[AFFILIATE] deprecated. No action taken.")
    return None
```

**✅ Новая функция для статистики:**
```python
async def update_affiliate_conversion_stats(subscription):
    """
    Обновляет статистику конверсий реферальной программы.
    НЕ начисляет бонусы - только обновляет счетчики.
    """
    # Обновление conversions, total_spent, first_payment_at
    ...
```

### 2. bot/routers/subscription.py

**✅ Изменен импорт:**
```python
from bot.services.affiliate import update_affiliate_conversion_stats
```

**✅ Заменен вызов (~50 строк удалено):**
```python
# Обновляем статистику реферальной программы (без бонусов)
try:
    stats_result = await update_affiliate_conversion_stats(subscription)
    if stats_result:
        logger.info(f"[AFFILIATE] Conversion stats updated: {stats_result}")
except Exception as e:
    logger.error(f"[AFFILIATE] Error updating conversion stats: {e}")
```

### 3. bot/routers/referral.py

**✅ Исправлен критический баг с импортом:**
```python
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
```

**✅ Обновлен текст (убрано обещание продления):**
```python
text = (
    "🔗 <b>Share with friends</b>\n\n"
    "Click the 'Share' button below to invite friends!\n\n"
    "📊 <b>Track your results</b>\n"
    "Monitor clicks and conversions from your referral link.\n"
    "See detailed statistics in real-time."
)
```

**✅ Добавлена информация о Telegram Program:**
```python
telegram_program_info = (
    "\n\n💰 <b>Want to earn Stars from referrals?</b>\n"
    "Connect to official Telegram Stars Affiliate Program!\n"
    "You'll receive up to 20% Stars from each referral's purchase.\n\n"
    ...
)
```

**✅ Добавлен handler с инструкцией:**
```python
@router.callback_query(F.data == 'referral_telegram_program')
async def show_telegram_program_info(callback: CallbackQuery):
    # Показывает детальную инструкцию подключения
    ...
```

**✅ Добавлена кнопка:**
```python
builder.button(
    text="📖 Telegram Stars Program",
    callback_data="referral_telegram_program"
)
```

**✅ Обновлены тексты истории:**
```python
text = "📅 <b>Referral History</b>\n\n"  # Было: Bonus history
if not rewards:
    text += (
        "ℹ️ <i>Subscription extension bonus discontinued as of Nov 12, 2025.\n"
        "Connect to Telegram Stars Affiliate Program to earn from referrals.</i>"
    )
```

### 4. bot/routers/start.py

**✅ Обновлено приветствие реферала:**
```python
referral_message = (
    "\n\n🤝 You joined via an affiliate link!\n"
    "ℹ️ <i>Note: Subscription extension bonus discontinued (Nov 12, 2025).\n"
    "Your friend can earn Stars via Telegram Affiliate Program.</i>"
)
```

---

## Что нужно сделать (Фаза 2)

### Архитектура решения

**Две системы параллельно:**

1. **Наши ссылки** (для внутренней статистики):
   - `t.me/bot?start=ref_CODE`
   - Отслеживание кликов, конверсий в БД
   - Модели: `AffiliateLink`, `AffiliateReferral`

2. **Telegram affiliate ссылки** (для Stars):
   - `t.me/bot?start=affiliate_TELEGRAM_CODE`
   - Создаются через MTProto API (`payments.connectStarRefBot`)
   - Stars выплачивает Telegram автоматически

**Почему две системы:**
- ✅ Наша БД - детальная статистика (кто, когда, сколько)
- ✅ Telegram - автоматические выплаты Stars
- ✅ Резервная копия данных (если Telegram API недоступен)

---

## Детальный план реализации

### ЭТАП 1: Подготовка (владелец бота делает один раз)

#### 1.1. Получение API_ID и API_HASH (5 минут)

**Шаги:**
1. Зайти на https://my.telegram.org
2. Авторизоваться своим номером телефона (номер владельца бота)
3. Перейти в **"API development tools"**
4. Нажать **"Create new application"**
5. Заполнить форму:
   - **App title:** "ExpenseBot Affiliate Client"
   - **Short name:** "expensebot"
   - **Platform:** "Other"
   - **Description:** "User client for affiliate program management"
6. Нажать **"Create application"**
7. Скопировать credentials:
   ```
   API_ID: 12345678 (число)
   API_HASH: abcdef1234567890abcdef1234567890 (строка)
   ```

**Добавить в `.env`:**
```bash
# Telegram MTProto API (для affiliate программы)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
```

**⚠️ ВАЖНО:**
- Эти credentials ТОЛЬКО для вашего аккаунта
- НЕ делитесь ими ни с кем
- НЕ коммитьте в Git (`.env` в `.gitignore`)

---

### ЭТАП 2: Установка зависимостей

#### 2.1. Добавить pyrogram в requirements.txt

**Файл:** `requirements.txt`

**ДОБАВИТЬ в конец файла:**
```txt
# MTProto API для Telegram Stars Affiliate Program
pyrogram==2.0.106
TgCrypto==1.2.5  # Ускоряет pyrogram (опционально, но рекомендуется)
```

**Установить локально:**
```bash
pip install pyrogram==2.0.106 TgCrypto==1.2.5
```

---

### ЭТАП 3: Создание скрипта первой авторизации User Client

#### 3.1. Создать скрипт setup_user_client.py

**Файл:** `setup_user_client.py` (в корне проекта)

**Создать новый файл:**
```python
"""
Скрипт для первой авторизации User Client Telegram MTProto API.
Запустить ОДИН РАЗ для создания файла сессии.

Использование:
    python setup_user_client.py

Вам понадобится:
    - Номер телефона владельца бота
    - Код подтверждения из Telegram (придет в личку)
    - (Опционально) 2FA пароль, если включен
"""

import asyncio
import os
from pyrogram import Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = "affiliate_user_client"

async def setup_user_client():
    """Первая авторизация User Client"""
    print("=" * 60)
    print("🔧 Настройка Telegram User Client для Affiliate Program")
    print("=" * 60)
    print()
    print("⚠️  ВАЖНО:")
    print("   - Используйте номер телефона ВЛАДЕЛЬЦА бота")
    print("   - Код подтверждения придет вам в личные сообщения Telegram")
    print("   - Этот процесс нужен ОДИН РАЗ")
    print()
    print("=" * 60)
    print()

    # Создаем клиент
    app = Client(
        SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="."  # Файл сессии сохранится в корне проекта
    )

    try:
        # Запускаем клиент (произойдет авторизация)
        await app.start()

        # Получаем информацию о текущем пользователе
        me = await app.get_me()

        print()
        print("=" * 60)
        print("✅ Успешно авторизован!")
        print("=" * 60)
        print(f"👤 Имя: {me.first_name} {me.last_name or ''}")
        print(f"📱 Номер: +{me.phone_number}")
        print(f"🆔 ID: {me.id}")
        print(f"📁 Файл сессии: {SESSION_NAME}.session")
        print("=" * 60)
        print()
        print("🎉 Настройка завершена!")
        print("   Файл сессии создан, больше авторизация не нужна.")
        print("   Можете закрыть это окно.")
        print()

        # Останавливаем клиент
        await app.stop()

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Ошибка авторизации!")
        print("=" * 60)
        print(f"   {e}")
        print()
        print("Возможные причины:")
        print("   1. Неверный API_ID или API_HASH в .env")
        print("   2. Неправильный номер телефона")
        print("   3. Неправильный код подтверждения")
        print("   4. Проблемы с интернет-соединением")
        print()
        raise

if __name__ == "__main__":
    # Запускаем настройку
    asyncio.run(setup_user_client())
```

#### 3.2. Запустить скрипт первой авторизации

**В командной строке:**
```bash
python setup_user_client.py
```

**Что будет происходить:**
```
🔧 Настройка Telegram User Client для Affiliate Program
=========================================

⚠️  ВАЖНО:
   - Используйте номер телефона ВЛАДЕЛЬЦА бота
   - Код подтверждения придет вам в личные сообщения Telegram

Enter phone number or bot token: +79001234567
Is "+79001234567" correct? (y/N): y

Enter the code you received: 12345

✅ Успешно авторизован!
=========================================
👤 Имя: Иван Иванов
📱 Номер: +79001234567
🆔 ID: 123456789
📁 Файл сессии: affiliate_user_client.session
=========================================

🎉 Настройка завершена!
```

**Результат:**
- ✅ Создан файл `affiliate_user_client.session`
- ✅ Больше никакая авторизация не требуется
- ✅ Бот может использовать этот клиент для создания affiliate ссылок

**⚠️ ВАЖНО: Добавить .session в .gitignore**
```bash
# В файл .gitignore добавить:
*.session
```

---

### ЭТАП 4: Создание User Client Service

#### 4.1. Создать bot/services/user_client.py

**Файл:** `bot/services/user_client.py` (новый файл)

**Создать новый файл:**
```python
"""
User Client Service для Telegram MTProto API.
Используется для создания настоящих affiliate ссылок через payments.connectStarRefBot.
"""

import os
import logging
from pyrogram import Client
from pyrogram.raw import functions
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton instance
_user_client: Optional[Client] = None

def get_user_client() -> Client:
    """
    Получить User Client для MTProto API.

    Returns:
        Client: Pyrogram client для MTProto методов
    """
    global _user_client

    if _user_client is None:
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if not api_id or not api_hash:
            raise ValueError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file. "
                "Run 'python setup_user_client.py' to configure."
            )

        _user_client = Client(
            "affiliate_user_client",
            api_id=int(api_id),
            api_hash=api_hash,
            workdir="."  # Файл сессии в корне проекта
        )

        logger.info("[USER_CLIENT] Pyrogram User Client initialized")

    return _user_client


async def start_user_client():
    """Запустить User Client (вызывается при старте бота)"""
    client = get_user_client()

    if not client.is_connected:
        try:
            await client.start()
            me = await client.get_me()
            logger.info(
                f"[USER_CLIENT] Connected as {me.first_name} "
                f"(ID: {me.id}, Phone: +{me.phone_number})"
            )
        except Exception as e:
            logger.error(f"[USER_CLIENT] Failed to start: {e}", exc_info=True)
            raise


async def stop_user_client():
    """Остановить User Client (вызывается при остановке бота)"""
    client = get_user_client()

    if client.is_connected:
        try:
            await client.stop()
            logger.info("[USER_CLIENT] Disconnected")
        except Exception as e:
            logger.error(f"[USER_CLIENT] Error stopping: {e}", exc_info=True)


async def create_affiliate_link(user_id: int, bot_username: str) -> Optional[str]:
    """
    Создать НАСТОЯЩУЮ affiliate ссылку Telegram для пользователя.

    Использует MTProto API метод payments.connectStarRefBot для программного
    создания affiliate ссылки, которая дает пользователю реальные Stars (до 20%).

    Args:
        user_id: Telegram ID пользователя (кто будет affiliate)
        bot_username: Username бота (например, "your_bot")

    Returns:
        str: Affiliate ссылка от Telegram или None при ошибке

    Example:
        >>> url = await create_affiliate_link(123456789, "your_bot")
        >>> print(url)
        "https://t.me/your_bot?start=affiliate_XYZ123ABC"
    """
    client = get_user_client()

    if not client.is_connected:
        logger.error("[USER_CLIENT] Client not connected, starting...")
        await start_user_client()

    try:
        # Вызываем MTProto API метод payments.connectStarRefBot
        result = await client.invoke(
            functions.payments.ConnectStarRefBot(
                bot=bot_username,  # Username бота
                peer=user_id       # ID пользователя-affiliate
            )
        )

        # Получаем affiliate ссылку из ответа
        affiliate_url = result.url

        logger.info(
            f"[USER_CLIENT] Created affiliate link for user {user_id}: "
            f"{affiliate_url}"
        )

        return affiliate_url

    except Exception as e:
        logger.error(
            f"[USER_CLIENT] Failed to create affiliate link for user {user_id}: {e}",
            exc_info=True
        )
        return None
```

---

### ЭТАП 5: Интеграция MTProto в affiliate.py

#### 5.1. Обновить bot/services/affiliate.py

**Файл:** `bot/services/affiliate.py`

**ДОБАВИТЬ импорт в начале файла (после существующих импортов):**
```python
# НОВЫЙ ИМПОРТ для MTProto API
from bot.services.user_client import create_affiliate_link
```

**НАЙТИ функцию `get_or_create_affiliate_link` (примерно строки 90-150)**

**ЗАМЕНИТЬ её на новую версию:**
```python
async def get_or_create_affiliate_link(user_id: int, bot_username: str) -> 'AffiliateLink':
    """
    Получить или создать реферальную ссылку для пользователя.

    НОВОЕ (12.11.2025): Создает ДВЕ ссылки параллельно:
    1. Нашу ссылку (t.me/bot?start=ref_CODE) - для внутренней статистики
    2. Telegram ссылку через MTProto API - для настоящих Stars

    Args:
        user_id: Telegram ID пользователя
        bot_username: Username бота

    Returns:
        AffiliateLink: Объект со ссылками (telegram_link содержит affiliate ссылку от Telegram)
    """
    try:
        profile = await Profile.objects.aget(telegram_id=user_id)

        # Проверяем существующую ссылку
        affiliate_link, created = await AffiliateLink.objects.aget_or_create(
            profile=profile,
            defaults={
                'affiliate_code': generate_affiliate_code(),
                'telegram_link': f"https://t.me/{bot_username}?start=ref_GENERATING",
                'clicks': 0,
                'conversions': 0,
            }
        )

        if created:
            logger.info(f"[AFFILIATE] Created new link for user {user_id}")

        # НОВОЕ: Создаем настоящую affiliate ссылку через MTProto API
        try:
            telegram_affiliate_url = await create_affiliate_link(user_id, bot_username)

            if telegram_affiliate_url:
                # Сохраняем настоящую Telegram affiliate ссылку
                affiliate_link.telegram_link = telegram_affiliate_url
                await affiliate_link.asave(update_fields=['telegram_link'])

                logger.info(
                    f"[AFFILIATE] Updated link for user {user_id} with Telegram affiliate URL: "
                    f"{telegram_affiliate_url}"
                )
            else:
                # Fallback: используем нашу ссылку если MTProto API недоступен
                fallback_link = f"https://t.me/{bot_username}?start=ref_{affiliate_link.affiliate_code}"
                affiliate_link.telegram_link = fallback_link
                await affiliate_link.asave(update_fields=['telegram_link'])

                logger.warning(
                    f"[AFFILIATE] MTProto API unavailable, using fallback link for user {user_id}"
                )

        except Exception as mtproto_error:
            logger.error(
                f"[AFFILIATE] MTProto API error for user {user_id}: {mtproto_error}",
                exc_info=True
            )

            # Fallback: наша ссылка
            fallback_link = f"https://t.me/{bot_username}?start=ref_{affiliate_link.affiliate_code}"
            affiliate_link.telegram_link = fallback_link
            await affiliate_link.asave(update_fields=['telegram_link'])

        return affiliate_link

    except Exception as e:
        logger.error(f"[AFFILIATE] Error creating link for user {user_id}: {e}", exc_info=True)
        raise
```

---

### ЭТАП 6: Обновление UI для показа настоящих affiliate ссылок

#### 6.1. Обновить bot/routers/referral.py

**Файл:** `bot/routers/referral.py`

**НАЙТИ функцию `get_referral_info_text` (строки 67-125)**

**ЗАМЕНИТЬ блок формирования текста (строки 85-103) на:**
```python
    if lang == 'en':
        share_message = (
            "Try Coins Bot — I've used it to get my budget in order! "
            "Track expenses easily right in Telegram."
        )
        text = (
            "🔗 <b>Your Affiliate Link</b>\n\n"
            "Share this link with friends and earn Stars!\n\n"
            "💰 <b>You'll receive:</b>\n"
            "• Up to 20% Stars from each friend's purchase\n"
            "• Automatic payouts from Telegram\n"
            "• No limits on earnings\n\n"
            "📊 <b>Track statistics</b>\n"
            "Monitor clicks and conversions in real-time."
        )
    else:
        share_message = (
            "Попробуй Coins Bot — я с его помощью навёл порядок в бюджете! "
            "Легко веду учёт трат прямо в Telegram."
        )
        text = (
            "🔗 <b>Ваша реферальная ссылка</b>\n\n"
            "Делитесь ей с друзьями и зарабатывайте Stars!\n\n"
            "💰 <b>Вы получите:</b>\n"
            "• До 20% Stars от каждой покупки друзей\n"
            "• Автоматические выплаты от Telegram\n"
            "• Без ограничений по сумме\n\n"
            "📊 <b>Отслеживайте статистику</b>\n"
            "Следите за кликами и конверсиями в реальном времени."
        )
```

**УДАЛИТЬ блок telegram_program_info (строки 105-117) - больше не нужен:**
```python
# УДАЛИТЬ ЭТИ СТРОКИ (105-117):
# Добавляем информацию о Telegram Stars Affiliate Program
if lang == 'en':
    telegram_program_info = (
        ...
    )
else:
    telegram_program_info = (
        ...
    )

text = text + telegram_program_info  # УДАЛИТЬ ЭТУ СТРОКУ
```

**ИТОГОВАЯ структура функции:**
```python
async def get_referral_info_text(...):
    affiliate_link = await get_or_create_affiliate_link(...)  # Создает настоящую ссылку
    stats = await get_referrer_stats(...)

    # Формируем текст про Stars
    text = "💰 Вы получите до 20% Stars..."

    # БЕЗ telegram_program_info - он больше не нужен!

    return text, True, share_message, affiliate_link.telegram_link  # Уже содержит настоящую ссылку
```

#### 6.2. Удалить handler show_telegram_program_info

**Файл:** `bot/routers/referral.py`

**УДАЛИТЬ ПОЛНОСТЬЮ handler (строки 163-270):**
```python
# УДАЛИТЬ ВСЮ ЭТУ ФУНКЦИЮ:
@router.callback_query(F.data == 'referral_telegram_program')
async def show_telegram_program_info(callback: CallbackQuery):
    ...  # Весь код функции
```

**Причина:** Больше не нужна инструкция "как подключиться вручную" - всё работает автоматически!

#### 6.3. Удалить кнопку "Telegram Stars Program"

**Файл:** `bot/routers/referral.py`

**НАЙТИ функцию `get_referral_keyboard` (строки 26-63)**

**УДАЛИТЬ блок кнопки (строки 40-44):**
```python
# УДАЛИТЬ ЭТИ СТРОКИ:
# НОВАЯ КНОПКА: Telegram Stars Program
builder.button(
    text="📖 Telegram Stars Program",
    callback_data="referral_telegram_program"
)
```

**Причина:** Кнопка больше не нужна - пользователи сразу получают настоящие ссылки!

---

### ЭТАП 7: Запуск User Client при старте бота

#### 7.1. Обновить bot/main.py

**Файл:** `bot/main.py`

**ДОБАВИТЬ импорт (после существующих импортов):**
```python
from bot.services.user_client import start_user_client, stop_user_client
```

**НАЙТИ функцию `on_startup` (примерно строки 30-50)**

**ДОБАВИТЬ в конец функции:**
```python
async def on_startup(bot: Bot, *args, **kwargs):
    # ... существующий код ...

    # ДОБАВИТЬ В КОНЕЦ:
    # Запускаем User Client для affiliate программы
    try:
        await start_user_client()
        logger.info("User Client for affiliate program started successfully")
    except Exception as e:
        logger.error(f"Failed to start User Client: {e}", exc_info=True)
        logger.warning("Affiliate program will work in fallback mode (without real Stars)")
```

**НАЙТИ функцию `on_shutdown` (примерно строки 55-70)**

**ДОБАВИТЬ в конец функции:**
```python
async def on_shutdown(bot: Bot, *args, **kwargs):
    # ... существующий код ...

    # ДОБАВИТЬ В КОНЕЦ:
    # Останавливаем User Client
    try:
        await stop_user_client()
        logger.info("User Client stopped")
    except Exception as e:
        logger.error(f"Error stopping User Client: {e}", exc_info=True)
```

---

## Чеклист выполнения

### Подготовка (владелец бота)

- [ ] **Получить API_ID и API_HASH** (https://my.telegram.org)
- [ ] **Добавить credentials в `.env`**
- [ ] **Убедиться что `.env` в `.gitignore`**

### Установка

- [ ] **Добавить pyrogram в `requirements.txt`**
- [ ] **Установить зависимости:** `pip install pyrogram TgCrypto`

### Настройка User Client

- [ ] **Создать скрипт `setup_user_client.py`**
- [ ] **Запустить скрипт:** `python setup_user_client.py`
- [ ] **Ввести номер телефона владельца бота**
- [ ] **Ввести код подтверждения из Telegram**
- [ ] **Проверить создание файла `affiliate_user_client.session`**
- [ ] **Добавить `*.session` в `.gitignore`**

### Код

- [ ] **Создать `bot/services/user_client.py`**
- [ ] **Обновить `bot/services/affiliate.py`** (импорт + get_or_create_affiliate_link)
- [ ] **Обновить `bot/routers/referral.py`** (текст + удалить старую кнопку/handler)
- [ ] **Обновить `bot/main.py`** (on_startup + on_shutdown)

### Проверка синтаксиса

- [ ] **Проверить `user_client.py`:** `python -m py_compile bot/services/user_client.py`
- [ ] **Проверить `affiliate.py`:** `python -m py_compile bot/services/affiliate.py`
- [ ] **Проверить `referral.py`:** `python -m py_compile bot/routers/referral.py`
- [ ] **Проверить `main.py`:** `python -m py_compile bot/main.py`

### Тестирование локально

- [ ] **Запустить бота:** `python run_bot.py`
- [ ] **Проверить логи:** User Client должен подключиться
- [ ] **Открыть реферальное меню в боте**
- [ ] **Проверить что ссылка содержит `start=affiliate_...`** (не `ref_...`)
- [ ] **Нажать "Поделиться" - проверить что ссылка корректная**
- [ ] **Создать тестовую покупку и проверить начисление Stars**

---

## Тестирование

### Сценарий 1: Создание affiliate ссылки

**Шаги:**
1. Открыть бота
2. Нажать кнопку реферальной программы
3. Посмотреть на ссылку

**Ожидаемый результат:**
- ✅ Ссылка формата `t.me/bot?start=affiliate_XXX` (НЕ `ref_XXX`)
- ✅ В логах: `[USER_CLIENT] Created affiliate link for user ...`
- ✅ Текст обещает до 20% Stars
- ✅ Нет кнопки "📖 Telegram Stars Program"

### Сценарий 2: Шаринг ссылки

**Шаги:**
1. Скопировать affiliate ссылку
2. Отправить другу (или открыть в другом аккаунте)
3. Друг регистрируется и покупает подписку
4. Проверить начисление Stars

**Ожидаемый результат:**
- ✅ Друг успешно регистрируется
- ✅ При покупке подписки рефереру приходят Stars (проверить в Telegram: Settings → My Stars)
- ✅ Статистика в боте обновляется (conversions +1, total_spent +150)

### Сценарий 3: Fallback при недоступности MTProto

**Шаги:**
1. Остановить User Client (временно отключить)
2. Попытаться создать affiliate ссылку
3. Проверить что работает fallback

**Ожидаемый результат:**
- ✅ В логах: `[AFFILIATE] MTProto API unavailable, using fallback link`
- ✅ Показывается наша ссылка `t.me/bot?start=ref_CODE`
- ✅ Статистика работает
- ❌ Stars НЕ начисляются (ожидаемо - fallback режим)

### Сценарий 4: Статистика

**Шаги:**
1. Открыть "📊 Статистика"
2. Проверить все метрики

**Ожидаемый результат:**
- ✅ Клики отображаются корректно
- ✅ Конверсии считаются правильно
- ✅ total_spent показывает сумму Stars
- ✅ Процент конверсии корректный

---

## Деплой

### 1. Подготовка на локальной машине

```bash
# Проверить что всё работает локально
python run_bot.py

# Убедиться что файл сессии создан
ls -la affiliate_user_client.session

# Проверить .gitignore
cat .gitignore | grep session  # Должно быть: *.session
```

### 2. Git commit

```bash
git status

# НЕ добавляем .session файлы в git!
# НЕ добавляем .env с API credentials!

git add requirements.txt
git add setup_user_client.py
git add bot/services/user_client.py
git add bot/services/affiliate.py
git add bot/routers/referral.py
git add bot/main.py
git add docs/AFFILIATE_PROGRAM_MIGRATION_PLAN.md

git commit -m "Feature: Интеграция MTProto API для настоящих Telegram Stars affiliate ссылок

Фаза 2: Полная интеграция с Telegram Stars Affiliate Program

Изменения:
- Добавлена зависимость pyrogram для MTProto API
- Создан User Client service (bot/services/user_client.py)
- Добавлен скрипт первой авторизации (setup_user_client.py)
- Обновлена get_or_create_affiliate_link для создания настоящих ссылок
- Обновлен UI: убрана инструкция, обновлены тексты про Stars
- User Client запускается автоматически при старте бота

Результат:
- ✅ Пользователи автоматически получают настоящие affiliate ссылки
- ✅ Stars начисляются автоматически от Telegram (до 20%)
- ✅ Никакой ручной настройки для пользователей
- ✅ Fallback на нашу ссылку если MTProto API недоступен

Настройка для владельца бота:
1. Получить API_ID и API_HASH на https://my.telegram.org
2. Добавить в .env: TELEGRAM_API_ID и TELEGRAM_API_HASH
3. Запустить: python setup_user_client.py
4. Ввести номер телефона и код подтверждения
5. Готово!

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin master
```

### 3. Деплой на сервер

**⚠️ ВАЖНО: Нужно настроить User Client на сервере!**

```bash
# 1. Подключиться к серверу
ssh batman@94.198.220.155

# 2. Перейти в директорию проекта
cd /home/batman/expense_bot

# 3. Обновить код
git pull origin master

# 4. ВАЖНО: Добавить API credentials в .env на сервере
nano .env
# Добавить строки:
# TELEGRAM_API_ID=12345678
# TELEGRAM_API_HASH=abcdef123...
# Сохранить: Ctrl+O, Enter, Ctrl+X

# 5. Установить зависимости (в venv или контейнере)
pip install pyrogram TgCrypto

# 6. КРИТИЧНО: Запустить первую авторизацию User Client
python setup_user_client.py
# Ввести СВОЙ номер телефона (владельца бота)
# Ввести код из Telegram

# 7. Проверить создание файла сессии
ls -la affiliate_user_client.session

# 8. Перезапустить контейнеры
docker-compose down
docker-compose build --no-cache expense_bot_app
docker-compose up -d

# 9. Проверить логи
docker-compose logs --tail=100 -f expense_bot_app

# Должно быть в логах:
# [USER_CLIENT] Connected as ...
# [USER_CLIENT] Pyrogram User Client initialized
```

### 4. Smoke test на продакшене

1. Открыть бота в Telegram
2. Перейти в реферальное меню
3. Проверить ссылку: должна быть `start=affiliate_...`
4. Нажать "Поделиться"
5. Отправить ссылку в Saved Messages
6. Открыть ссылку из другого аккаунта
7. Зарегистрироваться и купить подписку
8. Проверить в Telegram (Settings → My Stars) что Stars пришли

### 5. Откат (если что-то пошло не так)

```bash
cd /home/batman/expense_bot

# Откатить к предыдущей версии
git log --oneline -5
git reset --hard <hash_предыдущего_коммита>

# Перезапустить
docker-compose down
docker-compose up -d
```

---

## Преимущества нового подхода

### ✅ Для пользователей:

**Было (Фаза 1):**
1. Получить ссылку в боте → статистика работает
2. ВРУЧНУЮ идти: Settings → My Stars → Earn Stars
3. ВРУЧНУЮ найти бота в списке программ
4. ВРУЧНУЮ подключиться
5. Получить ДРУГУЮ ссылку от Telegram
6. Делиться ей → получать Stars

**Стало (Фаза 2):**
1. Получить ссылку в боте → **ГОТОВО!**
2. Делиться ей → **получать Stars автоматически**

**Результат:** В 6 раз проще! Один клик вместо 6 шагов.

### ✅ Для бизнеса:

- 📈 **Больше конверсия** - пользователи не бросают на полпути
- 💰 **Больше заработок** - все пользователи подключены к Stars
- 🎯 **Лучший UX** - никакой путаницы с двумя ссылками
- 📊 **Статистика работает** - наша БД сохраняется
- 🔄 **Fallback режим** - если MTProto недоступен, работает как раньше

### ✅ Для разработчика:

- 🛡️ **Безопасно** - User Client авторизован только от владельца
- 🔐 **Credentials защищены** - всё в .env, не коммитится в git
- 🧩 **Модульная архитектура** - user_client.py изолирован
- 📝 **Логирование** - все действия логируются
- ⚡ **Быстро** - MTProto API быстрее чем ручная настройка

---

## FAQ

### ❓ Безопасно ли хранить файл сессии?

**✅ Да, если:**
- Файл `.session` в `.gitignore` (НЕ коммитится в git)
- Доступ к серверу только у владельца
- User Client авторизован от аккаунта владельца бота

**⚠️ ВАЖНО:**
- Не делитесь файлом `.session` ни с кем
- Не коммитьте его в публичный репозиторий

### ❓ Что если забыл добавить .session в .gitignore?

**Срочные действия:**
1. Удалить файл из git: `git rm --cached *.session`
2. Добавить в `.gitignore`: `*.session`
3. Коммит: `git commit -m "Remove session file"`
4. **ПЕРЕСОЗДАТЬ сессию:** `python setup_user_client.py`

### ❓ Можно ли использовать бот-токен вместо User Client?

**❌ Нет.** MTProto API метод `payments.connectStarRefBot` доступен **только** для User Client (авторизация через номер телефона). Bot API (бот-токен) **не поддерживает** эти методы.

### ❓ Что если User Client отключается?

**Автоматический fallback:**
```python
try:
    telegram_url = await create_affiliate_link(user_id, bot_username)
except:
    # Fallback: используем нашу ссылку
    fallback_link = f"t.me/bot?start=ref_{code}"
```

**Результат:**
- ✅ Бот продолжает работать
- ✅ Статистика сохраняется
- ❌ Stars НЕ начисляются (но пользователи видят ссылку)

### ❓ Сколько стоит API_ID и API_HASH?

**🆓 Бесплатно!** Telegram предоставляет их бесплатно на https://my.telegram.org

### ❓ Можно ли изменить процент комиссии (20%)?

**Да,** но только через UI Telegram:
1. Открыть профиль бота в Telegram (от аккаунта создателя)
2. Edit → Affiliate Program
3. Изменить commission rate (максимум 20%)

**Нельзя** программно через API изменить процент для конкретного пользователя.

---

## Контакты и поддержка

**Вопросы по реализации:**
- 📖 Документация Telegram MTProto API: https://core.telegram.org/api/bots/referrals
- 📚 Pyrogram документация: https://docs.pyrogram.org

**Регистрация API credentials:**
- 🔑 https://my.telegram.org → API development tools

**Официальная программа:**
- ⭐ https://telegram.org/tour/affiliate-programs

---

**Статус:** 🚀 Готов к реализации
**Следующий шаг:** Начать ЭТАП 1 - Подготовка (получение API_ID и API_HASH)

**Дата последнего обновления:** 12.11.2025 23:45
