# Security Setup Documentation

**Дата настройки:** 30 января 2026
**Сервер:** PRIMARY (176.124.218.53)
**Статус:** ✅ АКТИВНО И РАБОТАЕТ

---

## 📋 Оглавление

1. [Двухуровневая защита](#двухуровневая-защита)
2. [Nginx Rate Limiting](#nginx-rate-limiting)
3. [fail2ban Configuration](#fail2ban-configuration)
4. [Полезные команды](#полезные-команды)
5. [Мониторинг](#мониторинг)
6. [Troubleshooting](#troubleshooting)

---

## 🛡️ Двухуровневая защита

### Уровень 1: Nginx Rate Limiting (Легковесная защита)
- **Где работает:** На уровне веб-сервера
- **Что делает:** Ограничивает количество запросов в минуту с одного IP
- **Реакция:** HTTP 429 (Too Many Requests)
- **Преимущества:** Мгновенная реакция, минимальная нагрузка

### Уровень 2: fail2ban (Тяжелая артиллерия)
- **Где работает:** На уровне firewall (iptables)
- **Что делает:** Полностью блокирует IP адрес
- **Реакция:** Все пакеты от IP отбрасываются
- **Преимущества:** Защита от серьезных атак, автоматическое разбанивание

---

## 🚦 Nginx Rate Limiting

### Конфигурация

**Файл:** `/etc/nginx/sites-available/expensebot`
**Backup:** `/etc/nginx/sites-available/expensebot.backup_20260130_214620`

### Лимиты по зонам:

#### 1. Webhook зона (`/webhook/`)
- **Лимит:** 30 запросов в минуту
- **Burst:** 10 (можно превысить на 10 запросов)
- **Применение:** `limit_req zone=webhook_limit burst=10 nodelay;`
- **Цель:** Защита от спама в Telegram webhook

#### 2. Admin зона (`/admin/`)
- **Лимит:** 20 запросов в минуту
- **Burst:** 5
- **Применение:** `limit_req zone=admin_limit burst=5 nodelay;`
- **Цель:** Защита админки от брутфорса

#### 3. General зона (все остальное)
- **Лимит:** 60 запросов в минуту
- **Burst:** 20
- **Применение:** `limit_req zone=general_limit burst=20 nodelay;`
- **Цель:** Общая защита сайта

### Connection Limiting
- **Макс. соединений на IP:** 10 одновременно
- **Применение:** `limit_conn conn_limit 10;`

### Security Headers
```nginx
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

---

## 🔒 fail2ban Configuration

### Активные Jail

#### 1. **nginx-bad-request** (Кастомный)
- **Цель:** Блокировка сканеров портов и bad HTTP методов
- **Паттерны:**
  - `UNKNOWN` HTTP методы
  - `BadStatusLine` ошибки
  - `BadHttpMessage` ошибки
  - Invalid method encountered
- **Лимит:** 3 попытки за 60 секунд
- **Бан:** 1800 секунд (30 минут)

#### 2. **nginx-http-auth**
- **Цель:** Защита от брутфорса HTTP авторизации
- **Лимит:** 5 попыток за 300 секунд
- **Бан:** 600 секунд (10 минут)

#### 3. **nginx-limit-req**
- **Цель:** Блокировка при превышении nginx rate limits
- **Лимит:** 3 превышения за 60 секунд
- **Бан:** 600 секунд (10 минут)

#### 4. **sshd**
- **Цель:** Защита SSH от брутфорса
- **Лимит:** 5 попыток за 300 секунд
- **Бан:** 600 секунд (10 минут)

### Общие настройки

```ini
[DEFAULT]
bantime = 600         # 10 минут блокировки
findtime = 300        # Окно наблюдения 5 минут
maxretry = 5          # Попыток до бана
ignoreip = 127.0.0.1/8 ::1
```

### Кастомный фильтр

**Файл:** `/etc/fail2ban/filter.d/nginx-bad-request.conf`

```ini
[Definition]
failregex = ^<HOST>.*"UNKNOWN.*HTTP.*" 400
            ^<HOST>.*BadStatusLine
            ^<HOST>.*BadHttpMessage
            ^<HOST>.*Invalid method encountered
ignoreregex =
```

---

## 📊 Полезные команды

### fail2ban

```bash
# Статус всех jail
sudo fail2ban-client status

# Статус конкретного jail
sudo fail2ban-client status nginx-bad-request
sudo fail2ban-client status sshd

# Список заблокированных IP
sudo fail2ban-client status sshd | grep "Banned IP"

# Разбанить IP вручную
sudo fail2ban-client set nginx-bad-request unbanip 1.2.3.4

# Забанить IP вручную
sudo fail2ban-client set nginx-bad-request banip 1.2.3.4

# Перезапустить fail2ban
sudo systemctl restart fail2ban

# Логи fail2ban
sudo tail -f /var/log/fail2ban.log

# Проверить правила iptables
sudo iptables -L -n -v | grep f2b
```

### Nginx

```bash
# Проверить конфигурацию
sudo nginx -t

# Перезагрузить конфигурацию (graceful)
sudo nginx -s reload

# Проверить rate limiting в логах
sudo tail -f /var/log/nginx/error.log | grep limiting

# Проверить access log
sudo tail -f /var/log/nginx/access.log
```

---

## 🔍 Мониторинг

### Что проверять регулярно

1. **Заблокированные IP:**
   ```bash
   sudo fail2ban-client status | grep "Jail list"
   sudo fail2ban-client status sshd | grep "Banned IP"
   ```

2. **Логи атак:**
   ```bash
   sudo tail -100 /var/log/fail2ban.log | grep NOTICE
   ```

3. **Nginx rate limiting:**
   ```bash
   sudo grep "limiting requests" /var/log/nginx/error.log | tail -20
   ```

4. **Активные соединения:**
   ```bash
   ss -tn | grep :443 | wc -l
   ```

### Метрики эффективности

После настройки (30 января 2026, 18:48):
- **SSH атаки заблокировано:** 2 IP (165.245.137.253, 45.78.217.20)
- **Nginx bad requests:** 0 (пока нет новых атак)
- **Rate limit превышений:** 0

---

## 🐛 Troubleshooting

### Проблема: Легитимный пользователь заблокирован

**Решение:**
```bash
# Разбанить IP
sudo fail2ban-client set <jail_name> unbanip <IP>

# Например:
sudo fail2ban-client set nginx-bad-request unbanip 1.2.3.4

# Добавить IP в whitelist (ignoreip)
sudo nano /etc/fail2ban/jail.local
# Добавить IP в ignoreip = 127.0.0.1/8 ::1 YOUR_IP
sudo systemctl restart fail2ban
```

### Проблема: fail2ban не блокирует атаки

**Диагностика:**
```bash
# Проверить что jail активен
sudo fail2ban-client status

# Проверить логи jail
sudo fail2ban-client status nginx-bad-request

# Проверить регулярное выражение фильтра
sudo fail2ban-regex /var/log/nginx/error.log /etc/fail2ban/filter.d/nginx-bad-request.conf

# Проверить логи fail2ban
sudo tail -100 /var/log/fail2ban.log
```

### Проблема: Nginx rate limiting не работает

**Диагностика:**
```bash
# Проверить конфигурацию
sudo nginx -t

# Проверить что лимиты применяются
curl -I https://expensebot.duckdns.org/webhook/

# Сделать много запросов и проверить HTTP 429
for i in {1..50}; do curl -I https://expensebot.duckdns.org/; done

# Проверить error.log
sudo grep "limiting" /var/log/nginx/error.log
```

### Проблема: Email уведомления не работают

**Статус:** Email уведомления ОТКЛЮЧЕНЫ (sendmail не установлен)

**Включить (опционально):**
```bash
# Установить postfix или sendmail
sudo apt-get install postfix

# Изменить action в jail.local
sudo nano /etc/fail2ban/jail.local
# Изменить action = %(action_)s на action = %(action_mwl)s

# Перезапустить
sudo systemctl restart fail2ban
```

---

## 📈 Статистика (Real-time)

### До настройки защиты:
- **BadStatusLine ошибки:** 5-10 в день
- **Сканирование портов:** Ежедневно с разных IP
- **SSH брутфорс:** Постоянные попытки

### После настройки защиты:
- **Заблокировано IP:** 2 (первый час работы)
- **Ошибки в логах:** Значительно меньше
- **Безопасность:** ✅ Значительно повышена

---

## 🔐 Рекомендации по безопасности

### ✅ Настроено:
1. Nginx rate limiting по IP
2. fail2ban автоблокировка
3. Security headers (X-Frame-Options, etc.)
4. Connection limiting
5. SSH защита

### 🔄 Дополнительно (опционально):
1. **CloudFlare** - для защиты от DDoS
2. **ModSecurity** - WAF для nginx
3. **GeoIP блокировка** - блокировка по странам
4. **2FA для SSH** - двухфакторная аутентификация

---

## 📞 Контакты

**Админ сервера:** batman@176.124.218.53
**Email для уведомлений:** nalbantov.aleksej@yandex.ru
**Документация создана:** 30 января 2026

---

**⚠️ ВАЖНО:**
- Все изменения в конфигурации ВСЕГДА делать через backup!
- Бэкап nginx: `/etc/nginx/sites-available/expensebot.backup_*`
- Не блокировать собственный IP!
- Регулярно проверять логи на наличие атак
