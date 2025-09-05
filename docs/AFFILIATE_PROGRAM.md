# 📊 Документация по реферальной программе Telegram Stars

> Последнее обновление: 05.09.2025

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Текущая реализация подписок](#текущая-реализация-подписок)
3. [Telegram Stars Affiliate Program](#telegram-stars-affiliate-program)
4. [План интеграции](#план-интеграции)
5. [Техническая реализация](#техническая-реализация)
6. [Статус разработки](#статус-разработки)

---

## 🎯 Обзор системы

### Цель
Реализация реферальной программы через нативную систему Telegram Stars Affiliate Programs, позволяющей пользователям и партнёрам получать комиссию за привлечение новых платящих клиентов.

### Ключевые преимущества
- ✅ Автоматическое начисление комиссий через Telegram
- ✅ Прозрачная система учёта
- ✅ Нативная интеграция с Telegram Stars
- ✅ Поддержка любых типов платежей (месячные и полугодовые)

---

## 💳 Текущая реализация подписок

### Архитектура системы

**⚠️ ВАЖНО:** Бот НЕ использует настоящие подписки Telegram Stars с автопродлением!

#### Как работает сейчас:

1. **Одноразовые платежи** через `send_invoice` с валютой `XTR` (Telegram Stars)
2. **Ручное управление** периодами подписки в базе данных
3. **Нет параметра** `subscription_period` в инвойсах
4. **Поддержка двух тарифов:**
   - Месячная подписка: 150 звёзд (30 дней)
   - Полугодовая подписка: 600 звёзд (180 дней)

#### Структура данных

**Модель Subscription** (`expenses/models.py`):
```python
class Subscription(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=[
        ('trial', 'Trial'),
        ('month', 'Monthly'),
        ('six_months', 'Six Months')
    ])
    payment_method = models.CharField(max_length=20, choices=[
        ('trial', 'Trial'),
        ('stars', 'Telegram Stars'),
        ('referral', 'Referral Bonus')
    ])
    amount = models.IntegerField()  # Количество звёзд
    telegram_payment_charge_id = models.CharField(max_length=255, blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Тарифы (`bot/routers/subscription.py`):
```python
SUBSCRIPTION_PRICES = {
    'month': {
        'stars': 150,
        'months': 1,
        'title': 'Подписка на месяц',
        'description': 'Полный доступ ко всем функциям на 1 месяц'
    },
    'six_months': {
        'stars': 600,
        'months': 6,
        'title': 'Подписка на 6 месяцев',
        'description': 'Полный доступ ко всем функциям на 6 месяцев'
    }
}
```

### Влияние на реферальную программу

| Аспект | Текущая система | Настоящие подписки Telegram |
|--------|-----------------|----------------------------|
| **Полугодовые платежи** | ✅ Работают (600 звёзд) | ❌ Только месячные |
| **Комиссия рефереру** | ✅ С любой суммы платежа | ✅ Ежемесячно с подписки |
| **Автопродление** | ❌ Нет | ✅ Есть |
| **Рекуррентный доход** | ❌ Только с новых платежей | ✅ С каждого продления |

---

## 🌟 Telegram Stars Affiliate Program

### Официальная документация

- [Affiliate programs](https://core.telegram.org/api/bots/referrals)
- [Bot Payments API](https://core.telegram.org/bots/payments-stars) 
- [Star subscriptions](https://core.telegram.org/api/subscriptions)
- [Terms of Service](https://telegram.org/tos/affiliate-program)

### Ключевые ограничения API (2024)

1. **Подписки:** Только месячный период (30 дней), максимум указан в `stars_subscription_amount_max`
2. **Комиссии:** От `starref_min_commission_permille` до `starref_max_commission_permille` (в промилле)
3. **Холд:** 21 день на вывод комиссий
4. **Изменения:** Нельзя снизить ставку или срок, только повысить или завершить программу

### Как работают комиссии

#### Для одноразовых платежей (наш случай):
- Пользователь платит 150 звёзд → реферер получает 15 звёзд (при 10%)
- Пользователь платит 600 звёзд → реферер получает 60 звёзд (при 10%)
- Комиссия начисляется **один раз** с каждого платежа

#### Для настоящих подписок (если бы использовали):
- Пользователь платит 100 звёзд/мес → реферер получает 10 звёзд ежемесячно
- Комиссии идут автоматически при каждом продлении

---

## 📝 План интеграции

### Этап 1: Подготовка (В процессе)

- [x] Изучить документацию Telegram Stars Affiliate
- [x] Проанализировать текущую систему подписок
- [x] Создать документацию
- [ ] Разработать модели данных

### Этап 2: Базовая интеграция

- [ ] Создать модель `AffiliateProgram` для хранения настроек
- [ ] Создать модель `AffiliateLink` для учёта реферальных ссылок  
- [ ] Создать модель `AffiliateCommission` для отслеживания комиссий
- [ ] Добавить миграции БД

### Этап 3: API интеграция

- [ ] Реализовать метод `create_affiliate_program()` через Bot API
- [ ] Реализовать метод `update_affiliate_program()` 
- [ ] Реализовать метод `get_affiliate_stats()`
- [ ] Добавить обработку affiliate параметров в `pre_checkout_query`

### Этап 4: Обработка ссылок

- [ ] Парсинг параметра `start` с affiliate ID
- [ ] Сохранение связи пользователь-реферер
- [ ] Валидация и проверка дублирования

### Этап 5: Начисление комиссий

- [ ] Обработка событий оплаты с учётом реферера
- [ ] Логирование транзакций через `payments.getStarsTransactions`
- [ ] Уведомления рефереру о начислениях

### Этап 6: Пользовательский интерфейс

- [ ] Команда `/affiliate` для получения реферальной ссылки
- [ ] Статистика привлечённых пользователей
- [ ] История начислений
- [ ] Админ-панель для управления программой

### Этап 7: Тестирование

- [ ] Unit-тесты моделей и сервисов
- [ ] Интеграционные тесты с Test Payment Provider
- [ ] Тестирование на реальных транзакциях
- [ ] Проверка корректности начислений

---

## 🔧 Техническая реализация

### Новые модели данных

#### AffiliateProgram
```python
class AffiliateProgram(models.Model):
    """Настройки реферальной программы"""
    commission_permille = models.IntegerField()  # Комиссия в промилле (100 = 10%)
    duration_months = models.IntegerField(null=True, blank=True)  # Срок действия
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    telegram_program_id = models.CharField(max_length=255, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### AffiliateLink
```python
class AffiliateLink(models.Model):
    """Реферальные ссылки пользователей"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    affiliate_code = models.CharField(max_length=100, unique=True, db_index=True)
    telegram_link = models.URLField()  # t.me/bot?start=ref_CODE
    clicks = models.IntegerField(default=0)
    conversions = models.IntegerField(default=0)
    total_earned = models.IntegerField(default=0)  # В звёздах
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
```

#### AffiliateCommission
```python
class AffiliateCommission(models.Model):
    """История начислений комиссий"""
    referrer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='commissions_earned')
    referred = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='commissions_generated')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.IntegerField()  # Сумма платежа
    commission_amount = models.IntegerField()  # Комиссия в звёздах
    commission_rate = models.IntegerField()  # Ставка в промилле
    telegram_transaction_id = models.CharField(max_length=255, unique=True, null=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('hold', 'On Hold'),  # 21-дневный холд
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ])
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### API методы

#### Создание программы
```python
async def create_affiliate_program(bot: Bot, commission_permille: int, duration_months: Optional[int] = None):
    """Создать или обновить реферальную программу через Bot API"""
    # TODO: Использовать метод bots.updateStarRefProgram
    pass
```

#### Обработка реферальной ссылки
```python
async def process_referral_start(user_id: int, referral_code: str):
    """Обработать переход по реферальной ссылке"""
    # 1. Найти владельца кода
    # 2. Проверить, не является ли пользователь сам себе рефералом
    # 3. Сохранить связь реферер-реферал
    # 4. Увеличить счётчик кликов
    pass
```

#### Обработка платежа
```python
async def process_referral_payment(subscription: Subscription):
    """Обработать платёж с учётом реферальной программы"""
    # 1. Проверить, есть ли реферер у пользователя
    # 2. Рассчитать комиссию
    # 3. Создать запись о начислении
    # 4. Отправить уведомление рефереру
    pass
```

### Интеграция с существующим кодом

#### Изменения в `/start` команде
- Добавить парсинг параметра `start` 
- Сохранять реферальную связь при первом запуске

#### Изменения в обработке платежей
- При успешной оплате проверять наличие реферера
- Создавать запись о комиссии
- Отправлять уведомление рефереру

#### Новые команды
- `/affiliate` - получить свою реферальную ссылку
- `/affiliate_stats` - статистика рефералов
- `/affiliate_admin` - управление программой (для админов)

---

## 📈 Статус разработки

### Текущий прогресс
- ✅ Анализ существующей системы завершён
- ✅ Документация создана
- ✅ Модели данных созданы и мигрированы
- ✅ Сервисный слой реализован
- 🔄 Интеграция с обработчиками бота
- ⏳ API интеграция с Telegram
- ⏳ Тестирование

### Следующие шаги
1. Добавить обработку реферальных ссылок в команду /start
2. Интегрировать начисление комиссий в обработчик платежей
3. Создать команду /affiliate для пользователей
4. Реализовать админ-команды управления программой
5. Протестировать на тестовых платежах

### Важные решения
- ✅ Использовать текущую систему одноразовых платежей
- ✅ Установить комиссию 10% (100 промилле)
- ⏳ Определить срок действия программы
- ⏳ Решить вопрос с минимальной суммой для комиссии

---

## 📚 Дополнительные ресурсы

### Официальные источники
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram Stars Documentation](https://core.telegram.org/api/stars)
- [Affiliate Programs Announcement](https://telegram.org/blog/affiliate-programs-ai-sticker-search)

### Внутренние документы
- [SUBSCRIPTION_INTEGRATION.md](./archive/SUBSCRIPTION_INTEGRATION.md) - Интеграция подписок
- [CELERY_DOCUMENTATION.md](./CELERY_DOCUMENTATION.md) - Фоновые задачи

---

## 📝 История изменений

| Дата | Изменения |
|------|-----------|
| 05.09.2025 | Создание документа, анализ системы |
| 05.09.2025 | Добавлены модели данных и сервисный слой |

---

*Этот документ будет обновляться по мере разработки реферальной программы*