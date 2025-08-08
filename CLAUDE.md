# Важные инструкции для Claude

## Работа с сервером
**ВАЖНО:** Я НЕ могу напрямую подключаться к серверу через SSH или выполнять команды на удаленном сервере.

При необходимости проверки логов или выполнения команд на сервере:
1. Я должен предоставить команду пользователю
2. Пользователь выполнит команду на сервере
3. Пользователь вставит результат обратно

## Информация о сервере
- IP: 194.87.98.75
- Путь к проекту: /root/expense_bot
- Логи Django: /root/expense_bot/logs/django.log

## Команды для отладки PDF отчетов
```bash
# Проверка последних ошибок в логах Django
tail -n 100 /root/expense_bot/logs/django.log | grep -E "(PDF|pdf|report|отчет|error|ERROR|Exception)"

# Проверка системных логов
journalctl -u expense_bot -n 100 --no-pager

# Проверка установки Playwright
cd /root/expense_bot && source venv/bin/activate && playwright --version

# Проверка браузеров Playwright
cd /root/expense_bot && source venv/bin/activate && playwright show-browsers
```