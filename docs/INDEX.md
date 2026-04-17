# Expense Bot — карта документации

**Обновлено:** 2026-04-12
**Всего файлов:** 67 (current: 16, active: 14, reference: 14, historical: 19, deprecated: 4)

---

## Current — как проект устроен сейчас

### architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) — aiogram + Django + Celery + Redis + PostgreSQL, схема взаимодействия
- [INFRASTRUCTURE.md](INFRASTRUCTURE.md) — PRIMARY сервер 176.124.218.53, Docker, Nginx, SSL, лендинг
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — каталоги, .env, docker-compose, скрипт восстановления БД
- [DATABASE.md](DATABASE.md) — ER-диаграмма, таблицы users_profile/expenses/categories/cashback, индексы
- [CELERY_DOCUMENTATION.md](CELERY_DOCUMENTATION.md) — очереди, периодические задачи, диагностика, troubleshooting
- [BACKUP_SERVER.md](BACKUP_SERVER.md) — резервный сервер 72.56.67.202, Docker Compose v2, процедура переключения
- [RESERVE_SERVER_72.56.67.202.md](RESERVE_SERVER_72.56.67.202.md) — архитектура, Nginx, контейнеры, WireGuard VPN, статус готовности
- [BACKUP_GDRIVE_PLAN.md](BACKUP_GDRIVE_PLAN.md) — ежедневный cron-бекап на Google Drive через rclone, ротация 30 копий

### features
- [FEATURES.md](FEATURES.md) — полный список возможностей: траты, категории, кешбэки, голос, отчёты
- [BOT_FEATURES_RU.md](BOT_FEATURES_RU.md) — все команды, подписки Stars, партнёрка, семейный бюджет, Celery Beat
- [MULTILINGUAL_CATEGORIES.md](MULTILINGUAL_CATEGORIES.md) — name_ru/name_en, get_display_name(), синхронизация с legacy name
- [TOP5_FEATURE.md](TOP5_FEATURE.md) — быстрый повтор операций, авто-обновление в 05:00, модели Top5Snapshot/Top5Pin
- [AI_MONTHLY_INSIGHTS_DOCUMENTATION.md](AI_MONTHLY_INSIGHTS_DOCUMENTATION.md) — AI-анализ месячных финансов, Gemini/OpenAI fallback, MonthlyInsight модель
- [AFFILIATE_PROGRAM.md](AFFILIATE_PROGRAM.md) — бонус рефереру при первой оплате, Telegram Stars Affiliate, статистика
- [ENHANCED_MONITORING.md](ENHANCED_MONITORING.md) — ежедневный отчёт админу, health check, AI-метрики, retention

### deployment
- [SERVER_COMMANDS.md](SERVER_COMMANDS.md) — docker-compose, обновление кода, Celery, логи, мониторинг

---

## Active — незавершённая работа

### features
- [EXPORT_IMPLEMENTATION_PLAN.md](EXPORT_IMPLEMENTATION_PLAN.md) — экспорт CSV/XLSX с графиками, Premium-only, openpyxl
- [MONTHLY_REPORTS_SHARE_FEATURE.md](MONTHLY_REPORTS_SHARE_FEATURE.md) — выбор формата отчёта (CSV/Excel/PDF) через push-кнопки 1 числа
- [CURRENCY_CONVERSION_INTEGRATION_PLAN.md](CURRENCY_CONVERSION_INTEGRATION_PLAN.md) — автоконвертация валют, ЦБ РФ + Fawaz API, original_amount поля
- [GROUP_CHAT_SUPPORT_PLAN.md](GROUP_CHAT_SUPPORT_PLAN.md) — работа бота в Telegram-группах без привязки к household, MVP
- [PROMOCODE_REWORK_PLAN.md](PROMOCODE_REWORK_PLAN.md) — атомарное применение промокодов, валидация, F-выражения

### architecture
- [UNIFIED_CATEGORY_LOGIC_MIGRATION_PLAN.md](UNIFIED_CATEGORY_LOGIC_MIGRATION_PLAN.md) — перенос keywords из кода в БД для всех пользователей
- [REMOVE_NORMALIZED_WEIGHT_PLAN.md](REMOVE_NORMALIZED_WEIGHT_PLAN.md) — удаление мёртвого поля normalized_weight из моделей и парсера
- [ASYNC_OPENAI_MIGRATION_PLAN.md](ASYNC_OPENAI_MIGRATION_PLAN.md) — переход на AsyncOpenAI + httpx-socks, удаление to_thread
- [CATEGORY_VALIDATION_UNIFICATION_PLAN.md](CATEGORY_VALIDATION_UNIFICATION_PLAN.md) — общие валидаторы для расходов/доходов, устранение асимметрии

### security
- [PII_REMOVAL_PLAN_ACTUAL.md](PII_REMOVAL_PLAN_ACTUAL.md) — удаление username/first_name из 6 файлов кода, GDPR compliance
- [MONTHLY_REPORTS_FIX_PLAN.md](MONTHLY_REPORTS_FIX_PLAN.md) — валюта в инсайтах/Excel/PDF, household-режим, валидация AI-ответа

### misc
- [MONTHLY_INSIGHTS_FIX_plan.md](MONTHLY_INSIGHTS_FIX_plan.md) — фикс primary_currency, timeout DeepSeek, пустое ai_recommendations
- [EXPENSE_CATEGORY_MATCHING_FIX.md](EXPENSE_CATEGORY_MATCHING_FIX.md) — маппинг category_key на реальные категории пользователя из БД
- [BOT_FREEZE_ISSUE.md](BOT_FREEZE_ISSUE.md) — зависание бота для отдельных пользователей из-за FSM, TODO: timeout и /reset

---

## Reference — справочники (читать по запросу)

### api
- [API.md](API.md) — REST API на DRF: JWT, endpoints пользователей/категорий/расходов/кешбэков
- [ANALYTICS_QUERY.md](ANALYTICS_QUERY.md) — FUNCTION_CALL fallback: JSON-spec для ad-hoc запросов через ORM

### deployment
- [WEBHOOK_DEPLOYMENT.md](WEBHOOK_DEPLOYMENT.md) — настройка webhook на резервном сервере: .env, Nginx, SSL, скрипты
- [WEBHOOK_SETUP_GUIDE.md](WEBHOOK_SETUP_GUIDE.md) — DNS timing issue после обновления, retry-механизм, set_webhook.sh
- [DOCKER_DNS_CONFIG.md](DOCKER_DNS_CONFIG.md) — /etc/docker/daemon.json с 8.8.8.8/1.1.1.1 для резолвинга api.telegram.org
- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) — автоматический запуск через run_bot.py, Redis + Celery + polling

### security
- [LEGAL_COMPLIANCE_AUDIT_RF.md](LEGAL_COMPLIANCE_AUDIT_RF.md) — аудит 152-ФЗ, cookie-баннер, удаление аккаунта, Роскомнадзор
- [PRIVACY_POLICY_RU.md](PRIVACY_POLICY_RU.md) — согласие на обработку ПДн, перечень данных, сроки хранения, ст. 6 152-ФЗ
- [TERMS_RU.md](TERMS_RU.md) — публичная оферта, Telegram Stars, ограничения, расторжение

### features
- [MARKDOWN_V2_ESCAPING.md](MARKDOWN_V2_ESCAPING.md) — правила экранирования спецсимволов MarkdownV2 в Telegram
- [CATEGORIZATION_IMPROVEMENTS.md](CATEGORIZATION_IMPROVEMENTS.md) — expense_categorizer.py, pyspellchecker, множественный ввод, EN/RU

### marketing
- [HABR_TECHNICAL_INFO.md](HABR_TECHNICAL_INFO.md) — стек для статьи на Хабр: aiogram 3, Django ORM, каскад категоризации
- [ANALYTICS_SETUP.md](ANALYTICS_SETUP.md) — Google Analytics 4 + Яндекс.Метрика для лендинга coins-bot.ru
- [LANDING_SEO.md](LANDING_SEO.md) — SEO-аудит лендинга: meta, Open Graph, JSON-LD, hreflang, Core Web Vitals

---

## Historical — события в прошлом (НЕ читать без явной причины)

### Инциденты
- [SECURITY_BOT_ATTACK_2025-09-20.md](SECURITY_BOT_ATTACK_2025-09-20.md) — 106 ботов за 4 секунды, внедрение AntiSpamMiddleware
- [INCIDENT_2026-02-07_SERVER_CRASH.md](INCIDENT_2026-02-07_SERVER_CRASH.md) — аппаратный сбой PRIMARY, простой 1ч24м, DNS-проблемы при восстановлении
- [INCIDENT_2026-04-10_BOT_NOT_RESPONDING.md](INCIDENT_2026-04-10_BOT_NOT_RESPONDING.md) — Nginx IPv6, проблемный IP Telegram, переход на polling
- [PDF_TIMEOUT_INCIDENT_2026-01-24.md](PDF_TIMEOUT_INCIDENT_2026-01-24.md) — timeout 315с при генерации PDF, каскад 15+ ошибок
- [DNS_FIREWALL_FIX.md](DNS_FIREWALL_FIX.md) — UFW блокировал DNS (порт 53), quick fix после обновлений
- [SERVER_ISSUES_2026-01-29.md](SERVER_ISSUES_2026-01-29.md) — массовые подключения к несуществующей БД, исправлено в docker-compose
- [BUG_ANALYSIS_VOICE_TRANSCRIPTION_REFUSAL.md](BUG_ANALYSIS_VOICE_TRANSCRIPTION_REFUSAL.md) — AI-отказ попал в описание траты, нет валидации ответа OpenRouter

### Миграции
- [MIGRATION_TO_NL_SERVER_2026-04-11.md](MIGRATION_TO_NL_SERVER_2026-04-11.md) — переезд на 144.31.97.139 (Нидерланды), DNS/SSL/webhook/polling
- [SERVER_MIGRATION_GUIDE.md](SERVER_MIGRATION_GUIDE.md) — миграция 80.66.87.178 на 94.198.220.155, пошаговая инструкция
- [RESERVE_SERVER_MIGRATION.md](RESERVE_SERVER_MIGRATION.md) — миграция на резервный 45.95.2.84 (устарел, заменён на 72.56.67.202)
- [MIGRATION_PLAN_CN_MODELS.md](MIGRATION_PLAN_CN_MODELS.md) — внедрение DeepSeek/Qwen, UnifiedAIService, OpenAI-совместимый API
- [BACKUP_TRANSFER_GUIDE.md](BACKUP_TRANSFER_GUIDE.md) — пошаговая инструкция бекапа через Windows на резервный 45.95.2.84

### Отчёты
- [HOUSEHOLD_AUDIT_REPORT.md](HOUSEHOLD_AUDIT_REPORT.md) — аудит семейного бюджета: валидация категорий, race condition, cleanup
- [INCOME_TYPE_DEPRECATION_REPORT.md](INCOME_TYPE_DEPRECATION_REPORT.md) — поле income_type дублирует IncomeCategory, кандидат на удаление
- [MONTHLY_INSIGHTS_FIX_REPORT.md](MONTHLY_INSIGHTS_FIX_REPORT.md) — удаление Google AI, переход на DeepSeek, исправление provider='google'
- [USER_ACTIVITY_REPORT_348740371.md](USER_ACTIVITY_REPORT_348740371.md) — стресс-тест бота: 100 трат, 12 категорий, 5 найденных ошибок
- [PII_REMOVAL_CHANGELOG.md](PII_REMOVAL_CHANGELOG.md) — changelog удаления PII: 6 файлов, 25 совпадений, скрипт check_pii.py
- [KEYWORD_MATCHING_IMPROVEMENT_PLAN.md](KEYWORD_MATCHING_IMPROVEMENT_PLAN.md) — реализована 2-уровневая система exact+word, STOP_WORDS
- [NOTIFY_USER_INSTRUCTIONS.md](NOTIFY_USER_INSTRUCTIONS.md) — одноразовая инструкция: уведомление user 411977529 о фиксе бага

### Справочники (workflow)
- [VIBE_CODING_WORKFLOW.md](VIBE_CODING_WORKFLOW.md) — мультимодельный Claude Code + Codex: hooks, PreToolUse, Stop review

---

## Deprecated — устарело, есть замена (кандидаты в archive/)

- [PII_REMOVAL_PLAN.md](PII_REMOVAL_PLAN.md) — замена: [PII_REMOVAL_PLAN_ACTUAL.md](PII_REMOVAL_PLAN_ACTUAL.md)
- [LANDING_OPTIMIZATION.md](LANDING_OPTIMIZATION.md) — WebP, nginx кеш; устарело после переезда на NL-сервер
- [INSTAGRAM_MICROBLOGGER_AD_BRIEF.md](INSTAGRAM_MICROBLOGGER_AD_BRIEF.md) — ТЗ для Instagram блогера; сценарии и промокод COINSFRIENDS
- [INSTAGRAM_MICROBLOGGER_AD_SCENARIOS_FORMAT1.md](INSTAGRAM_MICROBLOGGER_AD_SCENARIOS_FORMAT1.md) — сценарии Reels дублируют BRIEF, отдельный файл избыточен
