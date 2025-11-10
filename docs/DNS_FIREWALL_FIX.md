# Решение проблемы DNS в Docker контейнерах

**Дата:** 10 ноября 2025
**Обновлено:** 10 ноября 2025 (добавлена секция UFW)
**Проблема:** После обновления кода бот не запускался с ошибкой DNS
**Сервер:** 94.198.220.155 (5928595-kz47794)

---

## 🔥 UFW Configuration (Primary Issue)

### ⚠️ Главная проблема: UFW блокирует DNS запросы

**Что происходит:**
После системных обновлений или обновлений через `bash scripts/full_update.sh` бот перестает работать с ошибкой:
```
ERROR: Telegram server says - Bad Request: bad webhook: Failed to resolve host: Temporary failure in name resolution
```

**Почему это происходит:**
UFW (Uncomplicated Firewall) по умолчанию блокирует **исходящие DNS запросы** (порт 53 UDP/TCP), даже если правила iptables были добавлены. UFW работает на более высоком уровне и переопределяет некоторые правила iptables.

### 🚀 Quick Fix After Update (90 секунд)

**Если после обновления бот не работает, выполни эти команды:**

```bash
# 1. Проверить и исправить UFW (КРИТИЧНО!)
sudo ufw allow out 53/udp comment 'Allow DNS queries UDP'
sudo ufw allow out 53/tcp comment 'Allow DNS queries TCP'
sudo ufw allow in 53/udp comment 'Allow DNS responses UDP'
sudo ufw allow in 53/tcp comment 'Allow DNS responses TCP'
sudo ufw reload

# 2. Проверить статус UFW
sudo ufw status verbose

# 3. Проверить что правила добавлены
sudo ufw status numbered

# 4. Перезапустить Docker и бота
sudo systemctl restart docker
sleep 5
cd /home/batman/expense_bot
docker-compose restart bot

# 5. Проверить что работает
docker-compose logs --tail=20 bot
```

### 📋 Почему UFW блокирует DNS

**UFW vs iptables:**
- **iptables** - низкоуровневые правила файерволла
- **UFW** - высокоуровневая обертка над iptables с более простым синтаксисом
- **Проблема:** UFW может переопределять правила iptables

**Порядок применения правил:**
1. UFW применяет свои правила первыми
2. Затем применяются правила iptables
3. Если UFW блокирует - iptables не поможет

**Почему это важно для Docker:**
- Docker контейнеры используют DNS хоста
- Если хост не может резолвить DNS - контейнеры тоже не могут
- Без DNS бот не может установить webhook на api.telegram.org

### ✅ Проверка после исправления

```bash
# 1. Проверить DNS на хосте
nslookup expensebot.duckdns.org
# Должно резолвиться в 94.198.220.155

# 2. Проверить DNS внутри контейнера
docker-compose exec bot nslookup api.telegram.org
# Должно резолвиться без ошибок

# 3. Проверить логи бота
docker-compose logs --tail=30 bot | grep -E "webhook|DNS|error"
# Должно быть: "Webhook set successfully"

# 4. Проверить UFW правила
sudo ufw status numbered | grep 53
# Должно быть:
# [N] 53/udp ALLOW OUT Anywhere (v6)
# [N] 53/tcp ALLOW OUT Anywhere (v6)
```

### 🛡️ Правильная конфигурация UFW для проекта

**Минимальный набор правил UFW для работы бота:**

```bash
# Базовая конфигурация
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (обязательно!)
sudo ufw allow 22/tcp comment 'SSH'

# DNS (критично для бота!)
sudo ufw allow out 53/udp comment 'DNS UDP out'
sudo ufw allow out 53/tcp comment 'DNS TCP out'
sudo ufw allow in 53/udp comment 'DNS UDP in'
sudo ufw allow in 53/tcp comment 'DNS TCP in'

# HTTP/HTTPS (для webhook)
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# Применить и включить
sudo ufw enable
sudo ufw reload
```

### 🔧 Автоматическая проверка UFW после обновления

**Добавить в скрипт обновления `scripts/full_update.sh`:**

```bash
# После секции с docker-compose up -d добавить:

echo "🔍 Checking UFW DNS rules..."
UFW_DNS_OUT=$(sudo ufw status | grep -c "53.*ALLOW OUT")
UFW_DNS_IN=$(sudo ufw status | grep -c "53.*ALLOW")

if [ "$UFW_DNS_OUT" -eq 0 ] || [ "$UFW_DNS_IN" -eq 0 ]; then
    echo "⚠️  WARNING: UFW may block DNS requests!"
    echo "🔧 Adding UFW rules for DNS..."

    sudo ufw allow out 53/udp comment 'DNS UDP out' 2>/dev/null
    sudo ufw allow out 53/tcp comment 'DNS TCP out' 2>/dev/null
    sudo ufw allow in 53/udp comment 'DNS UDP in' 2>/dev/null
    sudo ufw allow in 53/tcp comment 'DNS TCP in' 2>/dev/null
    sudo ufw reload

    echo "✅ UFW rules updated"
    echo "🔄 Restarting Docker..."
    sudo systemctl restart docker
    sleep 5
fi

echo "✅ UFW DNS rules verified"
```

### 📊 Диагностика UFW проблем

**Проверка что UFW блокирует DNS:**

```bash
# 1. Проверить статус UFW
sudo ufw status verbose

# 2. Посмотреть последние блокировки
sudo tail -n 50 /var/log/ufw.log | grep "DPT=53"

# 3. Временно отключить UFW для теста
sudo ufw disable
nslookup expensebot.duckdns.org  # Если работает - проблема в UFW
sudo ufw enable

# 4. Посмотреть порядок применения правил
sudo iptables -L -n -v | grep -A5 "Chain ufw"
```

**Типичные ошибки в логах при блокировке DNS:**

```
[UFW BLOCK] IN= OUT=eth0 SRC=... DST=8.8.8.8 ... DPT=53 PROTO=UDP
[UFW BLOCK] IN= OUT=eth0 SRC=... DST=1.1.1.1 ... DPT=53 PROTO=TCP
```

### 🎯 Когда проверять UFW

**ВСЕГДА проверяй UFW после:**
1. ✅ Системных обновлений (`apt update && apt upgrade`)
2. ✅ Запуска `scripts/full_update.sh`
3. ✅ Перезагрузки сервера
4. ✅ Изменения правил файерволла
5. ✅ Проблем с DNS резолюцией

**Быстрая проверка (10 секунд):**
```bash
# Одна команда для проверки всего
sudo ufw status | grep 53 && nslookup expensebot.duckdns.org && docker-compose logs --tail=5 bot | grep webhook
```

---

## 🦆 DuckDNS Автообновление

### Проблема
DuckDNS удаляет неактивные домены через 30 дней. Для статического IP достаточно обновлять раз в неделю.

### Решение
Настроить автоматическое обновление через cron задачу, которая будет еженедельно обновлять IP адрес домена на DuckDNS.

### Команды для настройки

#### 1. Создать скрипт обновления DuckDNS
```bash
# Создать директорию для скриптов
mkdir -p /home/batman/scripts

# Создать скрипт обновления
cat > /home/batman/scripts/duckdns_update.sh << 'EOF'
#!/bin/bash
# DuckDNS Auto Update Script
# Обновляет IP адрес домена на DuckDNS

DOMAIN="expensebot"
TOKEN="YOUR_DUCKDNS_TOKEN_HERE"
LOG_FILE="/home/batman/logs/duckdns_update.log"

# Создать директорию для логов если не существует
mkdir -p /home/batman/logs

# Получить текущий IP
CURRENT_IP=$(curl -s ifconfig.me)

# Обновить DuckDNS
RESPONSE=$(curl -s "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=${CURRENT_IP}")

# Записать результат в лог
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Domain: ${DOMAIN}, IP: ${CURRENT_IP}, Response: ${RESPONSE}" >> "$LOG_FILE"

# Проверить результат
if [ "$RESPONSE" = "OK" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ DuckDNS update successful" >> "$LOG_FILE"
    exit 0
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ DuckDNS update failed!" >> "$LOG_FILE"
    exit 1
fi
EOF

# Сделать скрипт исполняемым
chmod +x /home/batman/scripts/duckdns_update.sh
```

**ВАЖНО:** Замени `YOUR_DUCKDNS_TOKEN_HERE` на реальный токен из https://www.duckdns.org/

#### 2. Добавить cron задачу (раз в неделю)
```bash
# Открыть crontab для редактирования
crontab -e

# Добавить в конец файла:
# DuckDNS auto-update every Sunday at 3:00 AM
0 3 * * 0 /home/batman/scripts/duckdns_update.sh

# Сохранить и выйти (Ctrl+X, затем Y, затем Enter)
```

#### 3. Проверка работы

**Проверить что cron задача добавлена:**
```bash
crontab -l | grep duckdns
# Должно показать: 0 3 * * 0 /home/batman/scripts/duckdns_update.sh
```

**Запустить скрипт вручную для теста:**
```bash
/home/batman/scripts/duckdns_update.sh
echo $?  # Должно быть 0 (успех)
```

**Проверить логи:**
```bash
tail -f /home/batman/logs/duckdns_update.log
# Должно быть: [YYYY-MM-DD HH:MM:SS] ✅ DuckDNS update successful
```

**Проверить что IP обновился:**
```bash
nslookup expensebot.duckdns.org
# Должно резолвиться в текущий IP сервера (94.198.220.155)
```

#### 4. Ручное обновление при необходимости
```bash
# Если нужно обновить немедленно
/home/batman/scripts/duckdns_update.sh

# Проверить результат
cat /home/batman/logs/duckdns_update.log
```

### Расписание cron
- **`0 3 * * 0`** = Каждое воскресенье в 3:00 ночи
- Частота: раз в неделю (достаточно для статического IP)
- DuckDNS требует обновления минимум раз в 30 дней

### Альтернативные расписания
```bash
# Каждый понедельник в 2:00
0 2 * * 1 /home/batman/scripts/duckdns_update.sh

# Каждые 2 недели (1-го и 15-го числа в 3:00)
0 3 1,15 * * /home/batman/scripts/duckdns_update.sh

# Каждый день в 3:00 (избыточно, но безопасно)
0 3 * * * /home/batman/scripts/duckdns_update.sh
```

### Мониторинг
```bash
# Проверить последнее обновление
tail -1 /home/batman/logs/duckdns_update.log

# Проверить все обновления за последний месяц
grep "✅" /home/batman/logs/duckdns_update.log

# Проверить ошибки
grep "❌" /home/batman/logs/duckdns_update.log
```

### Fallback: Использование IP вместо домена для webhook

**Если DuckDNS не работает, можно временно переключиться на IP:**

```bash
# В .env файле изменить WEBHOOK_URL
WEBHOOK_URL=https://94.198.220.155/webhook/

# Перезапустить бота
cd /home/batman/expense_bot
docker-compose restart bot

# Проверить что webhook установлен
docker-compose logs --tail=20 bot | grep webhook
```

**ВАЖНО:** SSL сертификат должен быть валиден для IP или нужен самоподписанный сертификат.

---

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

### 🚨 КРИТИЧЕСКИ ВАЖНО: Проверка UFW после каждого обновления

**ВСЕГДА выполняй эту последовательность после обновления:**

```bash
# 1. Обновление кода и контейнеров
cd /home/batman/expense_bot
git pull origin master
docker-compose build --no-cache
docker-compose up -d --force-recreate

# 2. ОБЯЗАТЕЛЬНО проверить UFW правила для DNS
sudo ufw status | grep 53

# 3. Если правил нет - добавить
sudo ufw allow out 53/udp comment 'DNS UDP out'
sudo ufw allow out 53/tcp comment 'DNS TCP out'
sudo ufw allow in 53/udp comment 'DNS UDP in'
sudo ufw allow in 53/tcp comment 'DNS TCP in'
sudo ufw reload

# 4. Перезапустить Docker после изменения UFW
sudo systemctl restart docker
sleep 5
cd /home/batman/expense_bot
docker-compose restart bot

# 5. Проверить что бот работает
docker-compose logs --tail=30 bot | grep -E "webhook|ERROR"
```

### 📝 Чек-лист после обновления сервера

**Используй этот чек-лист КАЖДЫЙ РАЗ после обновления:**

- [ ] Проверил UFW правила для DNS (`sudo ufw status | grep 53`)
- [ ] Добавил правила UFW если их нет
- [ ] Перезапустил Docker (`sudo systemctl restart docker`)
- [ ] Проверил DNS на хосте (`nslookup expensebot.duckdns.org`)
- [ ] Проверил DNS в контейнере (`docker-compose exec bot nslookup api.telegram.org`)
- [ ] Проверил логи бота (`docker-compose logs --tail=20 bot`)
- [ ] Убедился что webhook установлен успешно

### 🔄 После перезагрузки сервера

**Автоматическое восстановление:**
- `/etc/rc.local` восстановит правила iptables из `/etc/iptables/rules.v4`
- `/etc/docker/daemon.json` применится при старте Docker
- `/etc/resolv.conf` защищен от перезаписи (`chattr +i`)
- **UFW правила НЕ сбрасываются** при перезагрузке

**Проверка после перезагрузки:**

```bash
# 1. Проверить UFW статус
sudo ufw status verbose | grep 53

# 2. Проверить правила iptables
sudo iptables -L -n | grep "dport 53"

# 3. Проверить DNS в Docker daemon
sudo cat /etc/docker/daemon.json

# 4. Проверить DNS на хосте
cat /etc/resolv.conf
nslookup expensebot.duckdns.org

# 5. Проверить работу контейнеров
cd /home/batman/expense_bot
docker-compose ps
docker-compose logs --tail=50 bot

# 6. Если бот не работает - выполнить Quick Fix (см. выше)
```

### 🛠️ Интеграция проверки UFW в скрипт обновления

**Обновить файл `scripts/full_update.sh`:**

Добавить после блока `docker-compose up -d`:

```bash
# Проверка и исправление UFW правил для DNS
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Checking UFW DNS rules..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

UFW_ENABLED=$(sudo ufw status | grep -c "Status: active")
if [ "$UFW_ENABLED" -gt 0 ]; then
    UFW_DNS_OUT=$(sudo ufw status numbered | grep -c "53.*ALLOW OUT")
    UFW_DNS_IN=$(sudo ufw status numbered | grep -c "53.*ALLOW")

    if [ "$UFW_DNS_OUT" -lt 2 ] || [ "$UFW_DNS_IN" -lt 2 ]; then
        echo "⚠️  WARNING: UFW DNS rules incomplete!"
        echo "🔧 Adding UFW rules for DNS..."

        sudo ufw allow out 53/udp comment 'DNS UDP out' 2>/dev/null || true
        sudo ufw allow out 53/tcp comment 'DNS TCP out' 2>/dev/null || true
        sudo ufw allow in 53/udp comment 'DNS UDP in' 2>/dev/null || true
        sudo ufw allow in 53/tcp comment 'DNS TCP in' 2>/dev/null || true
        sudo ufw reload

        echo "✅ UFW rules updated"
        echo "🔄 Restarting Docker to apply changes..."
        sudo systemctl restart docker
        sleep 5
        docker-compose restart bot
    else
        echo "✅ UFW DNS rules OK"
    fi
else
    echo "ℹ️  UFW is not active"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing DNS resolution..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if nslookup expensebot.duckdns.org > /dev/null 2>&1; then
    echo "✅ DNS resolution works"
else
    echo "❌ ERROR: DNS resolution failed!"
    echo "   Run: sudo ufw allow out 53/udp && sudo ufw allow out 53/tcp"
fi

echo ""
```

### 💡 Признаки что UFW заблокировал DNS

**Если видишь эти ошибки - проблема в UFW:**

1. `Failed to resolve host: Temporary failure in name resolution`
2. `nslookup: communications error to 127.0.0.53#53: timed out`
3. `curl: (6) Could not resolve host`
4. Webhook не устанавливается в Telegram
5. В логах UFW: `[UFW BLOCK] ... DPT=53`

**Быстрое решение (30 секунд):**
```bash
sudo ufw allow out 53/udp && sudo ufw allow out 53/tcp && sudo ufw reload && sudo systemctl restart docker
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
- **10.11.2025 (вечер):** Обнаружена проблема с UFW, добавлена детальная секция о UFW
- **10.11.2025 (вечер):** Добавлен Quick Fix для быстрого исправления после обновлений
- **10.11.2025 (вечер):** Добавлен код для автоматической проверки UFW в скрипте обновления
- **10.11.2025 (вечер):** Добавлен чек-лист для проверки после обновления сервера
- **10.11.2025 19:30:** Добавлена информация о DuckDNS автообновлении через cron
- **10.11.2025 19:30:** Обновлен Quick Fix с проверкой UFW ПЕРЕД другими действиями
- **10.11.2025 19:30:** Добавлен fallback на IP для webhook при проблемах с DuckDNS
