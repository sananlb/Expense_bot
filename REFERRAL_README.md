# 🚀 Реферальная программа ExpenseBot - Краткое руководство

## Текущая реализация (v2.0)

### Как работает для пользователей:

1. **Реферер получает** уникальную ссылку: `https://t.me/bot_name?start=ref_CODE`
2. **Новый пользователь** переходит по ссылке и регистрируется
3. **При первой оплате** подписки новым пользователем:
   - Реферер получает бонусное продление на тот же срок (1 или 6 месяцев)
   - Бонус выдается только ОДИН раз за каждого приглашенного
4. **Статистика** доступна через команду `/referral`

### Техническая реализация:

```python
# Основная функция бонуса (bot/services/affiliate.py)
reward_referrer_subscription_extension(subscription)
# Создает подписку с payment_method='referral' для реферера

# Вызывается после успешной оплаты (bot/routers/subscription.py:898)
if payment.currency == "XTR":  # Оплата Stars
    reward_result = await reward_referrer_subscription_extension(subscription)
```

### Ключевые ограничения:

- ❌ **НЕ можем выплачивать Stars** - Telegram Bot API не поддерживает переводы
- ✅ **Даем продление подписки** - работает в рамках API
- 🔄 **Только первый платеж** - повторные покупки не генерируют бонусы
- 📊 **Полная статистика** - clicks, conversions, rewards в БД

## Миграция с v1.0

### Что было (не работало):
- Система `AffiliateCommission` для выплат Stars
- Celery задачи для обработки выплат
- Уведомления о "выплаченных" Stars (обман)

### Что стало (работает):
- Бонусные подписки через `AffiliateReferral.reward_*` поля
- Автоматическое продление при первой оплате
- Честное информирование пользователей

### Команды для миграции на production:
```bash
# Применить миграцию
python manage.py migrate

# Опционально: очистить старые данные о комиссиях
python manage.py shell
>>> from expenses.models import AffiliateCommission
>>> AffiliateCommission.objects.all().delete()
```

## FAQ

**Q: Почему не выплачиваем Stars?**
A: Telegram Bot API физически не позволяет переводить Stars между пользователями.

**Q: Можно ли подключить официальную Telegram Affiliate Program?**
A: Да, но только для Mini Apps. Обычные боты не поддерживаются.

**Q: Что если реферал купит подписку повторно?**
A: Бонус выдается только за первую покупку. Флаг `reward_granted` предотвращает повторы.

**Q: Как проверить что все работает?**
A: Запустить `python test_all_fixes.py` - тест "Бонус продления только за первый платеж"

## Файлы проекта

| Файл | Описание |
|------|----------|
| `bot/services/affiliate.py` | Основная логика реферальной программы |
| `bot/routers/subscription.py:898` | Интеграция в процесс оплаты |
| `bot/routers/referral.py` | Интерфейс для пользователей |
| `expenses/models.py:AffiliateReferral` | Модель с полями для бонусов |
| `migrations/0043_affiliaterewardfields.py` | Миграция новых полей |
| `docs/AFFILIATE_PROGRAM.md` | Полная документация |

---
*Последнее обновление: 20.09.2024*