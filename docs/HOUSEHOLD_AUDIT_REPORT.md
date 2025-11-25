# Аудит логики семейного бюджета (Household)

**Дата:** 2025-11-25
**Автор:** Claude Code
**Версия:** 1.5 (финальная проверка + исправления в family.py)

---

## Содержание

1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Что работает хорошо](#2-что-работает-хорошо)
3. [Исправленные проблемы](#3-исправленные-проблемы)
4. [Дизайн-решения (не баги)](#4-дизайн-решения-не-баги)
5. [Проверенные сценарии](#5-проверенные-сценарии)
6. [Резюме](#6-резюме)

---

## 1. Обзор архитектуры

### 1.1 Модели данных

| Модель | Файл | Описание |
|--------|------|----------|
| `Household` | `expenses/models.py:173-206` | Домохозяйство (семейный бюджет) |
| `FamilyInvite` | `expenses/models.py:208-253` | Приглашения в семью |
| `Profile.household` | `expenses/models.py:131-138` | FK связь профиля с household |
| `UserSettings.view_scope` | `expenses/models.py:263-272` | Режим отображения (personal/household) |

### 1.2 Ключевые файлы

```
bot/services/household.py    - Бизнес-логика household
bot/services/family.py       - Async функции для приглашений
bot/routers/household.py     - UI роутер семейного бюджета
bot/routers/inline_router.py - Inline приглашения
bot/keyboards_household.py   - Клавиатуры
```

### 1.3 Константы

```python
INVITE_EXPIRY_HOURS = 48      # Срок действия приглашения
MAX_HOUSEHOLD_MEMBERS = 5     # Максимум членов семьи
MIN_HOUSEHOLD_NAME_LENGTH = 3
MAX_HOUSEHOLD_NAME_LENGTH = 50
```

### 1.4 Workflow семейного бюджета

```
┌─────────────────┐
│ Создание семьи  │
│ (create_household)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Генерация       │────▶│ Deep-link       │
│ приглашения     │     │ t.me/bot?start= │
│ (generate_invite)     │ family_{token}  │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Присоединение   │
                        │ (join_household)│
                        └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Совместные      │     │ Переключение    │     │ Выход из семьи  │
│ отчеты          │     │ view_scope      │     │ (leave_household)
│ (household_mode)│     │ personal/family │     └─────────────────┘
└─────────────────┘     └─────────────────┘
```

---

## 2. Что работает хорошо

### 2.1 Создание и управление household

- ✅ Создание домохозяйства с транзакцией (`@transaction.atomic`)
- ✅ Валидация названия (3-50 символов)
- ✅ Проверка что пользователь не в другой семье

### 2.2 Система приглашений

- ✅ Уникальные токены (`secrets.token_urlsafe(32)`)
- ✅ Срок действия 48 часов
- ✅ Деактивация старых приглашений при создании нового
- ✅ Проверка `is_valid()` перед использованием
- ✅ Отметка использования (`used_by`, `used_at`)
- ✅ **Защита от повторного использования токена** (select_for_update на invite)

### 2.3 Валидация категорий

- ✅ **Расходы:** Категории проверяются на принадлежность пользователю или члену семьи, выбрасывается ValueError при нарушении
- ✅ **Доходы:** Категории проверяются аналогично, выбрасывается ValueError при нарушении (симметрично с расходами)

### 2.4 Отчеты и аналитика

- ✅ `get_expenses_summary()` - поддержка `household_mode`
- ✅ `analytics_query.py` - фильтрация по `profile__in=household_profiles`
- ✅ PDF отчеты - название household в заголовке
- ✅ CSV/XLSX экспорт - данные всех членов семьи
- ✅ `get_household_expenses()` / `get_household_incomes()` - правильные поля `expense_date` / `income_date`

### 2.5 Безопасность

- ✅ Только создатель может приглашать
- ✅ Только создатель может переименовывать
- ✅ Нет доступа к данным чужих семей
- ✅ GDPR compliance - только User ID в приглашениях
- ✅ **Race condition защита** при присоединении (select_for_update на invite + household)

### 2.6 Уведомления и cleanup

- ✅ При выходе члена - уведомление остальным
- ✅ При расформировании - уведомление всем
- ✅ **view_scope сбрасывается** при выходе из семьи (для всех членов при расформировании)

---

## 3. Исправленные проблемы

### 3.1 ✅ ИСПРАВЛЕНО: Доходы не валидировали категории household

**Файл:** `bot/services/income.py:121-151`

**Было:**
```python
category = IncomeCategory.objects.get(
    id=category_id,
    profile=profile,  # ← Только свои категории
    is_active=True
)
```

**Стало:**
```python
category = IncomeCategory.objects.select_related('profile').get(
    id=category_id,
    is_active=True
)

# Проверяем что категория принадлежит пользователю или члену его семьи
is_valid_category = False

if category.profile_id == profile.id:
    is_valid_category = True
elif profile.household_id is not None:
    if category.profile.household_id == profile.household_id:
        is_valid_category = True

if not is_valid_category:
    raise ValueError("Нельзя использовать категорию другого пользователя")
```

---

### 3.2 ✅ ИСПРАВЛЕНО: Race condition при присоединении (invite + household)

**Файл:** `bot/services/household.py:138-164`

**Было:**
```python
invite = FamilyInvite.objects.filter(token=token).first()  # Без блокировки
if not invite.is_valid(): ...
household = invite.household  # Без блокировки
```

**Стало:**
```python
# Блокируем invite для предотвращения повторного использования токена
invite = FamilyInvite.objects.select_for_update().filter(token=token).first()

if not invite: return False, "Приглашение не найдено"
if not invite.is_valid(): return False, "Приглашение недействительно или истекло"

# Блокируем household для предотвращения превышения лимита членов
household = Household.objects.select_for_update().get(id=invite.household_id)

if not household.can_add_member(): return False, "..."

# Сначала отмечаем приглашение как использованное (до присоединения!)
invite.used_by = profile
invite.used_at = timezone.now()
invite.is_active = False
invite.save()

# Затем присоединяем к домохозяйству
profile.household = household
profile.save()
```

**Защита:**
1. `select_for_update()` на invite - предотвращает повторное использование токена
2. `select_for_update()` на household - предотвращает превышение max_members
3. Порядок операций: сначала деактивация invite, потом присоединение

---

### 3.3 ✅ ИСПРАВЛЕНО: view_scope не сбрасывался при выходе

**Файл:** `bot/services/household.py:193-214`

**Добавлено:**
```python
# При расформировании семьи создателем:
member_ids = list(Profile.objects.filter(household=household).values_list('id', flat=True))
UserSettings.objects.filter(profile_id__in=member_ids, view_scope='household').update(view_scope='personal')

# При выходе обычного участника:
UserSettings.objects.filter(profile=profile, view_scope='household').update(view_scope='personal')
```

---

### 3.4 ✅ ИСПРАВЛЕНО: Неправильные имена полей в хелперах

**Файл:** `bot/services/household.py:237-268`

**Было:**
```python
expenses.filter(date__gte=start_date)  # ← Поле date не существует
incomes.filter(date__gte=start_date)   # ← Поле date не существует
```

**Стало:**
```python
expenses.filter(expense_date__gte=start_date)  # ✅ Правильное поле
incomes.filter(income_date__gte=start_date)    # ✅ Правильное поле
```

---

## 4. Дизайн-решения (не баги)

Следующие особенности являются **осознанными дизайн-решениями**, а не багами:

### 4.1 TOP-5 — индивидуальный

TOP-5 показывает только **личные** частые операции пользователя, независимо от семейного бюджета.

**Причина:** TOP-5 — это персональные "быстрые кнопки" для ускорения ввода, они должны отражать привычки конкретного пользователя.

### 4.2 Recurring Payments — индивидуальные

Регулярные платежи остаются **персональными** для каждого пользователя.

**Причина:** Регулярные платежи (аренда, подписки) — это личные обязательства пользователя.

### 4.3 Создатель семьи не может передать права

При выходе создателя семья **расформировывается** для всех участников.

**Причина:** Упрощение логики. Создатель несет ответственность за семью.

### 4.4 Приглашение одноразовое

Каждое приглашение может быть использовано только **1 раз**.

**Причина:** Контроль над тем, кто присоединяется к семье.

---

## 5. Проверенные сценарии

### 5.1 Все сценарии работают ✅

| # | Сценарий | Статус | Файл |
|---|----------|--------|------|
| 1 | Создание household | ✅ OK | `household.py:25-65` |
| 2 | Генерация приглашения | ✅ OK | `household.py:67-118` |
| 3 | Присоединение по deep-link | ✅ OK | `household.py:122-170` |
| 4 | Выход члена семьи | ✅ OK | `household.py:174-227` |
| 5 | Выход создателя (расформирование) | ✅ OK | `household.py:191-206` |
| 6 | Переключение view_scope | ✅ OK | `settings.py:32-52` |
| 7 | Отчеты в режиме семьи | ✅ OK | `reports.py:162-216` |
| 8 | Расход с категорией члена семьи | ✅ OK | `expense.py:100-127` |
| 9 | Доход с категорией члена семьи | ✅ ИСПРАВЛЕНО | `income.py:121-151` |
| 10 | PDF/CSV экспорт семьи | ✅ OK | `pdf_report.py`, `export_service.py` |
| 11 | Уведомления при выходе | ✅ OK | `household.py:306-317` |
| 12 | view_scope сброс при выходе | ✅ ИСПРАВЛЕНО | `household.py:193-214` |
| 13 | Race condition защита (invite) | ✅ ИСПРАВЛЕНО | `household.py:138-160` |
| 14 | Race condition защита (household) | ✅ ИСПРАВЛЕНО | `household.py:149-153` |
| 15 | Хелперы get_household_expenses/incomes | ✅ ИСПРАВЛЕНО | `household.py:237-268` |
| 16 | Race condition в family.py accept_invite | ✅ ИСПРАВЛЕНО | `family.py:64-105` |
| 17 | Race condition в toggle_view_scope | ✅ ИСПРАВЛЕНО | `settings.py:32-76` |
| 18 | Race condition в toggle_view_scope_diary | ✅ ИСПРАВЛЕНО | `reports.py:475-497` |
| 19 | Атомарность leave_household | ✅ ИСПРАВЛЕНО | `household.py:175-230` |
| 20 | Race condition в get_or_create_household_for_user | ✅ ИСПРАВЛЕНО | `family.py:17-31` |
| 21 | Race condition в generate_family_invite | ✅ ИСПРАВЛЕНО | `family.py:34-62` |

---

## 6. Резюме

### 6.1 Общая оценка после всех исправлений

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| **Архитектура** | 9/10 | Хорошо спроектировано |
| **Безопасность** | 10/10 | Все race conditions исправлены |
| **Функциональность** | 10/10 | Все критические баги исправлены |
| **Консистентность** | 10/10 | Income симметричен expense (raise ValueError) |
| **Код** | 9/10 | Чистый, понятный |

**Итоговая оценка: 9.6/10**

### 6.2 Исправленные файлы

| Файл | Изменения |
|------|-----------|
| `bot/services/income.py` | Валидация household категорий + raise ValueError |
| `bot/services/household.py` | select_for_update на invite + household, view_scope сброс, fix полей date |
| `bot/services/family.py` | select_for_update на invite + household, отметка invite как использованного |
| `bot/routers/settings.py` | Атомарное переключение view_scope с select_for_update |
| `bot/routers/reports.py` | Атомарное переключение view_scope_diary с select_for_update |

### 6.3 Что осталось индивидуальным (by design)

- TOP-5 — персональные быстрые кнопки
- Recurring Payments — персональные регулярные платежи
- Передача прав создателя — не реализована (семья расформировывается)

---

## Приложение A: Структура моделей

```
┌─────────────────┐
│   Household     │
├─────────────────┤
│ id              │◄─────────────────────┐
│ name            │                      │
│ creator ────────┼──► Profile           │
│ max_members = 5 │                      │
│ is_active       │                      │
│ created_at      │                      │
└────────┬────────┘                      │
         │                               │
         │ profiles (related_name)       │
         ▼                               │
┌─────────────────┐                      │
│    Profile      │                      │
├─────────────────┤                      │
│ id              │                      │
│ telegram_id     │                      │
│ household ──────┼──────────────────────┘
│ language_code   │
│ currency        │
└────────┬────────┘
         │
         │ settings (OneToOne)
         ▼
┌─────────────────┐
│  UserSettings   │
├─────────────────┤
│ profile         │
│ view_scope      │  ← 'personal' | 'household'
│ cashback_enabled│
└─────────────────┘

┌─────────────────┐
│  FamilyInvite   │
├─────────────────┤
│ id              │
│ inviter ────────┼──► Profile
│ household ──────┼──► Household
│ token (unique)  │
│ expires_at      │
│ is_active       │
│ used_by ────────┼──► Profile (nullable)
│ used_at         │
└─────────────────┘
```

---

*Документ обновлен после финальной проверки (2025-11-25 v1.5)*

---

## Приложение B: Дублирующий сервис family.py

### Проблема

В проекте существуют **два параллельных сервиса** для присоединения к семье:

| Сервис | Файл | Router |
|--------|------|--------|
| `HouseholdService.join_household()` | `household.py` | `routers/household.py` |
| `accept_invite()` | `family.py` | `routers/family.py` |

### Исправление (v1.3)

`family.py:accept_invite()` был исправлен для соответствия безопасности `household.py`:

```python
@sync_to_async
def accept_invite(joiner_telegram_id: int, token: str) -> tuple[bool, str]:
    with transaction.atomic():
        # Блокируем invite для предотвращения повторного использования
        invite = FamilyInvite.objects.select_for_update().get(token=token)

        # Блокируем household для предотвращения превышения лимита
        target_hh = Household.objects.select_for_update().get(id=invite.household_id)

        # Сначала отмечаем invite как использованный
        invite.used_by = joiner
        invite.used_at = timezone.now()
        invite.is_active = False
        invite.save()

        # Затем присоединяем
        joiner.household = target_hh
        joiner.save()
```

### Рекомендация

Рассмотреть объединение двух сервисов в один для упрощения поддержки.
