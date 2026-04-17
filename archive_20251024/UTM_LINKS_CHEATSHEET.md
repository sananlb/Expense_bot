# 🔗 Шпаргалка по UTM-ссылкам

## Яндекс.Директ

### Основные кампании
```
Общая кампания:
https://t.me/showmecoinbot?start=ads_yandex

Поиск Яндекса:
https://t.me/showmecoinbot?start=ads_yandex_search

РСЯ (Рекламная сеть):
https://t.me/showmecoinbot?start=ads_yandex_rsy

Мобильные:
https://t.me/showmecoinbot?start=ads_yandex_mobile
```

### Сезонные кампании
```
Январь 2025:
https://t.me/showmecoinbot?start=ads_yandex_jan2025

Новый год:
https://t.me/showmecoinbot?start=ads_yandex_newyear

Черная пятница:
https://t.me/showmecoinbot?start=ads_yandex_blackfriday

8 марта:
https://t.me/showmecoinbot?start=ads_yandex_8march
```

---

## Google Ads

```
Поиск Google:
https://t.me/showmecoinbot?start=ads_google_search

Медийная сеть:
https://t.me/showmecoinbot?start=ads_google_display

YouTube:
https://t.me/showmecoinbot?start=ads_google_youtube
```

---

## VK Реклама

```
Лента новостей:
https://t.me/showmecoinbot?start=ads_vk_feed

Истории VK:
https://t.me/showmecoinbot?start=ads_vk_stories

Клипы VK:
https://t.me/showmecoinbot?start=ads_vk_clips

Сообщества:
https://t.me/showmecoinbot?start=ads_vk_communities
```

---

## Telegram Ads

```
Каналы:
https://t.me/showmecoinbot?start=ads_telegram_channels

Боты:
https://t.me/showmecoinbot?start=ads_telegram_bots
```

---

## Блогеры

```
Формат:
https://t.me/showmecoinbot?start=b_ИМЯ_БЛОГЕРА_КАМПАНИЯ

Примеры:
https://t.me/showmecoinbot?start=b_ivan
https://t.me/showmecoinbot?start=b_ivan_stories
https://t.me/showmecoinbot?start=b_maria_review
https://t.me/showmecoinbot?start=b_finexpert_december
```

---

## Партнеры

```
Формат:
https://t.me/showmecoinbot?start=p_ИМЯ_ПАРТНЕРА

Примеры:
https://t.me/showmecoinbot?start=p_finblog
https://t.me/showmecoinbot?start=p_cashbackapp
https://t.me/showmecoinbot?start=p_budgetplanner
```

---

## Социальные сети (органика)

```
VK:
https://t.me/showmecoinbot?start=social_vk

Facebook:
https://t.me/showmecoinbot?start=social_fb

Instagram:
https://t.me/showmecoinbot?start=social_instagram

Telegram:
https://t.me/showmecoinbot?start=social_tg

Twitter/X:
https://t.me/showmecoinbot?start=social_x
```

---

## Лендинг (органический трафик)

```
Русская версия:
https://t.me/showmecoinbot?start=organic_landing

Английская версия:
https://t.me/showmecoinbot?start=organic_landing_en
```

---

## Реферальная программа (Telegram Stars)

```
Формат:
https://t.me/showmecoinbot?start=ref_TELEGRAM_ID

Пример:
https://t.me/showmecoinbot?start=ref_123456789
```

---

## Семейный бюджет (приглашение)

```
Формат:
https://t.me/showmecoinbot?start=family_HOUSEHOLD_ID

Пример:
https://t.me/showmecoinbot?start=family_42
```

---

## 📊 Просмотр статистики

### Django Admin
```
https://expensebot.duckdns.org/admin/

Разделы:
- Expenses → Profiles (фильтр по acquisition_source и acquisition_campaign)
- Expenses → Advertiser campaigns (управление кампаниями)
```

### SQL запрос (сервер)
```bash
ssh batman@80.66.87.178

docker exec expense_bot_db psql -U expense_user -d expense_bot -c "
SELECT
    acquisition_source,
    acquisition_campaign,
    COUNT(*) as users_count
FROM expenses_profile
WHERE acquisition_source IS NOT NULL
GROUP BY acquisition_source, acquisition_campaign
ORDER BY users_count DESC;
"
```

---

## 🎯 Быстрый старт для Яндекс.Директ

1. **Выберите ссылку** из раздела "Яндекс.Директ" выше
2. **Вставьте в объявление** Яндекс.Директ
3. **Дождитесь первых переходов** (1-24 часа)
4. **Проверьте статистику** в Django Admin

---

## 💡 Советы

### Именование кампаний
- Используйте **короткие** названия (до 20 символов)
- Используйте **латиницу** (a-z, 0-9, подчеркивание)
- Добавляйте **дату** для сезонных кампаний (jan2025, dec2024)
- Используйте **описательные** названия (search, rsy, mobile)

### Примеры хороших названий:
- ✅ `ads_yandex_search`
- ✅ `ads_yandex_jan2025`
- ✅ `b_ivan_stories`
- ✅ `p_finblog_review`

### Примеры плохих названий:
- ❌ `ads_yandex_очень_длинное_название_кампании_2025`
- ❌ `кампания1`
- ❌ `test123`

---

## 📝 Шаблон для создания новой кампании

```
Источник: [yandex/google/vk/telegram]
Тип: [ads/blogger/partner/social]
Название: [короткое_описание]

Ссылка:
https://t.me/showmecoinbot?start=[тип]_[источник]_[название]

Пример:
https://t.me/showmecoinbot?start=ads_yandex_feb2025
```

---

## 🔄 Обновление лендинга на сервере

После внесения изменений в файлы лендинга:

```bash
ssh batman@80.66.87.178

cd /home/batman/expense_bot && \
git pull && \
sudo cp -rf landing/* /var/www/coins-bot/ && \
sudo chown -R www-data:www-data /var/www/coins-bot/ && \
sudo nginx -s reload
```

В браузере: **Ctrl+F5** (полная перезагрузка без кеша)
