# Docker DNS Configuration

## Проблема
Docker контейнеры могут иметь проблемы с резолвингом DNS, особенно на некоторых серверах. Это приводит к ошибкам типа:
```
Cannot connect to host api.telegram.org:443 ssl:default [Temporary failure in name resolution]
```

## Решение
Настройте DNS серверы для Docker daemon на ОБОИХ серверах (основной и резервный).

### Шаг 1: Создайте/отредактируйте файл конфигурации Docker

```bash
sudo nano /etc/docker/daemon.json
```

### Шаг 2: Добавьте DNS конфигурацию

```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

### Шаг 3: Перезапустите Docker

```bash
sudo systemctl restart docker
```

### Шаг 4: Перезапустите контейнеры

```bash
cd /home/batman/expense_bot
docker-compose down
docker-compose up -d
```

## Проверка

Проверить что DNS работает внутри контейнера:
```bash
docker exec expense_bot_app nslookup api.telegram.org
```

## Важно!
Эта настройка должна быть **одинаковой на обоих серверах** для обеспечения идентичности конфигурации.