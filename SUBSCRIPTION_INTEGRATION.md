# Интеграция подписки через Telegram Stars

## Обзор

Реализована система подписок через Telegram Stars без использования внешних платежных систем.

### Тарифы:
- **Месячная подписка**: 100 Stars
- **Полугодовая подписка**: 500 Stars

## Структура

### 1. Модель данных

В `expenses/models.py` добавлена модель `Subscription`:
```python
class Subscription(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='subscriptions')
    type = models.CharField(max_length=20, choices=SUBSCRIPTION_TYPES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='stars')
    amount = models.IntegerField()  # Количество звезд
    telegram_payment_charge_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
```

### 2. Роутер подписки

Файл `bot/routers/subscription.py` содержит:
- Отображение меню подписки
- Создание инвойсов для оплаты
- Обработку успешной оплаты
- Автоматическое продление существующей подписки

### 3. Сервис подписки

Файл `bot/services/subscription.py` предоставляет:
- `check_subscription(telegram_id)` - проверка наличия активной подписки
- `get_active_subscription(telegram_id)` - получение активной подписки
- `require_subscription` - декоратор для функций, требующих подписку
- Вспомогательные функции для сообщений о подписке

## Интеграция в существующий функционал

### Пример 1: Проверка подписки в обработчике

```python
from bot.services.subscription import check_subscription, subscription_required_message, get_subscription_button

@router.callback_query(F.data == "some_premium_feature")
async def premium_feature_handler(callback: CallbackQuery):
    # Проверяем подписку
    has_subscription = await check_subscription(callback.from_user.id)
    
    if not has_subscription:
        await callback.message.edit_text(
            subscription_required_message(),
            reply_markup=get_subscription_button(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Код премиум функции
    await callback.message.edit_text("Премиум функция доступна!")
```

### Пример 2: Использование декоратора

```python
from bot.services.subscription import require_subscription

@router.callback_query(F.data == "premium_feature")
@require_subscription
async def premium_feature_handler(callback: CallbackQuery):
    # Этот код выполнится только если есть подписка
    await callback.message.edit_text("Премиум функция доступна!")
```

### Пример 3: Ограничение количества записей

```python
from bot.services.subscription import check_subscription

async def add_expense(telegram_id: int, amount: float, description: str):
    has_subscription = await check_subscription(telegram_id)
    
    if not has_subscription:
        # Проверяем количество трат за месяц
        expenses_count = await Expense.objects.filter(
            profile__telegram_id=telegram_id,
            expense_date__month=date.today().month
        ).acount()
        
        if expenses_count >= 50:  # Лимит для бесплатных пользователей
            return {
                'success': False,
                'message': 'Достигнут лимит трат для бесплатного аккаунта'
            }
    
    # Добавляем трату
    # ...
```

## Функции, требующие подписку

Рекомендуется добавить проверку подписки для:

1. **Экспорт данных** (PDF отчеты) - ✅ Уже реализовано
2. **Расширенная статистика** (графики, аналитика)
3. **Неограниченное количество трат** (лимит 50 в месяц без подписки)
4. **Экспорт в Excel/CSV**
5. **API доступ** (если планируется)
6. **Множественные валюты**
7. **Резервное копирование данных**

## Тестирование

Для тестирования оплаты в тестовой среде Telegram:

1. Используйте тестовый сервер Telegram
2. В тестовой среде Stars не списываются реально
3. Можно использовать тестовые карты для пополнения Stars

## Важные моменты

1. **Автопродление**: При покупке новой подписки она автоматически продлевается от даты окончания текущей
2. **Деактивация**: Необходимо периодически запускать `deactivate_expired_subscriptions()` для деактивации истекших подписок
3. **Миграции**: Не забудьте выполнить миграции после добавления модели
4. **Безопасность**: telegram_payment_charge_id уникален и предотвращает дублирование платежей