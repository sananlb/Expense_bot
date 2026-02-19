# План: Автоматический ежедневный бекап БД на Google Drive

## Контекст
Сейчас нет автоматического бекапа базы данных. Существующие скрипты (`scripts/backup_local.sh`, `scripts/backup_to_reserve.sh`) — ручные, с устаревшими IP и неправильным пользователем БД в некоторых из них. Нужен надёжный автоматический бекап на Google Drive с уведомлениями в Telegram.

## Что делаем
- Ежедневный бекап БД в **23:58 МСК** через cron на сервере
- Формат дампа: **pg_dump -Fc** (custom format — встроенное сжатие, валидация, выборочное восстановление)
- Хранение на **Google Drive** в отдельной папке — последние **30 бекапов**
- Локальное хранение — последние **3 бекапа** (для быстрого отката)
- Проверка восстановимости бекапа через `pg_restore --list`
- Уведомление в Telegram об успехе/ошибке

## Почему cron, а не Celery
Celery работает **внутри Docker-контейнера** и не может выполнять `docker exec` для pg_dump. Бекап БД — это задача уровня хоста, поэтому cron на сервере — правильный выбор.

---

## Файлы для создания

### 1. `scripts/backup_to_gdrive.sh` — основной скрипт бекапа

**Защитные механизмы:**
- `set -euo pipefail` — остановка при любой ошибке
- `trap` — уведомление в Telegram при падении на любом шаге
- `flock` — защита от параллельных запусков (lock-файл)
- `TZ=Europe/Moscow` — явная фиксация таймзоны

**Логика:**
1. Проверить lock (flock) — если уже запущен, выйти
2. Загрузить переменные из `.env` (MONITORING_BOT_TOKEN, ADMIN_TELEGRAM_ID)
3. `docker exec expense_bot_db pg_dump -Fc -U expense_user expense_bot` → файл `expense_bot_YYYYMMDD_HHMMSS.dump`
4. Валидация: `pg_restore --list backup.dump > /dev/null` — проверить что дамп читаемый
5. Загрузить на Google Drive через `rclone copy`
6. Ротация Google Drive: `rclone lsf` с фильтром по маске `expense_bot_*.dump` → если > 30, удалить самые старые
7. Ротация локальная: оставить последние 3 файла `expense_bot_*.dump`, остальные удалить
8. Отправить уведомление в Telegram через curl:
   - Успех: размер файла, количество бекапов на диске, время выполнения
   - Ошибка: на каком шаге упало (через trap)

**Конфигурация в скрипте:**
- `TZ="Europe/Moscow"`
- `BACKUP_DIR="/home/batman/backups"`
- `PROJECT_DIR="/home/batman/expense_bot"`
- `GDRIVE_REMOTE="gdrive:expense-bot-backups"` (имя rclone remote + папка)
- `LOCK_FILE="/tmp/backup_to_gdrive.lock"`
- `MAX_GDRIVE_BACKUPS=30`
- `MAX_LOCAL_BACKUPS=3`
- `BACKUP_MASK="expense_bot_*.dump"` (маска для ротации)

### 2. `scripts/setup_backup_cron.sh` — скрипт установки cron-задачи

**Идемпотентный** — проверяет наличие строки через `grep` перед добавлением.

Добавляет строку в crontab:
```
58 23 * * * TZ=Europe/Moscow /home/batman/expense_bot/scripts/backup_to_gdrive.sh >> /home/batman/backups/backup.log 2>&1
```

---

## Инструкция по настройке (ручные шаги)

### Шаг 1: Установить rclone на сервере
```bash
ssh batman@176.124.218.53
sudo apt install rclone
```

### Шаг 2: Настроить rclone с Google Drive
Поскольку сервер headless (без браузера), авторизация делается так:
1. Установить rclone на локальном компьютере (Windows): https://rclone.org/downloads/
2. Запустить `rclone authorize "drive"` на локальном — откроется браузер, авторизоваться в Google
3. Скопировать полученный токен (JSON строка)
4. На сервере: `rclone config` → New remote → name: `gdrive` → type: `drive` → вставить токен

### Шаг 3: Создать папку для бекапов
```bash
mkdir -p /home/batman/backups
```

### Шаг 4: Скопировать скрипт и установить cron
```bash
chmod +x /home/batman/expense_bot/scripts/backup_to_gdrive.sh
bash /home/batman/expense_bot/scripts/setup_backup_cron.sh
```

### Шаг 5: Тестовый запуск
```bash
bash /home/batman/expense_bot/scripts/backup_to_gdrive.sh
```

---

## Верификация
1. Тестовый запуск скрипта — проверить что бекап создаётся, проходит валидацию, загружается на Google Drive, приходит уведомление в Telegram
2. `rclone lsf gdrive:expense-bot-backups/` — проверить что файл появился на Google Drive
3. `pg_restore --list /home/batman/backups/expense_bot_*.dump` — проверить что дамп валидный
4. `crontab -l` — проверить что cron-задача установлена (ровно одна строка)
5. На следующий день проверить что бекап пришёл автоматически в 23:58

## Шифрование (отложено)
Решено не добавлять `rclone crypt` на текущем этапе:
- Google Drive защищён аккаунтом с 2FA
- В БД нет платёжных данных / документов — только Telegram ID, имена и суммы трат
- Шифрование усложняет восстановление и добавляет риск потери ключа
- Вернёмся к вопросу при появлении чувствительных данных (платежи, документы)
