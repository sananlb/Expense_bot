# Отслеживание трафика из Яндекс.Директ

## 📊 Обзор системы

В боте **уже реализована** полноценная система отслеживания источников трафика с поддержкой:
- ✅ UTM-меток для разных источников (реклама, блогеры, партнеры, соцсети)
- ✅ Автоматическое сохранение источника при первом запуске бота
- ✅ Статистика по кампаниям в Django Admin
- ✅ Детальная аналитика через команду `/blogger_stats`
- ✅ Отслеживание конверсий и ROI

---

## 🎯 Настройка Яндекс.Директ

### 1. Создание ссылки для рекламы

**Формат ссылки для Яндекс.Директ:**
```
https://t.me/showmecoinbot?start=ads_yandex_НАЗВАНИЕ_КАМПАНИИ
```

**Примеры:**

| Кампания | Ссылка | Когда использовать |
|----------|--------|-------------------|
| Общая | `https://t.me/showmecoinbot?start=ads_yandex` | Основная кампания в Яндекс.Директ |
| Яндекс Директ | `https://t.me/showmecoinbot?start=ads_yandex_direct` | Размещение в поиске Яндекса |
| РСЯ | `https://t.me/showmecoinbot?start=ads_yandex_rsy` | Рекламная сеть Яндекса |
| Черная пятница | `https://t.me/showmecoinbot?start=ads_yandex_blackfriday` | Акция Черная Пятница |
| Новый год | `https://t.me/showmecoinbot?start=ads_yandex_newyear2025` | Новогодняя кампания |

### 2. Настройка в Яндекс.Директ

#### Шаг 1: Создайте объявление
1. Зайдите в Яндекс.Директ
2. Создайте новую кампанию или объявление
3. В поле "Ссылка на сайт" вставьте URL с UTM-меткой

#### Шаг 2: Настройте параметры
```
Ссылка: https://t.me/showmecoinbot?start=ads_yandex_direct
```

#### Шаг 3: Дополнительные параметры (опционально)
Можно добавить дополнительные метки для более детального отслеживания:
```
https://t.me/showmecoinbot?start=ads_yandex_search_moscow
                                       ↑      ↑      ↑
                                    источник тип   регион
```

---

## 📈 Просмотр статистики

### Метод 1: Django Admin панель

1. **Откройте админку:**
   ```
   https://expensebot.duckdns.org/admin/
   ```

2. **Перейдите в раздел "Рекламные кампании":**
   - `Expenses` → `Advertiser campaigns`

3. **Создайте кампанию:**
   - Нажмите "Add Advertiser Campaign"
   - Заполните поля:
     - **Name:** `yandex`
     - **Campaign:** `direct` (или название вашей кампании)
     - **UTM code:** `ads_yandex_direct`
     - **Source type:** `ads`
     - **Budget:** бюджет в рублях
     - **Start date:** дата начала
     - **Status:** `active`

4. **Просматривайте статистику:**
   - Система автоматически покажет:
     - Количество пользователей
     - Количество платящих пользователей
     - Конверсию
     - Общий доход
     - ROI (возврат инвестиций)

### Метод 2: Прямой SQL запрос на сервере

```bash
# Подключитесь к серверу
ssh batman@80.66.87.178

# Выполните запрос
docker exec expense_bot_db psql -U expense_user -d expense_bot -c "
SELECT
    acquisition_source,
    acquisition_campaign,
    COUNT(*) as users_count,
    COUNT(CASE WHEN last_activity > NOW() - INTERVAL '7 days' THEN 1 END) as active_users,
    MIN(created_at) as first_user,
    MAX(created_at) as last_user
FROM expenses_profile
WHERE acquisition_source = 'ads'
  AND acquisition_campaign LIKE 'yandex%'
GROUP BY acquisition_source, acquisition_campaign
ORDER BY users_count DESC;
"
```

### Метод 3: Через бота (для блогеров)

Команда `/blogger_stats` работает только для источника `blogger`, но вы можете адаптировать её:

```python
# В боте создайте команду /campaign_stats
# Она будет показывать статистику по любому источнику
```

---

## 🔍 Детальная аналитика

### Какие данные собираются

**В модели Profile хранятся:**

```python
acquisition_source = 'ads'              # Тип источника (реклама)
acquisition_campaign = 'yandex_direct'  # Название кампании
acquisition_date = '2025-01-24 10:30:00' # Дата первого перехода
acquisition_details = {                 # Дополнительная информация
    'ad_platform': 'yandex',
    'campaign_type': 'direct'
}
```

### SQL запросы для аналитики

#### 1. Общая статистика по Яндекс.Директ

```sql
SELECT
    acquisition_campaign,
    COUNT(*) as total_users,
    COUNT(CASE WHEN last_activity > NOW() - INTERVAL '7 days' THEN 1 END) as active_7d,
    COUNT(CASE WHEN last_activity > NOW() - INTERVAL '30 days' THEN 1 END) as active_30d
FROM expenses_profile
WHERE acquisition_source = 'ads'
  AND acquisition_campaign LIKE 'yandex%'
GROUP BY acquisition_campaign;
```

#### 2. Конверсия в платящих пользователей

```sql
SELECT
    p.acquisition_campaign,
    COUNT(DISTINCT p.id) as total_users,
    COUNT(DISTINCT CASE WHEN s.status = 'active' AND s.is_trial = FALSE THEN p.id END) as paying_users,
    ROUND(
        COUNT(DISTINCT CASE WHEN s.status = 'active' AND s.is_trial = FALSE THEN p.id END)::numeric /
        NULLIF(COUNT(DISTINCT p.id), 0) * 100,
        2
    ) as conversion_percent
FROM expenses_profile p
LEFT JOIN expenses_subscription s ON s.profile_id = p.id
WHERE p.acquisition_source = 'ads'
  AND p.acquisition_campaign LIKE 'yandex%'
GROUP BY p.acquisition_campaign;
```

#### 3. Доход по кампаниям

```sql
SELECT
    p.acquisition_campaign,
    COUNT(DISTINCT p.id) as users,
    COUNT(DISTINCT t.id) as transactions,
    SUM(t.amount) as total_revenue_stars,
    SUM(t.amount) * 2 as total_revenue_rub  -- 1 звезда ≈ 2 рубля
FROM expenses_profile p
LEFT JOIN expenses_transaction t ON t.user_id = p.id
WHERE p.acquisition_source = 'ads'
  AND p.acquisition_campaign LIKE 'yandex%'
  AND t.status = 'completed'
GROUP BY p.acquisition_campaign;
```

---

## 🎨 Настройка целей в Яндекс.Метрике

### 1. Создание цели "Переход в бота"

1. **Зайдите в Яндекс.Метрику:**
   - Счетчик: `104228689`
   - URL: https://metrika.yandex.ru

2. **Создайте цель:**
   - Настройки → Цели → Добавить цель
   - **Название:** "Переход в Telegram бота"
   - **Тип:** JavaScript событие
   - **Идентификатор:** `OPEN_BOT`

3. **Код уже настроен в лендинге** (index.html, строки 3717-3737):

```javascript
// Отслеживание кликов по ссылкам бота
const botLinks = document.querySelectorAll('a[href*="t.me/showmecoinbot"]');

botLinks.forEach(link => {
  link.addEventListener('click', function(e) {
    // Google Analytics 4
    if (typeof gtag !== 'undefined') {
      gtag('event', 'open_bot_click', {
        'event_category': 'engagement',
        'event_label': 'telegram_bot',
        'value': 1
      });
    }

    // Яндекс.Метрика
    if (typeof ym !== 'undefined') {
      ym(104228689, 'reachGoal', 'OPEN_BOT');
    }
  });
});
```

### 2. Создание цели "Регистрация в боте"

**Проблема:** Telegram боты работают вне веб-страниц, поэтому прямое отслеживание регистрации в Метрике невозможно.

**Решение:** Используйте **Measurement Protocol API Яндекс.Метрики** для отправки событий с сервера.

#### Настройка:

1. **Получите токен доступа:**
   - Яндекс.Метрика → Настройки → API

2. **Добавьте код в бота** (`bot/routers/start.py`):

```python
import aiohttp

async def send_metrika_goal(user_id: int, goal: str):
    """Отправка цели в Яндекс.Метрику"""
    counter_id = "104228689"
    url = f"https://mc.yandex.ru/watch/{counter_id}"

    params = {
        'browser-info': f'user_id:{user_id}',
        'page-url': f'https://t.me/showmecoinbot?user_id={user_id}',
        'page-ref': 'https://www.coins-bot.ru',
        'rn': int(time.time() * 1000),
    }

    async with aiohttp.ClientSession() as session:
        await session.get(url, params=params)

# В функции cmd_start после создания пользователя:
if is_new_user:
    await send_metrika_goal(user_id, 'BOT_REGISTRATION')
```

---

## 📊 Пример отчета по кампании

### Данные за неделю

| Метрика | Значение |
|---------|----------|
| **Клики в Яндекс.Директ** | 1,250 |
| **Переходов на лендинг** | 1,100 (88%) |
| **Запусков бота** | 450 (41%) |
| **Новых пользователей** | 420 (93%) |
| **Платящих пользователей** | 23 (5.5%) |
| **Доход (Telegram Stars)** | 1,265 ⭐ |
| **Доход (рубли)** | ~2,530 ₽ |
| **Бюджет кампании** | 15,000 ₽ |
| **ROI** | -83% (окупится через 6 недель) |

---

## 🚀 Быстрый старт

### Для запуска отслеживания прямо сейчас:

1. **Создайте ссылку для Яндекс.Директ:**
   ```
   https://t.me/showmecoinbot?start=ads_yandex_january2025
   ```

2. **Вставьте в объявление Яндекс.Директ**

3. **Дождитесь первых переходов** (от 1 часа до 1 дня)

4. **Проверьте статистику в админке:**
   ```
   https://expensebot.duckdns.org/admin/expenses/profile/
   ```

   Отфильтруйте по:
   - `Acquisition source = ads`
   - `Acquisition campaign = yandex_january2025`

5. **Создайте кампанию в админке** для автоматического расчета метрик:
   ```
   https://expensebot.duckdns.org/admin/expenses/advertisercampaign/add/
   ```

---

## 🔧 Дополнительные источники трафика

Система поддерживает не только Яндекс.Директ, но и другие источники:

### Google Ads
```
https://t.me/showmecoinbot?start=ads_google_search
https://t.me/showmecoinbot?start=ads_google_display
```

### VK Реклама
```
https://t.me/showmecoinbot?start=ads_vk_feed
https://t.me/showmecoinbot?start=ads_vk_stories
```

### MyTarget
```
https://t.me/showmecoinbot?start=ads_mytarget_banner
```

### Блогеры
```
https://t.me/showmecoinbot?start=b_BLOGGER_NAME
https://t.me/showmecoinbot?start=b_ivan_stories
```

### Партнеры
```
https://t.me/showmecoinbot?start=p_PARTNER_NAME
https://t.me/showmecoinbot?start=p_finblog_review
```

### Социальные сети (органика)
```
https://t.me/showmecoinbot?start=social_vk
https://t.me/showmecoinbot?start=social_fb
https://t.me/showmecoinbot?start=social_instagram
```

---

## 📞 Поддержка

Если у вас возникли вопросы:
- Telegram: @SMF_support
- Email: help@tbotsupport.ru

---

## 📝 Changelog

- **2025-01-24:** Добавлены UTM-метки на лендинг для органического трафика
- **2025-01-24:** Создана документация по настройке Яндекс.Директ
- **2024-XX-XX:** Реализована система отслеживания UTM-меток
- **2024-XX-XX:** Добавлена модель AdvertiserCampaign для управления кампаниями
