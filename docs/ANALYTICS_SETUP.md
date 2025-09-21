# Настройка веб-аналитики для лендинга Coins Bot

## Что добавлено
В файлы `landing/index.html` и `landing/index_en.html` добавлены счетчики:
1. **Google Analytics 4** - для детальной аналитики посещений
2. **Яндекс.Метрика** - для тепловых карт и поведенческой аналитики

## Что нужно сделать для активации

### 1. Google Analytics 4

1. Зайдите в [Google Analytics](https://analytics.google.com/)
2. Создайте новое свойство для сайта www.coins-bot.ru
3. Получите Measurement ID (формат: G-XXXXXXXXXX)
4. Замените `G-XXXXXXXXXX` в файлах на ваш реальный ID:
   - `landing/index.html` (строки 11 и 16)
   - `landing/index_en.html` (строки 11 и 16)

### 2. Яндекс.Метрика

1. Зайдите в [Яндекс.Метрику](https://metrika.yandex.ru/)
2. Добавьте счетчик для сайта www.coins-bot.ru
3. Получите номер счетчика (8-значное число)
4. Замените `XXXXXXXX` в файлах на ваш номер счетчика:
   - `landing/index.html` (строки 27 и 34)
   - `landing/index_en.html` (строки 27 и 34)

### 3. Настройка целей (конверсий)

#### В Google Analytics:
1. Перейдите в Admin → Events
2. Создайте события для отслеживания:
   - Клик по кнопке "Открыть бота"
   - Переход в Telegram
   - Просмотр демо-видео

#### В Яндекс.Метрике:
1. Перейдите в Настройки → Цели
2. Создайте цели:
   - JavaScript-событие: клик по кнопке бота
   - Посещение страницы: переход на t.me/coinsexpense_bot
   - Глубина просмотра: более 30 секунд на сайте

### 4. Обновление на сервере

После замены ID выполните команду для обновления лендинга на сервере:

```bash
cd /home/batman/expense_bot && git pull && sudo cp -rf landing/* /var/www/coins-bot/ && sudo chown -R www-data:www-data /var/www/coins-bot/ && sudo nginx -s reload
```

## Что вы сможете отслеживать

### Google Analytics покажет:
- Количество посетителей (уникальные/общие)
- Источники трафика (откуда пришли)
- География посетителей
- Устройства (мобильные/десктоп)
- Время на сайте
- Показатель отказов (bounce rate)
- Конверсии в переходы к боту

### Яндекс.Метрика покажет:
- Тепловые карты кликов
- Карты скроллинга
- Вебвизор (запись действий пользователей)
- Формирование аудиторий для ретаргетинга
- А/Б тестирование

## Проверка работы

### Для Google Analytics:
1. Откройте сайт www.coins-bot.ru
2. В Google Analytics перейдите в Realtime → Overview
3. Вы должны увидеть себя как активного пользователя

### Для Яндекс.Метрики:
1. Откройте сайт www.coins-bot.ru
2. В Яндекс.Метрике перейдите в Онлайн
3. Вы должны увидеть себя в списке посетителей

## Дополнительные возможности

### Отслеживание кликов по кнопке "Открыть бота"
Можно добавить JavaScript для отслеживания события:

```javascript
// Для Google Analytics
document.querySelectorAll('a[href*="t.me"]').forEach(link => {
  link.addEventListener('click', () => {
    gtag('event', 'open_bot', {
      'event_category': 'engagement',
      'event_label': 'telegram_bot'
    });
  });
});

// Для Яндекс.Метрики
document.querySelectorAll('a[href*="t.me"]').forEach(link => {
  link.addEventListener('click', () => {
    ym(XXXXXXXX, 'reachGoal', 'open_bot');
  });
});
```

### UTM-метки для рекламных кампаний
Используйте UTM-метки в ссылках для отслеживания эффективности рекламы:
```
https://www.coins-bot.ru/?utm_source=telegram&utm_medium=post&utm_campaign=launch
```

## Безопасность и приватность

- Оба сервиса соответствуют GDPR
- Данные анонимизированы
- IP-адреса маскируются
- Cookies используются только для аналитики

## Поддержка

При возникновении вопросов:
- Google Analytics: https://support.google.com/analytics
- Яндекс.Метрика: https://yandex.ru/support/metrica