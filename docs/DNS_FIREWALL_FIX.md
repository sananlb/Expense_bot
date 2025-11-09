# Решение проблемы DNS в Docker контейнерах

**Дата:** 10 ноября 2025
**Проблема:** После обновления кода бот не запускался с ошибкой DNS

## Симптомы

После обновления кода через `git pull` и пересборки контейнеров бот падал с ошибкой:

```
ERROR: Telegram server says - Bad Request: bad webhook: Failed to resolve host: Temporary failure in name resolution
```

Контейнер постоянно перезапускался, не мог установить webhook.

## Диагностика

### 1. Проверка DNS на хосте
```bash
nslookup expensebot.duckdns.org
# Результат: DNS не резолвится, timeout от 127.0.0.53
```

### 2. Проверка DNS внутри контейнера
```bash
docker-compose exec bot cat /etc/resolv.conf
# Результат: nameserver 127.0.0.11 (внутренний Docker DNS)
# ExtServers: [host(127.0.0.53)] - использует DNS хоста
```

### 3. Проверка systemd-resolved
```bash
nslookup expensebot.duckdns.org
# Got SERVFAIL reply from 127.0.0.53
# communications error to 127.0.0.53#53: timed out
```

### 4. Проверка файерволла
```bash
sudo iptables -L -n | grep -i drop
# Chain INPUT (policy DROP)
# Chain FORWARD (policy DROP)
# Много правил DROP
```

## Корневая причина

**Файерволл блокировал исходящие DNS запросы (UDP порт 53).**

Политика по умолчанию `DROP` блокировала все пакеты, которые не были явно разрешены. DNS запросы не были в списке разрешенных.

## Решение

### Шаг 1: Настройка DNS в Docker daemon

Создали конфигурацию для использования публичных DNS серверов:

```bash
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
EOF
```

### Шаг 2: Разрешение DNS в файерволле

Добавили правила для разрешения DNS трафика:

```bash
# Разрешить исходящие DNS запросы (UDP)
sudo iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
sudo iptables -A INPUT -p udp --sport 53 -j ACCEPT

# Разрешить DNS через TCP
sudo iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
sudo iptables -A INPUT -p tcp --sport 53 -j ACCEPT
```

### Шаг 3: Исправление системного DNS на хосте

Отключили systemd-resolved и настроили статический DNS:

```bash
sudo systemctl stop systemd-resolved
sudo rm -f /etc/resolv.conf
sudo tee /etc/resolv.conf > /dev/null << 'EOF'
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF
sudo chattr +i /etc/resolv.conf  # Защита от перезаписи
```

### Шаг 4: Сохранение правил файерволла

Создали директорию и сохранили правила:

```bash
sudo mkdir -p /etc/iptables
sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
```

Создали скрипт автозапуска:

```bash
sudo tee /etc/rc.local > /dev/null << 'EOF'
#!/bin/bash
iptables-restore < /etc/iptables/rules.v4
exit 0
EOF
sudo chmod +x /etc/rc.local
```

### Шаг 5: Исправление hostname

Добавили hostname в /etc/hosts для устранения предупреждений sudo:

```bash
echo "127.0.0.1 5928595-kz47794" | sudo tee -a /etc/hosts
```

### Шаг 6: Перезапуск Docker и контейнеров

```bash
sudo systemctl restart docker
sleep 5
cd /home/batman/expense_bot
docker-compose up -d
```

## Проверка решения

```bash
# 1. DNS на хосте работает
nslookup expensebot.duckdns.org
# Name: expensebot.duckdns.org
# Address: 94.198.220.155 ✅

# 2. DNS внутри контейнера работает
docker-compose exec bot cat /etc/resolv.conf
# ExtServers: [8.8.8.8 1.1.1.1] ✅

# 3. Webhook установлен успешно
docker-compose logs bot | grep webhook
# INFO: "POST /webhook/ HTTP/1.1" 200 ✅

# 4. Бот работает
docker-compose ps
# expense_bot_app Up ✅
```

## Файлы конфигурации

### `/etc/docker/daemon.json`
```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

### `/etc/resolv.conf`
```
nameserver 8.8.8.8
nameserver 1.1.1.1
```

### `/etc/iptables/rules.v4`
```
# Правила для DNS (фрагмент)
-A OUTPUT -p udp -m udp --dport 53 -j ACCEPT
-A OUTPUT -p tcp -m tcp --dport 53 -j ACCEPT
-A INPUT -p udp -m udp --sport 53 -j ACCEPT
-A INPUT -p tcp -m tcp --sport 53 -j ACCEPT
```

### `/etc/rc.local`
```bash
#!/bin/bash
iptables-restore < /etc/iptables/rules.v4
exit 0
```

## Предотвращение в будущем

### При следующих обновлениях

Все настройки уже сохранены, достаточно выполнить:

```bash
cd /home/batman/expense_bot
git pull origin master
docker-compose build --no-cache
docker-compose up -d --force-recreate
```

### После перезагрузки сервера

Все правила восстановятся автоматически:
- `/etc/rc.local` восстановит правила iptables из `/etc/iptables/rules.v4`
- `/etc/docker/daemon.json` применится при старте Docker
- `/etc/resolv.conf` защищен от перезаписи (`chattr +i`)

### Проверка после перезагрузки

```bash
# 1. Проверить правила файерволла
sudo iptables -L -n | grep "dport 53"

# 2. Проверить DNS в Docker
sudo cat /etc/docker/daemon.json

# 3. Проверить DNS на хосте
cat /etc/resolv.conf

# 4. Проверить работу контейнеров
cd /home/batman/expense_bot
docker-compose ps
docker-compose logs --tail=50 bot
```

## Альтернативные решения (НЕ использовали)

### Вариант 1: Переключение на polling

Можно было переключить бота с webhook на polling:

```bash
sed -i 's/USE_WEBHOOK=True/USE_WEBHOOK=False/' .env
docker-compose restart bot
```

**Минусы:**
- Временное решение, не устраняет корневую проблему
- Polling менее эффективен чем webhook
- Не решает проблему DNS для других сервисов

### Вариант 2: DNS в docker-compose.yml

Можно было добавить DNS настройки в каждый сервис:

```yaml
services:
  bot:
    dns:
      - 8.8.8.8
      - 1.1.1.1
```

**Минусы:**
- Нужно добавлять в каждый сервис отдельно
- Не решает проблему на уровне хоста
- Более сложное обслуживание

## Связанные изменения кода

В этом же обновлении были внесены изменения в код:

### Изменения в поиске похожих трат (`bot/services/expense.py`)

**Было:**
- Fuzzy matching с расстоянием Левенштейна (1 опечатка на слово)
- Сложная логика проверки похожести

**Стало:**
- Точное совпадение слов (case-insensitive)
- Удалена обработка пунктуации через `re.findall(r'[а-яёa-z]+', ...)`
- Проверка на пустой запрос

### Изменения в извлечении ключевых слов (`expense_bot/celery_tasks.py`)

**Было:**
```python
text = re.sub(r'[₽$€£¥р\.,"\'!?;:\-\(\)]', ' ', text)
```

**Стало:**
```python
text = re.sub(r'[₽$€£¥\.,"\'!?;:\-\(\)]', ' ', text)
```

Убрана буква 'р' из regex (она удаляла 'р' из слов типа "гороховый", "гренки").

### Изменения в обработке временных маркеров (`bot/utils/expense_intent.py`)

**Было:**
- Проверка подстроки: `'лет' in text_lower`
- Ложные срабатывания на "тарталетка"

**Стало:**
- Проверка целого слова для коротких маркеров (≤4 символа)
- Префиксы месяцев как подстроки
- Многословные фразы как подстроки

## Полезные команды для отладки

```bash
# Проверка DNS на хосте
nslookup expensebot.duckdns.org
ping -c 3 8.8.8.8

# Проверка DNS в контейнере
docker-compose exec bot cat /etc/resolv.conf

# Проверка правил файерволла
sudo iptables -L -n | grep -E "INPUT|OUTPUT|FORWARD"
sudo iptables -L -n | grep "53"

# Проверка Docker daemon
sudo cat /etc/docker/daemon.json
sudo systemctl status docker

# Проверка логов
docker-compose logs --tail=100 bot | grep -E "ERROR|DNS|webhook"

# Перезапуск всего стека
docker-compose down
sudo systemctl restart docker
sleep 5
docker-compose up -d
```

## Контакты

- **Сервер:** 94.198.220.155 (5928595-kz47794)
- **Домен:** expensebot.duckdns.org
- **Пользователь:** batman
- **Проект:** /home/batman/expense_bot

## История изменений

- **10.11.2025:** Первичная диагностика и решение проблемы DNS
- **10.11.2025:** Документирование решения
