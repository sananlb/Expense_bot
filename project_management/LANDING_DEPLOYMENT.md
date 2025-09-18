# 🌐 Landing Page Deployment Documentation

## Обзор
Лендинг страница Coins Bot размещается отдельно от основного сервера бота.

## Инфраструктура

### Домены и серверы
- **Домен лендинга:** `www.coins-bot.ru` / `coins-bot.ru`
- **Домен бота:** `expensebot.duckdns.org`
- **Сервер бота:** 80.66.87.178
- **Корневая директория лендинга на сервере:** `/var/www/coins-bot`
- **Исходные файлы в репозитории:** `/home/batman/expense_bot/landing/`

### Структура файлов лендинга
```
landing/
├── index.html              # Главная страница (RU)
├── index_en.html           # Главная страница (EN) [не используется]
├── privacy.html            # Политика конфиденциальности (RU)
├── privacy_en.html         # Privacy Policy (EN)
├── offer.html              # Публичная оферта (RU)
├── offer_en.html           # Terms of Service (EN)
├── demos/                  # Видео демонстрации
│   ├── ai-categorization.mp4
│   ├── analytics.mp4
│   ├── bot-questions.mp4
│   ├── cashback.mp4
│   ├── pdf-reports.mp4
│   └── recent-expenses.mp4
└── [изображения и скриншоты]
```

## Обновление лендинга

### Ручное обновление (на сервере)
```bash
# 1. Подключиться к серверу
ssh batman@80.66.87.178

# 2. Перейти в папку проекта
cd /home/batman/expense_bot

# 3. Получить последние изменения из Git
git pull origin master

# 4. Запустить скрипт обновления лендинга
bash scripts/update_landing.sh
```

### Автоматическое обновление
При использовании основного скрипта обновления `scripts/update.sh`, лендинг обновится автоматически если в папке `landing/` были изменения:
```bash
cd /home/batman/expense_bot
bash scripts/update.sh
```

### Что делает скрипт update_landing.sh
1. Создает резервную копию текущего лендинга в `/var/www/backups/coins-bot/`
2. Копирует все файлы из `~/expense_bot/landing/` в `/var/www/coins-bot/`
3. Устанавливает правильные права доступа (www-data:www-data)
4. Перезагружает nginx для сброса кеша
5. Удаляет старые резервные копии (оставляет последние 5)

## Nginx конфигурация

### Расположение конфигурации
- **Файл:** `/etc/nginx/sites-available/coins-bot`
- **Симлинк:** `/etc/nginx/sites-enabled/coins-bot`

### Особенности конфигурации
- **HTML файлы:** Отключено кеширование (no-cache)
- **Статические ресурсы:** Кеширование на 30 дней
- **SSL сертификат:** Let's Encrypt для coins-bot.ru

### Проверка конфигурации
```bash
# Проверить синтаксис nginx
sudo nginx -t

# Перезагрузить nginx
sudo nginx -s reload

# Проверить статус
sudo systemctl status nginx
```

## Восстановление из резервной копии

Если после обновления что-то пошло не так:
```bash
# Посмотреть доступные бэкапы
ls -la /var/www/backups/coins-bot/

# Восстановить последний бэкап
sudo cp -r /var/www/backups/coins-bot/coins-bot.backup.YYYYMMDD_HHMMSS/* /var/www/coins-bot/

# Установить права доступа
sudo chown -R www-data:www-data /var/www/coins-bot/
sudo chmod -R 755 /var/www/coins-bot/

# Перезагрузить nginx
sudo nginx -s reload
```

## Проверка после обновления

1. **Проверить главную страницу:** https://www.coins-bot.ru
2. **Проверить документы:**
   - https://www.coins-bot.ru/privacy.html
   - https://www.coins-bot.ru/offer.html
3. **Проверить видео:** https://www.coins-bot.ru/demos/
4. **Очистить кеш браузера:** Ctrl+F5

## Решение проблем

### Страница не обновляется
1. Очистить кеш браузера (Ctrl+F5)
2. Проверить в режиме инкогнито
3. Проверить логи nginx:
   ```bash
   sudo tail -f /var/log/nginx/access.log
   sudo tail -f /var/log/nginx/error.log
   ```

### Ошибка 403 Forbidden
```bash
# Проверить права доступа
ls -la /var/www/coins-bot/

# Исправить права
sudo chown -R www-data:www-data /var/www/coins-bot/
sudo chmod -R 755 /var/www/coins-bot/
```

### Видео не загружаются
```bash
# Проверить наличие папки demos
ls -la /var/www/coins-bot/demos/

# Проверить размер файлов
du -sh /var/www/coins-bot/demos/*
```

## Разработка лендинга локально

1. **Редактировать файлы в:** `/Users/aleksejnalbantov/Desktop/expense_bot/landing/`
2. **Проверить локально:** Открыть `landing/index.html` в браузере
3. **Сделать коммит:**
   ```bash
   git add landing/
   git commit -m "Update landing: [описание изменений]"
   git push origin master
   ```
4. **Обновить на сервере:** Выполнить инструкции выше

## Контакты и поддержка

- **Telegram бот:** @showmecoinbot
- **Email поддержки:** support@coins-bot.ru
- **GitHub issues:** https://github.com/anthropics/claude-code/issues