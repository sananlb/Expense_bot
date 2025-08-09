# Обновление сервера

## Изменения для админки

1. **Обновлен settings.py:**
   - Добавлена поддержка CSRF_TRUSTED_ORIGINS для работы админки через HTTPS
   - Теперь можно настраивать через переменную окружения

2. **Создан .env.example:**
   - Пример конфигурации со всеми необходимыми настройками
   - Включает настройки для домена expensebot.duckdns.org

## Команды для обновления на сервере:

```bash
# 1. Подключиться к серверу
ssh batman@80.66.87.178

# 2. Перейти в директорию проекта
cd ~/expense_bot

# 3. Получить обновления из GitHub
git pull origin master

# 4. Обновить .env файл - добавить эти строки:
echo "CSRF_TRUSTED_ORIGINS=https://expensebot.duckdns.org,http://localhost:8000" >> .env
echo "ALLOWED_HOSTS=localhost,127.0.0.1,80.66.87.178,expensebot.duckdns.org" >> .env

# 5. Перезапустить контейнеры
docker-compose down
docker-compose up -d

# 6. Проверить статус
docker-compose ps

# 7. Проверить логи
docker logs expense_bot_web --tail 50
```

## После обновления:

Админка будет доступна по адресу:
**https://expensebot.duckdns.org/admin/**

## Если нужно временно отключить SSL redirect:

```bash
# Добавить в .env
echo "SECURE_SSL_REDIRECT=False" >> .env

# Перезапустить
docker-compose restart web
```

## Проверка миграций:

```bash
docker exec expense_bot_web python manage.py makemigrations
docker exec expense_bot_web python manage.py migrate
```