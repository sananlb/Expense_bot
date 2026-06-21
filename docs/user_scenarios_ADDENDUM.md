# User Scenarios & Edge Cases – ADDENDUM (clean)

Дата: 2025-11-24
Статус: Deep verification + дополнения по коду

> Дополнение к основному документу `user_scenarios_edge_cases.md`. Здесь собраны краткие выводы по найденным зонам риска и то, что требует явного покрытия в сценариях/UX.

---

## Status Update
- [done] Voice input number parsing implemented (convert_words_to_numbers in bot/utils/expense_parser.py; tests/test_number_parser.py green).
- [done] Voice Recognition Migration: Yandex SpeechKit + OpenRouter Gemini with symmetric fallback (see VOICE_RECOGNITION_MIGRATION_PLAN.md)
- [done] Voice: UX для неподдерживаемых типов медиа (audio, video_note) — добавлены обработчики в expense.py:1777-1835
- [done] Voice: сценарий падения обоих STT провайдеров — уже реализован в voice_recognition.py:227-244
- [verified] Парсер сумм: лимиты `<=0` и `>999 999 999` подтверждены в validators.py:30-35, input_sanitizer.py:121-123
- [verified] Recurring: дни 1-30 (models.py:554-556 + routers/recurring.py:326,690)
- [verified] Recurring: лимит 50 записей (services/recurring.py:40-43)
- [verified] Recurring: описание ≤200 символов (models.py:553 + services/recurring.py:79-81)
- [verified] Recurring: защита от дубликатов через last_processed (services/recurring.py:178)
- [fixed] Recurring: убран опасный delete+create при редактировании → теперь подсказка использовать кнопки (routers/recurring.py:704-722)
- [verified] Cashback: уникальность (profile, bank_name, month, category) — models.py:646 unique_together
- [verified] Cashback: процент <=99 — models.py:619 MaxValueValidator(99)
- [verified] Cashback: месячный контекст обязателен — models.py:621-624
- [verified] Cashback: персональность (нет household поля)
- [verified] Cashback: upsert при дубликате — cashback.py:42-57 обновляет существующий
- [fixed] Cashback: UI проверка процента исправлена с >100 на >99 (routers/cashback.py)
- [verified] Inline: cache_time=1, is_personal=True для всех ответов (inline_router.py)
- [verified] Inline: проверка can_add_member() перед генерацией инвайта (inline_router.py:78)
- [verified] Inline: подсказка "try again" при ошибках (inline_router.py:144-150)
- [verified] Household: max_members по умолчанию 5, изменяемый (models.py:184)
- [verified] Household: is_active блокирует приглашения (models.py:185, family.py:81)
- [verified] FamilyInvite: is_valid() проверяет is_active, used_by, expires_at (models.py:238-246)
- [verified] accept_invite: полная проверка валидности и вместимости (family.py:64-92)

---

## 12. Inline Mode (приглашения в хозяйство)
- Проверка: участник должен быть в household и быть его создателем; иначе показ `switch_pm` с подсказкой.
- `Household.max_members` задаётся в БД, по умолчанию 5, но не захардкожено. В сценариях писать «по умолчанию 5» и учитывать, что админ может изменить.
- Инвайты должны быть активны и household – активным; если household неактивен или инвайт использован/просрочен — выводить ошибку/подсказку.
- Inline ответы возвращаются с `is_personal=True` и `cache_time=1` для персональной выдачи и избежания кеша.

## 13. Voice Input
- Лимит длительности: `MAX_VOICE_DURATION_SECONDS` (по умолчанию 60). Длинные — ответ об ошибке.
- Поддерживается только `message.voice` (OGG Opus). Аудио/видео-ноты и другие типы — добавить явный UX-ответ «неподдерживаемый тип, пришлите голос или текст».
- STT fallback: RU — Yandex → OpenRouter; EN/other — OpenRouter → Yandex. Нужен сценарий на случай падения обоих провайдеров (мягкое сообщение и просьба повторить текстом).

## 14. Household / Family Budget
- Приглашать может только creator; `household.is_active` блокирует приглашения.
- Лимит участников: `Household.max_members` (по умолчанию 5, не жёстко).
- View scope хранится в `UserSettings.view_scope` (`personal`/`household`). Сценарий переключения должен учитывать, что данные и фильтры меняются.
- Recurring и Cashback являются персональными (см. ниже) — не шарятся на household.

## 15. Recurring Expenses / Income
- День месяца: в UI и валидаторах 1–30. В сценариях убрать ссылки на 31; крайний день месяца не поддержан явно.
- Лимиты из кода: максимум 50 записей на пользователя; описание ≤ 200 символов; валюта берётся из профиля.
- Таймзона: операции создаются по `date.today()` / `datetime.now()` сервера, timezone профиля не учитывается — потенциальный сдвиг дня при разнице TZ.
- При редактировании через свободный ввод старый платёж удаляется и создаётся новый — теряется `last_processed`. Edge case: редактирование в день автосписания может дать дубликат.
- Recurring связаны только с `profile` (нет `household` поля). При выходе из household или удалении категории — возможен разрыв ссылки; нужен UX/очистка.

## 16. Cashback Tracking
- Модель `Cashback`: уникальность `(profile, bank_name, month, category)`. Нельзя создать два правила с одинаковыми банк/месяц/категория (включая NULL категории).
- `cashback_percent` ограничен валидатором `<=99`. Попытки >99 отваливаются до бизнес-логики — зафиксировать в сценариях.
- Контекст месяца обязателен: данные не «общие», а помесячные. В UX добавить переключение месяца и пояснение.
- Персональный контекст: нет поля household, правила не шарятся между членами семьи.

## 17. Reports & Export
- Объёмные выгрузки должны учитывать лимиты Telegram (50MB) и таймауты; это уже отражено, оставить.

## 18. Дополнительные находки (из кода)
- Парсер сумм: `validate_amount` режет `<=0` и `>999 999 999`. Привести документацию к этим фактическим порогам.
- Inline: обработка генерации инвайта логирует ошибки; для UX оставить подсказку «попробуйте снова» при любой ошибке.

## 19. Приоритетные доработки сценариев
1) Recurring: диапазон дней 1–30, лимит 50, описание 200, TZ сдвиги, риск дублирования при редактировании в день списания.
2) Cashback: уникальность записи, потолок 99%, месячный контекст, персональность.
3) Inline/Household: неактивный household, изменяемый max_members, истёкший/использованный инвайт.
4) Voice: неподдерживаемые типы медиа + падение обоих STT провайдеров.
5) Парсер сумм: актуальные лимиты (`>999 999 999` / `<=0`).
