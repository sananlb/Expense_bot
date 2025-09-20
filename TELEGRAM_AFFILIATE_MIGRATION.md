# План миграции на официальную Telegram Affiliate Program

## Текущая ситуация:
- У нас обычный бот (не Mini App)
- Самодельная реферальная система, которая НЕ может выплачивать Stars
- Telegram запустил официальную Affiliate Program, но только для Mini Apps

## Преимущества миграции:
✅ Автоматические выплаты Stars от Telegram
✅ Прозрачность и доверие пользователей
✅ Нет нужды в костылях и обходных путях
✅ Официальная поддержка от Telegram

## План миграции:

### Этап 1: Создание Mini App (2-3 недели)
1. Создать веб-приложение (React/Vue/vanilla JS)
2. Реализовать интерфейс для:
   - Просмотра подписки
   - Оплаты через Stars
   - Реферальной программы
3. Хостинг на HTTPS (обязательно)

### Этап 2: Интеграция с ботом (1 неделя)
1. Подключить Mini App к боту через BotFather
2. Добавить кнопку запуска Mini App в бота
3. Синхронизировать данные между ботом и Mini App

### Этап 3: Настройка Affiliate Program (2-3 дня)
1. Вызвать `bots.updateStarRefProgram` с параметрами:
   - commission_permille: 100 (10% комиссия)
   - duration_months: null (бессрочно)
2. Протестировать автоматические выплаты
3. Обновить документацию для пользователей

### Технические требования:
- **Frontend**: HTML5 + JS (React рекомендуется)
- **Backend**: Существующий Django можно использовать
- **Hosting**: HTTPS обязателен
- **Telegram Web App SDK**: Для авторизации и платежей

### Примерная архитектура Mini App:
```javascript
// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;

// Авторизация пользователя
const user = tg.initDataUnsafe.user;

// Создание платежа Stars
async function createStarsPayment(amount) {
    const invoice = await fetch('/api/create-invoice', {
        method: 'POST',
        body: JSON.stringify({
            amount: amount,
            user_id: user.id
        })
    });

    tg.openInvoice(invoice.url);
}

// Обработка успешной оплаты
tg.onEvent('invoiceClosed', (event) => {
    if (event.status === 'paid') {
        // Обновить подписку
        updateSubscription();
    }
});
```

## Альтернатива: Временное решение

### Если миграция невозможна сейчас:
1. **Отключить** ложные уведомления о выплатах Stars
2. **Переименовать** в "Бонусную программу"
3. **Давать скидки** вместо Stars:
   - Накапливать баллы
   - Использовать для скидок на подписку
4. **Честно объяснить** пользователям ограничения

### Код для временного решения:
```python
# models.py - добавить поле для баллов
class Profile(models.Model):
    referral_points = models.IntegerField(default=0)

# При начислении "комиссии"
referrer.referral_points += commission_amount
referrer.save()

# При оплате - применить скидку
if user.referral_points > 0:
    discount = min(user.referral_points, price)
    final_price = price - discount
    # Создать инвойс на final_price
    user.referral_points -= discount
    user.save()
```

## Рекомендация:
**Краткосрочно**: Реализовать временное решение с баллами
**Долгосрочно**: Мигрировать на Mini App для полноценной интеграции

## Важные ссылки:
- [Telegram Web Apps Documentation](https://core.telegram.org/bots/webapps)
- [Affiliate Programs API](https://core.telegram.org/api/bots/referrals)
- [Mini App Examples](https://github.com/Telegram-Web-Apps)