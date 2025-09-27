# Инструкция по резервному копированию ExpenseBot

## Схема копирования

```
Основной сервер (80.66.87.178)
        ↓
    [Создание архивов]
        ↓
Локальный компьютер (Windows)
        ↓
    [Передача файлов]
        ↓
Резервный сервер (45.95.2.84)
```

## Пошаговая инструкция

### ШАГ 1: Создание резервной копии на основном сервере

Подключитесь к основному серверу:
```bash
ssh batman@80.66.87.178
cd /home/batman/expense_bot
```

Запустите скрипт создания резервной копии:
```bash
bash server_scripts/expense_bot/backup_to_reserve.sh
```

Скрипт создаст в папке `/home/batman/backups/`:
- `expense_bot_latest.sql` - дамп базы данных
- `expense_bot_latest.tar.gz` - архив проекта

### ШАГ 2: Копирование через локальный компьютер

На вашем Windows компьютере откройте **PowerShell** и выполните:

#### 2.1 Создание временной папки
```powershell
mkdir C:\temp\expense_backup
cd C:\temp\expense_backup
```

#### 2.2 Скачивание с основного сервера
```powershell
# Скачать оба файла одной командой
scp batman@80.66.87.178:/home/batman/backups/expense_bot_latest.* ./

# Или по отдельности
scp batman@80.66.87.178:/home/batman/backups/expense_bot_latest.sql ./
scp batman@80.66.87.178:/home/batman/backups/expense_bot_latest.tar.gz ./
```

#### 2.3 Проверка файлов
```powershell
dir
# Должны увидеть:
# expense_bot_latest.sql
# expense_bot_latest.tar.gz
```

#### 2.4 Загрузка на резервный сервер

Сначала подключитесь к резервному серверу и создайте папку (если еще не создана):
```powershell
ssh root@45.95.2.84 "mkdir -p /root/expense_bot_backups"
```

Затем скопируйте файлы:
```powershell
scp expense_bot_latest.* root@45.95.2.84:/root/expense_bot_backups/
```

### ШАГ 3: Развертывание на резервном сервере

Подключитесь к резервному серверу:
```bash
ssh root@45.95.2.84
```

#### 3.1 Первичная настройка (выполнить один раз)

Если это первое развертывание, выполните настройку:
```bash
# Скачать и запустить скрипт настройки
curl -o setup_reserve.sh https://raw.githubusercontent.com/sananlb/Expense_bot/master/server_scripts/expense_bot/setup_reserve_server.sh
bash setup_reserve.sh
```

Или создайте скрипты вручную:
```bash
mkdir -p /root/server_scripts/expense_bot
cd /root/server_scripts/expense_bot

# Скопировать содержимое deploy_on_reserve.sh из репозитория
nano deploy_on_reserve.sh
# Вставить содержимое скрипта
chmod +x deploy_on_reserve.sh
```

#### 3.2 Создание .env файла

**ВАЖНО!** Скопируйте .env с основного сервера:

На основном сервере:
```bash
cat /home/batman/expense_bot/.env
```

На резервном сервере создайте файл:
```bash
nano /opt/expense_bot/.env
# Вставить содержимое
```

#### 3.3 Развертывание проекта

Варианты развертывания:

```bash
# Вариант 1: Только обновить код (БД не трогаем)
bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest

# Вариант 2: Обновить код и восстановить БД
bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db

# Вариант 3: Полное развертывание с запуском
bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db --start
```

### ШАГ 4: Проверка работоспособности

После развертывания проверьте:

```bash
cd /opt/expense_bot

# Статус контейнеров
docker-compose ps

# Логи бота
docker-compose logs --tail=50 bot

# Проверка БД
docker exec expense_bot_db psql -U batman expense_bot -c "SELECT COUNT(*) FROM expenses_expense;"
```

## Автоматизация процесса

### PowerShell скрипт для Windows

Создайте файл `backup_expense_bot.ps1`:

```powershell
# backup_expense_bot.ps1
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ExpenseBot Backup Transfer Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Конфигурация
$TempDir = "C:\temp\expense_backup"
$MainServer = "batman@80.66.87.178"
$ReserveServer = "root@45.95.2.84"

# Создание временной директории
Write-Host "`n1. Creating temp directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
Set-Location $TempDir

# Скачивание с основного сервера
Write-Host "2. Downloading from main server..." -ForegroundColor Yellow
scp ${MainServer}:/home/batman/backups/expense_bot_latest.* ./
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error downloading files!" -ForegroundColor Red
    exit 1
}

# Проверка файлов
$files = Get-ChildItem -Filter "expense_bot_latest.*"
Write-Host "   Downloaded files:" -ForegroundColor Green
$files | ForEach-Object { Write-Host "   - $($_.Name) ($([math]::Round($_.Length/1MB, 2)) MB)" }

# Загрузка на резервный сервер
Write-Host "`n3. Uploading to reserve server..." -ForegroundColor Yellow
ssh $ReserveServer "mkdir -p /root/expense_bot_backups"
scp expense_bot_latest.* ${ReserveServer}:/root/expense_bot_backups/
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error uploading files!" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✓ Transfer completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nNext steps on reserve server:" -ForegroundColor Cyan
Write-Host "ssh $ReserveServer" -ForegroundColor White
Write-Host "bash /root/server_scripts/expense_bot/deploy_on_reserve.sh latest --restore-db" -ForegroundColor White
```

Запуск скрипта:
```powershell
powershell -ExecutionPolicy Bypass -File backup_expense_bot.ps1
```

## Частые вопросы

### Как часто делать резервные копии?

- **Ежедневно:** для критически важных данных
- **Еженедельно:** для обычной эксплуатации
- **Перед обновлениями:** обязательно

### Что делать если контейнеры не запускаются?

```bash
# Проверить логи
docker-compose logs bot

# Проверить .env файл
cat /opt/expense_bot/.env

# Пересобрать образы
docker-compose build --no-cache
docker-compose up -d
```

### Как откатиться к предыдущей версии?

Скрипт автоматически сохраняет старую версию:
```bash
ls -la /opt/expense_bot_backup_*
# Восстановить старую версию
mv /opt/expense_bot /opt/expense_bot_broken
mv /opt/expense_bot_backup_20241227_143022 /opt/expense_bot
cd /opt/expense_bot
docker-compose up -d
```

## Контакты для помощи

При возникновении проблем проверьте:
1. Логи контейнеров: `docker-compose logs`
2. Настройки в `.env`
3. Документацию в `/docs/`